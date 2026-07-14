"""Legacy widgets - 当前主界面未使用，保留备用."""

from .chat_panel import ChatPanel
from .code_view import CodeViewerWidget
from .diff_panel import DiffPanel
from .file_tree import FileTreeWidget
from .model_selector import ModelSelectorWidget
from .terminal_panel import TerminalPanel

__all__ = [
    "ChatPanel",
    "CodeViewerWidget",
    "DiffPanel",
    "FileTreeWidget",
    "ModelSelectorWidget",
    "TerminalPanel",
]
