"""代码块操作对话框."""

from pathlib import Path
from typing import Callable, Coroutine, List, Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button

from codex.core.code_block_applier import CodeBlock, detect_target_file_path


CodeBlockCallback = Callable[[CodeBlock], Coroutine]


class CodeBlockDialog(ModalScreen[None]):
    """展示最近 AI 消息中的代码块，并提供复制/插入/写入操作."""

    CSS = """
    CodeBlockDialog {
        align: center middle;
        background: $background 70%;
    }
    CodeBlockDialog > Container {
        width: 95;
        height: auto;
        max-height: 90%;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    CodeBlockDialog Container > Static.title {
        text-style: bold;
        text-align: center;
        color: $primary-lighten-2;
        height: auto;
        margin-bottom: 0;
    }
    CodeBlockDialog Container > Static.hint {
        height: auto;
        color: $text-muted;
        text-style: italic;
        text-align: center;
        margin-bottom: 1;
    }
    CodeBlockDialog Container > Horizontal {
        height: auto;
        margin-bottom: 1;
    }
    CodeBlockDialog Container > Horizontal > Static {
        width: 1fr;
        content-align: center middle;
        color: $text;
    }
    CodeBlockDialog Container > Horizontal > Button {
        margin-left: 1;
    }
    """

    def __init__(
        self,
        code_blocks: List[CodeBlock],
        full_content: str,
        project_path: Path,
        on_copy: CodeBlockCallback,
        on_insert: CodeBlockCallback,
        on_write: CodeBlockCallback,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.code_blocks = code_blocks
        self.full_content = full_content
        self.project_path = project_path
        self.on_copy = on_copy
        self.on_insert = on_insert
        self.on_write = on_write

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("代码块操作", classes="title")
            yield Static("选择一个代码块执行复制、插入到输入框或写入文件", classes="hint")
            for i, block in enumerate(self.code_blocks):
                path = detect_target_file_path(block, self.full_content, self.project_path)
                label = f"#{i + 1} {block.language or 'code'}"
                if path:
                    label += f" -> {path}"
                with Horizontal():
                    yield Static(label)
                    yield Button("复制", id=f"copy_{i}", variant="default")
                    yield Button("插入", id=f"insert_{i}", variant="default")
                    if path:
                        yield Button("写入", id=f"write_{i}", variant="primary")
            with Horizontal():
                yield Button("关闭", id="btn_close", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        button_id = event.button.id
        if button_id == "btn_close":
            self.dismiss(None)
            return

        prefix, _, idx_str = button_id.partition("_")
        try:
            idx = int(idx_str)
        except ValueError:
            return
        if idx < 0 or idx >= len(self.code_blocks):
            return

        block = self.code_blocks[idx]
        if prefix == "copy":
            self.run_worker(self._run_callback(self.on_copy, block))
        elif prefix == "insert":
            self.run_worker(self._run_callback(self.on_insert, block))
        elif prefix == "write":
            self.run_worker(self._run_callback(self.on_write, block))

    async def _run_callback(self, callback: CodeBlockCallback, block: CodeBlock):
        """运行异步回调并忽略常见异常."""
        try:
            await callback(block)
        except Exception:
            pass

    def on_key(self, event):
        """键盘快捷键."""
        if event.key == "escape":
            self.dismiss(None)
