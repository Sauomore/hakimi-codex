"""Hakimi 主应用 - 直接启动主界面."""

import asyncio
import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from .screens.main_screen import MainScreen


class HakimiApp(App):
    """Hakimi 主应用类."""
    
    CSS_PATH = "styles/codex.tcss"
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]
    
    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = Path(project_path).resolve()
        super().__init__(**kwargs)
    
    def on_mount(self):
        """直接打开主界面，跳过启动画面."""
        self.push_screen(MainScreen(project_path=str(self.project_path)))
    
    def action_quit(self):
        """退出应用."""
        self.exit()
