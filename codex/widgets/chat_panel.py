"""聊天面板组件."""

from typing import Callable, Optional

from textual.widgets import Input, Static, Button, RichLog
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.app import ComposeResult
from rich.text import Text
from rich.panel import Panel
from rich.syntax import Syntax
import re


class ChatPanel(Vertical):
    """聊天面板组件."""
    
    DEFAULT_CSS = """
    ChatPanel {
        width: 100%;
        height: 100%;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
    }
    ChatPanel > .chat-header {
        height: 1;
        content-align: center middle;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }
    ChatPanel > RichLog {
        width: 100%;
        height: 1fr;
        border: none;
        background: transparent;
        padding: 0 1;
    }
    ChatPanel > Horizontal.input-area {
        height: auto;
        border-top: solid $primary-darken-2;
        padding: 0 1;
    }
    ChatPanel > Horizontal.input-area > Input {
        width: 1fr;
        height: auto;
        min-height: 3;
        max-height: 10;
        border: solid $primary;
        background: $surface;
    }
    ChatPanel > Horizontal.input-area > Button {
        width: 8;
        height: 3;
        content-align: center middle;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    ChatPanel > Horizontal.input-area > Button:hover {
        background: $primary-lighten-1;
    }
    """
    
    is_streaming = reactive(False)
    
    def __init__(self, on_send: Optional[Callable] = None, **kwargs):
        self.on_send_message = on_send
        self.messages = []
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        """组装组件."""
        yield Static("💬 聊天", classes="chat-header")
        
        chat_log = RichLog(id="chat_log", wrap=True, markup=True, highlight=True)
        chat_log.auto_scroll = True
        yield chat_log
        
        with Horizontal(classes="input-area"):
            yield Input(placeholder="输入消息... (Shift+Enter 换行)", multiline=True, id="chat_input")
            yield Button("发送", id="send_btn", variant="primary")
    
    def on_mount(self):
        """挂载后初始化."""
        self.add_system_message("欢迎使用 Codex! 输入消息开始与 AI 助手对话。")
    
    def add_user_message(self, content: str):
        """添加用户消息."""
        self.messages.append({"role": "user", "content": content})
        self._append_message("👤 你", content, "user")
    
    def add_ai_message(self, content: str):
        """添加 AI 消息."""
        self.messages.append({"role": "assistant", "content": content})
        self._append_message("🤖 AI", content, "assistant")
    
    def add_system_message(self, content: str):
        """添加系统消息."""
        self._append_message("ℹ️ 系统", content, "system")
    
    def _append_message(self, label: str, content: str, msg_type: str):
        """追加消息到聊天日志."""
        log = self.query_one("#chat_log", RichLog)
        
        if msg_type == "user":
            header = f"[bold blue]{label}[/bold blue]"
        elif msg_type == "assistant":
            header = f"[bold green]{label}[/bold green]"
        else:
            header = f"[bold yellow]{label}[/bold yellow]"
        
        # 处理代码块
        formatted_content = self._format_code_blocks(content)
        
        log.write("")
        log.write(f"{header}")
        log.write("─" * 60)
        log.write(formatted_content)
        log.write("")
    
    def _format_code_blocks(self, content: str) -> str:
        """格式化消息中的代码块."""
        # 简单处理，保留原始内容让 RichLog 渲染
        return content
    
    def update_streaming_message(self, chunk: str):
        """更新流式消息."""
        if not self.is_streaming:
            self.is_streaming = True
            self._current_stream_content = ""
            self._stream_line_count = 0
        
        self._current_stream_content += chunk
        
        # 每积累一定内容更新一次显示
        log = self.query_one("#chat_log", RichLog)
        
        # 流式消息使用不同的显示方式
        lines = self._current_stream_content.split("\n")
        if len(lines) > self._stream_line_count + 5:
            self._stream_line_count = len(lines)
    
    def finish_streaming(self):
        """完成流式响应."""
        if self.is_streaming and hasattr(self, '_current_stream_content'):
            self.add_ai_message(self._current_stream_content)
            self.is_streaming = False
            del self._current_stream_content
            del self._stream_line_count
    
    def clear_chat(self):
        """清空聊天记录."""
        self.messages = []
        log = self.query_one("#chat_log", RichLog)
        log.clear()
        self.add_system_message("聊天记录已清空。")
    
    def get_messages(self) -> list:
        """获取所有消息（用于 API 调用）."""
        return self.messages.copy()
    
    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        if event.button.id == "send_btn":
            self._send_message()
    
    def on_input_submitted(self, event: Input.Submitted):
        """输入提交事件."""
        if event.input.id == "chat_input":
            self._send_message()
    
    def _send_message(self):
        """发送消息."""
        input_widget = self.query_one("#chat_input", Input)
        content = input_widget.value.strip()
        
        if not content or self.is_streaming:
            return
        
        input_widget.value = ""
        self.add_user_message(content)
        
        if self.on_send_message:
            self.on_send_message(content)
