"""Hakimi 主应用."""

import asyncio
import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from .core.config import load_config
from .screens.splash_screen import SplashScreen
from .screens.main_screen import MainScreen


class HakimiApp(App):
    """Hakimi 主应用类."""
    
    CSS_PATH = "styles/codex.tcss"
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("d", "toggle_diff", "Toggle Diff"),
        ("c", "chat", "Chat"),
        ("ctrl+s", "save", "Save"),
    ]
    
    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = Path(project_path).resolve()
        super().__init__(**kwargs)
    
    def on_mount(self):
        """应用挂载后显示启动画面."""
        self.push_screen(SplashScreen(), self._on_splash_dismissed)
    
    def _on_splash_dismissed(self, result: str):
        """启动画面关闭回调."""
        if result == "open_project":
            self._open_project()
        elif result == "settings":
            self._open_project()
        elif result == "help":
            self._open_project()
        else:
            self._open_project()
    
    def _open_project(self):
        """打开项目主界面."""
        self.push_screen(MainScreen(project_path=str(self.project_path)))
    
    def action_refresh(self):
        """刷新操作."""
        main_screen = self.screen
        if isinstance(main_screen, MainScreen):
            main_screen.action_refresh()
    
    def action_toggle_diff(self):
        """切换 diff 面板."""
        main_screen = self.screen
        if isinstance(main_screen, MainScreen):
            main_screen.action_toggle_diff()
    
    def action_chat(self):
        """聚焦聊天."""
        main_screen = self.screen
        if isinstance(main_screen, MainScreen):
            chat = main_screen.query_one("#chat_panel")
            chat.focus()
