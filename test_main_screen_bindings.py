"""测试 MainScreen 快捷键绑定."""

from codex.ui.screens.main_screen import MainScreen
from codex.ui.screens.copy_view_dialog import CopyViewDialog


def test_bindings():
    keys = {b[0] for b in MainScreen.BINDINGS}
    assert "f5" in keys, f"missing f5: {keys}"
    assert "f6" in keys, f"missing f6: {keys}"
    assert "ctrl+c" in keys, f"missing ctrl+c: {keys}"
    print("MainScreen bindings test passed")


def test_copy_view_dialog_bindings():
    keys = {b[0] for b in CopyViewDialog.BINDINGS}
    assert "ctrl+c" in keys, f"missing ctrl+c: {keys}"
    assert "escape" in keys, f"missing escape: {keys}"
    print("CopyViewDialog bindings test passed")


if __name__ == "__main__":
    test_bindings()
    test_copy_view_dialog_bindings()
