"""主工作界面 - Claude Code 风格布局."""

import asyncio
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Static, Input, RichLog
from textual.reactive import reactive
from textual.worker import Worker, get_current_worker

from ..core.models import ModelConfig
from ..core.config import AppConfig, get_active_model, add_model, remove_model, load_config, set_active_model
from ..core.llm_client import LLMClient
from ..core import git_utils
from ..core.tools import ToolExecutor, ToolResultStatus
from ..core.settings_manager import Settings, load_settings, save_settings
from ..core.command_handler import CommandHandler, CommandResult
from .model_edit_dialog import ModelEditDialog


class MainScreen(Screen):
    """Claude Code 风格主界面."""
    
    CSS = """
    MainScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: #0d1117;
    }
    
    /* 顶部状态栏 */
    #status_bar {
        height: 1;
        background: #161b22;
        color: #8b949e;
        content-align: left middle;
        padding: 0 2;
        text-style: none;
    }
    
    /* 消息区域 */
    #messages_container {
        height: 1fr;
        background: #0d1117;
        border: none;
        scrollbar-color: #30363d;
        scrollbar-background: #0d1117;
    }
    
    /* 输入区域 */
    #input_container {
        height: auto;
        background: #161b22;
        border-top: solid #30363d;
        padding: 0 1;
    }
    
    #input_container Input {
        height: auto;
        min-height: 1;
        background: #0d1117;
        color: #e6edf3;
        border: none;
        padding: 0 1;
    }
    
    #input_container Input:focus {
        border: none;
    }
    
    #input_hint {
        height: 1;
        color: #484f58;
        text-style: dim;
        padding: 0 2;
    }
    
    /* 消息样式 */
    .user-msg {
        height: auto;
        padding: 0 2;
        margin: 1 0;
        color: #58a6ff;
    }
    
    .ai-msg {
        height: auto;
        padding: 0 2;
        margin: 1 0;
        color: #e6edf3;
    }
    
    .system-msg {
        height: auto;
        padding: 0 2;
        margin: 0;
        color: #484f58;
        text-style: dim;
    }
    
    .tool-msg {
        height: auto;
        padding: 0 2;
        margin: 0;
        color: #8b949e;
        background: #161b22;
        border-left: solid #30363d;
    }
    
    /* Diff 内联样式 */
    .diff-block {
        height: auto;
        margin: 1 0;
        padding: 0;
    }
    
    .diff-header {
        height: 1;
        background: #161b22;
        color: #e6edf3;
        padding: 0 2;
        text-style: bold;
    }
    
    .diff-line-added {
        height: auto;
        color: #3fb950;
        background: #0f2d1f;
        padding: 0 2;
    }
    
    .diff-line-removed {
        height: auto;
        color: #f85149;
        background: #3d1010;
        padding: 0 2;
    }
    
    .diff-line-context {
        height: auto;
        color: #8b949e;
        padding: 0 2;
    }
    
    /* 代码块 */
    .code-block {
        height: auto;
        margin: 1 0;
        background: #161b22;
        border: solid #30363d;
    }
    
    .code-header {
        height: 1;
        background: #21262d;
        color: #8b949e;
        padding: 0 2;
        text-style: bold;
    }
    
    .code-content {
        height: auto;
        padding: 0 2;
        color: #e6edf3;
    }
    
    /* 工具调用 */
    .tool-call {
        height: auto;
        margin: 1 0;
        background: #161b22;
        border-left: solid #58a6ff;
    }
    
    .tool-call-header {
        height: 1;
        color: #58a6ff;
        padding: 0 2;
        text-style: bold;
    }
    
    .tool-call-content {
        height: auto;
        padding: 0 2;
        color: #8b949e;
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
        """组装 Claude Code 风格界面."""
        # 顶部状态栏
        yield Static(
            f"Hakimi Codex v0.2.0 | {self.project_path.name} | /help for commands",
            id="status_bar"
        )
        
        # 消息区域
        yield ScrollableContainer(id="messages_container")
        
        # 底部输入区域
        with Vertical(id="input_container"):
            yield Input(
                placeholder="Type a message or /command...",
                id="chat_input"
            )
            yield Static(
                "Ctrl+C to quit | /help for commands | /model to switch model",
                id="input_hint"
            )
    
    def on_mount(self):
        """挂载后初始化."""
        self.app_config = load_config()
        self._update_status_bar()
        
        # 显示欢迎信息
        self._add_system_message(f"Project: {self.project_path}")
        
        # 自动分析项目
        if self.settings.ai.auto_analyze:
            try:
                from ..core.project_analyzer import ProjectAnalyzer
                analyzer = ProjectAnalyzer(str(self.project_path))
                summary = analyzer.get_summary()
                self._add_system_message(summary)
            except Exception:
                pass
        
        active_model = get_active_model(self.app_config)
        if active_model:
            self._add_system_message(f"Model: {active_model.name}")
        else:
            self._add_system_message("No model selected. Use /model to configure.")
        
        self._add_system_message("Type /help for available commands")
    
    def _update_status_bar(self):
        """更新状态栏."""
        status = self.query_one("#status_bar", Static)
        active_model = get_active_model(self.app_config)
        model_name = active_model.name if active_model else "none"
        
        branch = ""
        if git_utils.is_git_repo(str(self.project_path)):
            branch = git_utils.get_git_branch(str(self.project_path))
            if branch:
                branch = f" | git:{branch}"
        
        status.update(
            f"Hakimi Codex v0.2.0 | {self.project_path.name} | model:{model_name}{branch} | /help"
        )
    
    def _add_user_message(self, content: str):
        """添加用户消息."""
        self.messages.append({"role": "user", "content": content})
        container = self.query_one("#messages_container", ScrollableContainer)
        msg = Static(f"> {content}", classes="user-msg")
        container.mount(msg)
        self._scroll_to_bottom()
    
    def _add_ai_message(self, content: str, thinking: Optional[str] = None):
        """添加 AI 消息，解析并渲染 diff 和代码块."""
        self.messages.append({"role": "assistant", "content": content, "thinking": thinking})
        container = self.query_one("#messages_container", ScrollableContainer)
        
        # 解析内容，分离 diff 块和代码块
        parts = self._parse_content(content)
        
        for part in parts:
            if part["type"] == "text":
                msg = Static(part["content"], classes="ai-msg")
                container.mount(msg)
            elif part["type"] == "diff":
                self._render_diff(container, part["content"], part.get("filename"))
            elif part["type"] == "code":
                self._render_code_block(container, part["content"], part.get("language"))
        
        self._scroll_to_bottom()
    
    def _add_system_message(self, content: str):
        """添加系统消息."""
        container = self.query_one("#messages_container", ScrollableContainer)
        msg = Static(content, classes="system-msg")
        container.mount(msg)
        self._scroll_to_bottom()
    
    def _add_tool_result(self, tool_name: str, result: str):
        """添加工具执行结果."""
        if not self.settings.ai.show_tool_results:
            return
        container = self.query_one("#messages_container", ScrollableContainer)
        
        tool_widget = Vertical(classes="tool-call")
        tool_widget.mount(Static(f"{tool_name}", classes="tool-call-header"))
        
        # 截断过长的输出
        display_result = result
        if len(result) > 2000:
            display_result = result[:2000] + "\n\n... (output truncated)"
        
        tool_widget.mount(Static(display_result, classes="tool-call-content"))
        container.mount(tool_widget)
        self._scroll_to_bottom()
    
    def _parse_content(self, content: str) -> List[Dict[str, Any]]:
        """解析内容，分离 diff 和代码块."""
        parts = []
        
        # 匹配 diff 块
        diff_pattern = r'```diff\n(.*?)```'
        code_pattern = r'```(\w+)?\n(.*?)```'
        
        # 简单分割：先找 diff 和 code 块
        remaining = content
        
        while remaining:
            # 找 diff 块
            diff_match = re.search(r'```diff\n(.*?)```', remaining, re.DOTALL)
            code_match = re.search(r'```(\w+)?\n(.*?)```', remaining, re.DOTALL)
            
            # 找到最近的块
            matches = []
            if diff_match:
                matches.append(("diff", diff_match))
            if code_match:
                matches.append(("code", code_match))
            
            if not matches:
                # 没有更多块
                parts.append({"type": "text", "content": remaining.strip()})
                break
            
            # 选择最早的匹配
            matches.sort(key=lambda x: x[1].start())
            block_type, match = matches[0]
            
            # 添加前面的文本
            if match.start() > 0:
                text = remaining[:match.start()].strip()
                if text:
                    parts.append({"type": "text", "content": text})
            
            # 添加块
            if block_type == "diff":
                parts.append({"type": "diff", "content": match.group(1)})
            elif block_type == "code":
                language = match.group(1) or ""
                parts.append({"type": "code", "content": match.group(2), "language": language})
            
            remaining = remaining[match.end():]
        
        return parts
    
    def _render_diff(self, container: ScrollableContainer, diff_content: str, filename: Optional[str] = None):
        """渲染 diff 块."""
        diff_widget = Vertical(classes="diff-block")
        
        header = filename or "diff"
        diff_widget.mount(Static(f"--- {header}", classes="diff-header"))
        
        for line in diff_content.split("\n"):
            if line.startswith("+"):
                diff_widget.mount(Static(line, classes="diff-line-added"))
            elif line.startswith("-"):
                diff_widget.mount(Static(line, classes="diff-line-removed"))
            elif line.startswith("@@"):
                diff_widget.mount(Static(line, classes="diff-line-context"))
            else:
                diff_widget.mount(Static(line, classes="diff-line-context"))
        
        container.mount(diff_widget)
    
    def _render_code_block(self, container: ScrollableContainer, code: str, language: Optional[str] = None):
        """渲染代码块."""
        code_widget = Vertical(classes="code-block")
        code_widget.mount(Static(language or "code", classes="code-header"))
        code_widget.mount(Static(code, classes="code-content"))
        container.mount(code_widget)
    
    def _scroll_to_bottom(self):
        """滚动到底部."""
        container = self.query_one("#messages_container", ScrollableContainer)
        container.scroll_end(animate=False)
    
    def _on_chat_send(self, content: str):
        """处理聊天发送."""
        active_model = get_active_model(self.app_config)
        
        if not active_model:
            self._add_system_message("No model selected. Use /model to configure.")
            return
        
        if not active_model.api_key:
            self._add_system_message("No API key configured. Use /model to edit.")
            return
        
        self.run_worker(self._process_chat_message(content))
    
    def _on_command(self, action: str, data: Optional[Dict]):
        """处理指令."""
        handlers = {
            "show_settings": self._show_settings,
            "set_setting": self._update_setting,
            "get_setting": self._show_setting,
            "model_list": self._show_models,
            "model_select": self._select_model,
            "model_add": self._on_model_add,
            "model_edit": self._on_model_edit,
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
            if data:
                handler(data)
            else:
                handler()
    
    def _show_settings(self):
        """显示设置."""
        ai = self.settings.ai
        ui = self.settings.ui
        
        lines = [
            "Settings:",
            "-" * 40,
            f"  stream:          {ai.stream}",
            f"  think_mode:      {ai.think_mode}",
            f"  think_fold:      {ai.think_fold}",
            f"  temperature:     {ai.temperature}",
            f"  show_tool_results: {ai.show_tool_results}",
            f"  auto_analyze:    {ai.auto_analyze}",
            "",
            "Usage: /setting key=value",
        ]
        self._add_system_message("\n".join(lines))
    
    def _update_setting(self, data: Dict):
        """更新设置."""
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
        elif key == "auto_analyze":
            self.settings.ai.auto_analyze = value
        
        save_settings(self.settings)
        self._add_system_message(f"Setting updated: {key} = {value}")
    
    def _show_setting(self, data: Dict):
        """显示单个设置."""
        key = data.get("key")
        # ...
        self._add_system_message(f"{key} = ...")
    
    def _show_models(self):
        """显示模型."""
        lines = ["Models:", "-" * 40]
        for m in self.app_config.models:
            active = "* " if m.id == self.app_config.active_model_id else "  "
            lines.append(f"  {active}{m.name} ({m.provider})")
        lines.append("")
        lines.append("Use /model select <id>")
        self._add_system_message("\n".join(lines))
    
    def _select_model(self, data: Dict):
        """选择模型."""
        model_id = data.get("id")
        if set_active_model(self.app_config, model_id):
            active = get_active_model(self.app_config)
            if active:
                self._add_system_message(f"Model: {active.name}")
                self.llm_client = LLMClient(active)
                self._update_status_bar()
        else:
            self._add_system_message(f"Model not found: {model_id}")
    
    def _on_model_add(self):
        """添加模型."""
        self.push_screen(ModelEditDialog(), self._on_model_saved)
    
    def _on_model_edit(self, data: Dict):
        """编辑模型."""
        model_id = data.get("id")
        for model in self.app_config.models:
            if model.id == model_id:
                self.push_screen(ModelEditDialog(model=model), self._on_model_saved)
                return
    
    def _on_model_delete(self, data: Dict):
        """删除模型."""
        model_id = data.get("id")
        if remove_model(self.app_config, model_id):
            self._add_system_message(f"Model removed: {model_id}")
    
    def _on_model_saved(self, result: Optional[ModelConfig]):
        """模型保存."""
        if result:
            add_model(self.app_config, result)
            self._add_system_message(f"Model saved: {result.name}")
    
    def _add_file_to_context(self, data: Dict):
        """添加文件."""
        file_path = data.get("path")
        result = self.tool_executor.read_file(file_path)
        if result.status == ToolResultStatus.SUCCESS:
            self._add_system_message(f"File loaded: {file_path}")
            # 显示文件内容预览
            preview = result.output[:500]
            if len(result.output) > 500:
                preview += "\n... (truncated)"
            self._add_tool_result(f"read_file: {file_path}", preview)
        else:
            self._add_system_message(f"Failed to load: {result.output}")
    
    def _show_diff(self, data: Optional[Dict] = None):
        """显示 diff."""
        self._add_system_message("Diff: (not implemented in chat view)")
    
    def _clear_chat(self):
        """清空聊天."""
        self.messages = []
        container = self.query_one("#messages_container", ScrollableContainer)
        for child in list(container.children):
            child.remove()
        self._add_system_message("Chat cleared.")
    
    def _undo_last_change(self):
        """撤销."""
        self._add_system_message("Undo not yet implemented")
    
    def _git_commit(self, data: Dict):
        """Git 提交."""
        message = data.get("message", "Hakimi update")
        if git_utils.is_git_repo(str(self.project_path)):
            files = [f for _, f in git_utils.get_git_status(str(self.project_path))]
            if files:
                git_utils.git_add(str(self.project_path), files)
                git_utils.git_commit(str(self.project_path), message)
                self._add_system_message(f"Committed: {message}")
            else:
                self._add_system_message("No changes to commit")
        else:
            self._add_system_message("Not a git repository")
    
    def _show_status(self):
        """显示状态."""
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
        """运行命令."""
        command = data.get("command")
        result = self.tool_executor.execute_command(command)
        
        if result.status == ToolResultStatus.SUCCESS:
            self._add_tool_result(f"$ {command}", result.output)
        else:
            self._add_tool_result(f"$ {command} (exit {result.exit_code})", result.output)
    
    def _exit(self):
        """退出."""
        if self.llm_client:
            asyncio.create_task(self.llm_client.close())
        self.app.exit()
    
    async def _process_chat_message(self, content: str):
        """处理聊天消息."""
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
        
        messages = self.messages.copy()
        api_messages = [m for m in messages if m["role"] in ("user", "assistant")]
        
        system_prompt = self._build_system_prompt()
        
        full_response = ""
        
        try:
            async for chunk in self.llm_client.chat(api_messages, system_prompt=system_prompt, stream=self.settings.ai.stream):
                if worker.is_cancelled:
                    break
                full_response += chunk
            
            if not worker.is_cancelled:
                self._add_ai_message(full_response)
                await self._check_tool_calls(full_response)
                
        except Exception as e:
            self.app.call_from_thread(self._add_system_message, f"Error: {str(e)}")
        finally:
            self.is_processing = False
            self.app.call_from_thread(self._update_status_bar)
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词."""
        return f"""You are Hakimi Codex, a professional coding assistant.

Project: {self.project_path.name}
Path: {self.project_path}

## Rules

1. Use Chinese for responses, English for code comments
2. Be concise and professional
3. Show code changes in diff format using ```diff blocks
4. When modifying files, show the full content using ```code blocks
5. Use tools by returning JSON in ```tool blocks

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
    
    async def _check_tool_calls(self, content: str):
        """检查并执行工具调用."""
        pattern = r'```tool\s*\n(.*?)\n```'
        matches = list(re.finditer(pattern, content, re.DOTALL))
        
        if not matches:
            return
        
        for match in matches:
            try:
                tool_call = json.loads(match.group(1).strip())
                tool_name = tool_call.get("tool")
                parameters = tool_call.get("parameters", {})
                
                self.app.call_from_thread(
                    self._add_tool_result,
                    f"tool: {tool_name}",
                    f"parameters: {json.dumps(parameters, indent=2, ensure_ascii=False)}"
                )
                
                result = self.tool_executor.execute_tool(tool_name, parameters)
                
                self.app.call_from_thread(
                    self._add_tool_result,
                    f"result: {tool_name}",
                    result.output
                )
                
            except json.JSONDecodeError as e:
                self.app.call_from_thread(
                    self._add_system_message,
                    f"Tool parse error: {e}"
                )
    
    def on_input_submitted(self, event: Input.Submitted):
        """输入提交."""
        if event.input.id == "chat_input":
            self._process_input()
    
    def _process_input(self):
        """处理输入."""
        input_widget = self.query_one("#chat_input", Input)
        content = input_widget.value.strip()
        
        if not content or self.is_processing:
            return
        
        input_widget.value = ""
        
        # 检查是否是命令
        is_cmd, cmd, args = self.command_handler.parse(content)
        
        if is_cmd:
            result = self.command_handler.handle(content)
            
            if result.message:
                if result.success:
                    self._add_system_message(result.message)
                else:
                    self._add_system_message(f"Error: {result.message}")
            
            if result.action:
                self._on_command(result.action, result.data)
        else:
            # 普通消息
            self._add_user_message(content)
            self._on_chat_send(content)
    
    def action_quit(self):
        """退出."""
        self._exit()
