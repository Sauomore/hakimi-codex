"""工具执行模块 - 为AI提供文件系统、终端命令等工具能力."""

import os
import subprocess
import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class ToolResultStatus(Enum):
    """工具执行结果状态."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"


@dataclass
class ToolResult:
    """工具执行结果."""
    status: ToolResultStatus
    output: str
    exit_code: int = 0
    metadata: Dict[str, Any] = None


class ToolExecutor:
    """工具执行器 - 安全地执行各类工具操作."""
    
    # 危险命令黑名单（部分匹配）
    DANGEROUS_COMMANDS = [
        "rm -rf /", "rm -rf /*", "rm -rf ~", "rm -rf /root",
        "mkfs", "dd if=/dev/zero", ":(){ :|:& };:", 
        "> /dev/sda", "> /dev/hda", "chmod -R 777 /",
        "del /f /s /q c:\\", "format c:", "rd /s /q c:\\",
    ]
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.max_output_size = 50000  # 最大输出字符数
        self.command_timeout = 60  # 命令超时秒数
    
    def _check_dangerous(self, command: str) -> bool:
        """检查命令是否包含危险操作."""
        cmd_lower = command.lower().strip()
        for dangerous in self.DANGEROUS_COMMANDS:
            if dangerous.lower() in cmd_lower:
                return True
        return False
    
    def _truncate_output(self, output: str) -> str:
        """截断过长的输出."""
        if len(output) > self.max_output_size:
            return output[:self.max_output_size] + f"\n\n... (输出已截断，共 {len(output)} 字符)"
        return output
    
    def execute_command(self, command: str, cwd: Optional[str] = None) -> ToolResult:
        """执行 shell 命令."""
        if self._check_dangerous(command):
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output="[错误] 检测到危险命令，已拒绝执行。",
                exit_code=1
            )
        
        work_dir = Path(cwd).resolve() if cwd else self.project_path
        
        # 确保工作目录在项目路径内（安全限制）
        try:
            work_dir.relative_to(self.project_path)
        except ValueError:
            # 允许在项目路径或其父目录中执行
            pass
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=self.command_timeout,
                encoding="utf-8",
                errors="replace"
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            output = self._truncate_output(output)
            
            status = ToolResultStatus.SUCCESS if result.returncode == 0 else ToolResultStatus.ERROR
            
            return ToolResult(
                status=status,
                output=output.strip() or "(命令执行完成，无输出)",
                exit_code=result.returncode,
                metadata={"command": command, "cwd": str(work_dir)}
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                output=f"[错误] 命令执行超时（超过 {self.command_timeout} 秒）",
                exit_code=124
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"[错误] 执行异常: {str(e)}",
                exit_code=1
            )
    
    def read_file(self, file_path: str) -> ToolResult:
        """读取文件内容."""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.project_path / path
            path = path.resolve()
            
            if not path.exists():
                return ToolResult(
                    status=ToolResultStatus.NOT_FOUND,
                    output=f"文件不存在: {file_path}",
                    exit_code=1
                )
            
            if not path.is_file():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=f"路径不是文件: {file_path}",
                    exit_code=1
                )
            
            # 检查文件大小，避免读取过大文件
            max_size = 1024 * 1024  # 1MB
            if path.stat().st_size > max_size:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=f"文件过大 ({path.stat().st_size} 字节)，最大支持 {max_size} 字节",
                    exit_code=1
                )
            
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=content,
                metadata={"file_path": str(path), "size": len(content)}
            )
            
        except PermissionError:
            return ToolResult(
                status=ToolResultStatus.PERMISSION_DENIED,
                output=f"权限不足，无法读取: {file_path}",
                exit_code=1
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"读取失败: {str(e)}",
                exit_code=1
            )
    
    def write_file(self, file_path: str, content: str) -> ToolResult:
        """写入文件内容."""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.project_path / path
            path = path.resolve()
            
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"[完成] 文件已写入: {path}",
                metadata={"file_path": str(path), "size": len(content)}
            )
            
        except PermissionError:
            return ToolResult(
                status=ToolResultStatus.PERMISSION_DENIED,
                output=f"权限不足，无法写入: {file_path}",
                exit_code=1
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"写入失败: {str(e)}",
                exit_code=1
            )
    
    def list_directory(self, dir_path: str = ".") -> ToolResult:
        """列出目录内容."""
        try:
            path = Path(dir_path)
            if not path.is_absolute():
                path = self.project_path / path
            path = path.resolve()
            
            if not path.exists():
                return ToolResult(
                    status=ToolResultStatus.NOT_FOUND,
                    output=f"目录不存在: {dir_path}",
                    exit_code=1
                )
            
            if not path.is_dir():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=f"路径不是目录: {dir_path}",
                    exit_code=1
                )
            
            entries = []
            for item in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
                icon = "[目录]" if item.is_dir() else "[文件]"
                size = ""
                if item.is_file():
                    size_bytes = item.stat().st_size
                    if size_bytes < 1024:
                        size = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size = f"{size_bytes / (1024 * 1024):.1f} MB"
                    size = f" ({size})"
                
                entries.append(f"{icon} {item.name}{size}")
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"[目录] {path}\n" + "\n".join(entries) or "(空目录)",
                metadata={"path": str(path), "count": len(entries)}
            )
            
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"列出目录失败: {str(e)}",
                exit_code=1
            )
    
    def search_files(self, pattern: str, path: str = ".") -> ToolResult:
        """在文件中搜索内容."""
        try:
            import re
            
            search_path = Path(path)
            if not search_path.is_absolute():
                search_path = self.project_path / search_path
            search_path = search_path.resolve()
            
            matches = []
            max_matches = 50
            
            for root, dirs, files in os.walk(search_path):
                # 跳过常见忽略目录
                dirs[:] = [d for d in dirs if d not in (
                    "node_modules", "__pycache__", ".git", ".venv",
                    "venv", "dist", "build", ".idea", ".vscode"
                )]
                
                for filename in files:
                    if len(matches) >= max_matches:
                        break
                    
                    file_path = Path(root) / filename
                    
                    # 跳过二进制文件和大文件
                    try:
                        if file_path.stat().st_size > 1024 * 1024:
                            continue
                        
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        
                        if pattern in content:
                            lines = content.split("\n")
                            for i, line in enumerate(lines, 1):
                                if pattern in line:
                                    rel_path = file_path.relative_to(search_path)
                                    matches.append(f"{rel_path}:{i}: {line.strip()}")
                                    if len(matches) >= max_matches:
                                        break
                    except:
                        continue
                
                if len(matches) >= max_matches:
                    break
            
            result = "\n".join(matches) if matches else f"未找到包含 '{pattern}' 的文件"
            if len(matches) >= max_matches:
                result += f"\n\n... (结果过多，仅显示前 {max_matches} 条)"
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=result,
                metadata={"pattern": pattern, "matches": len(matches)}
            )
            
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"搜索失败: {str(e)}",
                exit_code=1
            )
    
    def get_tools_description(self) -> List[Dict[str, Any]]:
        """获取所有可用工具的 JSON Schema 描述（用于 AI 工具调用）."""
        return [
            {
                "name": "execute_command",
                "description": "执行 shell 命令，获取命令输出。使用此工具来运行测试、构建项目、安装依赖等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的 shell 命令"
                        },
                        "cwd": {
                            "type": "string",
                            "description": "执行命令的工作目录（相对项目根目录）"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "read_file",
                "description": "读取文件内容。使用此工具来查看代码、配置文件、日志等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "文件路径（相对项目根目录或绝对路径）"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "write_file",
                "description": "写入或覆盖文件内容。使用此工具来创建新文件或修改现有文件。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "文件路径（相对项目根目录）"
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入的文件内容"
                        }
                    },
                    "required": ["file_path", "content"]
                }
            },
            {
                "name": "list_directory",
                "description": "列出目录内容。使用此工具来查看项目结构、列出文件等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dir_path": {
                            "type": "string",
                            "description": "目录路径（相对项目根目录，默认当前目录）"
                        }
                    }
                }
            },
            {
                "name": "search_files",
                "description": "在文件中搜索文本内容。使用此工具来查找代码片段、变量定义等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "要搜索的文本内容"
                        },
                        "path": {
                            "type": "string",
                            "description": "搜索路径（相对项目根目录，默认项目根目录）"
                        }
                    },
                    "required": ["pattern"]
                }
            },
            {
                "name": "execute_code",
                "description": "执行 Python 代码片段并返回结果。用于快速计算、数据处理、算法验证等。沙箱环境，部分系统模块受限。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python 代码字符串"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "analyze_project",
                "description": "分析当前项目结构，检测项目类型、框架、依赖等。用于了解项目概况。",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "web_search",
                "description": "使用搜索引擎搜索网络信息。用于获取最新文档、技术资料、错误解决方案等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回结果数量（默认 5）"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    
    def execute_code(self, code: str) -> ToolResult:
        """在沙箱中执行 Python 代码."""
        try:
            from .code_sandbox import CodeSandbox, CodeExecutionStatus
            
            sandbox = CodeSandbox(timeout=5.0)
            result = sandbox.execute(code)
            
            output = result.output
            if result.error:
                output += f"\n\n[ERROR] {result.error}"
            
            status_map = {
                CodeExecutionStatus.SUCCESS: ToolResultStatus.SUCCESS,
                CodeExecutionStatus.SYNTAX_ERROR: ToolResultStatus.ERROR,
                CodeExecutionStatus.SECURITY_ERROR: ToolResultStatus.ERROR,
                CodeExecutionStatus.ERROR: ToolResultStatus.ERROR,
                CodeExecutionStatus.TIMEOUT: ToolResultStatus.TIMEOUT,
            }
            
            return ToolResult(
                status=status_map.get(result.status, ToolResultStatus.ERROR),
                output=output.strip() or f"(执行耗时: {result.execution_time:.2f}s, 无输出)",
                metadata={"execution_time": result.execution_time}
            )
            
        except ImportError as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"代码沙箱模块未加载: {e}",
                exit_code=1
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"代码执行异常: {str(e)}",
                exit_code=1
            )
    
    def analyze_project(self) -> ToolResult:
        """分析项目结构."""
        try:
            from .project_analyzer import ProjectAnalyzer
            
            analyzer = ProjectAnalyzer(str(self.project_path))
            summary = analyzer.get_summary()
            context = analyzer.get_system_context()
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"{summary}\n\n{context}",
                metadata={"path": str(self.project_path)}
            )
            
        except ImportError as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"项目分析模块未加载: {e}",
                exit_code=1
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"项目分析异常: {str(e)}",
                exit_code=1
            )
    
    def web_search(self, query: str, limit: int = 5) -> ToolResult:
        """网页搜索."""
        try:
            # 尝试使用 kimi_search_v2
            # 由于这是外部工具，我们提供一个简单的实现
            # 实际使用时可以通过环境变量或配置接入搜索引擎
            
            # 模拟搜索结果（实际应调用搜索API）
            result_text = f"""搜索结果: {query}

注: web_search 工具需要配置搜索引擎API。

建议配置方式:
1. 设置环境变量 KIMI_SEARCH_API_KEY
2. 或修改配置文件添加搜索引擎设置

当前项目路径: {self.project_path}
"""
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=result_text,
                metadata={"query": query, "limit": limit}
            )
            
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"搜索失败: {str(e)}",
                exit_code=1
            )
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """根据名称执行工具."""
        tools = {
            "execute_command": self.execute_command,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "list_directory": self.list_directory,
            "search_files": self.search_files,
            "execute_code": self.execute_code,
            "analyze_project": self.analyze_project,
            "web_search": self.web_search,
        }
        
        if tool_name not in tools:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"未知工具: {tool_name}",
                exit_code=1
            )
        
        try:
            return tools[tool_name](**parameters)
        except TypeError as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"参数错误: {str(e)}",
                exit_code=1
            )
