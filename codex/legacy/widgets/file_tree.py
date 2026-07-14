"""文件树组件."""

import os
from pathlib import Path
from typing import Callable, Optional

from textual.widgets import Tree, Static
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from textual.containers import Vertical


class FileTreeWidget(Vertical):
    """可交互的文件树组件."""
    
    DEFAULT_CSS = """
    FileTreeWidget {
        width: 100%;
        height: 100%;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
    }
    FileTreeWidget > Static.title {
        height: 1;
        content-align: center middle;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }
    FileTreeWidget > Tree {
        width: 100%;
        height: 1fr;
        border: none;
        background: transparent;
        padding: 0 1;
    }
    FileTreeWidget > Tree:focus {
        background: $primary-darken-3;
    }
    """
    
    selected_file = reactive[Optional[str]](None)
    
    def __init__(self, root_path: str = ".", on_select: Optional[Callable] = None, **kwargs):
        self.root_path = Path(root_path).resolve()
        self.on_file_select = on_select
        self.ignored_patterns = [
            "*.pyc", "__pycache__", ".git", "node_modules",
            ".env", "*.log", "dist", "build", ".idea", ".vscode",
            "*.egg-info", ".pytest_cache", ".mypy_cache", ".coverage"
        ]
        super().__init__(**kwargs)
    
    def compose(self):
        """组装组件."""
        yield Static(f"[目录] {self.root_path.name}", classes="title")
        tree = Tree(f"{self.root_path.name}", id="file_tree")
        tree.show_root = False
        tree.guide_depth = 2
        yield tree
    
    def on_mount(self):
        """挂载后加载文件树."""
        tree = self.query_one(Tree)
        self._build_tree(tree.root, self.root_path)
    
    def _should_ignore(self, path: Path) -> bool:
        """检查是否应该忽略该路径."""
        name = path.name
        for pattern in self.ignored_patterns:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False
    
    def _build_tree(self, node: TreeNode, path: Path):
        """递归构建文件树."""
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except (PermissionError, OSError):
            return
        
        for entry in entries:
            if self._should_ignore(entry):
                continue
            
            if entry.is_dir():
                icon = "[目录]"
                label = f"{icon} {entry.name}"
                child_node = node.add(label, data=str(entry))
                child_node.allow_expand = True
            else:
                icon = self._get_file_icon(entry)
                label = f"{icon} {entry.name}"
                child_node = node.add(label, data=str(entry))
                child_node.allow_expand = False
    
    def _get_file_icon(self, path: Path) -> str:
        """根据文件类型返回图标."""
        suffix = path.suffix.lower()
        icons = {
            ".py": "[py]",
            ".js": "[js]",
            ".ts": "[ts]",
            ".jsx": "[jsx]",
            ".tsx": "[jsx]",
            ".html": "[html]",
            ".css": "[css]",
            ".scss": "[css]",
            ".json": "[json]",
            ".yaml": "[cfg]",
            ".yml": "[cfg]",
            ".toml": "[cfg]",
            ".md": "[md]",
            ".rst": "[md]",
            ".txt": "[file]",
            ".rs": "[rs]",
            ".go": "[O]",
            ".java": "[java]",
            ".kt": "[kt]",
            ".cpp": "[cfg]",
            ".c": "[cfg]",
            ".h": "[cfg]",
            ".hpp": "[cfg]",
            ".rb": "[rb]",
            ".php": "[php]",
            ".swift": "[swift]",
            ".dart": "[dart]",
            ".sh": "[sh]",
            ".dockerfile": "[docker]",
            ".sql": "[sql]",
        }
        return icons.get(suffix, "[file]")
    
    def on_tree_node_selected(self, event: Tree.NodeSelected):
        """节点选择事件."""
        node = event.node
        if node.data and not Path(node.data).is_dir():
            self.selected_file = node.data
            if self.on_file_select:
                self.on_file_select(node.data)
    
    def on_tree_node_expanded(self, event: Tree.NodeExpanded):
        """节点展开事件."""
        node = event.node
        if node.data and Path(node.data).is_dir():
            # 清除现有子节点并重新加载
            node.remove_children()
            self._build_tree(node, Path(node.data))
    
    def refresh_tree(self):
        """刷新文件树."""
        tree = self.query_one(Tree)
        tree.root.remove_children()
        self._build_tree(tree.root, self.root_path)
