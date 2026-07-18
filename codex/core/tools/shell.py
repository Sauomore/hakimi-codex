"""Shell 命令执行工具."""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

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


def _extract_windows_start_target(command: str) -> Optional[str]:
    """从 Windows start 命令中提取目标文件路径."""
    rest = command[5:].strip()  # 去掉开头的 "start"

    # 跳过常见选项；/d 和 /affinity 需要额外跳过一个参数
    option_with_arg = {"/d", "/affinity"}
    while True:
        match = re.match(r'^/[a-zA-Z]+', rest)
        if not match:
            break
        option = match.group(0).lower()
        rest = rest[match.end():].strip()
        if option in option_with_arg and rest:
            # 跳过选项的参数（一个 token 或引号字符串）
            if rest.startswith('"'):
                end = rest.find('"', 1)
                if end != -1:
                    rest = rest[end + 1:].strip()
            else:
                parts = rest.split(None, 1)
                rest = parts[1] if len(parts) > 1 else ""

    # 跳过可选的窗口标题（引号包裹）
    if rest.startswith('"'):
        end = rest.find('"', 1)
        if end != -1:
            rest = rest[end + 1:].strip()

    if not rest:
        return None

    # 取第一个 token 作为目标路径
    parts = rest.split(None, 1)
    target = parts[0].strip('"').strip("'")
    return target or None


def _handle_windows_start_command(command: str, work_dir: Path) -> Optional[ToolResult]:
    """处理 Windows start 命令：目标文件不存在时直接返回错误，避免系统弹窗."""
    if sys.platform != "win32":
        return None

    cmd_lower = command.strip().lower()
    if not cmd_lower.startswith("start ") and cmd_lower != "start":
        return None

    target = _extract_windows_start_target(command)
    if not target:
        return None

    # URL 直接放行
    if target.lower().startswith(("http://", "https://", "ftp://")):
        return None

    # 解析为绝对路径
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = work_dir / target

    if not target_path.exists():
        return ToolResult(
            status=ToolResultStatus.ERROR,
            output=f"[错误] 无法打开文件（不存在）: {target_path}",
            exit_code=1,
            metadata={"command": command, "cwd": str(work_dir)},
        )

    return None


def execute_command(executor: "ToolExecutor", command: str, cwd: str = None) -> ToolResult:
    """执行 shell 命令."""
    if _check_dangerous(command):
        return ToolResult(
            status=ToolResultStatus.ERROR,
            output="[错误] 检测到危险命令，已拒绝执行。",
            exit_code=1
        )

    work_dir = Path(cwd).resolve() if cwd else executor.project_path

    # Windows start 命令特殊处理：文件不存在时提前返回，避免系统错误弹窗
    start_result = _handle_windows_start_command(command, work_dir)
    if start_result is not None:
        return start_result

    try:
        # Windows 下 cmd.exe 默认使用 GBK 编码，需要特殊处理
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
