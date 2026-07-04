"""代码执行沙箱 - 安全运行 Python 代码."""

import sys
import io
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
    
    # 危险模块黑名单
    DANGEROUS_MODULES = {
        "os", "sys", "subprocess", "socket", "urllib", "http", "ftplib",
        "smtplib", "telnetlib", "webbrowser", "shutil", "pathlib",
        "importlib", "imp", "pkgutil", "ctypes", "mmap", "pty",
        "pickle", "cPickle", "dill", "cloudpickle",
        "exec", "eval", "compile", "__import__",
    }
    
    # 危险内置函数
    DANGEROUS_BUILTINS = {
        "exec", "eval", "compile", "open", "__import__",
        "input", "raw_input", "exit", "quit",
    }
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
    
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
            
            # 检查 __import__
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    return "安全限制: 禁止调用 __import__"
        
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
        safe_globals = {
            "__builtins__": {
                name: getattr(__builtins__, name)
                for name in dir(__builtins__)
                if name not in self.DANGEROUS_BUILTINS
            }
        }
        
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
    
    def execute_expression(self, expression: str) -> CodeExecutionResult:
        """执行单个表达式并返回结果."""
        code = f"_result = {expression}\nprint(repr(_result))"
        result = self.execute(code)
        return result
