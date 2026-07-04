"""启动画面 - 简洁风格."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Button, Static


class SplashScreen(Screen):
    """应用启动画面."""
    
    CSS = """
    SplashScreen {
        align: center middle;
        background: #111827;
    }
    SplashScreen > Container {
        width: 60;
        height: auto;
        border: solid #374151;
        background: #1f2937;
        padding: 2;
    }
    SplashScreen Container > Static.logo {
        text-align: center;
        text-style: bold;
        color: #3b82f6;
        height: 3;
    }
    SplashScreen Container > Static.subtitle {
        text-align: center;
        color: #6b7280;
        height: 1;
        margin-bottom: 1;
    }
    SplashScreen Container > Button {
        margin: 1 0;
        width: 100%;
        background: #374151;
        color: #e5e7eb;
        border: solid #4b5563;
    }
    SplashScreen Container > Button:hover {
        background: #4b5563;
    }
    SplashScreen Container > Button:focus {
        background: #3b82f6;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static("""
HAKIMI CODEX

AI Coding Assistant
            """, classes="logo")
            yield Static("v0.1.0", classes="subtitle")
            yield Button("Open Project", id="open_project", variant="primary")
            yield Button("Settings", id="settings", variant="default")
            yield Button("Help", id="help", variant="default")
    
    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        if event.button.id == "open_project":
            self.dismiss("open_project")
        elif event.button.id == "settings":
            self.dismiss("settings")
        elif event.button.id == "help":
            self.dismiss("help")
