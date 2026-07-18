"""聊天记录搜索对话框."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button, Input, RichLog


@dataclass
class SearchResult:
    """搜索结果项."""

    message_id: str
    role: str
    timestamp: datetime
    preview: str


class SearchDialog(ModalScreen[None]):
    """聊天记录搜索对话框.

    输入关键词后点击搜索，结果会显示消息 ID、角色、时间和摘要，
    关闭后可在主界面使用 /copy <id> 复制指定消息。
    """

    CSS = """
    SearchDialog {
        align: center middle;
        background: $background 70%;
    }
    SearchDialog > Container {
        width: 90;
        height: auto;
        max-height: 90%;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    SearchDialog Container > Static.title {
        text-style: bold;
        text-align: center;
        color: $primary-lighten-2;
        height: auto;
        margin-bottom: 0;
    }
    SearchDialog Container > Static.hint {
        height: auto;
        color: $text-muted;
        text-style: italic;
        text-align: center;
        margin-bottom: 1;
    }
    SearchDialog Container > Horizontal {
        height: auto;
        margin-bottom: 1;
    }
    SearchDialog Container > Horizontal > Input {
        width: 1fr;
    }
    SearchDialog Container > Horizontal > Button {
        margin-left: 1;
    }
    SearchDialog Container > RichLog.results {
        height: 1fr;
        min-height: 5;
        max-height: 35;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
        overflow: auto scroll;
        scrollbar-size: 1 1;
    }
    """

    def __init__(
        self,
        search_callback: Callable[[str], List[SearchResult]],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.search_callback = search_callback

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("搜索聊天记录", classes="title")
            yield Static("输入关键词，使用 /copy <id> 可复制指定消息", classes="hint")
            with Horizontal():
                yield Input(placeholder="关键词...", id="keyword_input")
                yield Button("搜索", id="btn_search", variant="primary")
            yield RichLog(classes="results", id="results_log", wrap=True, markup=False, highlight=False)
            with Horizontal():
                yield Button("关闭", id="btn_close", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        if event.button.id == "btn_search":
            self._do_search()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted):
        """回车直接搜索."""
        if event.input.id == "keyword_input":
            self._do_search()

    def on_key(self, event):
        """键盘快捷键."""
        if event.key == "escape":
            self.dismiss(None)

    def _do_search(self):
        """执行搜索并渲染结果."""
        keyword_input = self.query_one("#keyword_input", Input)
        keyword = keyword_input.value.strip()
        results_log = self.query_one("#results_log", RichLog)
        results_log.clear()

        if not keyword:
            results_log.write("请输入关键词")
            return

        results = self.search_callback(keyword)
        if not results:
            results_log.write(f'未找到包含 "{keyword}" 的记录')
            return

        results_log.write(f'"{keyword}" 共 {len(results)} 条结果')
        results_log.write("-" * 40)
        for r in results:
            ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            results_log.write(f"[{r.message_id}] [{ts}] {r.role}: {r.preview}")
        results_log.write("-" * 40)
        results_log.write("使用 /copy <id> 复制指定消息")
