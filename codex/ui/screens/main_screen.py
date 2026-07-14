"""主工作界面 - Claude Code 风格布局."""

import asyncio
import re
from pathlib import Path
from typing import Optional, Dict, Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, RichLog, TextArea
from textual.reactive import reactive

from rich.markdown import Markdown
from rich.syntax import Syntax

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
from codex.core.tools import ToolExecutor, ToolResultStatus
from codex.core.command_handler import CommandHandler, CommandResult
from codex.core.chat_engine import ChatEngine, ChatCallbacks
from codex.core.agents import Orchestrator
from codex.utils.markdown import parse_content
from codex.utils.logger import setup_logger, debug as log_debug
from .confirmation_dialog import ConfirmationDialog


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

    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = Path(project_path).resolve()
        self.command_handler = CommandHandler()
        self.input_history: list[str] = []
        self.input_history_index = -1
        super().__init__(**kwargs)
        self.chat_engine = ChatEngine(str(self.project_path), self.config)

    def compose(self) -> ComposeResult:
        with Horizontal(id="main_layout"):
            with Vertical(id="left_sidebar"):
                yield Static("Project", classes="sidebar_title", id="sidebar_title_project")
                yield Static(id="project_info")
                yield Static("Model", classes="sidebar_title", id="sidebar_title_model")
                yield Static(id="model_info")
                yield Static("Agent Cluster", classes="sidebar_title", id="sidebar_title_agent")
                yield Static(id="agent_info")
                yield Static("Runtime", classes="sidebar_title", id="sidebar_title_runtime")
                yield Static(id="runtime_info")
                yield Static("Shortcuts", classes="sidebar_title", id="sidebar_title_shortcuts")
                yield Static(id="shortcuts_info")
            with Vertical(id="center_panel"):
                yield RichLog(id="messages_log", wrap=True, markup=True, highlight=False, auto_scroll=True)
        with Vertical(id="bottom_panel"):
            yield Static("Tool Result", id="bottom_panel_title")
            yield RichLog(id="tool_result_log", wrap=True, markup=True, highlight=False, auto_scroll=True)
        with Vertical(id="input_container"):
            with Horizontal(id="input_row"):
                yield ChatInput(id="chat_input")
                yield Button("Send", id="send_button")
            yield Static(
                "Enter newline · Ctrl+O exit · /help",
                id="input_hint",
            )

    def on_mount(self):
        self.config = load_config()
        self.chat_engine.config = self.config
        setup_logger(self.project_path, self.config.ai.debug_mode)
        self._update_sidebar()
        self._update_runtime_status({"agent": "-", "model": "-", "state": "idle"})

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
            model_info.update(
                f"[bold]{active_model.name}[/bold]\n"
                f"{provider_label}\n"
                f"max:{active_model.max_tokens}"
            )
        else:
            model_info.update("[bold yellow]none[/bold yellow]\n-\n-")

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
            "Ctrl+O exit\n"
            "Up/Down history\n"
            "/help commands"
        )

    def _add_user_message(self, content: str):
        self.chat_engine.add_user_message(content)
        log = self.query_one("#messages_log", RichLog)
        log.write("")
        log.write(f"[bold #4da6ff]> {content}[/bold #4da6ff]")
        log.write("")

    def _add_ai_message(self, content: str, thinking: Optional[str] = None):
        log = self.query_one("#messages_log", RichLog)

        if thinking and self.config.ai.think_mode:
            if self.config.ai.think_fold:
                log.write(f"[#888888]Thinking... (use /setting think_fold=false to expand)[/#888888]")
            else:
                log.write(f"[#{self.config.ui.think_color}]{thinking}[/#{self.config.ui.think_color}]")
            log.write("")

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
                self._render_code(log, part["content"], part.get("language"))

        log.write("")

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
            display = result[:2000] + "\n... (output truncated)" if len(result) > 2000 else result
            for line in display.split("\n"):
                log.write(f"[#888888]{line}[/#888888]")
        log.write("")

        bottom_panel = self.query_one("#bottom_panel", Vertical)
        bottom_panel.display = True
        tool_log = self.query_one("#tool_result_log", RichLog)
        tool_log.clear()
        tool_log.write(f"[bold #58a6ff][{tool_name}][/bold #58a6ff]")
        display = result[:2000] + "\n... (output truncated)" if len(result) > 2000 else result
        for line in display.split("\n"):
            tool_log.write(f"[#888888]{line}[/#888888]")

    def _render_diff(self, log: RichLog, diff: str):
        log.write("")
        log.write("[bold #e0e0e0]--- diff[/bold #e0e0e0]")
        for line in diff.split("\n"):
            if line.startswith("+"):
                log.write(f"[bold #3fb950]{line}[/bold #3fb950]")
            elif line.startswith("-"):
                log.write(f"[bold #f85149]{line}[/bold #f85149]")
            elif line.startswith("@@"):
                log.write(f"[#888888]{line}[/#888888]")
            else:
                log.write(f"[#aaaaaa]{line}[/#aaaaaa]")
        log.write("[bold #e0e0e0]---[/bold #e0e0e0]")
        log.write("")

    def _render_code(self, log: RichLog, code: str, lang: Optional[str] = None):
        log.write("")
        if lang:
            try:
                syntax = Syntax(code, lang, theme="monokai", line_numbers=False, word_wrap=True)
                log.write(syntax)
            except Exception:
                # 语言无法识别时回退到普通文本
                log.write(f"[bold #888888]--- {lang}[/bold #888888]")
                for line in code.split("\n"):
                    log.write(f"[#e0e0e0]{line}[/#e0e0e0]")
        else:
            log.write(f"[bold #888888]--- code[/bold #888888]")
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
        """显示确认对话框并等待用户确认."""
        log_debug(f"Showing confirmation dialog: {title} - {content[:100]}")
        dialog = ConfirmationDialog(
            title=title,
            content=content,
            content_type=content_type,
            confirm_label=confirm_label,
            cancel_label="取消",
        )
        try:
            result = await self.app.push_screen_wait(dialog)
            log_debug(f"Confirmation dialog result: {result}")
            return result
        except Exception as e:
            log_debug(f"Confirmation dialog error: {type(e).__name__}: {e}")
            return False

    def _build_callbacks(self) -> ChatCallbacks:
        """构建聊天引擎回调."""
        return ChatCallbacks(
            add_system_message=self._add_system_message,
            add_ai_message=self._add_ai_message,
            add_tool_result=self._add_tool_result,
            confirm_action=self._confirm_action,
            show_diff_preview=lambda diff: self._render_diff(
                self.query_one("#messages_log", RichLog), diff
            ),
        )

    def _on_chat_send(self, content: str):
        active_model = get_active_model(self.config)
        if not active_model:
            self._add_system_message("[bold yellow]No model selected.[/bold yellow] Use /model to configure.")
            return
        if not active_model.api_key:
            self._add_system_message("[bold yellow]No API key configured.[/bold yellow] Use /model to edit.")
            return
        if self.config.ai.agent_mode:
            self.run_worker(self._run_agent_cluster({"request": content}))
        else:
            self.run_worker(self.chat_engine.process_message(content, self._build_callbacks()))

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
            "undo": self._undo_last_change,
            "git_commit": self._git_commit,
            "show_status": self._show_status,
            "run_command": self._run_command,
            "agent_execute": self._run_agent_cluster,
            "show_about": self._show_about,
            "exit": self._exit,
        }
        handler = handlers.get(action)
        if handler:
            result = handler(data) if data else handler()
            if asyncio.iscoroutine(result):
                self.run_worker(result)

    def _show_settings(self):
        ai = self.config.ai
        lines = [
            "Settings:", "-" * 40,
            f"  stream:                   {ai.stream}",
            f"  think_mode:               {ai.think_mode}",
            f"  think_fold:               {ai.think_fold}",
            f"  temperature:              {ai.temperature}",
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

    def _clear_chat(self):
        self.chat_engine.clear_history()
        log = self.query_one("#messages_log", RichLog)
        log.clear()
        self._add_system_message("Chat cleared.")

    def _undo_last_change(self):
        self._add_system_message("Undo not yet implemented")

    def _git_commit(self, data: Dict):
        message = data.get("message", "Hakimi update")
        if git_utils.is_git_repo(str(self.project_path)):
            files = [f for _, f in git_utils.get_git_status(str(self.project_path))]
            if files:
                git_utils.git_add(str(self.project_path), files)
                git_utils.git_commit(str(self.project_path), message)
                self._add_system_message(f"[bold green]Committed: {message}[/bold green]")
            else:
                self._add_system_message("No changes to commit")
        else:
            self._add_system_message("Not a git repository")
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
