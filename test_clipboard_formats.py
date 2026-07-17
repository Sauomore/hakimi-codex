"""验证 Windows 剪贴板同时包含 Unicode 和 ANSI(GBK) 格式."""

import asyncio
import ctypes

from codex.utils.clipboard import copy_to_clipboard


async def test_clipboard_formats():
    text = "Hello 世界"
    await copy_to_clipboard(text)

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_bool
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p

    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool

    if not user32.OpenClipboard(None):
        raise RuntimeError("无法打开剪贴板")

    try:
        # CF_UNICODETEXT = 13
        handle_uni = user32.GetClipboardData(13)
        if handle_uni:
            ptr_uni = kernel32.GlobalLock(handle_uni)
            try:
                uni_text = ctypes.wstring_at(ptr_uni)
                assert uni_text == text, f"Unicode 不匹配: {uni_text!r}"
                print(f"CF_UNICODETEXT OK: {uni_text!r}")
            finally:
                kernel32.GlobalUnlock(handle_uni)
        else:
            print("CF_UNICODETEXT not available")

        # CF_TEXT = 1
        handle_ansi = user32.GetClipboardData(1)
        if handle_ansi:
            ptr_ansi = kernel32.GlobalLock(handle_ansi)
            try:
                ansi_text = ctypes.string_at(ptr_ansi).decode("gbk", errors="replace")
                # string_at includes null terminator, strip it
                ansi_text = ansi_text.rstrip("\x00")
                assert ansi_text == text, f"ANSI 不匹配: {ansi_text!r}"
                print(f"CF_TEXT OK (GBK): {ansi_text!r}")
            finally:
                kernel32.GlobalUnlock(handle_ansi)
        else:
            print("CF_TEXT not available")
    finally:
        user32.CloseClipboard()


if __name__ == "__main__":
    asyncio.run(test_clipboard_formats())
