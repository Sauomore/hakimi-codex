import re
from typing import Optional, Callable, List
from textual.widgets import Input, Static, Collapsible
from textual.containers import Vertical, ScrollableContainer, Horizontal
from textual.reactive import reactive
from textual.app import ComposeResult
from rich.syntax import Syntax
from rich.text import Text
from rich.panel import Panel

from ..core.settings_manager import Settings, load_settings
from ..core.command_handler import CommandHandler, CommandResult


class UserMessage(Static):
    
    DEFAULT_CSS = """
    UserMessage {
        height: auto;
        margin: 1 0;
        padding: 0 1;
        color: $text;
    }
    """
    
    def __init__(self, content: str, settings: Settings, **kwargs):
        self.content = content
        self.settings = settings
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        yield Static(f"[bold]> {self.content}[/bold]")


class AIMessage(Vertical):
    
    DEFAULT_CSS = """
    AIMessage {
        height: auto;
        margin: 1 0;
        padding: 0 1;
    }
    AIMessage .thinking-collapsible {
        background: $surface-darken-2;
        color: $text-muted;
        padding: 0 1;
    }
    AIMessage .thinking-collapsible:focus {
        background: $surface-darken-1;
    }
    AIMessage .thinking-content {
        color: $text-muted;
        padding: 0 1;
    }
    AIMessage .output-content {
        color: $text;
        padding: 0 1;
        margin-top: 1;
    }
    """
    
    def __init__(self, content: str, thinking: Optional[str], settings: Settings, **kwargs):
        self.content = content
        self.thinking = thinking
        self.settings = settings
        self.is_thinking_expanded = False
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        if self.thinking and self.settings.ai.think_mode:
            if self.settings.ai.think_fold:
                with Collapsible(title="thinking...", collapsed=True, classes="thinking-collapsible"):
                    yield Static(self.thinking, classes="thinking-content")
            else:
                yield Static(f"thinking:\n{self.thinking}", classes="thinking-content")
        
        if self.content.strip():
            yield Static(self.content, classes="output-content")


class ToolResultMessage(Static):
    
    DEFAULT_CSS = """
    ToolResultMessage {
        height: auto;
        margin: 1 0;
        padding: 0 1;
        color: $text-muted;
        background: $surface-darken-2;
    }
    """
    
    def __init__(self, tool_name: str, result: str, **kwargs):
        self.tool_name = tool_name
        self.result = result
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        yield Static(f"[{self.tool_name}]\n{self.result}")


class SystemMessage(Static):
    
    DEFAULT_CSS = """
    SystemMessage {
        height: auto;
        margin: 1 0;
        padding: 0 1;
        color: $text-muted;
        text-style: dim;
    }
    """
    
    def __init__(self, content: str, **kwargs):
        self.content = content
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        yield Static(f"[dim]{self.content}[/dim]")


class ChatPanel(Vertical):
    
    DEFAULT_CSS = """
    ChatPanel {
        width: 100%;
        height: 100%;
        background: $surface;
    }
    ChatPanel > ScrollableContainer {
        height: 1fr;
        background: $surface;
        border: none;
    }
    ChatPanel > Input {
        height: auto;
        min-height: 1;
        border-top: solid $panel-border-color;
        background: $surface;
        padding: 0 1;
    }
    ChatPanel > Input:focus {
        border: solid $primary;
    }
    """
    
    is_streaming = reactive(False)
    
    def __init__(self, on_send: Optional[Callable] = None, on_command: Optional[Callable] = None, **kwargs):
        self.on_send_message = on_send
        self.on_command = on_command
        self.settings = load_settings()
        self.command_handler = CommandHandler()
        self.messages: List[dict] = []
        self.current_streaming_container: Optional[AIMessage] = None
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        yield ScrollableContainer(id="messages_container")
        yield Input(placeholder="Enter message or /command...", id="chat_input")
    
    def on_mount(self):
        self.add_system_message("Hakimi Codex v0.1.0")
        self.add_system_message("Type /help for available commands")
    
    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        container = self.query_one("#messages_container", ScrollableContainer)
        msg = UserMessage(content, self.settings)
        container.mount(msg)
        self.scroll_to_bottom()
    
    def add_ai_message(self, content: str, thinking: Optional[str] = None):
        self.messages.append({"role": "assistant", "content": content, "thinking": thinking})
        container = self.query_one("#messages_container", ScrollableContainer)
        msg = AIMessage(content, thinking, self.settings)
        container.mount(msg)
        self.scroll_to_bottom()
    
    def add_system_message(self, content: str):
        container = self.query_one("#messages_container", ScrollableContainer)
        msg = SystemMessage(content)
        container.mount(msg)
        self.scroll_to_bottom()
    
    def add_tool_result(self, tool_name: str, result: str):
        if not self.settings.ai.show_tool_results:
            return
        container = self.query_one("#messages_container", ScrollableContainer)
        msg = ToolResultMessage(tool_name, result)
        container.mount(msg)
        self.scroll_to_bottom()
    
    def start_streaming(self) -> None:
        self.is_streaming = True
        self._stream_content = ""
        self._stream_thinking = ""
        self._in_thinking = False
        self._streaming_widget = None
    
    def append_stream(self, chunk: str) -> None:
        self._stream_content += chunk

        while True:
            if not self._in_thinking:
                idx = self._stream_content.find("<thinking>")
                if idx == -1:
                    break
                end_idx = self._stream_content.find("</thinking>", idx + len("<thinking>"))
                if end_idx == -1:
                    self._in_thinking = True
                    break
                else:
                    think_text = self._stream_content[idx + len("<thinking>"):end_idx]
                    self._stream_thinking += think_text
                    self._stream_content = (
                        self._stream_content[:idx] +
                        self._stream_content[end_idx + len("</thinking>"):]
                    )
            else:
                idx = self._stream_content.find("</thinking>")
                if idx == -1:
                    break
                think_text = self._stream_content[:idx]
                self._stream_thinking += think_text
                self._stream_content = self._stream_content[idx + len("</thinking>"):]
                self._in_thinking = False

        if self._streaming_widget is not None:
            self._streaming_widget.remove()

        container = self.query_one("#messages_container", ScrollableContainer)
        self._streaming_widget = AIMessage(
            self._stream_content,
            self._stream_thinking if self._stream_thinking else None,
            self.settings
        )
        container.mount(self._streaming_widget)
        self.scroll_to_bottom()
    
    def finish_streaming(self) -> None:
        self.is_streaming = False

        while True:
            if not self._in_thinking:
                idx = self._stream_content.find("<thinking>")
                if idx == -1:
                    break
                end_idx = self._stream_content.find("</thinking>", idx + len("<thinking>"))
                if end_idx == -1:
                    think_text = self._stream_content[idx + len("<thinking>"):]
                    self._stream_thinking += think_text
                    self._stream_content = self._stream_content[:idx]
                    break
                else:
                    think_text = self._stream_content[idx + len("<thinking>"):end_idx]
                    self._stream_thinking += think_text
                    self._stream_content = (
                        self._stream_content[:idx] +
                        self._stream_content[end_idx + len("</thinking>"):]
                    )
            else:
                idx = self._stream_content.find("</thinking>")
                if idx == -1:
                    self._stream_thinking += self._stream_content
                    self._stream_content = ""
                    break
                think_text = self._stream_content[:idx]
                self._stream_thinking += think_text
                self._stream_content = self._stream_content[idx + len("</thinking>"):]
                self._in_thinking = False

        self._stream_content = self._stream_content.strip()

        if self._streaming_widget is not None:
            self._streaming_widget.remove()
            self._streaming_widget = None

        self.add_ai_message(
            self._stream_content,
            self._stream_thinking if self._stream_thinking else None
        )
        self._stream_content = ""
        self._stream_thinking = ""
        self._in_thinking = False
    
    def clear_chat(self):
        self.messages = []
        container = self.query_one("#messages_container", ScrollableContainer)
        for child in list(container.children):
            child.remove()
        self.add_system_message("Chat cleared.")
    
    def get_messages(self) -> List[dict]:
        return [msg for msg in self.messages if msg["role"] in ("user", "assistant")]
    
    def scroll_to_bottom(self):
        container = self.query_one("#messages_container", ScrollableContainer)
        container.scroll_end(animate=False)
    
    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "chat_input":
            self._process_input()
    
    def _process_input(self):
        input_widget = self.query_one("#chat_input", Input)
        content = input_widget.value.strip()
        
        if not content or self.is_streaming:
            return
        
        input_widget.value = ""
        
        # 检查是否是命令
        is_cmd, cmd, args = self.command_handler.parse(content)
        
        if is_cmd:
            # 执行命令
            result = self.command_handler.handle(content)
            
            if result.message:
                if result.success:
                    self.add_system_message(result.message)
                else:
                    self.add_system_message(f"Error: {result.message}")
            
            # 触发命令回调
            if result.action and self.on_command:
                self.on_command(result.action, result.data)
        else:
            # 普通消息
            self.add_user_message(content)
            if self.on_send_message:
                self.on_send_message(content)
    
    def update_settings(self, settings: Settings):
        self.settings = settings
