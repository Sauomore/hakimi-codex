"""代码查看器组件."""

from pathlib import Path
from typing import Optional

from textual.widgets import Static
from textual.containers import Vertical
from textual.reactive import reactive
from rich.syntax import Syntax
from rich.text import Text
from rich.panel import Panel


class CodeViewerWidget(Vertical):
    """代码查看与编辑组件."""
    
    DEFAULT_CSS = """
    CodeViewerWidget {
        width: 100%;
        height: 100%;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
    }
    CodeViewerWidget > .code-header {
        height: 1;
        content-align: center middle;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }
    CodeViewerWidget > Static.code-content {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
        padding: 0 1;
    }
    CodeViewerWidget > Static.code-content > RichText {
        width: 100%;
    }
    """
    
    current_file = reactive[Optional[str]](None)
    file_content = reactive[str]("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def compose(self):
        """组装组件."""
        yield Static("📄 代码查看", classes="code-header")
        yield Static("选择文件以查看内容...", classes="code-content", id="code_display")
    
    def watch_current_file(self, file_path: Optional[str]):
        """监听文件变化."""
        if file_path:
            self._load_file(file_path)
    
    def _load_file(self, file_path: str):
        """加载文件内容."""
        path = Path(file_path)
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.file_content = content
            self._render_content(path, content)
        except UnicodeDecodeError:
            display = self.query_one("#code_display", Static)
            display.update("[yellow]无法显示二进制文件[/yellow]")
        except Exception as e:
            display = self.query_one("#code_display", Static)
            display.update(f"[red]读取文件失败: {e}[/red]")
    
    def _render_content(self, path: Path, content: str):
        """渲染文件内容."""
        display = self.query_one("#code_display", Static)
        
        # 获取语言标识
        language = self._detect_language(path)
        
        # 更新标题
        header = self.query_one(".code-header", Static)
        header.update(f"📄 {path.name}")
        
        if language:
            try:
                syntax = Syntax(
                    content,
                    language,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=False,
                    indent_guides=True
                )
                display.update(syntax)
            except Exception:
                display.update(content)
        else:
            display.update(content)
    
    def _detect_language(self, path: Path) -> Optional[str]:
        """检测文件语言."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".md": "markdown",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".kt": "kotlin",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".dart": "dart",
            ".sh": "bash",
            ".zsh": "bash",
            ".bash": "bash",
            ".sql": "sql",
            ".dockerfile": "dockerfile",
            ".vue": "vue",
            ".svelte": "svelte",
            ".lua": "lua",
            ".r": "r",
            ".m": "matlab",
            ".scala": "scala",
            ".clj": "clojure",
            ".erl": "erlang",
            ".ex": "elixir",
            ".fs": "fsharp",
            ".hs": "haskell",
            ".jl": "julia",
            ".pas": "pascal",
            ".pl": "perl",
            ".rkt": "racket",
            ".tcl": "tcl",
            ".v": "verilog",
            ".sv": "verilog",
            ".vhd": "vhdl",
            ".asm": "asm",
            ".nim": "nim",
            ".zig": "zig",
            ".elm": "elm",
            ".purescript": "purescript",
            ".coffee": "coffeescript",
            ".ls": "livescript",
            ".tsv": "tsv",
            ".csv": "csv",
            ".ini": "ini",
            ".cfg": "ini",
            ".properties": "properties",
        }
        
        suffix = path.suffix.lower()
        
        # 特殊处理 Dockerfile
        if path.name.lower().startswith("dockerfile"):
            return "dockerfile"
        
        # 特殊处理 Makefile
        if path.name.lower() in ("makefile", "gnumakefile"):
            return "makefile"
        
        return ext_map.get(suffix, None)
    
    def get_content(self) -> str:
        """获取当前内容."""
        return self.file_content
    
    def set_content(self, content: str):
        """设置内容（用于 AI 修改后）."""
        self.file_content = content
        if self.current_file:
            self._render_content(Path(self.current_file), content)
