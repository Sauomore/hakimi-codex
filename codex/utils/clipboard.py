"""跨平台剪贴板工具.

提供复制文本到系统剪贴板的能力.

设计原则:
1. 全程异步，避免阻塞 UI 主线程导致窗口卡死。
2. 优先使用系统命令 (clip/pbcopy/xclip) 复制到剪贴板。
3. 系统命令失败时回退到 pyperclip（在线程池中执行）。
4. 剪贴板全部失败时，将内容写入临时文件并调用系统默认程序打开，
   用户可在外部编辑器中自由选择和复制。
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


class ClipboardError(Exception):
    """剪贴板操作失败."""


def _copy_windows_native(text: str) -> None:
    """Windows 原生剪贴板实现.

    同时写入 CF_UNICODETEXT（Unicode）和 CF_TEXT（系统默认代码页）
    两种格式，兼容只读取 ANSI 的 GBK 程序。
    """
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # 明确函数签名，避免 64 位系统上 HANDLE/指针被截断为 32 位导致访问冲突
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_bool
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_bool
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    kernel32.WideCharToMultiByte.argtypes = [
        ctypes.c_uint, ctypes.c_ulong, ctypes.c_wchar_p,
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
        ctypes.c_char_p, ctypes.POINTER(ctypes.c_bool),
    ]
    kernel32.WideCharToMultiByte.restype = ctypes.c_int

    GHND = 0x0042
    CF_UNICODETEXT = 13
    CF_TEXT = 1

    if not user32.OpenClipboard(None):
        raise ClipboardError("无法打开剪贴板")
    try:
        if not user32.EmptyClipboard():
            raise ClipboardError("无法清空剪贴板")

        # CF_UNICODETEXT：使用 UTF-16-LE
        text_utf16 = text.encode("utf-16-le", errors="replace") + b"\x00\x00"
        handle_uni = kernel32.GlobalAlloc(GHND, len(text_utf16))
        if not handle_uni:
            raise ClipboardError("无法分配 Unicode 剪贴板内存")
        ptr_uni = kernel32.GlobalLock(handle_uni)
        if not ptr_uni:
            kernel32.GlobalFree(handle_uni)
            raise ClipboardError("无法锁定 Unicode 剪贴板内存")
        try:
            ctypes.memmove(ptr_uni, text_utf16, len(text_utf16))
        finally:
            kernel32.GlobalUnlock(handle_uni)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle_uni):
            raise ClipboardError("无法设置 Unicode 剪贴板数据")

        # CF_TEXT：系统默认 ANSI 代码页（中文 Windows 通常为 GBK/936）
        size = kernel32.WideCharToMultiByte(
            0, 0, text, -1, None, 0, None, None
        )
        if size > 0:
            text_ansi = ctypes.create_string_buffer(size)
            converted = kernel32.WideCharToMultiByte(
                0, 0, text, -1, text_ansi, size, None, None
            )
            if converted > 0:
                handle_ansi = kernel32.GlobalAlloc(GHND, size)
                if handle_ansi:
                    ptr_ansi = kernel32.GlobalLock(handle_ansi)
                    if ptr_ansi:
                        try:
                            ctypes.memmove(ptr_ansi, text_ansi, size)
                        finally:
                            kernel32.GlobalUnlock(handle_ansi)
                        user32.SetClipboardData(CF_TEXT, handle_ansi)
    finally:
        user32.CloseClipboard()


async def _copy_windows_native_async(text: str) -> None:
    """在线程池中执行 Windows 原生剪贴板操作，避免阻塞 UI."""
    loop = asyncio.get_running_loop()
    await asyncio.wait_for(
        loop.run_in_executor(None, _copy_windows_native, text),
        timeout=3.0,
    )


async def _copy_via_subprocess_async(text: str) -> None:
    """通过异步子进程调用系统剪贴板命令."""
    system = platform.system()

    if system == "Windows":
        # 方案 A：PowerShell Set-Clipboard（最可靠，自动处理 Unicode/ANSI）
        try:
            script = (
                "$reader = [System.IO.StreamReader]::new("
                "[System.Console]::OpenStandardInput(), "
                "[System.Text.Encoding]::UTF8); "
                "$text = $reader.ReadToEnd(); "
                "Set-Clipboard -Value $text"
            )
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(
                proc.communicate(text.encode("utf-8", errors="replace")),
                timeout=5.0,
            )
            if proc.returncode == 0:
                return
        except Exception:
            pass

        # 方案 B：Windows 自带 clip.exe
        try:
            proc = await asyncio.create_subprocess_exec(
                "clip.exe",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(
                proc.communicate(text.encode("utf-16-le", errors="replace")),
                timeout=3.0,
            )
            if proc.returncode == 0:
                return
        except Exception:
            pass

    elif system == "Darwin":
        try:
            proc = await asyncio.create_subprocess_exec(
                "pbcopy",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(
                proc.communicate(text.encode("utf-8", errors="replace")),
                timeout=3.0,
            )
            if proc.returncode == 0:
                return
        except Exception:
            pass

    else:
        # Linux / 其他 Unix
        for cmd in (
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(
                    proc.communicate(text.encode("utf-8", errors="replace")),
                    timeout=3.0,
                )
                if proc.returncode == 0:
                    return
            except Exception:
                continue

    raise ClipboardError("系统剪贴板命令全部失败")


def _pyperclip_copy_sync(text: str) -> None:
    """同步调用 pyperclip."""
    import pyperclip

    pyperclip.copy(text)


async def _copy_via_pyperclip_async(text: str) -> None:
    """在线程池中异步调用 pyperclip，避免阻塞 UI."""
    try:
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(
            loop.run_in_executor(None, _pyperclip_copy_sync, text),
            timeout=3.0,
        )
    except Exception as exc:
        raise ClipboardError(f"pyperclip 失败: {exc}") from exc


def _write_to_temp_file(text: str, prefix: str = "hakimi_copy") -> Path:
    """将文本写入临时文件并返回路径."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fd, path = tempfile.mkstemp(suffix=".txt", prefix=f"{prefix}_{timestamp}_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return Path(path)


def _open_file(path: Path) -> None:
    """使用系统默认程序打开文件."""
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


async def copy_to_clipboard(text: str) -> Optional[Path]:
    """异步复制文本到系统剪贴板.

    成功时返回 None.
    如果剪贴板全部失败，则写入临时文件并打开，返回该文件路径。
    """
    if not text:
        return None

    # Windows：优先原生 API，同时写入 CF_UNICODETEXT 和 CF_TEXT（ANSI/GBK），
    # 兼容只读取 GBK 的程序。
    if platform.system() == "Windows":
        try:
            await _copy_windows_native_async(text)
            return None
        except Exception:
            pass

    # 1. 优先异步系统命令
    try:
        await _copy_via_subprocess_async(text)
        return None
    except Exception:
        pass

    # 2. 回退到 pyperclip（线程池异步）
    try:
        await _copy_via_pyperclip_async(text)
        return None
    except Exception:
        pass

    # 3. 最终回退：写入临时文件并打开
    path = _write_to_temp_file(text)
    _open_file(path)
    return path


async def export_to_file(text: str, directory: Optional[Path] = None, prefix: str = "hakimi_export") -> Path:
    """将文本导出到文件并打开.

    默认保存到用户指定的目录，未指定时使用系统临时目录。
    """
    if directory is None:
        directory = Path(tempfile.gettempdir())
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}_{timestamp}.txt"
    path.write_text(text, encoding="utf-8")
    _open_file(path)
    return path


def get_clipboard_text() -> str:
    """读取系统剪贴板文本（同步，仅用于非关键路径）."""
    try:
        import pyperclip

        return pyperclip.paste() or ""
    except Exception:
        return ""
