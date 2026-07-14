"""Shell 命令执行工具."""

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ToolExecutor

from .base import ToolResult, ToolResultStatus


# 危险命令黑名单（部分匹配）
DANGEROUS_COMMANDS = [
    "rm -rf /", "rm -rf /*", "rm -rf ~", "rm -rf /root",
    "mkfs", "dd if=/dev/zero", ":(){ :|:& };:",
    "> /dev/sda", "> /dev/hda", "chmod -R 777 /",
    "del /f /s /q c:\\", "format c:", "rd /s /q c:\\",
]


def _check_dangerous(command: str) -> bool:
    """检查命令是否包含危险操作."""
    cmd_lower = command.lower().strip()
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous.lower() in cmd_lower:
            return True
    return False


def execute_command(executor: "ToolExecutor", command: str, cwd: str = None) -> ToolResult:
    """执行 shell 命令."""
    if _check_dangerous(command):
        return ToolResult(
            status=ToolResultStatus.ERROR,
            output="[错误] 检测到危险命令，已拒绝执行。",
            exit_code=1
        )

    work_dir = Path(cwd).resolve() if cwd else executor.project_path

    try:
        # Windows 下 cmd.exe 默认使用 GBK 编码，需要特殊处理
        import sys
        if sys.platform == "win32":
            # 在 Windows 上使用二进制模式，然后手动解码
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(work_dir),
                capture_output=True,
                timeout=executor.command_timeout,
            )
            # 尝试 UTF-8 解码，失败则用 GBK
            try:
                output = result.stdout.decode("utf-8")
            except UnicodeDecodeError:
                output = result.stdout.decode("gbk", errors="replace")
            stderr_output = ""
            if result.stderr:
                try:
                    stderr_output = result.stderr.decode("utf-8")
                except UnicodeDecodeError:
                    stderr_output = result.stderr.decode("gbk", errors="replace")
        else:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=executor.command_timeout,
                encoding="utf-8",
                errors="replace"
            )
            output = result.stdout
            stderr_output = result.stderr

        if stderr_output:
            output += "\n" + stderr_output

        output = executor._truncate_output(output)

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
            output=f"[错误] 命令执行超时（超过 {executor.command_timeout} 秒）",
            exit_code=124
        )
    except Exception as e:
        return ToolResult(
            status=ToolResultStatus.ERROR,
            output=f"[错误] 执行异常: {str(e)}",
            exit_code=1
        )
