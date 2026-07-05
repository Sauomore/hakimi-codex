"""主工作界面 - Claude Code 风格布局."""

import asyncio
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Input, RichLog
from textual.reactive import reactive
from textual.worker import Worker, get_current_worker

from rich.markdown import Markdown

from ..core.models import ModelConfig, ProviderType
from ..core.config import AppConfig, get_active_model, add_model, remove_model, load_config, set_active_model
from ..core.llm_client import LLMClient
from ..core import git_utils
from ..core.tools import ToolExecutor, ToolResultStatus
from ..core.settings_manager import Settings, load_settings, save_settings
from ..core.command_handler import CommandHandler, CommandResult


class MainScreen(Screen):
    
    CSS = """
    MainScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: #0a0a0a;
    }
    
    #status_bar {
        height: 1;
        background: #141414;
        color: #cccccc;
        padding: 0 2;
    }
    
    #messages_log {
        height: 1fr;
        background: #0a0a0a;
        color: #f0f0f0;
        border: none;
        padding: 0 1;
    }
    
    #input_container {
        height: auto;
        background: #141414;
        border-top: solid #333333;
        padding: 0 1;
    }
    
    #chat_input {
        height: auto;
        min-height: 1;
        background: #141414;
        color: #f0f0f0;
        border: none;
        padding: 0 1;
    }
    
    #input_hint {
        height: 1;
        color: #888888;
        background: #141414;
        padding: 0 2;
    }
    """
    
    app_config = reactive[AppConfig](AppConfig())
    is_processing = reactive(False)
    
    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = Path(project_path).resolve()
        self.llm_client: Optional[LLMClient] = None
        self.tool_executor = ToolExecutor(str(self.project_path))
        self.command_handler = CommandHandler()
        self.settings = load_settings()
        self.messages: List[dict] = []
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        yield Static(
            f"Hakimi Codex v0.2.2 | {self.project_path.name} | /help for commands",
            id="status_bar"
        )
        yield RichLog(id="messages_log", wrap=True, markup=True, highlight=False, auto_scroll=True)
        with Vertical(id="input_container"):
            yield Input(
                placeholder="Type a message or /command...",
                id="chat_input"
            )
            yield Static(
                "Ctrl+C to quit | /help for commands | /model to configure",
                id="input_hint"
            )
    
    def on_mount(self):
        self.app_config = load_config()
        self._update_status_bar()
        
        self._add_system_message("")
        self._add_system_message("██╗  ██╗ █████╗ ██╗  ██╗██╗███╗   ███╗██╗")
        self._add_system_message("██║  ██║██╔══██╗██║ ██╔╝██║████╗ ████║██║")
        self._add_system_message("███████║███████║█████╔╝ ██║██╔████╔██║██║")
        self._add_system_message("██╔══██║██╔══██║██╔═██╗ ██║██║╚██╔╝██║██║")
        self._add_system_message("██║  ██║██║  ██║██║  ██╗██║██║ ╚═╝ ██║██║")
        self._add_system_message("╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝")
        self._add_system_message("")
        self._add_system_message("Welcome to Hakimi Codex v0.2.2")
        self._add_system_message(f"Project: {self.project_path}")
        
        if self.settings.ai.auto_analyze:
            try:
                from ..core.project_analyzer import ProjectAnalyzer
                analyzer = ProjectAnalyzer(str(self.project_path))
                summary = analyzer.get_summary()
                for line in summary.split("\n"):
                    if line.strip():
                        self._add_system_message(line)
            except Exception:
                pass
        
        active_model = get_active_model(self.app_config)
        if active_model:
            self._add_system_message(f"Active model: {active_model.name}")
        else:
            self._add_system_message("[bold yellow]No model configured.[/bold yellow] Type /model add <model_id> <api_key> [provider]")
            self._add_system_message("Example: /model add deepseek-v3 sk-xxx deepseek")
        
        self._add_system_message("Type /help for all commands")
    
    def _update_status_bar(self):
        status = self.query_one("#status_bar", Static)
        active_model = get_active_model(self.app_config)
        model_name = active_model.name if active_model else "none"
        
        branch = ""
        if git_utils.is_git_repo(str(self.project_path)):
            branch = git_utils.get_git_branch(str(self.project_path))
            if branch:
                branch = f" | git:{branch}"
        
        status.update(
            f"Hakimi v0.2.2 | {self.project_path.name} | model:{model_name}{branch} | /help"
        )
    
    def _add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        log = self.query_one("#messages_log", RichLog)
        log.write("")
        log.write(f"[bold #4da6ff]> {content}[/bold #4da6ff]")
        log.write("")
    
    def _add_ai_message(self, content: str, thinking: Optional[str] = None):
        self.messages.append({"role": "assistant", "content": content, "thinking": thinking})
        log = self.query_one("#messages_log", RichLog)

        if thinking and self.settings.ai.think_mode:
            think_lines = thinking.strip().split("\n")
            if self.settings.ai.think_fold:
                preview_lines = think_lines[:self.settings.ai.think_lines]
                preview = "\n".join(preview_lines)
                remaining = len(think_lines) - self.settings.ai.think_lines
                if remaining > 0:
                    preview += f"\n... ({remaining} more lines, use /setting think_fold=false to expand)"
                log.write(f"[#{self.settings.ui.think_color}]{preview}[/#{self.settings.ui.think_color}]")
            else:
                log.write(f"[#{self.settings.ui.think_color}]{thinking}[/#{self.settings.ui.think_color}]")
            log.write("")
        
        parts = self._parse_content(content)
        for part in parts:
            if part["type"] == "text":
                if self.settings.ai.markdown_render:
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
        log.write(f"[#aaaaaa]{content}[/#aaaaaa]")
    
    def _add_tool_result(self, tool_name: str, result: str):
        if not self.settings.ai.show_tool_results:
            return
        log = self.query_one("#messages_log", RichLog)
        log.write("")
        
        line_count = result.count("\n") + 1
        char_count = len(result)
        
        if self.settings.ai.tool_results_fold:
            log.write(f"[bold #58a6ff][{tool_name}][/bold #58a6ff] [#888888]({line_count} lines, {char_count} chars) [use /setting tool_results_fold=false to expand][/#888888]")
        else:
            log.write(f"[bold #58a6ff][{tool_name}][/bold #58a6ff]")
            display = result[:2000] + "\n... (output truncated)" if len(result) > 2000 else result
            for line in display.split("\n"):
                log.write(f"[#888888]{line}[/#888888]")
        log.write("")
    
    def _parse_content(self, content: str) -> List[Dict[str, Any]]:
        parts = []
        remaining = content
        
        while remaining:
            diff_match = re.search(r'```diff\n(.*?)```', remaining, re.DOTALL)
            code_match = re.search(r'```(\w+)?\n(.*?)```', remaining, re.DOTALL)
            
            matches = []
            if diff_match:
                matches.append(("diff", diff_match))
            if code_match:
                matches.append(("code", code_match))
            
            if not matches:
                parts.append({"type": "text", "content": remaining.strip()})
                break
            
            matches.sort(key=lambda x: x[1].start())
            block_type, match = matches[0]
            
            if match.start() > 0:
                text = remaining[:match.start()].strip()
                if text:
                    parts.append({"type": "text", "content": text})
            
            if block_type == "diff":
                parts.append({"type": "diff", "content": match.group(1)})
            elif block_type == "code":
                lang = match.group(1) or ""
                parts.append({"type": "code", "content": match.group(2), "language": lang})
            
            remaining = remaining[match.end():]
        
        return parts
    
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
        log.write(f"[bold #888888]--- {lang or 'code'}[/bold #888888]")
        for line in code.split("\n"):
            log.write(f"[#e0e0e0]{line}[/#e0e0e0]")
        log.write("[bold #888888]---[/bold #888888]")
        log.write("")
    
    def _on_chat_send(self, content: str):
        active_model = get_active_model(self.app_config)
        if not active_model:
            self._add_system_message("[bold yellow]No model selected.[/bold yellow] Use /model to configure.")
            return
        if not active_model.api_key:
            self._add_system_message("[bold yellow]No API key configured.[/bold yellow] Use /model to edit.")
            return
        self.run_worker(self._process_chat_message(content))
    
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
            "exit": self._exit,
        }
        handler = handlers.get(action)
        if handler:
            handler(data) if data else handler()
    
    def _show_settings(self):
        ai = self.settings.ai
        lines = [
            "Settings:", "-" * 40,
            f"  stream:          {ai.stream}",
            f"  think_mode:      {ai.think_mode}",
            f"  think_fold:      {ai.think_fold}",
            f"  temperature:     {ai.temperature}",
            f"  show_tool_results: {ai.show_tool_results}",
            f"  tool_results_fold: {ai.tool_results_fold}",
            f"  markdown_render: {ai.markdown_render}",
            f"  auto_analyze:    {ai.auto_analyze}",
            "", "Usage: /setting key=value",
        ]
        self._add_system_message("\n".join(lines))
    
    def _update_setting(self, data: Dict):
        key = data.get("key")
        value = data.get("value")
        if key == "stream":
            self.settings.ai.stream = value
        elif key == "think_mode":
            self.settings.ai.think_mode = value
        elif key == "think_fold":
            self.settings.ai.think_fold = value
        elif key == "temperature":
            self.settings.ai.temperature = value
        elif key == "show_tool_results":
            self.settings.ai.show_tool_results = value
        elif key == "tool_results_fold":
            self.settings.ai.tool_results_fold = value
        elif key == "markdown_render":
            self.settings.ai.markdown_render = value
        elif key == "auto_analyze":
            self.settings.ai.auto_analyze = value
        save_settings(self.settings)
        self._add_system_message(f"Setting updated: {key} = {value}")
    
    def _show_setting(self, data: Dict):
        self._add_system_message(f"{data.get('key')} = ...")
    
    def _show_models(self):
        lines = ["Models:", "-" * 40]
        for m in self.app_config.models:
            active = "* " if m.id == self.app_config.active_model_id else "  "
            lines.append(f"  {active}{m.name} ({m.provider})")
        lines.append(""); lines.append("Use /model select <id>")
        self._add_system_message("\n".join(lines))
    
    def _select_model(self, data: Dict):
        model_id = data.get("id")
        if set_active_model(self.app_config, model_id):
            active = get_active_model(self.app_config)
            if active:
                self._add_system_message(f"Model activated: [bold]{active.name}[/bold]")
                self.llm_client = LLMClient(active)
                self._update_status_bar()
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
        
        api_base = None
        if provider == ProviderType.DEEPSEEK:
            api_base = "https://api.deepseek.com/v1"
        elif provider == ProviderType.OPENAI:
            api_base = None
        elif provider == ProviderType.ANTHROPIC:
            api_base = "https://api.anthropic.com/v1"
        elif provider == ProviderType.GOOGLE:
            api_base = "https://generativelanguage.googleapis.com/v1beta"
        elif provider == ProviderType.MISTRAL:
            api_base = "https://api.mistral.ai/v1"
        elif provider == ProviderType.OLLAMA:
            api_base = "http://localhost:11434/v1"
        elif provider == ProviderType.OPENROUTER:
            api_base = "https://openrouter.ai/api/v1"
        
        model = ModelConfig(
            id=model_id, name=name, provider=provider, model_id=model_id,
            api_key=api_key, api_base=api_base, temperature=0.7,
            max_tokens=4096, context_window=8192, enabled=True, is_default=False,
        )
        add_model(self.app_config, model)
        self._add_system_message(f"[bold green]Model added: {name} ({provider.value})[/bold green]")
        self._add_system_message(f"Use /model select {model_id} to activate")
    
    def _on_model_delete(self, data: Dict):
        model_id = data.get("id")
        if remove_model(self.app_config, model_id):
            self._add_system_message(f"[bold yellow]Model removed: {model_id}[/bold yellow]")
    
    def _add_file_to_context(self, data: Dict):
        file_path = data.get("path")
        result = self.tool_executor.read_file(file_path)
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
        self.messages = []
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
    
    def _show_status(self):
        lines = ["Status:", "-" * 40]
        if git_utils.is_git_repo(str(self.project_path)):
            branch = git_utils.get_git_branch(str(self.project_path))
            files = git_utils.get_git_status(str(self.project_path))
            lines.append(f"  Git branch: {branch}")
            lines.append(f"  Changes: {len(files)}")
        active = get_active_model(self.app_config)
        if active:
            lines.append(f"  Model: {active.name}")
        lines.append(f"  Project: {self.project_path}")
        self._add_system_message("\n".join(lines))
    
    def _run_command(self, data: Dict):
        command = data.get("command")
        result = self.tool_executor.execute_command(command)
        if result.status == ToolResultStatus.SUCCESS:
            self._add_tool_result(f"$ {command}", result.output)
        else:
            self._add_tool_result(f"$ {command} (exit {result.exit_code})", result.output)

    def _exit(self):
        if self.llm_client:
            asyncio.create_task(self.llm_client.close())
        self.app.exit()

    async def _process_chat_message(self, content: str):
        worker = get_current_worker()
        active_model = get_active_model(self.app_config)
        if not active_model:
            return

        if not self.llm_client or self.llm_client.model.id != active_model.id:
            if self.llm_client:
                await self.llm_client.close()
            self.llm_client = LLMClient(active_model)

        self.is_processing = True
        self._update_status_bar()

        try:
            max_rounds = 10
            for round_num in range(max_rounds):
                api_messages = [m for m in self.messages if m["role"] in ("user", "assistant")]
                system_prompt = self._build_system_prompt()
                full_response = ""
                thinking_content = ""

                log = self.query_one("#messages_log", RichLog)
                log.write("")
                log.write("[#888888]Thinking...[/#888888]")
                

                async for chunk in self.llm_client.chat(api_messages, system_prompt=system_prompt, stream=self.settings.ai.stream):
                    if worker.is_cancelled:
                        break
                    full_response += chunk

                if worker.is_cancelled:
                    break

                # Extract thinking content
                while True:
                    idx = full_response.find("<thinking>")
                    if idx == -1:
                        break
                    end_idx = full_response.find("</thinking>", idx + len("<thinking>"))
                    if end_idx == -1:
                        thinking_content += full_response[idx + len("<thinking>"):]
                        full_response = full_response[:idx]
                        break
                    thinking_content += full_response[idx + len("<thinking>"):end_idx]
                    full_response = full_response[:idx] + full_response[end_idx + len("</thinking>"):]

                tool_results = await self._execute_tool_calls(full_response)

                if not tool_results:
                    text_only = re.sub(r'```tool\s*\n.*?\n```', '', full_response, flags=re.DOTALL).strip()
                    if self._is_transitional_response(text_only) and round_num < max_rounds - 1:
                        self.messages.append({"role": "assistant", "content": full_response})
                        self._add_system_message(f"[#888888]> {text_only}[/#888888]")
                        self.messages.append({
                            "role": "user",
                            "content": "Please provide the complete analysis or answer based on the data already provided. Do not use transitional phrases."
                        })
                        continue

                    self._add_ai_message(full_response, thinking_content if thinking_content else None)
                    break
                else:
                    self.messages.append({"role": "assistant", "content": full_response})
                    text_only = re.sub(r'```tool\s*\n.*?\n```', '', full_response, flags=re.DOTALL).strip()
                    if text_only:
                        self._add_system_message(f"[#888888]> {text_only}[/#888888]")
                    for tr in tool_results:
                        self.messages.append({
                            "role": "user",
                            "content": f"[Tool '{tr['tool_name']}' result]\n```\n{tr['output']}\n```"
                        })

            if round_num >= max_rounds - 1:
                self._add_system_message("[bold yellow]Max tool rounds reached (10). Stopping.[/bold yellow]")

        except Exception as e:
            self._add_system_message(f"[bold red]Error: {str(e)}[/bold red]")
        finally:
            self.is_processing = False
            self._update_status_bar()

    def _build_system_prompt(self) -> str:
        return f"""You are Hakimi Codex, a professional coding assistant.

Project: {self.project_path.name}
Path: {self.project_path}

## CRITICAL RULES

1. Use Chinese for responses, English for code comments
2. Be concise and professional
3. Show code changes in diff format using ```diff blocks
4. When modifying files, show the full content using ```code blocks
5. Use tools by returning JSON in ```tool blocks

## MOST IMPORTANT: TOOL RESULT HANDLING

After receiving tool results (file contents, directory listings, command output, etc.), you MUST immediately analyze the data and provide your complete analysis or answer. 

DO NOT say things like "let me check", "let me confirm", "我来确认一下", "让我看看", "让我确认一下" or similar transitional phrases when the tool results already contain the data. The user is waiting for your analysis, not for you to ask for more time.

If the data is sufficient, provide the full analysis right away. If you genuinely need more data, call another tool immediately in the same response.

## Available Tools

```tool
{{"tool": "execute_command", "parameters": {{"command": "..."}}}}
```

```tool
{{"tool": "read_file", "parameters": {{"file_path": "..."}}}}
```

```tool
{{"tool": "write_file", "parameters": {{"file_path": "...", "content": "..."}}}}
```

```tool
{{"tool": "list_directory", "parameters": {{"dir_path": "."}}}}
```

```tool
{{"tool": "search_files", "parameters": {{"pattern": "..."}}}}
```
"""
    
    def _is_transitional_response(self, text: str) -> bool:
        if not text or len(text) < 10:
            return False
        
        text_lower = text.lower()

        transitional_keywords = [
            "让我看看", "让我确认", "让我检查", "让我确认一下", "让我检查下",
            "我来确认", "我来检查", "我来确认一下", "我来检查下",
            "需要确认", "需要确认一下", "需要检查", "需要检查下",
            "确认一下", "检查下", "检查", "确认",
            "让我先", "我先",
            "现在让我", "现在我来", "现在我",
            "先确认", "先检查", "先查看",
            "了解一下", "看一下",
            "let me check", "let me confirm", "let me verify",
            "let me take a look", "let me see", "let me review",
            "i will check", "i will confirm", "i will verify",
            "i need to check", "i need to confirm", "i need to verify",
            "need to check", "need to confirm", "need to verify",
            "checking", "confirming", "verifying",
            "taking a look", "taking a look at",
            "reviewing", "looking at",
            "hold on", "one moment", "just a moment",
            "wait a moment", "give me a moment",
            "looking into", "going to check", "going to confirm",
            "let me review", "i will review", "need to review",
        ]

        has_transitional = any(kw in text_lower for kw in transitional_keywords)
        
        if not has_transitional:
            return False

        if len(text) < 150:
            return True

        if len(text) <= 300:
            has_analysis = any(kw in text_lower for kw in [
                "分析", "总结", "结论", "建议", "方案", "实现",
                "修改", "优化", "问题", "原因", "方法", "步骤", "结果",
                "analysis", "summary", "conclusion", "recommendation",
                "solution", "implementation", "issue", "cause", "result",
            ])
            has_code_blocks = "```" in text or "diff" in text_lower
            
            if has_analysis or has_code_blocks:
                return False
            return True

        return False

    async def _execute_tool_calls(self, content: str) -> List[Dict[str, str]]:
        matches = list(re.finditer(r'```tool\s*\n(.*?)\n```', content, re.DOTALL))
        if not matches:
            return []

        results = []
        for match in matches:
            try:
                tool_call = json.loads(match.group(1).strip())
                tool_name = tool_call.get("tool")
                parameters = tool_call.get("parameters", {})

                self._add_tool_result(
                    f"tool: {tool_name}",
                    f"parameters: {json.dumps(parameters, indent=2, ensure_ascii=False)}"
                )

                # For write_file, show diff preview before applying
                if tool_name == "write_file":
                    file_path = parameters.get("file_path", "")
                    new_content = parameters.get("content", "")
                    old_content = ""

                    # Read existing file content if exists
                    read_result = self.tool_executor.read_file(file_path)
                    if read_result.status == ToolResultStatus.SUCCESS:
                        old_content = read_result.output

                    # Show diff preview if file exists and has changes
                    if old_content and old_content != new_content:
                        self._add_system_message(f"[bold yellow]Preview changes to {file_path}:[/bold yellow]")
                        diff = self._generate_diff(old_content, new_content, file_path)
                        log = self.query_one("#messages_log", RichLog)
                        self._render_diff(log, diff)
                        self._add_system_message("[dim]Applying changes...[/dim]")

                result = self.tool_executor.execute_tool(tool_name, parameters)
                self._add_tool_result(f"result: {tool_name}", result.output)

                results.append({
                    "tool_name": tool_name,
                    "output": result.output,
                    "status": "success" if result.status == ToolResultStatus.SUCCESS else "error"
                })
            except json.JSONDecodeError as e:
                self._add_system_message(f"[bold red]Tool parse error: {e}[/bold red]")

        return results

    def _generate_diff(self, old_content: str, new_content: str, file_path: str) -> str:
        """Generate unified diff between old and new content."""
        import difflib
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        # Ensure lines end with newline for proper diff
        if old_lines and not old_lines[-1].endswith('\n'):
            old_lines[-1] += '\n'
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=''
        )
        return ''.join(diff)

    
    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "chat_input":
            self._process_input()
    
    def _process_input(self):
        input_widget = self.query_one("#chat_input", Input)
        content = input_widget.value.strip()
        if not content or self.is_processing:
            return
        input_widget.value = ""
        
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
