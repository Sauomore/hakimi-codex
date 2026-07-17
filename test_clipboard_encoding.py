"""测试剪贴板编码."""

import asyncio
from codex.utils.clipboard import copy_to_clipboard


async def test_encoding():
    text = "Hello 世界 🌍 中文测试"
    await copy_to_clipboard(text)

    # 用 pyperclip 读回验证
    try:
        import pyperclip
        result = pyperclip.paste()
        print(f"original: {text!r}")
        print(f"from clipboard: {result!r}")
        assert result == text, f"mismatch: {result!r} != {text!r}"
        print("encoding test passed")
    except Exception as e:
        print(f"read back failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_encoding())
