"""工具执行基座."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict


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
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolExecutor:
    """工具执行器 - 安全地执行各类工具操作."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.max_output_size = 50000  # 最大输出字符数
        self.command_timeout = 60  # 命令超时秒数

    def _truncate_output(self, output: str) -> str:
        """截断过长的输出."""
        if len(output) > self.max_output_size:
            return output[:self.max_output_size] + f"\n\n... (输出已截断，共 {len(output)} 字符)"
        return output

    def execute_command(self, command: str, cwd: str = None) -> ToolResult:
        """执行 shell 命令."""
        from .shell import execute_command
        return execute_command(self, command, cwd)

    def read_file(self, file_path: str = None, limit: int = 0) -> ToolResult:
        """读取文件内容."""
        if not file_path:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output='参数错误: read_file 必须提供 "file_path" 参数，例如 {"file_path": "random_generator.py"}',
                exit_code=1
            )
        # 确保 limit 是整数（LLM 可能传递字符串）
        try:
            limit = int(limit) if limit else 0
        except (ValueError, TypeError):
            limit = 0
        from .filesystem import read_file
        return read_file(self, file_path, limit)

    def write_file(self, file_path: str, content: str) -> ToolResult:
        """写入文件内容."""
        from .filesystem import write_file
        return write_file(self, file_path, content)

    def list_directory(self, dir_path: str = ".") -> ToolResult:
        """列出目录内容."""
        from .filesystem import list_directory
        return list_directory(self, dir_path)

    def search_files(self, pattern: str, path: str = ".") -> ToolResult:
        """在文件中搜索内容."""
        from .filesystem import search_files
        return search_files(self, pattern, path)

    def execute_code(self, code: str) -> ToolResult:
        """在沙箱中执行 Python 代码."""
        from .code import execute_code
        return execute_code(self, code)

    def analyze_project(self) -> ToolResult:
        """分析项目结构."""
        from .project import analyze_project
        return analyze_project(self)

    def web_search(self, query: str, limit: int = 5) -> ToolResult:
        """网页搜索（占位实现）."""
        from .web import web_search
        return web_search(self, query, limit)

    def get_tools_description(self) -> list:
        """获取所有可用工具的 JSON Schema 描述."""
        from .schemas import get_tools_description
        return get_tools_description()

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

        # 常见参数别名兼容
        params = dict(parameters)

        # list_directory: arguments/path -> dir_path
        if tool_name == "list_directory":
            if "arguments" in params:
                params["dir_path"] = params.pop("arguments")
            elif "path" in params and "dir_path" not in params:
                params["dir_path"] = params.pop("path")

        # search_files: search_path -> path
        if tool_name == "search_files" and "search_path" in params and "path" not in params:
            params["path"] = params.pop("search_path")

        # read_file: arguments -> file_path
        if tool_name == "read_file" and "arguments" in params and "file_path" not in params:
            params["file_path"] = params.pop("arguments")

        # execute_command: arguments -> command
        if tool_name == "execute_command" and "arguments" in params and "command" not in params:
            params["command"] = params.pop("arguments")

        # execute_code: arguments -> code
        if tool_name == "execute_code" and "arguments" in params and "code" not in params:
            params["code"] = params.pop("arguments")

        # write_file: arguments -> file_path/content
        if tool_name == "write_file" and "arguments" in params:
            args_val = params.pop("arguments")
            if "file_path" not in params:
                params["file_path"] = args_val

        try:
            return tools[tool_name](**params)
        except TypeError as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"参数错误: {str(e)}",
                exit_code=1
            )
