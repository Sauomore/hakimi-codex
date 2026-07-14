"""代码沙箱执行工具."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ToolExecutor

from .base import ToolResult, ToolResultStatus
from ..code_sandbox import CodeSandbox, CodeExecutionStatus


_STATUS_MAP = {
    CodeExecutionStatus.SUCCESS: ToolResultStatus.SUCCESS,
    CodeExecutionStatus.SYNTAX_ERROR: ToolResultStatus.ERROR,
    CodeExecutionStatus.SECURITY_ERROR: ToolResultStatus.ERROR,
    CodeExecutionStatus.ERROR: ToolResultStatus.ERROR,
    CodeExecutionStatus.TIMEOUT: ToolResultStatus.TIMEOUT,
}


def execute_code(executor: "ToolExecutor", code: str) -> ToolResult:
    """在沙箱中执行 Python 代码."""
    try:
        sandbox = CodeSandbox(timeout=5.0)
        result = sandbox.execute(code)

        output = result.output
        if result.error:
            output += f"\n\n[ERROR] {result.error}"

        return ToolResult(
            status=_STATUS_MAP.get(result.status, ToolResultStatus.ERROR),
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
