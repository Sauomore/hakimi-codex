"""Diff 面板 - 显示代码修改的红绿对比."""

from typing import Optional, List, Tuple
from textual.widgets import Static
from textual.containers import Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.app import ComposeResult
from rich.text import Text
from rich.panel import Panel
from rich.syntax import Syntax
import difflib


class DiffLine(Static):
    """单行 Diff 显示."""
    
    DEFAULT_CSS = """
    DiffLine {
        height: auto;
        padding: 0 1;
        text-style: none;
    }
    DiffLine.added {
        background: #1a3a1a;
        color: #4ade80;
    }
    DiffLine.removed {
        background: #3a1a1a;
        color: #f87171;
    }
    DiffLine.context {
        color: #9ca3af;
    }
    DiffLine .line-number {
        color: #6b7280;
        width: 4;
        text-align: right;
        padding-right: 1;
    }
    """
    
    def __init__(self, line: str, line_type: str, old_lineno: Optional[int] = None, new_lineno: Optional[int] = None, **kwargs):
        self.line_text = line
        self.line_type = line_type  # "added", "removed", "context", "header"
        self.old_lineno = old_lineno
        self.new_lineno = new_lineno
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        if self.line_type == "header":
            yield Static(f"[bold]{self.line_text}[/bold]")
        elif self.line_type == "added":
            lineno = f"{self.new_lineno or '':>4}" if self.new_lineno else "    "
            yield Static(f"[green]+ {lineno} {self.line_text}[/green]")
        elif self.line_type == "removed":
            lineno = f"{self.old_lineno or '':>4}" if self.old_lineno else "    "
            yield Static(f"[red]- {lineno} {self.line_text}[/red]")
        else:
            lineno = f"{self.old_lineno or '':>4}" if self.old_lineno else "    "
            yield Static(f"  {lineno} {self.line_text}")


class DiffPanel(Vertical):
    """Diff 显示面板 - 红绿对比."""
    
    DEFAULT_CSS = """
    DiffPanel {
        width: 100%;
        height: 100%;
        background: $surface;
        border: solid $panel-border-color;
    }
    DiffPanel > .diff-header {
        height: 1;
        content-align: center middle;
        background: $surface-darken-1;
        color: $text;
        text-style: bold;
        border-bottom: solid $panel-border-color;
    }
    DiffPanel > ScrollableContainer {
        height: 1fr;
        background: $surface;
        border: none;
    }
    """
    
    current_file = reactive[Optional[str]](None)
    original_content = reactive[str]("")
    modified_content = reactive[str]("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        yield Static("Diff View", classes="diff-header")
        yield ScrollableContainer(id="diff_container")
    
    def show_file(self, file_path: str, content: str):
        """显示文件内容（无 diff）."""
        self.current_file = file_path
        self.original_content = content
        self.modified_content = ""
        self._render_content(file_path, content)
    
    def show_diff(self, file_path: str, original: str, modified: str):
        """显示 diff 对比."""
        self.current_file = file_path
        self.original_content = original
        self.modified_content = modified
        self._render_diff(file_path, original, modified)
    
    def _render_content(self, file_path: str, content: str):
        """渲染文件内容."""
        container = self.query_one("#diff_container", ScrollableContainer)
        # 清除旧内容
        for child in list(container.children):
            child.remove()
        
        header = self.query_one(".diff-header", Static)
        header.update(f"{file_path}")
        
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            diff_line = DiffLine(line, "context", old_lineno=i)
            container.mount(diff_line)
    
    def _render_diff(self, file_path: str, original: str, modified: str):
        """渲染 diff 对比."""
        container = self.query_one("#diff_container", ScrollableContainer)
        # 清除旧内容
        for child in list(container.children):
            child.remove()
        
        header = self.query_one(".diff-header", Static)
        header.update(f"{file_path} (modified)")
        
        # 使用 unified diff
        original_lines = original.splitlines(keepends=False)
        modified_lines = modified.splitlines(keepends=False)
        
        diff = difflib.unified_diff(
            original_lines, modified_lines,
            fromfile="a/" + file_path,
            tofile="b/" + file_path,
            lineterm=""
        )
        
        diff_lines = list(diff)
        
        if not diff_lines:
            # 无差异
            diff_line = DiffLine("No changes", "context")
            container.mount(diff_line)
            return
        
        # 解析 diff 输出
        old_lineno = 0
        new_lineno = 0
        
        for line in diff_lines:
            if line.startswith("---") or line.startswith("+++"):
                diff_line = DiffLine(line, "header")
                container.mount(diff_line)
            elif line.startswith("@@"):
                # 解析行号信息
                match = difflib.re.search(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if match:
                    old_start = int(match.group(1))
                    new_start = int(match.group(3))
                    old_lineno = old_start
                    new_lineno = new_start
                
                diff_line = DiffLine(line, "header")
                container.mount(diff_line)
            elif line.startswith("+"):
                diff_line = DiffLine(line[1:], "added", new_lineno=new_lineno)
                container.mount(diff_line)
                if new_lineno:
                    new_lineno += 1
            elif line.startswith("-"):
                diff_line = DiffLine(line[1:], "removed", old_lineno=old_lineno)
                container.mount(diff_line)
                if old_lineno:
                    old_lineno += 1
            elif line.startswith(" "):
                diff_line = DiffLine(line[1:], "context", old_lineno=old_lineno, new_lineno=new_lineno)
                container.mount(diff_line)
                if old_lineno:
                    old_lineno += 1
                if new_lineno:
                    new_lineno += 1
            else:
                diff_line = DiffLine(line, "context")
                container.mount(diff_line)
        
        self.scroll_to_top()
    
    def clear(self):
        """清空 diff."""
        container = self.query_one("#diff_container", ScrollableContainer)
        for child in list(container.children):
            child.remove()
        
        header = self.query_one(".diff-header", Static)
        header.update("Diff View")
        
        self.current_file = None
        self.original_content = ""
        self.modified_content = ""
    
    def scroll_to_top(self):
        """滚动到顶部."""
        container = self.query_one("#diff_container", ScrollableContainer)
        container.scroll_home(animate=False)
    
    def scroll_to_bottom(self):
        """滚动到底部."""
        container = self.query_one("#diff_container", ScrollableContainer)
        container.scroll_end(animate=False)
