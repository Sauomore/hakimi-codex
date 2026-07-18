"""主工作界面 - Claude Code 风格布局."""

import asyncio
import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, RichLog, TextArea, Tree
from textual.reactive import reactive

from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table

from codex import __version__, __author__
from codex.core.models import AppConfig, ModelConfig, ProviderType
from codex.core.config import (
    load_config,
    save_config,
    get_active_model,
    add_model,
    remove_model,
    set_active_model,
)
from codex.core.llm_client import LLMClient
from codex.core import git_utils
from codex.core.prompts import build_system_prompt
from codex.core.tools import ToolExecutor, ToolResultStatus
from codex.core.command_handler import CommandHandler, CommandResult
from codex.core.chat_engine import ChatEngine, ChatCallbacks
from codex.core.agents import Orchestrator
from codex.core.diff_utils import generate_unified_diff
from codex.utils.markdown import parse_content
from codex.utils.logger import setup_logger, debug as log_debug
from codex.utils.clipboard import copy_to_clipboard, export_to_file
from codex.core.code_block_applier import CodeBlock, extract_code_blocks, detect_target_file_path
from .confirmation_dialog import ConfirmationDialog
from .copy_view_dialog import CopyViewDialog
from .plan_review_dialog import PlanReviewDialog
from .search_dialog import SearchDialog, SearchResult
from .code_block_dialog import CodeBlockDialog


class ChatInput(TextArea):
    """自定义多行输入框，处理快捷键."""

    def on_key(self, event):
        # 显式处理普通 Enter：插入换行并阻止事件继续冒泡，
        # 避免某些终端/焦点状态下误触发按钮或退出
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return

        # 让 Ctrl+C 弹出退出确认框，避免被 TextArea 默认 copy 占用
        if event.key == "ctrl+c":
            event.prevent_default()
            event.stop()
            self.screen.action_confirm_quit()
            return

        # Ctrl+F 打开聊天记录搜索
        if event.key == "ctrl+f":
            event.prevent_default()
            event.stop()
            self.screen.action_show_search()
            return

        if event.key == "up":
            row, _ = self.cursor_location
            if row == 0 and self.screen.input_history:
                event.prevent_default()
                event.stop()
                self.screen._history_up()
                return

        if event.key == "down":
            row, _ = self.cursor_location
            lines = self.text.split("\n")
            if row == len(lines) - 1 and self.screen.input_history:
                event.prevent_default()
                event.stop()
                self.screen._history_down()
                return

        # 其他按键（Backspace、Tab、普通字符等）直接返回，
        # 不阻止事件，让 Textual/TextArea 的默认绑定/行为处理。
        # 注意：TextArea 本身没有 on_key 方法，不能调用 super().on_key()。


class MainScreen(Screen):
    """Hakimi 主界面."""

    config = reactive[AppConfig](AppConfig())
    is_processing = reactive(False)

    BINDINGS = [
        ("f5", "copy_last_message", "Copy last message"),
        ("f6", "show_copy_view", "Show copy view"),
        ("f7", "show_code_blocks", "Code blocks"),
        ("ctrl+f", "show_search", "Search"),
        ("ctrl+r", "retry_last_response", "Retry last"),
        ("ctrl+c", "confirm_quit", "Quit"),
    ]

    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = Path(project_path).resolve()
        self.command_handler = CommandHandler()
        self.input_history: list[str] = []
        self.input_history_index = -1
        self._streaming_buffer = ""
        self._streaming_active = False
        self._code_blocks: List[CodeBlock] = []
        self._last_ai_content: str = ""
        super().__init__(**kwargs)
        self.chat_engine = ChatEngine(str(self.project_path), self.config)

    def compose(self) -> ComposeResult:
        with Horizontal(id="main_layout"):
            with Vertical(id="left_sidebar"):
                yield Static("Project", classes="sidebar_title", id="sidebar_title_project")
                yield Static(id="project_info")
                yield Tree(self.project_path.name, id="file_tree")
                yield Static("Model", classes="sidebar_title", id="sidebar_title_model")
                yield Static(id="model_info")
                yield Static("Agent Cluster", classes="sidebar_title", id="sidebar_title_agent")
                yield Static(id="agent_info")
                yield Static("Runtime", classes="sidebar_title", id="sidebar_title_runtime")
                yield Static(id="runtime_info")
                yield Static("Shortcuts", classes="sidebar_title", id="sidebar_title_shortcuts")
                yield Static(id="shortcuts_info")
            with Vertical(id="center_panel"):
                yield RichLog(
                    id="messages_log",
                    wrap=True,
                    markup=True,
                    highlight=False,
                    auto_scroll=True,
                )
                yield Static("", id="streaming_output")
        with Vertical(id="bottom_panel"):
            yield Static("Tool Result", id="bottom_panel_title")
            yield RichLog(id="tool_result_log", wrap=True, markup=True, highlight=False, auto_scroll=True)
        with Vertical(id="input_container"):
            with Horizontal(id="input_row"):
                yield ChatInput(id="chat_input")
                yield Button("Send", id="send_button")
            yield Static(
                "Enter newline · F5 copy · F6 view · F7 blocks · Ctrl+F search · Ctrl+C exit · /help",
                id="input_hint",
            )

    def on_mount(self):
        self.config = load_config()
        self.chat_engine.config = self.config
        setup_logger(self.project_path, self.config.ai.debug_mode)
        self._update_sidebar()
        self._populate_file_tree()
        self._update_runtime_status({"agent": "-", "model": "-", "state": "idle"})

        streaming_output = self.query_one("#streaming_output", Static)
        streaming_output.display = False

        hakimi_lines = [
            "██╗  ██╗ █████╗ ██╗  ██╗██╗███╗   ███╗██╗",
            "██║  ██║██╔══██╗██║ ██╔╝██║████╗ ████║██║",
            "███████║███████║█████╔╝ ██║██╔████╔██║██║",
            "██╔══██║██╔══██║██╔═██╗ ██║██║╚██╔╝██║██║",
            "██║  ██║██║  ██║██║  ██╗██║██║ ╚═╝ ██║██║",
            "╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝",
        ]
        cat_lines = [
            "   ██╗   ██╗",
            "  ██████████║",
            "  ██  ██  ██║",
            "  ██ ████ ██║",
            "  ██████████║",
            "   ██    ██╝",
        ]
        title_width = max(len(line) for line in hakimi_lines)
        combined = "\n".join(
            f"{h_line:<{title_width}}    {c_line}"
            for h_line, c_line in zip(hakimi_lines, cat_lines)
        )
        for line in combined.split("\n"):
            self._add_system_message(line)

        if self.config.ai.auto_analyze:
            try:
                from codex.core.project_analyzer import ProjectAnalyzer
                analyzer = ProjectAnalyzer(str(self.project_path))
                summary = analyzer.get_summary()
                for line in summary.split("\n"):
                    if line.strip():
                        self._add_system_message(line)
            except Exception:
                pass

        active_model = get_active_model(self.config)
        if active_model:
            self._add_system_message(f"Active model: {active_model.name}")
        else:
            self._add_system_message("[bold yellow]No model configured.[/bold yellow] Type /model add <model_id> <api_key> [provider]")
            self._add_system_message("Example: /model add deepseek-v3 sk-xxx deepseek")

        self._add_system_message("Type /help for all commands")

        # 加载并显示历史聊天记录
        if self.config.ai.save_chat_history:
            self._load_and_show_history()

        bottom_panel = self.query_one("#bottom_panel", Vertical)
        bottom_panel.display = False

    def _format_provider_name(self, provider: str) -> str:
        """格式化 provider 显示名称."""
        mapping = {
            "deepseek": "DeepSeek",
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "google": "Google",
            "kimi": "Kimi",
            "mistral": "Mistral",
            "ollama": "Ollama",
            "openrouter": "OpenRouter",
            "custom": "Custom",
        }
        return mapping.get(provider.lower(), provider.capitalize())

    def _update_runtime_status(self, status: Dict[str, str]):
        """更新侧边栏 Runtime 区域，显示当前 Agent 运行状态."""
        runtime_info = self.query_one("#runtime_info", Static)
        agent = status.get("agent", "-")
        model = status.get("model", "-")
        state = status.get("state", "idle")

        state_labels = {
            "idle": ("idle", "#888888"),
            "running": ("running", "#4da6ff"),
            "deciding": ("deciding", "#f59e0b"),
            "error": ("error", "#ef4444"),
        }
        label, color = state_labels.get(state, (state, "#aaaaaa"))

        runtime_info.update(
            f"agent: {agent}\n"
            f"model: {model}\n"
            f"state: [{color}]{label}[/{color}]"
        )

    def _update_sidebar(self):
        project_info = self.query_one("#project_info", Static)
        model_info = self.query_one("#model_info", Static)
        agent_info = self.query_one("#agent_info", Static)
        shortcuts_info = self.query_one("#shortcuts_info", Static)

        branch = ""
        changes = 0
        if git_utils.is_git_repo(str(self.project_path)):
            branch = git_utils.get_git_branch(str(self.project_path)) or ""
            changes = len(git_utils.get_git_status(str(self.project_path)))

        project_info.update(
            f"{self.project_path.name}\n"
            f"{self.project_path}\n"
            f"git:{branch or 'n/a'}\n"
            f"changes:{changes}"
        )

        active_model = get_active_model(self.config)
        if active_model:
            provider_label = self._format_provider_name(active_model.provider)
            tracker = self.chat_engine.token_tracker
            token_line = f"tokens:{tracker.session_usage.total}"
            today_line = f"today:{tracker.today_usage.total}"
            model_info.update(
                f"[bold]{active_model.name}[/bold]\n"
                f"{provider_label}\n"
                f"max:{active_model.max_tokens}\n"
                f"{token_line}\n"
                f"{today_line}"
            )
        else:
            model_info.update("[bold yellow]none[/bold yellow]\n-\n-\n-\n-")

        ai = self.config.ai
        mode_color = "bold green" if ai.agent_mode else "bold #888888"
        tests_color = "bold green" if ai.agent_run_tests else "bold #888888"
        fold_color = "bold green" if ai.agent_fold_output else "bold #888888"
        agent_info.update(
            f"mode: [{mode_color}]{'ON' if ai.agent_mode else 'OFF'}[/{mode_color}]\n"
            f"tests: [{tests_color}]{'ON' if ai.agent_run_tests else 'OFF'}[/{tests_color}]\n"
            f"fold: [{fold_color}]{'ON' if ai.agent_fold_output else 'OFF'}[/{fold_color}]\n"
            f"planner: {ai.planner_model or '(main)'}\n"
            f"coder: {ai.coder_model or '(main)'}\n"
            f"reviewer: {ai.reviewer_model or '(main)'}\n"
            f"tester: {ai.tester_model or '(main)'}"
        )

        shortcuts_info.update(
            "Enter newline\n"
            "F5 copy last AI\n"
            "F6 copy view\n"
            "F7 code blocks\n"
            "Ctrl+F search\n"
            "Ctrl+R retry\n"
            "Ctrl+C exit\n"
            "Up/Down history\n"
            "/help commands"
        )

    def _populate_file_tree(self):
        """加载项目文件树到侧边栏."""
        try:
            tree = self.query_one("#file_tree", Tree)
        except Exception:
            return
        tree.show_root = False
        tree.guide_depth = 2
        tree.root.remove_children()
        self._build_file_tree(tree.root, self.project_path)

    def _is_ignored_path(self, path: Path) -> bool:
        """判断文件树中是否应该忽略的路径."""
        ignored_names = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            ".hakimi", ".env", ".idea", ".vscode", "dist", "build",
            ".pytest_cache", ".mypy_cache", ".coverage", ".gitattributes",
        }
        name = path.name
        if name in ignored_names:
            return True
        if name.endswith(".pyc"):
            return True
        if name == "hakimi_debug.log":
            return True
        return False

    def _build_file_tree(self, parent, path: Path):
        """递归构建文件树节点."""
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except (PermissionError, OSError):
            return

        for entry in entries:
            if self._is_ignored_path(entry):
                continue
            if entry.is_dir():
                node = parent.add(f"📁 {entry.name}", data=entry)
                node.allow_expand = True
            else:
                node = parent.add_leaf(f"📄 {entry.name}", data=entry)
                node.allow_expand = False

    def on_tree_node_expanded(self, event: Tree.NodeExpanded):
        """目录展开时动态加载子节点."""
        node = event.node
        data = node.data
        if not data or not isinstance(data, Path):
            return
        if not data.is_dir():
            return
        node.remove_children()
        self._build_file_tree(node, data)

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        """点击文件时添加到上下文."""
        node = event.node
        data = node.data
        if not data or not isinstance(data, Path):
            return
        if data.is_file():
            try:
                rel_path = data.relative_to(self.project_path).as_posix()
            except ValueError:
                rel_path = str(data)
            self._add_file_to_context({"path": rel_path})

    def _load_and_show_history(self):
        """加载历史记录并渲染到消息区."""
        history = self.chat_engine.history
        if not history.messages:
            return

        self._add_system_message("--- 历史聊天记录 ---")
        for msg in history.messages:
            if msg.role == "user":
                self._render_user_message(msg.content, msg.id)
            elif msg.role == "assistant":
                self._render_ai_message(msg.content, msg.thinking, msg.id)
            elif msg.role == "tool":
                self._add_tool_result(msg.tool_name or "tool", msg.content)
        self._add_system_message("--- 以上为历史记录 ---")

    def _message_header(self, label: str, color: str, message_id: str) -> Text:
        """生成带复制按钮标记的消息头部."""
        ts = datetime.now().strftime("%H:%M:%S")
        text = Text()
        text.append(f"{label} {ts}", style=f"bold {color}")
        text.append(f" id={message_id}", style="bold #888888")
        return text

    def _get_ai_label(self) -> str:
        """获取当前 AI 消息应显示的标签（模型名或 AI）."""
        active = get_active_model(self.config)
        if active and active.name:
            name = active.name.strip()
            # 限制长度，避免头部过宽
            return name[:18] + "..." if len(name) > 18 else name
        return "AI"

    def _add_user_message(self, content: str):
        msg = self.chat_engine.add_user_message(content)
        self._render_user_message(content, msg.id)

    def _render_user_message(self, content: str, message_id: str):
        log = self.query_one("#messages_log", RichLog)
        log.write("")
        log.write(self._message_header("You", self.config.ui.user_color, message_id))
        log.write(f"[bold {self.config.ui.user_color}]> {content}[/bold {self.config.ui.user_color}]")
        log.write("")

    def _add_ai_message(self, content: str, thinking: Optional[str] = None, message_id: Optional[str] = None):
        self._render_ai_message(content, thinking, message_id)

    def _render_ai_message(self, content: str, thinking: Optional[str] = None, message_id: Optional[str] = None):
        log = self.query_one("#messages_log", RichLog)
        log.write("")
        msg_id = message_id or "unknown"
        ai_label = self._get_ai_label()
        log.write(self._message_header(ai_label, self.config.ui.output_color, msg_id))

        # 防御性过滤：确保内容中不再残留 thinking 标签
        content = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL)

        if thinking and self.config.ai.think_mode:
            if self.config.ai.think_fold:
                log.write(f"[#888888]Thinking... (use /setting think_fold=false to expand)[/#888888]")
            else:
                tc = self.config.ui.think_color
                log.write(f"[bold {tc}]╭─ Thinking ──────────────────────────────[/bold {tc}]")
                for line in thinking.split("\n"):
                    log.write(f"[{tc}]│ {line}[/{tc}]")
                log.write(f"[bold {tc}]╰─────────────────────────────────────────[/bold {tc}]")
            log.write("")

        self._last_ai_content = content
        self._code_blocks = extract_code_blocks(content)
        code_block_iter = iter(self._code_blocks)
        parts = parse_content(content)
        for part in parts:
            if part["type"] == "text":
                if self.config.ai.markdown_render:
                    log.write(Markdown(part["content"]))
                else:
                    log.write(part["content"])
            elif part["type"] == "diff":
                self._render_diff(log, part["content"])
            elif part["type"] == "code":
                try:
                    block = next(code_block_iter)
                except StopIteration:
                    block = None
                self._render_code(log, part["content"], part.get("language"), block)

        log.write("")

    def _on_stream_chunk(self, chunk: Optional[str]):
        """处理流式输出 chunk."""
        streaming_output = self.query_one("#streaming_output", Static)

        if chunk is None:
            # 流式结束
            self._streaming_active = False
            self._streaming_buffer = ""
            streaming_output.display = False
            streaming_output.update("")
            return

        if not self._streaming_active:
            self._streaming_active = True
            self._streaming_buffer = ""
            streaming_output.display = True

        self._streaming_buffer += chunk
        # 实时移除 thinking 标签，避免界面闪烁
        display_text = re.sub(r"<thinking>.*?</thinking>", "", self._streaming_buffer, flags=re.DOTALL)
        display_text = display_text.strip()
        # 转义 Rich markup，避免未闭合标签导致渲染错误
        display_text = display_text.replace("[", "[[")
        # 预览区只保留最新 5 行
        lines = display_text.split("\n")
        if len(lines) > 5:
            display_text = "\n".join(lines[-5:])
        ai_label = self._get_ai_label()
        if not display_text:
            if self.config.ai.think_mode:
                streaming_output.update("[italic #888888]Thinking...[/italic #888888]")
            else:
                streaming_output.update(f"[italic #888888]{ai_label} is typing...[/italic #888888]")
        else:
            streaming_output.update(f"[bold #58a6ff]{ai_label}:[/bold #58a6ff] {display_text}")

    def _add_system_message(self, content: str):
        log = self.query_one("#messages_log", RichLog)
        # 检测是否包含 Rich 标记（如 [bold green]...[/bold green]）
        has_rich_markup = bool(re.search(r'\[/?[a-z][a-z0-9_ -]*\]', content))
        # 检测是否包含 Markdown 标记
        has_markdown = any(marker in content for marker in ("##", "**", "```", "- "))

        if has_rich_markup:
            # 有 Rich 标记，直接渲染（不再用灰色包裹，避免标记被当作纯文本）
            log.write(content)
        elif self.config.ai.markdown_render and has_markdown:
            # 有 Markdown 标记，用 Markdown 渲染
            log.write(Markdown(content))
        else:
            # 普通文本，用灰色显示
            log.write(f"[#aaaaaa]{content}[/#aaaaaa]")

    def _on_add_system_message(self, data: Dict):
        """通过命令动作添加系统消息."""
        content = data.get("message", "") if data else ""
        self._add_system_message(content)

    def _add_tool_result(self, tool_name: str, result: str):
        if not self.config.ai.show_tool_results:
            return
        log = self.query_one("#messages_log", RichLog)
        log.write("")

        line_count = result.count("\n") + 1
        char_count = len(result)

        if self.config.ai.tool_results_fold:
            log.write(f"[bold #58a6ff][{tool_name}][/bold #58a6ff] [#888888]({line_count} lines, {char_count} chars) [use /setting tool_results_fold=false to expand][/#888888]")
        else:
            log.write(f"[bold #58a6ff][{tool_name}][/bold #58a6ff]")
            for line in result.split("\n"):
                log.write(f"[#888888]{line}[/#888888]")
        log.write("")

        bottom_panel = self.query_one("#bottom_panel", Vertical)
        bottom_panel.display = True
        tool_log = self.query_one("#tool_result_log", RichLog)
        tool_log.clear()
        tool_log.write(f"[bold #58a6ff][{tool_name}] ({line_count} lines, {char_count} chars) ↑↓ scroll[/bold #58a6ff]")
        for line in result.split("\n"):
            tool_log.write(f"[#888888]{line}[/#888888]")
        tool_log.focus()

    def _render_diff(self, log: RichLog, diff: str):
        log.write("")
        log.write(Text("--- diff", style="bold #e0e0e0"))
        for line in diff.split("\n"):
            if line.startswith("+"):
                style = "bold #3fb950"
            elif line.startswith("-"):
                style = "bold #f85149"
            elif line.startswith("@@"):
                style = "#888888"
            else:
                style = "#aaaaaa"
            log.write(Text(line, style=style))
        log.write(Text("---", style="bold #e0e0e0"))
        log.write("")

    def _show_diff_preview(self, diff: str, file_path: Optional[str] = None):
        """在消息区显示 diff 预览."""
        log = self.query_one("#messages_log", RichLog)
        header = f"检测到文件修改建议: {file_path}" if file_path else "diff 预览"
        log.write("")
        log.write(Text(header, style="bold #58a6ff"))
        self._render_diff(log, diff)

    def _search_callback(self, keyword: str) -> List[SearchResult]:
        """聊天记录搜索回调，返回给 SearchDialog 的结果."""
        results: List[SearchResult] = []
        for msg in self.chat_engine.history.search(keyword):
            preview = msg.content[:80].replace("\n", " ")
            if len(msg.content) > 80:
                preview += "..."
            results.append(
                SearchResult(
                    message_id=msg.id,
                    role=msg.role,
                    timestamp=msg.timestamp,
                    preview=preview,
                )
            )
        return results

    def action_show_search(self):
        """打开聊天记录搜索对话框."""
        dialog = SearchDialog(search_callback=self._search_callback)
        self.app.push_screen(dialog)

    def action_show_code_blocks(self):
        """打开代码块操作对话框."""
        if not self._code_blocks:
            self._add_system_message("[italic #888888]当前没有可操作的代码块[/italic #888888]")
            return
        dialog = CodeBlockDialog(
            code_blocks=self._code_blocks,
            full_content=self._last_ai_content,
            project_path=self.project_path,
            on_copy=self._copy_code_block,
            on_insert=self._insert_code_block,
            on_write=self._write_code_block,
        )
        self.app.push_screen(dialog)

    async def _copy_code_block(self, block: CodeBlock):
        """复制单个代码块到剪贴板."""
        try:
            fallback = await copy_to_clipboard(block.code)
            if fallback:
                self._add_system_message(f"[bold yellow]代码块已导出到文件：{fallback}[/bold yellow]")
            else:
                self._add_system_message("[bold green]代码块已复制到剪贴板[/bold green]")
        except Exception as e:
            self._add_system_message(f"[bold red]复制失败: {e}[/bold red]")

    async def _insert_code_block(self, block: CodeBlock):
        """将代码块插入到输入框当前光标/选区位置."""
        try:
            input_widget = self.query_one("#chat_input", ChatInput)
            start, end = input_widget.selection
            input_widget.replace(block.code, start, end)
            input_widget.focus()
            self._add_system_message("[#888888]已插入代码块到输入框[/#888888]")
        except Exception as e:
            self._add_system_message(f"[bold red]插入失败: {e}[/bold red]")

    async def _write_code_block(self, block: CodeBlock):
        """将代码块写入推断出的目标文件（带 diff 确认）."""
        file_path = detect_target_file_path(block, self._last_ai_content, self.project_path)
        if not file_path:
            self._add_system_message("[bold yellow]无法推断该代码块要写入的文件路径[/bold yellow]")
            return

        read_result = self.chat_engine.tool_executor.read_file(file_path)
        file_exists = read_result.status == ToolResultStatus.SUCCESS
        old_content = read_result.output if file_exists else ""
        new_content = block.code

        if file_exists and old_content == new_content:
            self._add_system_message(
                f"[#888888]代码块与 {file_path} 内容一致，无需写入。[/#888888]"
            )
            return

        diff = generate_unified_diff(old_content, new_content, file_path)
        self._show_diff_preview(diff, file_path)

        confirmed = await self._confirm_action(
            title=f"确认应用代码块到: {file_path}",
            content=diff,
            content_type="diff",
            confirm_label="确认写入",
        )
        if confirmed:
            write_result = self.chat_engine.tool_executor.write_file(file_path, new_content)
            if write_result.status == ToolResultStatus.SUCCESS:
                action = "覆盖" if file_exists else "创建"
                self._add_system_message(f"[bold green]已{action}文件: {file_path}[/bold green]")
            else:
                self._add_system_message(
                    f"[bold red]写入 {file_path} 失败: {write_result.output}[/bold red]"
                )
        else:
            self._add_system_message(f"[bold yellow]已取消写入 {file_path}[/bold yellow]")

    def _render_code(self, log: RichLog, code: str, lang: Optional[str] = None, block: Optional[CodeBlock] = None):
        log.write("")
        idx = 0
        if block and block in self._code_blocks:
            idx = self._code_blocks.index(block) + 1

        if idx:
            log.write(f"[#888888]--- {lang or 'code'} (#{idx}) · F7 /codeblocks[/]")
        else:
            log.write(f"[bold #888888]--- {lang or 'code'}[/bold #888888]")

        if lang:
            try:
                syntax = Syntax(code, lang, theme="monokai", line_numbers=False, word_wrap=True)
                log.write(syntax)
            except Exception:
                for line in code.split("\n"):
                    log.write(f"[#e0e0e0]{line}[/#e0e0e0]")
        else:
            for line in code.split("\n"):
                log.write(f"[#e0e0e0]{line}[/#e0e0e0]")
        log.write("")

    async def _confirm_action(
        self,
        title: str,
        content: str,
        content_type: str = "text",
        confirm_label: str = "确认"
    ) -> bool:
        """显示确认对话框并等待用户确认.

        push_screen_wait 必须在主线程调用。如果在主线程中直接调用；
        如果在 worker 线程中，使用 call_from_thread 将 push_screen 派发到主线程，
        并通过 on_dismiss 回调唤醒等待。
        """
        import threading

        log_debug(f"Showing confirmation dialog: {title} - {content[:100]}")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()

        def on_dismiss(result: bool) -> None:
            if not future.done():
                future.set_result(bool(result))

        dialog = ConfirmationDialog(
            title=title,
            content=content,
            content_type=content_type,
            confirm_label=confirm_label,
            cancel_label="取消",
            on_dismiss=on_dismiss,
        )

        def show_dialog() -> None:
            try:
                self.app.push_screen(dialog)
            except Exception as e:
                log_debug(f"push_screen error: {type(e).__name__}: {e}")
                if not future.done():
                    future.set_result(False)

        try:
            if threading.current_thread().ident == getattr(self.app, "_thread_id", None):
                # 主线程中直接 push_screen
                show_dialog()
            else:
                # worker 线程中通过 call_from_thread 安全推送对话框
                # wait=False 避免阻塞主事件循环
                self.app.call_from_thread(show_dialog, wait=False)
            result = await future
            log_debug(f"Confirmation dialog result: {result}")
            return result
        except Exception as e:
            log_debug(f"Confirmation dialog error: {type(e).__name__}: {e}")
            return False

    async def _review_plan(self, plan: str) -> Optional[str]:
        """显示 Agent 计划审核对话框，返回用户确认（可能已编辑）的计划或 None."""
        import threading

        log_debug("Showing plan review dialog")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Optional[str]] = loop.create_future()

        def on_dismiss(result: Optional[str]) -> None:
            if not future.done():
                future.set_result(result)

        dialog = PlanReviewDialog(plan=plan, on_dismiss=on_dismiss)

        def show_dialog() -> None:
            try:
                self.app.push_screen(dialog)
            except Exception as e:
                log_debug(f"push_screen error: {type(e).__name__}: {e}")
                if not future.done():
                    future.set_result(None)

        try:
            if threading.current_thread().ident == getattr(self.app, "_thread_id", None):
                show_dialog()
            else:
                self.app.call_from_thread(show_dialog, wait=False)
            return await future
        except Exception as e:
            log_debug(f"Plan review dialog error: {type(e).__name__}: {e}")
            return None

    def _build_callbacks(self) -> ChatCallbacks:
        """构建聊天引擎回调."""
        return ChatCallbacks(
            add_system_message=self._add_system_message,
            add_ai_message=self._add_ai_message,
            add_tool_result=self._add_tool_result,
            stream_chunk=self._on_stream_chunk,
            confirm_action=self._confirm_action,
            show_diff_preview=self._show_diff_preview,
        )

    async def action_copy_last_message(self):
        """复制最后一条 AI 消息到剪贴板."""
        await self._copy_text(
            self.chat_engine.history.get_copy_text(),
            "最后一条 AI 消息",
        )

    async def action_show_copy_view(self):
        """打开可复制文本查看弹窗."""
        text = self.chat_engine.history.get_all_text() or self.chat_engine.history.get_copy_text()
        dialog = CopyViewDialog(
            title="复制视图（Ctrl+C 复制全部 · 鼠标滑动选择 · Esc 关闭）",
            content=text,
            export_directory=self.project_path,
        )
        await self.app.push_screen(dialog)

    async def _copy_message_by_id(self, message_id: str):
        """根据消息 ID 复制内容."""
        await self._copy_text(
            self.chat_engine.history.get_copy_text(message_id),
            f"消息 {message_id}",
            not_found_msg=f"未找到消息: {message_id}",
        )

    async def _copy_all_messages(self):
        """复制完整聊天记录."""
        await self._copy_text(
            self.chat_engine.history.get_all_text(),
            "完整聊天记录",
        )

    async def _copy_text(
        self,
        text: str,
        label: str,
        not_found_msg: str = "没有可复制的聊天记录",
    ):
        """通用复制逻辑：优先剪贴板，失败则导出到文件."""
        if not text:
            self._add_system_message(f"[bold yellow]{not_found_msg}[/bold yellow]")
            return

        try:
            fallback_path = await copy_to_clipboard(text)
            if fallback_path:
                self._add_system_message(
                    f"[bold yellow]剪贴板不可用，{label}已导出到文件并打开：{fallback_path}[/bold yellow]"
                )
            else:
                self._add_system_message(f"[bold green]已复制{label}到剪贴板[/bold green]")
        except Exception as e:
            self._add_system_message(f"[bold red]复制失败: {e}[/bold red]")

    def _hide_tool_result_panel(self):
        """隐藏底部 Tool Result 面板并恢复输入框焦点."""
        try:
            bottom_panel = self.query_one("#bottom_panel", Vertical)
            bottom_panel.display = False
            tool_log = self.query_one("#tool_result_log", RichLog)
            tool_log.clear()
            input_widget = self.query_one("#chat_input", ChatInput)
            input_widget.focus()
        except Exception:
            pass

    def _on_chat_send(self, content: str):
        # 新用户消息开始时隐藏之前的工具结果面板，避免一直占用屏幕
        self._hide_tool_result_panel()

        async def _wrapped():
            self.is_processing = True
            try:
                active_model = get_active_model(self.config)
                if not active_model:
                    self._add_system_message("[bold yellow]No model selected.[/bold yellow] Use /model to configure.")
                    return
                if not active_model.api_key:
                    self._add_system_message("[bold yellow]No API key configured.[/bold yellow] Use /model to edit.")
                    return
                if self.config.ai.agent_mode:
                    await self._run_agent_cluster({"request": content})
                else:
                    await self.chat_engine.process_message(content, self._build_callbacks())
            finally:
                self.is_processing = False
                self._update_sidebar()

        self.run_worker(_wrapped())

    def _on_command(self, action: str, data: Optional[Dict]):
        handlers = {
            "show_settings": self._show_settings,
            "set_setting": self._update_setting,
            "get_setting": self._show_setting,
            "model_list": self._show_models,
            "model_select": self._select_model,
            "model_add": self._on_model_add,
            "model_delete": self._on_model_delete,
            "add_file": self._add_file_to_context,
            "show_diff": self._show_diff,
            "clear_chat": self._clear_chat,
            "copy_message": self._on_copy_command,
            "export_history": self._export_history,
            "import_history": self._import_history,
            "show_history": self._on_history_command,
            "search_history": self._search_history,
            "show_search_dialog": self.action_show_search,
            "show_code_blocks": self.action_show_code_blocks,
            "retry_last_response": self._retry_last_response,
            "compare_models": self._compare_models,
            "undo": self._undo_last_change,
            "git_commit": self._git_commit,
            "show_status": self._show_status,
            "run_command": self._run_command,
            "run_git_command": self._run_git_command,
            "agent_execute": self._run_agent_cluster,
            "show_about": self._show_about,
            "exit": self._exit,
            "add_system_message": self._on_add_system_message,
        }
        handler = handlers.get(action)
        if handler:
            result = handler(data) if data else handler()
            if asyncio.iscoroutine(result):
                self.run_worker(result)

    async def _on_copy_command(self, data: Optional[Dict] = None):
        """处理 /copy 命令."""
        target = (data or {}).get("target", "last")
        if target == "last":
            await self.action_copy_last_message()
        elif target == "all":
            await self._copy_all_messages()
        elif target == "view":
            await self.action_show_copy_view()
        elif target == "file":
            await self._export_all_messages_to_file()
        else:
            await self._copy_message_by_id(target)

    async def _export_all_messages_to_file(self):
        """将完整聊天记录导出到项目目录文件."""
        text = self.chat_engine.history.get_all_text()
        if not text:
            self._add_system_message("[bold yellow]没有可导出的聊天记录[/bold yellow]")
            return
        try:
            path = await export_to_file(text, directory=self.project_path, prefix="hakimi_chat")
            self._add_system_message(f"[bold green]已导出聊天记录到文件并打开：{path}[/bold green]")
        except Exception as e:
            self._add_system_message(f"[bold red]导出失败: {e}[/bold red]")

    def _on_history_command(self, data: Optional[Dict] = None):
        """处理 /history 命令."""
        history = self.chat_engine.history
        if not history.messages:
            self._add_system_message("[bold yellow]暂无聊天记录[/bold yellow]")
            return

        lines = ["Chat history:", "-" * 40]
        for msg in history.messages:
            ts = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            preview = msg.content[:60].replace("\n", " ")
            if len(msg.content) > 60:
                preview += "..."
            lines.append(f"  [{msg.id}] [{ts}] {msg.role}: {preview}")
        lines.append("-" * 40)
        lines.append(
            "Use /copy <id> to copy a message, /copy last for latest AI, /copy all for full log, "
            "/copy view for selectable view, /export [json|text] [path] to export, "
            "/import <path> [--merge] to import."
        )
        self._add_system_message("\n".join(lines))

    def _search_history(self, data: Dict):
        """处理 /search 命令：搜索聊天记录."""
        keyword = data.get("keyword", "").strip()
        if not keyword:
            self._add_system_message("[bold yellow]用法: /search <keyword>[/bold yellow]")
            return

        results = self.chat_engine.history.search(keyword)
        if not results:
            self._add_system_message(f"[italic #888888]未找到包含 \"{keyword}\" 的记录[/italic #888888]")
            return

        lines = [f'搜索结果: "{keyword}" ({len(results)} 条)', "-" * 40]
        for msg in results:
            ts = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            preview = msg.content[:80].replace("\n", " ")
            if len(msg.content) > 80:
                preview += "..."
            role_label = {"user": "You", "assistant": self._get_ai_label(), "tool": "Tool"}.get(msg.role, msg.role)
            lines.append(f"  [{msg.id}] [{ts}] {role_label}: {preview}")
        lines.append("-" * 40)
        lines.append("使用 /copy <id> 复制指定消息")
        self._add_system_message("\n".join(lines))

    def _refresh_messages_log(self):
        """清空并重新渲染消息区."""
        log = self.query_one("#messages_log", RichLog)
        log.clear()
        for msg in self.chat_engine.history.messages:
            if msg.role == "user":
                self._render_user_message(msg.content, msg.id)
            elif msg.role == "assistant":
                self._render_ai_message(msg.content, msg.thinking, msg.id)
            elif msg.role == "tool":
                self._add_tool_result(msg.tool_name or "tool", msg.content)

    async def _retry_last_response(self):
        """处理 /retry 命令：重新生成最后一条 AI 回复."""
        if self.is_processing:
            self._add_system_message("[bold yellow]AI 正在处理中，请稍后再试[/bold yellow]")
            return

        last_user = self.chat_engine.history.get_last_message("user")
        if not last_user:
            self._add_system_message("[bold yellow]没有可重试的用户消息[/bold yellow]")
            return

        last_ai = self.chat_engine.history.get_last_message("assistant")
        if not last_ai:
            self._add_system_message("[bold yellow]没有可重试的 AI 回复[/bold yellow]")
            return

        self.is_processing = True
        self._update_runtime_status({"agent": "-", "model": self._get_ai_label(), "state": "running"})

        # 移除最后一条 AI 回复并刷新界面
        self.chat_engine.history.pop_last("assistant")
        self._refresh_messages_log()
        self._add_system_message(f"[italic #888888]正在重新生成对上文 \"{last_user.content[:30]}{'...' if len(last_user.content) > 30 else ''}\" 的回复...[/italic #888888]")

        def make_callbacks() -> ChatCallbacks:
            return ChatCallbacks(
                add_system_message=self._add_system_message,
                add_ai_message=self._add_ai_message,
                add_tool_result=self._add_tool_result,
                stream_chunk=self._on_stream_chunk,
                confirm_action=self._confirm_action,
                show_diff_preview=self._show_diff_preview,
            )

        try:
            await self.chat_engine.retry_last_response(make_callbacks())
        finally:
            self.is_processing = False
            self._update_runtime_status({"agent": "-", "model": "-", "state": "idle"})
            streaming_output = self.query_one("#streaming_output", Static)
            streaming_output.display = False
            streaming_output.update("")

    def action_retry_last_response(self):
        """快捷键 Ctrl+R：重新生成最后一条 AI 回复."""
        self.run_worker(self._retry_last_response())

    async def _compare_models(self, data: Dict):
        """处理 /compare 命令：并发请求多个模型并并排显示结果."""
        model_ids = data.get("model_ids", [])
        prompt = data.get("prompt", "").strip()
        if not model_ids or not prompt:
            self._add_system_message("[bold yellow]用法: /compare <model_ids> <prompt>[/bold yellow]")
            return

        available = {
            m.id: m for m in self.config.models
            if m.enabled and m.api_key
        }
        models = []
        missing = []
        for mid in model_ids:
            if mid in available:
                models.append(available[mid])
            else:
                missing.append(mid)

        if missing:
            self._add_system_message(
                f"[bold yellow]未找到或不可用模型: {', '.join(missing)}[/bold yellow]"
            )
        if not models:
            return

        if self.is_processing:
            self._add_system_message("[bold yellow]AI 正在处理中，请稍后再试[/bold yellow]")
            return

        self.is_processing = True
        self._add_system_message(
            f"[italic #888888]正在并发请求 {len(models)} 个模型进行对比...[/italic #888888]"
        )

        system_prompt = build_system_prompt(self.project_path)

        async def ask_model(model: ModelConfig) -> Dict:
            client = LLMClient(model, think_mode=self.config.ai.think_mode)
            try:
                messages = [{"role": "user", "content": prompt}]
                response = ""
                async for chunk in client.chat(
                    messages,
                    system_prompt=system_prompt,
                    stream=False,
                ):
                    response += chunk

                usage = client.last_usage
                if usage:
                    self.chat_engine.token_tracker.add_usage(model, usage)

                return {"model": model, "response": response, "error": None}
            except Exception as e:
                return {"model": model, "response": "", "error": str(e)}
            finally:
                await client.close()

        try:
            results = await asyncio.gather(*(ask_model(m) for m in models))
        finally:
            self.is_processing = False
            self._update_sidebar()

        table = Table(title="模型对比结果", expand=True, show_header=True)
        table.add_column("模型", width=20, no_wrap=True)
        table.add_column("回答", ratio=1)

        for r in results:
            name = r["model"].name
            if r["error"]:
                content = f"[错误] {r['error']}"
            else:
                content = r["response"].strip()
            table.add_row(name, Text(content))

        log = self.query_one("#messages_log", RichLog)
        log.write("")
        log.write(table)
        log.write("")

    async def _export_history(self, data: Optional[Dict] = None):
        """处理 /export 命令：导出聊天记录到文件."""
        data = data or {}
        fmt = data.get("format", "text")
        path_str = data.get("path", "")

        history = self.chat_engine.history
        if not history.messages:
            self._add_system_message("[bold yellow]没有可导出的聊天记录[/bold yellow]")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = ".jsonl" if fmt == "jsonl" else ".txt"
        default_name = f"hakimi_chat_{timestamp}{suffix}"

        if path_str:
            path = Path(path_str)
            if not path.is_absolute():
                path = self.project_path / path
        else:
            path = self.project_path / default_name

        try:
            exported = history.export_to(path, fmt=fmt)
            self._add_system_message(f"[bold green]已导出聊天记录：{exported}[/bold green]")
        except Exception as e:
            self._add_system_message(f"[bold red]导出失败: {e}[/bold red]")

    async def _import_history(self, data: Optional[Dict] = None):
        """处理 /import 命令：从 JSONL 文件导入聊天记录."""
        data = data or {}
        path_str = data.get("path", "")
        merge = data.get("merge", False)

        if not path_str:
            self._add_system_message("[bold red]用法: /import <path> [--merge][/bold red]")
            return

        path = Path(path_str)
        if not path.is_absolute():
            path = self.project_path / path

        try:
            count = self.chat_engine.history.import_from(path, merge=merge)
            self._add_system_message(f"[bold green]已导入 {count} 条聊天记录[/bold green]")
            self._load_and_show_history()
        except Exception as e:
            self._add_system_message(f"[bold red]导入失败: {e}[/bold red]")

    def _show_settings(self):
        ai = self.config.ai
        lines = [
            "Settings:", "-" * 40,
            f"  stream:                   {ai.stream}",
            f"  think_mode:               {ai.think_mode}",
            f"  think_fold:               {ai.think_fold}",
            f"  temperature:              {ai.temperature}",
            f"  max_context_messages:     {ai.max_context_messages}",
            f"  context_ttl_hours:        {ai.context_ttl_hours or '(disabled)'}",
            f"  save_chat_history:        {ai.save_chat_history}",
            f"  show_tool_results:        {ai.show_tool_results}",
            f"  tool_results_fold:        {ai.tool_results_fold}",
            f"  markdown_render:          {ai.markdown_render}",
            f"  auto_analyze:             {ai.auto_analyze}",
            f"  confirm_tool_execution:   {ai.confirm_tool_execution}",
            f"  confirm_command_execution:{ai.confirm_command_execution}",
            f"  confirm_write_file:       {ai.confirm_write_file}",
            f"  max_tool_rounds:          {ai.max_tool_rounds}",
            f"  agent_mode:               {ai.agent_mode}",
            f"  agent_run_tests:          {ai.agent_run_tests}",
            f"  agent_fold_output:        {ai.agent_fold_output}",
            f"  debug_mode:               {ai.debug_mode}",
            f"  planner_model:            {ai.planner_model or '(main)'}",
            f"  coder_model:              {ai.coder_model or '(main)'}",
            f"  reviewer_model:           {ai.reviewer_model or '(main)'}",
            f"  tester_model:             {ai.tester_model or '(main)'}",
            "", "Usage: /setting key=value",
        ]
        self._add_system_message("\n".join(lines))

    def _update_setting(self, data: Dict):
        key = data.get("key")
        value = data.get("value")
        ai = self.config.ai
        if key == "stream":
            ai.stream = value
        elif key == "think_mode":
            ai.think_mode = value
        elif key == "think_fold":
            ai.think_fold = value
        elif key == "temperature":
            ai.temperature = value
        elif key == "max_context_messages":
            ai.max_context_messages = max(2, min(200, value))
            self.chat_engine.history.max_context_messages = ai.max_context_messages
        elif key == "context_ttl_hours":
            ai.context_ttl_hours = value if value is None or value > 0 else None
            self.chat_engine.history.context_ttl_hours = ai.context_ttl_hours
        elif key == "save_chat_history":
            ai.save_chat_history = value
        elif key == "show_tool_results":
            ai.show_tool_results = value
        elif key == "tool_results_fold":
            ai.tool_results_fold = value
        elif key == "markdown_render":
            ai.markdown_render = value
        elif key == "auto_analyze":
            ai.auto_analyze = value
        elif key == "confirm_tool_execution":
            ai.confirm_tool_execution = value
        elif key == "confirm_command_execution":
            ai.confirm_command_execution = value
        elif key == "confirm_write_file":
            ai.confirm_write_file = value
        elif key == "max_tool_rounds":
            ai.max_tool_rounds = max(1, min(50, value))
        elif key == "agent_mode":
            ai.agent_mode = value
        elif key == "agent_run_tests":
            ai.agent_run_tests = value
        elif key == "agent_fold_output":
            ai.agent_fold_output = value
        elif key == "debug_mode":
            ai.debug_mode = value
            setup_logger(self.project_path, self.config.ai.debug_mode)
        elif key == "planner_model":
            ai.planner_model = value
        elif key == "coder_model":
            ai.coder_model = value
        elif key == "reviewer_model":
            ai.reviewer_model = value
        elif key == "tester_model":
            ai.tester_model = value
        save_config(self.config)
        self.chat_engine.config = self.config
        self._update_sidebar()
        self._add_system_message(f"Setting updated: {key} = {value}")

    def _show_setting(self, data: Dict):
        self._add_system_message(f"{data.get('key')} = ...")

    def _show_models(self):
        lines = ["Models:", "-" * 40]
        for m in self.config.models:
            active = "* " if m.id == self.config.active_model_id else "  "
            lines.append(f"  {active}{m.name} ({m.provider})")
        lines.append(""); lines.append("Use /model select <id>")
        self._add_system_message("\n".join(lines))

    def _select_model(self, data: Dict):
        model_id = data.get("id")
        if set_active_model(self.config, model_id):
            active = get_active_model(self.config)
            if active:
                self._add_system_message(f"Model activated: [bold]{active.name}[/bold]")
                self.chat_engine.set_model(active)
                self._update_sidebar()
        else:
            self._add_system_message(f"[bold red]Model not found: {model_id}[/bold red]")

    def _on_model_add(self, data: Dict):
        model_id = data.get("model_id")
        api_key = data.get("api_key")
        provider_str = data.get("provider", "custom")
        name = data.get("name", model_id)

        if not model_id or not api_key:
            self._add_system_message("[bold red]Error: model_id and api_key are required[/bold red]")
            return

        try:
            provider = ProviderType(provider_str.lower())
        except ValueError:
            provider = ProviderType.CUSTOM

        api_base = self._infer_api_base(provider)

        model = ModelConfig(
            id=model_id, name=name, provider=provider, model_id=model_id,
            api_key=api_key, api_base=api_base, temperature=0.7,
            max_tokens=4096, context_window=8192, enabled=True, is_default=False,
        )
        add_model(self.config, model)
        self._add_system_message(f"[bold green]Model added: {name} ({provider.value})[/bold green]")
        self._add_system_message(f"Use /model select {model_id} to activate")

    def _infer_api_base(self, provider: ProviderType) -> Optional[str]:
        """根据提供商推断 API 基础 URL."""
        defaults = {
            ProviderType.DEEPSEEK: "https://api.deepseek.com/v1",
            ProviderType.KIMI: "https://api.moonshot.cn/v1",
            ProviderType.ANTHROPIC: "https://api.anthropic.com/v1",
            ProviderType.GOOGLE: "https://generativelanguage.googleapis.com/v1beta",
            ProviderType.MISTRAL: "https://api.mistral.ai/v1",
            ProviderType.OLLAMA: "http://localhost:11434/v1",
            ProviderType.OPENROUTER: "https://openrouter.ai/api/v1",
        }
        return defaults.get(provider)

    async def _on_model_delete(self, data: Dict):
        model_id = data.get("id")
        if not model_id:
            self._add_system_message("[bold red]Usage: /model delete <id>[/bold red]")
            return

        target = next((m for m in self.config.models if m.id == model_id), None)
        if not target:
            self._add_system_message(f"[bold red]Model not found: {model_id}[/bold red]")
            return

        confirmed = await self._confirm_action(
            title="删除模型",
            content=f"确认删除已保存模型 [bold]{target.name}[/bold] ({target.provider})?",
            content_type="markdown",
            confirm_label="删除",
        )
        if not confirmed:
            self._add_system_message("删除已取消")
            return

        was_active = self.config.active_model_id == model_id
        if remove_model(self.config, model_id):
            self._add_system_message(f"[bold yellow]Model removed: {target.name}[/bold yellow]")
            if was_active:
                await self.chat_engine.close()
                self._update_sidebar()
                self._add_system_message("[bold yellow]当前激活模型已被删除，请使用 /model select 选择新模型[/bold yellow]")
        else:
            self._add_system_message(f"[bold red]Failed to remove model: {model_id}[/bold red]")

    def _add_file_to_context(self, data: Dict):
        file_path = data.get("path")
        result = self.chat_engine.tool_executor.read_file(file_path)
        if result.status == ToolResultStatus.SUCCESS:
            self._add_system_message(f"File loaded: {file_path}")
            preview = result.output[:500]
            if len(result.output) > 500:
                preview += "\n... (truncated)"
            self._add_tool_result(f"read_file: {file_path}", preview)
        else:
            self._add_system_message(f"[bold red]Failed to load: {result.output}[/bold red]")

    def _show_diff(self, data: Optional[Dict] = None):
        self._add_system_message("Diff: (not implemented in chat view)")

    async def _clear_chat(self):
        """清空聊天记录（带确认）."""
        if self.chat_engine.history.messages:
            confirmed = await self._confirm_action(
                title="清空聊天记录",
                content="确定要清空当前会话的所有聊天记录吗？此操作不可恢复。",
                content_type="text",
                confirm_label="清空",
            )
            if not confirmed:
                self._add_system_message("[bold yellow]已取消清空[/bold yellow]")
                return

        self.chat_engine.clear_history()
        log = self.query_one("#messages_log", RichLog)
        log.clear()
        self._add_system_message("[bold green]聊天记录已清空[/bold green]")

    def _undo_last_change(self):
        self._add_system_message("Undo not yet implemented")

    async def _git_commit(self, data: Dict):
        message = data.get("message", "").strip()

        if not git_utils.is_git_repo(str(self.project_path)):
            self._add_system_message("[bold yellow]当前项目不是 Git 仓库[/bold yellow]")
            self._update_sidebar()
            return

        files = [f for _, f in git_utils.get_git_status(str(self.project_path))]
        if not files:
            self._add_system_message("[italic #888888]没有可提交的更改[/italic #888888]")
            self._update_sidebar()
            return

        # 未提供提交信息时，让 AI 根据 diff 生成
        if not message:
            diff = git_utils.get_git_diff(str(self.project_path))
            if not diff:
                self._add_system_message("[bold yellow]没有可提交的 diff[/bold yellow]")
                return

            active_model = get_active_model(self.config)
            if not active_model or not active_model.api_key:
                self._add_system_message(
                    "[bold yellow]未配置模型或 API key，无法自动生成提交信息。"
                    "请手动指定：/commit <message>[/bold yellow]"
                )
                return

            self.is_processing = True
            self._update_runtime_status({"agent": "-", "model": self._get_ai_label(), "state": "deciding"})
            self._add_system_message("[italic #888888]AI 正在根据 diff 生成提交信息...[/italic #888888]")
            try:
                if not self.chat_engine.llm_client or self.chat_engine.llm_client.model.id != active_model.id:
                    await self.chat_engine.close()
                    self.chat_engine.llm_client = LLMClient(active_model, think_mode=self.config.ai.think_mode)

                prompt = (
                    "请根据以下 git diff 生成一条简洁的英文 conventional commit message。"
                    "只返回消息本身，不要加任何解释、引号或 markdown 格式。\n\n"
                    f"{diff[:4000]}"
                )
                messages = [{"role": "user", "content": prompt}]
                generated = ""
                async for chunk in self.chat_engine.llm_client.chat(messages, stream=False):
                    generated += chunk
                message = generated.strip().strip('"').strip("'")
                if not message:
                    message = "Hakimi update"
                self._add_system_message(f"[bold #58a6ff]生成提交信息:[/bold #58a6ff] {message}")

                # 累计本次生成消耗的 token
                usage = self.chat_engine.llm_client.last_usage
                if usage:
                    self.chat_engine.token_tracker.add_usage(active_model, usage)
            except Exception as e:
                self._add_system_message(f"[bold red]生成提交信息失败: {e}[/bold red]")
                return
            finally:
                self.is_processing = False
                self._update_runtime_status({"agent": "-", "model": "-", "state": "idle"})

        git_utils.git_add(str(self.project_path), files)
        if git_utils.git_commit(str(self.project_path), message):
            self._add_system_message(f"[bold green]已提交: {message}[/bold green]")
        else:
            self._add_system_message(f"[bold red]提交失败: {message}[/bold red]")
        self._update_sidebar()

    def _show_status(self):
        lines = ["Status:", "-" * 40]
        if git_utils.is_git_repo(str(self.project_path)):
            branch = git_utils.get_git_branch(str(self.project_path))
            files = git_utils.get_git_status(str(self.project_path))
            lines.append(f"  Git branch: {branch}")
            lines.append(f"  Changes: {len(files)}")
        active = get_active_model(self.config)
        if active:
            lines.append(f"  Model: {active.name}")
        lines.append(f"  Project: {self.project_path}")
        lines.append(f"  Agent mode: {self.config.ai.agent_mode}")
        self._add_system_message("\n".join(lines))

    def _show_about(self):
        """显示 Hakimi CLI 的 Markdown 格式详细信息."""
        from rich.markdown import Markdown

        active = get_active_model(self.config)
        model_line = f"- 当前模型: {active.name}" if active else "- 当前模型: 未配置"

        about_md = f"""# Hakimi Codex

一个为个人工作流设计的现代化 AI 代码助手 CLI 工具。

## 版本信息

- 版本: v{__version__}
- 作者: {__author__}
{model_line}
- 项目路径: {self.project_path}

## 主要特性

- 💬 多轮对话与流式输出
- 🛠️ 内置文件读写、终端命令、Git 操作等工具
- ✅ 工具执行前可配置用户确认
- 🤖 多 Agent 协作模式（Planner / Coder / Reviewer / Tester）
- 🧠 支持 DeepSeek、OpenAI、Anthropic、Kimi、Mistral 等多家模型
- 📝 代码 diff 预览与写入确认
- 🐱 像素风 Hakimi 猫

## Agent 集群角色

| 角色 | 职责 |
|------|------|
| Planner | 分析需求并制定实现计划 |
| Coder | 根据计划编写或修改代码 |
| Reviewer | 审查实现质量 |
| Tester | 生成并运行测试 |

## 常用命令

- `/help` - 显示所有命令
- `/model` - 模型管理
- `/agent on` - 开启 Agent 集群模式
- `/setting` - 查看与修改设置
- `/about` - 显示本页面
- `/exit` - 退出应用

## 项目链接

- GitHub: https://github.com/hakimi-team/hakimi-cli
"""
        log = self.query_one("#messages_log", RichLog)
        log.write("")
        log.write(Markdown(about_md))
        log.write("")

    async def _run_command(self, data: Dict):
        command = data.get("command")
        if (
            self.config.ai.confirm_tool_execution
            and self.config.ai.confirm_command_execution
        ):
            confirmed = await self._confirm_action(
                title="确认执行终端命令",
                content=f"$ {command}",
                content_type="text",
                confirm_label="确认执行",
            )
            if not confirmed:
                self._add_system_message("[bold yellow]已取消命令执行[/bold yellow]")
                return
        result = self.chat_engine.tool_executor.execute_command(command)
        if result.status == ToolResultStatus.SUCCESS:
            self._add_tool_result(f"$ {command}", result.output)
        else:
            self._add_tool_result(f"$ {command} (exit {result.exit_code})", result.output)

    async def _run_git_command(self, data: Dict):
        args_str = data.get("args", "").strip()
        if not args_str:
            self._add_system_message("[bold yellow]用法: /git <git 命令参数>[/bold yellow]")
            return

        if not git_utils.is_git_repo(str(self.project_path)):
            self._add_system_message("[bold yellow]当前项目不是 Git 仓库[/bold yellow]")
            return

        # 简单分词：支持引号内的空格
        try:
            args = shlex.split(args_str)
        except ValueError as exc:
            self._add_system_message(f"[bold red]参数解析失败: {exc}[/bold red]")
            return

        # 过滤危险子命令（可选）
        dangerous = {"rm", "clean", "reset", "rebase", "filter-branch"}
        if args and args[0].lower() in dangerous:
            confirmed = await self._confirm_action(
                title="确认执行 Git 危险命令",
                content=f"git {' '.join(args)}",
                content_type="text",
                confirm_label="确认执行",
            )
            if not confirmed:
                self._add_system_message("[bold yellow]已取消 git 命令[/bold yellow]")
                return
        elif self.config.ai.confirm_tool_execution and self.config.ai.confirm_command_execution:
            confirmed = await self._confirm_action(
                title="确认执行 Git 命令",
                content=f"git {' '.join(args)}",
                content_type="text",
                confirm_label="确认执行",
            )
            if not confirmed:
                self._add_system_message("[bold yellow]已取消 git 命令[/bold yellow]")
                return

        exit_code, stdout, stderr = git_utils.run_git_command(str(self.project_path), args)
        output = stdout
        if stderr:
            output = (output + "\n" + stderr).strip()
        if not output:
            output = "(无输出)"
        if exit_code == 0:
            self._add_tool_result(f"$ git {' '.join(args)}", output)
        else:
            self._add_tool_result(f"$ git {' '.join(args)} (exit {exit_code})", output)

    async def _run_agent_cluster(self, data: Dict):
        request = data.get("request", "")
        active_model = get_active_model(self.config)
        if not active_model:
            self._add_system_message("[bold yellow]No model selected.[/bold yellow] Use /model to configure.")
            return
        if not active_model.api_key:
            self._add_system_message("[bold yellow]No API key configured.[/bold yellow] Use /model to edit.")
            return
        orchestrator = Orchestrator(
            project_path=str(self.project_path),
            config=self.config,
            model=active_model,
            progress_callback=lambda msg: self._add_system_message(msg),
            status_callback=lambda status: self._update_runtime_status(status),
            confirm_callback=self._confirm_action,
            plan_review_callback=self._review_plan,
        )
        result = await orchestrator.process(request)
        self._add_system_message(result)

    def _exit(self):
        asyncio.create_task(self.chat_engine.close())
        self.app.exit()

    def _history_up(self):
        input_widget = self.query_one("#chat_input", ChatInput)
        if not self.input_history:
            return
        if self.input_history_index == -1:
            self.input_history_index = len(self.input_history) - 1
        elif self.input_history_index > 0:
            self.input_history_index -= 1
        else:
            return
        input_widget.text = self.input_history[self.input_history_index]
        lines = input_widget.text.split("\n")
        input_widget.cursor_location = (len(lines) - 1, len(lines[-1]))

    def _history_down(self):
        input_widget = self.query_one("#chat_input", ChatInput)
        if not self.input_history:
            return
        if self.input_history_index < len(self.input_history) - 1:
            self.input_history_index += 1
            input_widget.text = self.input_history[self.input_history_index]
        elif self.input_history_index == len(self.input_history) - 1:
            self.input_history_index = -1
            input_widget.text = ""

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "send_button":
            self._process_input()

    def _process_input(self):
        input_widget = self.query_one("#chat_input", ChatInput)
        content = input_widget.text.strip()
        if not content or self.is_processing:
            return
        input_widget.text = ""
        self.input_history.append(content)
        self.input_history_index = -1

        is_cmd, cmd, args = self.command_handler.parse(content)
        if is_cmd:
            result = self.command_handler.handle(content)
            if result.message:
                if result.success:
                    self._add_system_message(result.message)
                else:
                    self._add_system_message(f"[bold red]Error: {result.message}[/bold red]")
            if result.action:
                self._on_command(result.action, result.data)
        else:
            self._add_user_message(content)
            self._on_chat_send(content)

    def action_quit(self):
        self._exit()

    def action_confirm_quit(self):
        """弹出确认框后再退出应用."""
        dialog = ConfirmationDialog(
            title="确认退出",
            content="确定要退出 Hakimi Codex 吗？",
            confirm_label="退出",
            cancel_label="取消",
            on_dismiss=self._on_quit_confirmed,
        )
        self.app.push_screen(dialog)

    def _on_quit_confirmed(self, confirmed: bool):
        if confirmed:
            self._exit()
