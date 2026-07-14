"""文件系统相关工具."""

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ToolExecutor

from .base import ToolResult, ToolResultStatus


def read_file(executor: "ToolExecutor", file_path: str, limit: int = 0) -> ToolResult:
    """读取文件内容.

    Args:
        limit: 最多读取的字符数，0 表示不限制。
    """
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = executor.project_path / path
        path = path.resolve()

        # 限制读取 debug log 文件（除非指定 limit 参数）
        if path.name == "hakimi_debug.log" and limit <= 0:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output="读取 debug log 文件需要指定 limit 参数（如 limit: 500），避免读取过大文件。",
                exit_code=1
            )

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

        max_size = 1024 * 1024  # 1MB
        file_size = path.stat().st_size
        if file_size > max_size and limit <= 0:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=f"文件过大 ({file_size} 字节)，最大支持 {max_size} 字节。请使用 limit 参数读取前 N 个字符。",
                exit_code=1
            )

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            if limit > 0:
                content = f.read(limit)
            else:
                content = f.read()

        if limit > 0 and file_size > limit:
            content += f"\n\n... (仅显示前 {limit} 个字符，文件共 {file_size} 字节)"

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


def write_file(executor: "ToolExecutor", file_path: str, content: str) -> ToolResult:
    """写入文件内容."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = executor.project_path / path
        path = path.resolve()

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


def list_directory(executor: "ToolExecutor", dir_path: str = ".") -> ToolResult:
    """列出目录内容."""
    try:
        path = Path(dir_path)
        if not path.is_absolute():
            path = executor.project_path / path
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

        # 排除的文件/目录（debug log、临时文件等）
        exclude_names = {"hakimi_debug.log", "__pycache__", ".git", "node_modules"}

        entries = []
        for item in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            # 跳过排除的文件/目录
            if item.name in exclude_names:
                continue

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


def search_files(executor: "ToolExecutor", pattern: str, path: str = ".") -> ToolResult:
    """在文件中搜索内容."""
    try:
        search_path = Path(path)
        if not search_path.is_absolute():
            search_path = executor.project_path / search_path
        search_path = search_path.resolve()

        matches = []
        max_matches = 50

        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if d not in (
                "node_modules", "__pycache__", ".git", ".venv",
                "venv", "dist", "build", ".idea", ".vscode"
            )]

            for filename in files:
                if len(matches) >= max_matches:
                    break

                file_path = Path(root) / filename

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
                except Exception:
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
