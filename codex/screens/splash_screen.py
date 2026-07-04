"""启动画面."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Button, Static


class SplashScreen(Screen):
    """应用启动画面."""
    
    CSS = """
    SplashScreen {
        align: center middle;
        background: $surface-darken-2;
    }
    SplashScreen > Container {
        width: 60;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 2;
    }
    SplashScreen Container > Static.logo {
        text-align: center;
        text-style: bold;
        color: $primary-lighten-2;
        height: 3;
    }
    SplashScreen Container > Static.subtitle {
        text-align: center;
        color: $text-muted;
        height: 1;
        margin-bottom: 1;
    }
    SplashScreen Container > Button {
        margin: 1 0;
        width: 100%;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static("""
 ██╗  ██╗ █████╗ ██╗  ██╗██╗███╗   ███╗██╗
 ██║  ██║██╔══██╗██║ ██╔╝██║████╗ ████║██║
 ███████║███████║█████╔╝ ██║██╔████╔██║██║
 ██╔══██║██╔══██║██╔═██╗ ██║██║╚██╔╝██║██║
 ██║  ██║██║  ██║██║  ██╗██║██║ ╚═╝ ██║██║
 ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝
            """, classes="logo")
            yield Static("🚀 现代化 AI 代码助手", classes="subtitle")
            yield Button("📂 打开项目", id="open_project", variant="primary")
            yield Button("⚙️ 模型设置", id="settings", variant="default")
            yield Button("❓ 帮助", id="help", variant="default")
    
    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        if event.button.id == "open_project":
            self.dismiss("open_project")
        elif event.button.id == "settings":
            self.dismiss("settings")
        elif event.button.id == "help":
            self.dismiss("help")
