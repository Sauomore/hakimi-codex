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
        ("q", "quit", "退出"),
        ("r", "refresh", "刷新"),
        ("m", "models", "模型管理"),
        ("c", "chat", "聊天"),
        ("f", "files", "文件"),
        ("ctrl+t", "terminal", "终端"),
        ("ctrl+s", "save", "保存"),
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
            self._show_settings()
        elif result == "help":
            self._show_help()
        else:
            self._open_project()
    
    def _open_project(self):
        """打开项目主界面."""
        self.push_screen(MainScreen(project_path=str(self.project_path)))
    
    def _show_settings(self):
        """显示设置."""
        self.push_screen(MainScreen(project_path=str(self.project_path)))
    
    def _show_help(self):
        """显示帮助."""
        help_text = """
# Hakimi 快捷键

| 快捷键 | 功能 |
|--------|------|
| `q` | 退出应用 |
| `r` | 刷新文件树和Git状态 |
| `m` | 打开模型管理 |
| `c` | 聚焦聊天输入 |
| `f` | 聚焦文件树 |
| `Ctrl+S` | 保存当前文件 |

## 使用说明

1. **选择模型**: 在右上角模型面板中配置并选择你的 AI 模型
2. **浏览文件**: 在左侧文件树中点击文件查看代码
3. **开始对话**: 在下方聊天面板输入消息与 AI 交流
4. **代码编辑**: AI 可以建议修改，你可以审阅并应用

## 支持的模型提供商

- OpenAI (GPT-4, GPT-4o, GPT-4o-mini)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Haiku)
- DeepSeek
- Google (Gemini)
- Mistral
- Ollama (本地模型)
- OpenRouter
- 自定义 API

## 配置

配置文件位于: `~/.config/codex/config.toml`
"""
        self.notify(help_text, title="帮助", timeout=10)
    
    def action_refresh(self):
        """刷新操作."""
        main_screen = self.screen
        if isinstance(main_screen, MainScreen):
            main_screen.action_refresh()
    
    def action_models(self):
        """打开模型管理."""
        pass
    
    def action_chat(self):
        """聚焦聊天."""
        main_screen = self.screen
        if isinstance(main_screen, MainScreen):
            chat = main_screen.query_one("#chat_panel")
            chat.focus()
    
    def action_terminal(self):
        """切换终端."""
        main_screen = self.screen
        if isinstance(main_screen, MainScreen):
            main_screen.action_toggle_terminal()
    
    def action_files(self):
        """聚焦文件树."""
        main_screen = self.screen
        if isinstance(main_screen, MainScreen):
            tree = main_screen.query_one("#file_tree_panel")
            tree.focus()
