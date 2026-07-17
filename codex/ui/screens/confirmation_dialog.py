"""确认对话框 - 用于终端命令和代码修改前的用户确认."""

from typing import Callable, Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button, RichLog


class ConfirmationDialog(ModalScreen[bool]):
    """通用确认对话框.

    支持纯文本和 diff 两种内容展示模式，返回 True/False 表示用户确认/取消.
    """

    CSS = """
    ConfirmationDialog {
        align: center middle;
        background: $background 70%;
    }
    ConfirmationDialog > Container {
        width: 90;
        height: auto;
        max-height: 90%;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    ConfirmationDialog Container > Static.title {
        text-style: bold;
        text-align: center;
        color: $primary-lighten-2;
        height: auto;
        margin-bottom: 0;
    }
    ConfirmationDialog Container > Static.scroll_hint {
        height: auto;
        color: $text-muted;
        text-style: italic;
        text-align: center;
        margin-bottom: 1;
    }
    ConfirmationDialog Container > RichLog.content {
        height: 1fr;
        min-height: 5;
        max-height: 35;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
        margin-bottom: 1;
        overflow: auto scroll;
        scrollbar-size: 1 1;
    }
    ConfirmationDialog Container > Horizontal {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    ConfirmationDialog Container > Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        title: str,
        content: str,
        content_type: str = "text",
        confirm_label: str = "确认",
        cancel_label: str = "取消",
        on_dismiss: Optional[Callable[[bool], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.title = title
        self.content = content
        self.content_type = content_type  # "text" 或 "diff"
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.on_dismiss_callback = on_dismiss

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self.title, classes="title")
            yield Static("↑↓ 鼠标滚轮 / PageUp / PageDown 滚动查看", classes="scroll_hint")

            if self.content_type == "diff":
                log = RichLog(
                    classes="content",
                    wrap=True,
                    markup=True,
                    highlight=False,
                    auto_scroll=False,
                )
                yield log
                self._render_diff(log, self.content)
            else:
                log = RichLog(
                    classes="content",
                    wrap=True,
                    markup=False,
                    highlight=False,
                    auto_scroll=False,
                )
                yield log
                self._render_text(log, self.content)

            with Horizontal():
                yield Button(self.confirm_label, id="btn_confirm", variant="success")
                yield Button(self.cancel_label, id="btn_cancel", variant="default")

    def _render_diff(self, log: RichLog, diff: str):
        """渲染 diff 内容."""
        log.write("[bold #e0e0e0]--- diff[/bold #e0e0e0]")
        for line in diff.split("\n"):
            if line.startswith("+"):
                log.write(f"[bold #3fb950]{line}[/bold #3fb950]")
            elif line.startswith("-"):
                log.write(f"[bold #f85149]{line}[/bold #f85149]")
            elif line.startswith("@@"):
                log.write(f"[#888888]{line}[/#888888]")
            else:
                log.write(f"[#aaaaaa]{line}[/#aaaaaa]")
        log.write("[bold #e0e0e0]---[/bold #e0e0e0]")

    def _render_text(self, log: RichLog, text: str):
        """渲染纯文本内容（按行写入，支持长文本滚动）."""
        for line in text.split("\n"):
            log.write(line)

    def dismiss(self, result: Optional[bool] = None) -> None:
        """关闭对话框并触发回调."""
        if self.on_dismiss_callback is not None and result is not None:
            try:
                self.on_dismiss_callback(bool(result))
            except Exception:
                pass
        super().dismiss(result)

    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        if event.button.id == "btn_confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event):
        """键盘快捷键."""
        if event.key == "escape":
            self.dismiss(False)
        elif event.key == "enter":
            self.dismiss(True)
