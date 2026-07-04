"""终端面板组件 - 内置命令行终端."""

import subprocess
from typing import Callable, Optional

from textual.widgets import Input, Static, RichLog, Button
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.app import ComposeResult
from rich.syntax import Syntax
from rich.text import Text
from rich.panel import Panel

from ..core.tools import ToolExecutor, ToolResult, ToolResultStatus


class TerminalPanel(Vertical):
    """内置终端面板."""
    
    DEFAULT_CSS = """
    TerminalPanel {
        width: 100%;
        height: 100%;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
    }
    TerminalPanel > .terminal-header {
        height: 1;
        content-align: center middle;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }
    TerminalPanel > RichLog {
        width: 100%;
        height: 1fr;
        border: none;
        background: #1a1a2e;
        color: #e0e0e0;
        padding: 0 1;
    }
    TerminalPanel > Horizontal.input-area {
        height: auto;
        border-top: solid $primary-darken-2;
        padding: 0 1;
    }
    TerminalPanel > Horizontal.input-area > Static.prompt {
        width: auto;
        height: 3;
        content-align: center middle;
        color: #00ff88;
        text-style: bold;
    }
    TerminalPanel > Horizontal.input-area > Input {
        width: 1fr;
        height: auto;
        min-height: 3;
        max-height: 10;
        border: solid $primary-darken-2;
        background: #1a1a2e;
        color: #e0e0e0;
    }
    TerminalPanel > Horizontal.input-area > Button {
        width: 8;
        height: 3;
        content-align: center middle;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    """
    
    is_executing = reactive(False)
    
    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = project_path
        self.tool_executor = ToolExecutor(project_path)
        self.command_history = []
        self.history_index = -1
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        """组装组件."""
        yield Static("[终端]", classes="terminal-header")
        
        log = RichLog(id="terminal_log", wrap=True, markup=False, highlight=False)
        log.auto_scroll = True
        yield log
        
        with Horizontal(classes="input-area"):
            yield Static("$", classes="prompt")
            yield Input(
                placeholder="输入命令... (Shift+Enter 换行)",
                multiline=True,
                id="terminal_input"
            )
            yield Button("运行", id="run_btn", variant="primary")
    
    def on_mount(self):
        """挂载后初始化."""
        self._print_welcome()
    
    def _print_welcome(self):
        """打印欢迎信息."""
        log = self.query_one("#terminal_log", RichLog)
        log.write("\n")
        log.write("╔════════════════════════════════════════════════════════╗")
        log.write("║          Hakimi 内置终端 v0.1.0                        ║")
        log.write("╠════════════════════════════════════════════════════════╣")
        log.write("║  可用命令:                                             ║")
        log.write("║    ls/dir    - 列出目录                                ║")
        log.write("║    cat       - 查看文件内容                            ║")
        log.write("║    pwd       - 显示当前路径                            ║")
        log.write("║    git       - Git 命令                                ║")
        log.write("║    python/py - 运行 Python                             ║")
        log.write("║    npm/yarn  - 包管理命令                              ║")
        log.write("║    任何 shell 命令...                                  ║")
        log.write("╚════════════════════════════════════════════════════════╝")
        log.write(f"\n[目录] 工作目录: {self.project_path}")
        log.write("")
    
    def execute_command(self, command: str) -> None:
        """执行命令并显示结果."""
        command = command.strip()
        if not command:
            return
        
        # 添加到历史
        self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        log = self.query_one("#terminal_log", RichLog)
        
        # 显示命令
        log.write(f"\n[bold bright_green]$[/bold bright_green] {command}")
        log.write("─" * 60)
        
        self.is_executing = True
        
        # 处理内置快捷命令
        result = self._handle_builtin_command(command)
        
        if result is None:
            # 使用工具执行器执行
            result = self.tool_executor.execute_command(command)
        
        # 显示结果
        if result.status == ToolResultStatus.SUCCESS:
            if result.output:
                log.write(result.output)
        else:
            log.write(f"[bold red]{result.output}[/bold red]")
        
        log.write(f"[dim]exit code: {result.exit_code}[/dim]")
        log.write("")
        
        self.is_executing = False
        
        # 聚焦输入框
        input_widget = self.query_one("#terminal_input", Input)
        input_widget.focus()
    
    def _handle_builtin_command(self, command: str) -> Optional:
        """处理内置快捷命令."""
        parts = command.split()
        if not parts:
            return None
        
        cmd = parts[0].lower()
        
        # ls / dir
        if cmd in ("ls", "dir"):
            path = parts[1] if len(parts) > 1 else "."
            return self.tool_executor.list_directory(path)
        
        # cat / type
        if cmd in ("cat", "type"):
            if len(parts) > 1:
                return self.tool_executor.read_file(parts[1])
            else:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output="用法: cat <文件路径>",
                    exit_code=1
                )
        
        # pwd / cd
        if cmd == "pwd":
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=str(self.tool_executor.project_path),
                exit_code=0
            )
        
        # clear / cls
        if cmd in ("clear", "cls"):
            log = self.query_one("#terminal_log", RichLog)
            log.clear()
            self._print_welcome()
            return ToolResult(status=ToolResultStatus.SUCCESS, output="", exit_code=0)
        
        # help
        if cmd == "help":
            help_text = """可用命令:
  ls [路径]      - 列出目录
  cat <文件>     - 查看文件
  pwd            - 显示当前路径
  clear          - 清屏
  git <命令>     - Git 操作
  python <脚本>  - 运行 Python
  help           - 显示此帮助
  
也可直接输入任何 shell 命令。"""
            return ToolResult(status=ToolResultStatus.SUCCESS, output=help_text, exit_code=0)
        
        return None
    
    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        if event.button.id == "run_btn":
            self._execute_input()
    
    def on_input_submitted(self, event: Input.Submitted):
        """输入提交事件."""
        if event.input.id == "terminal_input":
            self._execute_input()
    
    def _execute_input(self):
        """执行输入框中的命令."""
        input_widget = self.query_one("#terminal_input", Input)
        command = input_widget.value.strip()
        
        if not command or self.is_executing:
            return
        
        input_widget.value = ""
        self.execute_command(command)
    
    def on_key(self, event):
        """键盘事件处理（历史记录）."""
        if event.key == "up":
            if self.history_index > 0:
                self.history_index -= 1
                input_widget = self.query_one("#terminal_input", Input)
                input_widget.value = self.command_history[self.history_index]
            event.stop()
        elif event.key == "down":
            if self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                input_widget = self.query_one("#terminal_input", Input)
                input_widget.value = self.command_history[self.history_index]
            elif self.history_index == len(self.command_history) - 1:
                self.history_index = len(self.command_history)
                input_widget = self.query_one("#terminal_input", Input)
                input_widget.value = ""
            event.stop()
