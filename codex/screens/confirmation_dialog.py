"""确认对话框 - 用于终端命令和代码修改前的用户确认."""

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
        margin-bottom: 1;
    }
    ConfirmationDialog Container > Static.message {
        height: auto;
        margin-bottom: 1;
        color: $text;
    }
    ConfirmationDialog Container > RichLog.content {
        height: 1fr;
        min-height: 5;
        max-height: 30;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
        margin-bottom: 1;
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
        **kwargs
    ):
        super().__init__(**kwargs)
        self.title = title
        self.content = content
        self.content_type = content_type  # "text" 或 "diff"
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self.title, classes="title")
            
            if self.content_type == "diff":
                log = RichLog(classes="content", wrap=True, markup=True, highlight=False, auto_scroll=True)
                yield log
                self._render_diff(log, self.content)
            else:
                yield Static(self.content, classes="message")
            
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
