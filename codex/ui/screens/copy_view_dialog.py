"""可复制文本查看弹窗.

提供一个只读的 TextArea，允许用户使用鼠标滑动选择并复制内容。
同时提供"复制到剪贴板"和"导出到文件"按钮，避免依赖单一剪贴板方案。
"""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, TextArea, Button

from codex.utils.clipboard import copy_to_clipboard, export_to_file


class CopyViewTextArea(TextArea):
    """复制视图中的只读文本区，Ctrl+C 复制全部内容."""

    def on_key(self, event):
        if event.key == "ctrl+c":
            event.prevent_default()
            event.stop()
            self.screen.action_copy_to_clipboard()
            return


class CopyViewDialog(ModalScreen[str]):
    """显示可复制文本的弹窗."""

    BINDINGS = [
        ("ctrl+c", "copy_to_clipboard", "Copy"),
        ("escape", "dismiss", "Close"),
    ]

    # 单次弹窗最大显示字符数，避免 TextArea 加载过大内容导致卡死
    MAX_DISPLAY_CHARS = 50_000

    def __init__(
        self,
        title: str,
        content: str,
        export_directory: Optional[Path] = None,
        **kwargs
    ):
        self.title_text = title
        self.content = content
        self.export_directory = export_directory
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        display_content = self.content
        truncated = False
        if len(display_content) > self.MAX_DISPLAY_CHARS:
            display_content = display_content[: self.MAX_DISPLAY_CHARS]
            truncated = True

        with Vertical(id="copy_dialog_container"):
            yield Static(self.title_text, classes="title")
            if truncated:
                yield Static(
                    (
                        f"内容过长，仅显示前 {self.MAX_DISPLAY_CHARS} 字符；"
                        '可使用下方"导出到文件"按钮保存完整内容。'
                    ),
                    classes="hint"
                )
            yield CopyViewTextArea(display_content, id="copy_text_area", read_only=True)
            yield Static("", id="copy_status")
            with Horizontal(id="copy_dialog_buttons"):
                yield Button("复制到剪贴板", id="copy_clipboard_button", variant="success")
                yield Button("导出到文件", id="copy_file_button", variant="primary")
                yield Button("关闭 (Esc)", id="copy_close_button", variant="default")

    def _get_text(self) -> str:
        return self.content

    async def _copy_to_clipboard(self) -> None:
        text = self._get_text()
        status = self.query_one("#copy_status", Static)
        try:
            fallback_path = await copy_to_clipboard(text)
            if fallback_path:
                status.update(
                    f"[bold yellow]剪贴板不可用，已导出到文件并打开：{fallback_path}[/bold yellow]"
                )
            else:
                status.update("[bold green]已复制到剪贴板[/bold green]")
        except Exception as e:
            status.update(f"[bold red]复制失败：{e}[/bold red]")

    async def _export_to_file(self) -> None:
        text = self._get_text()
        status = self.query_one("#copy_status", Static)
        try:
            path = await export_to_file(text, directory=self.export_directory)
            status.update(f"[bold green]已导出并打开：{path}[/bold green]")
        except Exception as e:
            status.update(f"[bold red]导出失败：{e}[/bold red]")

    def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id == "copy_close_button":
            self.dismiss("")
        elif button_id == "copy_clipboard_button":
            self.run_worker(self._copy_to_clipboard())
        elif button_id == "copy_file_button":
            self.run_worker(self._export_to_file())

    async def action_copy_to_clipboard(self):
        """弹窗内 Ctrl+C：复制全部内容到剪贴板."""
        await self._copy_to_clipboard()

    def action_dismiss(self):
        self.dismiss("")
