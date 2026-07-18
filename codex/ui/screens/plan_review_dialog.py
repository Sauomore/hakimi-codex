"""计划审核对话框 - 允许用户查看、编辑并确认 Agent 执行计划."""

from typing import Callable, Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button, TextArea


class PlanReviewDialog(ModalScreen[Optional[str]]):
    """Agent 计划审核对话框.

    用户可以在文本框中编辑计划，点击"确认执行"后开始流水线，
    点击"取消"则终止 Agent 执行。
    """

    CSS = """
    PlanReviewDialog {
        align: center middle;
        background: $background 70%;
    }
    PlanReviewDialog > Container {
        width: 95;
        height: auto;
        max-height: 90%;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    PlanReviewDialog Container > Static.title {
        text-style: bold;
        text-align: center;
        color: $primary-lighten-2;
        height: auto;
        margin-bottom: 0;
    }
    PlanReviewDialog Container > Static.hint {
        height: auto;
        color: $text-muted;
        text-style: italic;
        text-align: center;
        margin-bottom: 1;
    }
    PlanReviewDialog Container > TextArea.plan_input {
        height: 1fr;
        min-height: 8;
        max-height: 40;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
        margin-bottom: 1;
    }
    PlanReviewDialog Container > Horizontal {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    PlanReviewDialog Container > Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        plan: str,
        on_dismiss: Optional[Callable[[Optional[str]], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.plan = plan
        self.on_dismiss_callback = on_dismiss

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Agent Planner 生成的执行计划", classes="title")
            yield Static("可直接编辑计划内容，确认后 Coder 开始执行", classes="hint")
            yield TextArea(self.plan, classes="plan_input", id="plan_input")
            with Horizontal():
                yield Button("确认执行", id="btn_confirm", variant="success")
                yield Button("取消", id="btn_cancel", variant="default")

    def dismiss(self, result: Optional[str] = None) -> None:
        """关闭对话框并触发回调（包括取消时返回 None）."""
        if self.on_dismiss_callback is not None:
            try:
                self.on_dismiss_callback(result)
            except Exception:
                pass
        super().dismiss(result)

    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        if event.button.id == "btn_confirm":
            plan_input = self.query_one("#plan_input", TextArea)
            self.dismiss(plan_input.text)
        else:
            self.dismiss(None)

    def on_key(self, event):
        """键盘快捷键."""
        if event.key == "escape":
            self.dismiss(None)
