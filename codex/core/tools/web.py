"""网页搜索工具（占位实现）."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ToolExecutor

from .base import ToolResult, ToolResultStatus


def web_search(executor: "ToolExecutor", query: str, limit: int = 5) -> ToolResult:
    """网页搜索（占位实现）."""
    result_text = f"""搜索结果: {query}

注: web_search 工具需要配置搜索引擎API。

建议配置方式:
1. 设置环境变量 KIMI_SEARCH_API_KEY
2. 或修改配置文件添加搜索引擎设置

当前项目路径: {executor.project_path}
"""

    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        output=result_text,
        metadata={"query": query, "limit": limit}
    )
