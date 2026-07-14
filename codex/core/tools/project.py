"""项目分析工具."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ToolExecutor

from .base import ToolResult, ToolResultStatus


def analyze_project(executor: "ToolExecutor") -> ToolResult:
    """分析项目结构."""
    try:
        from ..project_analyzer import ProjectAnalyzer

        analyzer = ProjectAnalyzer(str(executor.project_path))
        summary = analyzer.get_summary()
        context = analyzer.get_system_context()

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output=f"{summary}\n\n{context}",
            metadata={"path": str(executor.project_path)}
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
