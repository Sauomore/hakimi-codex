"""代码执行沙箱 - 安全运行 Python 代码."""

import sys
import io
import os
import builtins
import traceback
import ast
import compileall
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class CodeExecutionStatus(Enum):
    """代码执行状态."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    SYNTAX_ERROR = "syntax_error"
    SECURITY_ERROR = "security_error"


@dataclass
class CodeExecutionResult:
    """代码执行结果."""
    status: CodeExecutionStatus
    output: str
    error: str = ""
    execution_time: float = 0.0
    return_value: Any = None


class CodeSandbox:
    """Python 代码执行沙箱."""
    
    # 危险模块黑名单（os/sys 通过安全包装器单独处理，不在这里拦截）
    DANGEROUS_MODULES = {
        "subprocess", "socket", "urllib", "http", "ftplib",
        "smtplib", "telnetlib", "webbrowser", "shutil", "pathlib",
        "importlib", "imp", "pkgutil", "ctypes", "mmap", "pty",
        "pickle", "cPickle", "dill", "cloudpickle",
        "exec", "eval", "compile", "__import__",
    }

    # sys 模块中禁止访问的属性
    BLOCKED_SYS_ATTRIBUTES = frozenset({
        "modules", "modules_cleardocs", "dllhandle", "setdlopenflags",
    })
    
    # 危险内置函数
    DANGEROUS_BUILTINS = {
        "exec", "eval", "compile",
        "input", "raw_input", "exit", "quit",
    }

    # 沙箱内允许的文件打开模式（只读）
    ALLOWED_OPEN_MODES = {"r", "rb", "rt"}
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    class _SafeSys:
        """受限的 sys 模块包装器."""

        def __init__(self):
            import sys as _real_sys
            self._real_sys = _real_sys

        def __getattr__(self, name: str):
            if name in CodeSandbox.BLOCKED_SYS_ATTRIBUTES:
                raise AttributeError(
                    f"sys.{name} is not accessible in sandbox"
                )
            value = getattr(self._real_sys, name)
            # 返回 sys.path 的副本，避免沙箱代码污染真实 sys.path
            if name == "path":
                return list(value)
            return value

        def __dir__(self):
            return [
                name for name in dir(self._real_sys)
                if name not in CodeSandbox.BLOCKED_SYS_ATTRIBUTES
            ]

    class _SafeOS:
        """受限的 os 模块包装器."""

        # 允许暴露的安全属性（os.path 完整暴露，其余仅限只读常量）
        SAFE_ATTRIBUTES = frozenset({
            "path", "name", "linesep", "sep", "pathsep", "altsep",
            "curdir", "pardir", "devnull", "error", "strerror",
        })

        def __init__(self):
            import os as _real_os
            self._real_os = _real_os

        def __getattr__(self, name: str):
            if name not in self.SAFE_ATTRIBUTES:
                raise AttributeError(
                    f"os.{name} is not accessible in sandbox"
                )
            return getattr(self._real_os, name)

        def __dir__(self):
            return list(self.SAFE_ATTRIBUTES)

    def _safe_open(self, file, mode: str = "r", *args, **kwargs):
        """沙箱内受限的 open，仅允许读取项目内文件."""
        if mode not in self.ALLOWED_OPEN_MODES:
            raise PermissionError(
                f"Sandbox open: mode '{mode}' is not allowed (read-only modes only)"
            )

        abs_file = os.path.abspath(file)
        abs_cwd = os.path.abspath(os.getcwd())

        if not (
            abs_file == abs_cwd
            or abs_file.startswith(abs_cwd + os.sep)
        ):
            raise PermissionError(
                f"Sandbox open: path '{file}' is outside allowed directory '{abs_cwd}'"
            )

        return open(file, mode, *args, **kwargs)

    def _safe_import(self, name: str, *args, **kwargs):
        """沙箱内受限的 __import__，禁止导入危险模块."""
        module_name = name.split(".")[0]
        if module_name in self.DANGEROUS_MODULES:
            raise ImportError(
                f"Sandbox import: module '{module_name}' is not allowed"
            )
        if module_name == "sys":
            return self._SafeSys()
        if module_name == "os":
            return self._SafeOS()
        return __import__(name, *args, **kwargs)

    def _check_ast_security(self, code: str) -> Optional[str]:
        """检查 AST 安全性."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"语法错误: {e}"
        
        for node in ast.walk(tree):
            # 检查 import
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    if module_name in self.DANGEROUS_MODULES:
                        return f"安全限制: 禁止导入模块 '{module_name}'"
            
            # 检查函数调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.DANGEROUS_BUILTINS:
                        return f"安全限制: 禁止调用内置函数 '{node.func.id}'"
                
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("system", "popen", "call", "run", "exec", "eval"):
                        return f"安全限制: 禁止调用方法 '{node.func.attr}'"

        return None
    
    def execute(self, code: str, globals_dict: Optional[Dict] = None) -> CodeExecutionResult:
        """执行 Python 代码."""
        import time
        
        start_time = time.time()
        
        # 安全检查
        security_error = self._check_ast_security(code)
        if security_error:
            return CodeExecutionResult(
                status=CodeExecutionStatus.SECURITY_ERROR,
                output="",
                error=security_error,
                execution_time=0.0
            )
        
        # 创建安全的执行环境
        safe_builtins = {
            name: getattr(builtins, name)
            for name in dir(builtins)
            if name not in self.DANGEROUS_BUILTINS
        }
        # 使用受限的 open 替代原生 open
        safe_builtins["open"] = self._safe_open
        # 使用受限的 __import__ 替代原生导入
        safe_builtins["__import__"] = self._safe_import

        safe_globals = {"__builtins__": safe_builtins}

        if globals_dict:
            safe_globals.update(globals_dict)

        safe_locals = {}

        # 捕获输出
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        sys.stdout = stdout_buffer
        sys.stderr = stderr_buffer

        # 临时把当前工作目录加入 sys.path，以便沙箱内能导入项目模块
        old_sys_path = sys.path.copy()
        cwd_entry = os.getcwd()
        if cwd_entry not in sys.path:
            sys.path.insert(0, cwd_entry)

        try:
            # 编译并执行
            compiled = compile(code, "<sandbox>", "exec")

            exec(compiled, safe_globals, safe_locals)
            
            output = stdout_buffer.getvalue()
            error = stderr_buffer.getvalue()
            
            execution_time = time.time() - start_time
            
            return CodeExecutionResult(
                status=CodeExecutionStatus.SUCCESS,
                output=output,
                error=error,
                execution_time=execution_time,
                return_value=None
            )
            
        except SyntaxError as e:
            return CodeExecutionResult(
                status=CodeExecutionStatus.SYNTAX_ERROR,
                output="",
                error=f"语法错误: {e}",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return CodeExecutionResult(
                status=CodeExecutionStatus.ERROR,
                output=stdout_buffer.getvalue(),
                error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
                execution_time=time.time() - start_time
            )
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.path = old_sys_path
    
    def execute_expression(self, expression: str) -> CodeExecutionResult:
        """执行单个表达式并返回结果."""
        code = f"_result = {expression}\nprint(repr(_result))"
        result = self.execute(code)
        return result
