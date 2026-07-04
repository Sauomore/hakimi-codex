"""主工作界面 - 简洁风格：左侧 AI 交互，右侧代码/Diff."""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Button, Header, Footer, Input, TabbedContent, TabPane
from textual.reactive import reactive
from textual.worker import Worker, get_current_worker

from ..core.models import ModelConfig
from ..core.config import AppConfig, get_active_model, add_model, remove_model, load_config, set_active_model
from ..core.llm_client import LLMClient
from ..core import git_utils
from ..core.tools import ToolExecutor, ToolResultStatus
from ..core.settings_manager import Settings, load_settings, save_settings
from ..core.command_handler import CommandHandler, CommandResult
from ..widgets.chat_panel import ChatPanel
from ..widgets.diff_panel import DiffPanel
from ..widgets.code_view import CodeViewerWidget
from .model_edit_dialog import ModelEditDialog


class MainScreen(Screen):
    """主工作界面 - 简洁双栏布局."""
    
    CSS = """
    MainScreen {
        layout: horizontal;
        width: 100%;
        height: 100%;
        background: $surface;
    }
    
    #left_panel {
        width: 55%;
        height: 100%;
        layout: vertical;
        border: solid $panel-border-color;
    }
    
    #right_panel {
        width: 45%;
        height: 100%;
        layout: vertical;
        border: solid $panel-border-color;
    }
    
    #status_bar {
        height: 1;
        background: $surface-darken-1;
        color: $text-muted;
        content-align: left middle;
        padding: 0 1;
    }
    """
    
    app_config = reactive[AppConfig](AppConfig())
    settings = reactive[Settings](Settings())
    current_project_path = reactive[str](".")
    is_processing = reactive(False)
    
    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = Path(project_path).resolve()
        self.llm_client: Optional[LLMClient] = None
        self.tool_executor = ToolExecutor(str(self.project_path))
        self.settings = load_settings()
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        """组装主界面."""
        # 左侧：AI 交互面板
        with Vertical(id="left_panel"):
            yield ChatPanel(
                on_send=self._on_chat_send,
                on_command=self._on_command,
                id="chat_panel"
            )
        
        # 右侧：代码/Diff 面板
        with Vertical(id="right_panel"):
            yield DiffPanel(id="diff_panel")
        
        # 底部状态栏
        yield Static("Hakimi Codex v0.1.0 | /help for commands", id="status_bar")
    
    def on_mount(self):
        """挂载后初始化."""
        self.app_config = load_config()
        
        # 显示项目信息
        chat = self.query_one("#chat_panel", ChatPanel)
        chat.add_system_message(f"Project: {self.project_path.name}")
        chat.add_system_message(f"Path: {self.project_path}")
        
        # 自动分析项目
        if self.settings.ai.auto_analyze:
            try:
                from ..core.project_analyzer import ProjectAnalyzer
                analyzer = ProjectAnalyzer(str(self.project_path))
                summary = analyzer.get_summary()
                chat.add_system_message(summary)
            except Exception:
                pass
        
        active_model = get_active_model(self.app_config)
        if active_model:
            chat.add_system_message(f"Model: {active_model.name}")
        else:
            chat.add_system_message("No model selected. Use /model to configure.")
        
        chat.add_system_message("Commands: /help /setting /model /file /diff /clear /run /exit")
    
    def _on_chat_send(self, content: str):
        """聊天发送回调."""
        active_model = get_active_model(self.app_config)
        
        if not active_model:
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message("No model selected. Use /model to configure.")
            return
        
        if not active_model.api_key:
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message("No API key configured. Use /model to edit.")
            return
        
        self.run_worker(self._process_chat_message(content))
    
    def _on_command(self, action: str, data: Optional[Dict]):
        """指令回调."""
        if action == "show_settings":
            self._show_settings()
        elif action == "set_setting":
            self._update_setting(data)
        elif action == "get_setting":
            self._show_setting(data)
        elif action == "model_list":
            self._show_models()
        elif action == "model_select":
            self._select_model(data)
        elif action == "model_add":
            self._on_model_add()
        elif action == "model_edit":
            self._on_model_edit(data)
        elif action == "model_delete":
            self._on_model_delete(data)
        elif action == "add_file":
            self._add_file_to_context(data)
        elif action == "show_diff":
            self._show_diff(data)
        elif action == "clear_chat":
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.clear_chat()
        elif action == "undo":
            self._undo_last_change()
        elif action == "git_commit":
            self._git_commit(data)
        elif action == "show_status":
            self._show_status()
        elif action == "run_command":
            self._run_command(data)
        elif action == "exit":
            self._exit()
    
    def _show_settings(self):
        """显示当前设置."""
        chat = self.query_one("#chat_panel", ChatPanel)
        lines = [
            "Settings:",
            "-" * 40,
        ]
        
        ui = self.settings.ui
        ai = self.settings.ai
        editor = self.settings.editor
        git = self.settings.git
        
        lines.extend([
            f"  stream:          {ai.stream}",
            f"  think_mode:      {ai.think_mode}",
            f"  think_fold:      {ai.think_fold}",
            f"  think_lines:     {ai.think_lines}",
            f"  temperature:     {ai.temperature}",
            f"  font_size:       {ui.font_size}",
            f"  theme:           {ui.theme}",
            f"  show_tool_results: {ai.show_tool_results}",
            f"  auto_analyze:    {ai.auto_analyze}",
            f"  auto_commit:     {git.auto_commit}",
            f"  tab_size:        {editor.tab_size}",
            f"  word_wrap:       {editor.word_wrap}",
        ])
        
        lines.append("")
        lines.append("Usage: /setting key=value")
        lines.append("Example: /setting temperature=0.5")
        
        chat.add_system_message("\n".join(lines))
    
    def _update_setting(self, data: Optional[Dict]):
        """更新设置."""
        if not data:
            return
        
        key = data.get("key")
        value = data.get("value")
        
        if key and value is not None:
            # 更新对应设置
            if key == "stream":
                self.settings.ai.stream = value
            elif key == "think_mode":
                self.settings.ai.think_mode = value
            elif key == "think_fold":
                self.settings.ai.think_fold = value
            elif key == "think_lines":
                self.settings.ai.think_lines = value
            elif key == "temperature":
                self.settings.ai.temperature = value
            elif key == "font_size":
                self.settings.ui.font_size = value
            elif key == "theme":
                self.settings.ui.theme = value
            elif key == "show_tool_results":
                self.settings.ai.show_tool_results = value
            elif key == "auto_analyze":
                self.settings.ai.auto_analyze = value
            
            save_settings(self.settings)
            
            # 更新 UI
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.update_settings(self.settings)
            chat.add_system_message(f"Setting updated: {key} = {value}")
    
    def _show_setting(self, data: Optional[Dict]):
        """显示单个设置."""
        if not data:
            return
        
        key = data.get("key")
        chat = self.query_one("#chat_panel", ChatPanel)
        
        # 获取当前值
        value = None
        if key == "stream":
            value = self.settings.ai.stream
        elif key == "think_mode":
            value = self.settings.ai.think_mode
        elif key == "temperature":
            value = self.settings.ai.temperature
        
        if value is not None:
            chat.add_system_message(f"{key} = {value}")
    
    def _show_models(self):
        """显示模型列表."""
        chat = self.query_one("#chat_panel", ChatPanel)
        lines = ["Models:", "-" * 40]
        
        for m in self.app_config.models:
            active = "* " if m.id == self.app_config.active_model_id else "  "
            status = "[enabled]" if m.enabled else "[disabled]"
            lines.append(f"  {active}{m.name:<20} {m.provider:<12} {status}")
        
        lines.append("")
        lines.append("Use /model select <id> to activate")
        
        chat.add_system_message("\n".join(lines))
    
    def _select_model(self, data: Optional[Dict]):
        """选择模型."""
        if not data:
            return
        
        model_id = data.get("id")
        if set_active_model(self.app_config, model_id):
            chat = self.query_one("#chat_panel", ChatPanel)
            active = get_active_model(self.app_config)
            if active:
                chat.add_system_message(f"Model activated: {active.name}")
                self.llm_client = LLMClient(active)
        else:
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message(f"Model not found: {model_id}")
    
    def _on_model_add(self):
        """添加模型."""
        self.push_screen(ModelEditDialog(), self._on_model_saved)
    
    def _on_model_edit(self, data: Optional[Dict]):
        """编辑模型."""
        if not data:
            return
        
        model_id = data.get("id")
        for model in self.app_config.models:
            if model.id == model_id:
                self.push_screen(ModelEditDialog(model=model), self._on_model_saved)
                return
    
    def _on_model_delete(self, data: Optional[Dict]):
        """删除模型."""
        if not data:
            return
        
        model_id = data.get("id")
        if remove_model(self.app_config, model_id):
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message(f"Model removed: {model_id}")
    
    def _on_model_saved(self, result: Optional[ModelConfig]):
        """模型保存回调."""
        if result:
            add_model(self.app_config, result)
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message(f"Model saved: {result.name}")
    
    def _add_file_to_context(self, data: Optional[Dict]):
        """添加文件到上下文."""
        if not data:
            return
        
        file_path = data.get("path")
        # 读取文件并在右侧显示
        result = self.tool_executor.read_file(file_path)
        
        if result.status == ToolResultStatus.SUCCESS:
            diff_panel = self.query_one("#diff_panel", DiffPanel)
            diff_panel.show_file(file_path, result.output)
            
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message(f"File loaded: {file_path}")
        else:
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message(f"Failed to load: {result.output}")
    
    def _show_diff(self, data: Optional[Dict]):
        """显示 diff."""
        file_path = data.get("file") if data else None
        
        if not file_path:
            # 显示当前文件的 diff
            diff_panel = self.query_one("#diff_panel", DiffPanel)
            if diff_panel.current_file and diff_panel.modified_content:
                diff_panel.show_diff(
                    diff_panel.current_file,
                    diff_panel.original_content,
                    diff_panel.modified_content
                )
            else:
                chat = self.query_one("#chat_panel", ChatPanel)
                chat.add_system_message("No file to diff")
        else:
            # 读取文件并显示 diff（需要知道修改后的内容）
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message(f"Diff: {file_path}")
    
    def _undo_last_change(self):
        """撤销最后一次修改."""
        chat = self.query_one("#chat_panel", ChatPanel)
        chat.add_system_message("Undo not yet implemented")
    
    def _git_commit(self, data: Optional[Dict]):
        """Git 提交."""
        message = data.get("message") if data else "Hakimi update"
        
        if git_utils.is_git_repo(str(self.project_path)):
            # 添加所有更改
            files = [f for _, f in git_utils.get_git_status(str(self.project_path))]
            if files:
                git_utils.git_add(str(self.project_path), files)
                git_utils.git_commit(str(self.project_path), message)
                chat = self.query_one("#chat_panel", ChatPanel)
                chat.add_system_message(f"Committed: {message}")
            else:
                chat = self.query_one("#chat_panel", ChatPanel)
                chat.add_system_message("No changes to commit")
        else:
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message("Not a git repository")
    
    def _show_status(self):
        """显示状态."""
        chat = self.query_one("#chat_panel", ChatPanel)
        lines = ["Status:", "-" * 40]
        
        # Git 状态
        if git_utils.is_git_repo(str(self.project_path)):
            branch = git_utils.get_git_branch(str(self.project_path))
            files = git_utils.get_git_status(str(self.project_path))
            lines.append(f"  Git branch: {branch}")
            lines.append(f"  Changes: {len(files)}")
            for status, name in files[:10]:
                lines.append(f"    [{status}] {name}")
        else:
            lines.append("  Git: not initialized")
        
        # 模型状态
        active = get_active_model(self.app_config)
        if active:
            lines.append(f"  Model: {active.name}")
        
        lines.append(f"  Project: {self.project_path}")
        
        chat.add_system_message("\n".join(lines))
    
    def _run_command(self, data: Optional[Dict]):
        """运行命令."""
        if not data:
            return
        
        command = data.get("command")
        result = self.tool_executor.execute_command(command)
        
        chat = self.query_one("#chat_panel", ChatPanel)
        if result.status == ToolResultStatus.SUCCESS:
            chat.add_tool_result(f"run: {command}", result.output)
        else:
            chat.add_tool_result(f"run: {command}", f"Error (exit {result.exit_code}):\n{result.output}")
    
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
        
        chat = self.query_one("#chat_panel", ChatPanel)
        chat.start_streaming()
        
        messages = chat.get_messages()
        api_messages = []
        for msg in messages:
            api_messages.append({"role": msg["role"], "content": msg["content"]})
        
        system_prompt = self._build_system_prompt()
        
        full_response = ""
        
        try:
            async for chunk in self.llm_client.chat(api_messages, system_prompt=system_prompt, stream=self.settings.ai.stream):
                if worker.is_cancelled:
                    break
                full_response += chunk
                chat.append_stream(chunk)
            
            if not worker.is_cancelled:
                chat.finish_streaming()
                
                # 检查是否包含工具调用
                await self._check_tool_calls(full_response)
                
        except Exception as e:
            self.app.call_from_thread(
                self._show_error,
                f"Request failed: {str(e)}"
            )
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词."""
        return f"""You are Hakimi Codex, a professional coding assistant.

Project: {self.project_path.name}
Path: {self.project_path}

## Available Tools

You can use the following tools by returning JSON format:

```tool
{{"tool": "execute_command", "parameters": {{"command": "python -m pytest"}}}}
```

```tool
{{"tool": "read_file", "parameters": {{"file_path": "src/main.py"}}}}
```

```tool
{{"tool": "write_file", "parameters": {{"file_path": "src/main.py", "content": "..."}}}}
```

```tool
{{"tool": "list_directory", "parameters": {{"dir_path": "."}}}}
```

```tool
{{"tool": "search_files", "parameters": {{"pattern": "def main"}}}}
```

```tool
{{"tool": "execute_code", "parameters": {{"code": "print(1+1)"}}}}
```

```tool
{{"tool": "analyze_project", "parameters": {{}}}}
```

## Rules

1. Use Chinese for responses, English for code comments
2. Be concise and professional
3. When modifying code, show the full file content in write_file
4. Run tests after making changes to verify correctness
5. For complex tasks, plan and execute step by step
"""
    
    async def _check_tool_calls(self, content: str):
        """检查并执行工具调用."""
        import re
        import json
        
        pattern = r'```tool\s*\n(.*?)\n```'
        matches = list(re.finditer(pattern, content, re.DOTALL))
        
        if not matches:
            return
        
        chat = self.query_one("#chat_panel", ChatPanel)
        
        for match in matches:
            try:
                tool_call = json.loads(match.group(1).strip())
                tool_name = tool_call.get("tool")
                parameters = tool_call.get("parameters", {})
                
                chat.add_system_message(f"Tool: {tool_name}")
                
                result = self.tool_executor.execute_tool(tool_name, parameters)
                
                if result.status == ToolResultStatus.SUCCESS:
                    chat.add_tool_result(tool_name, result.output)
                else:
                    chat.add_tool_result(tool_name, f"Error: {result.output}")
                
                # 如果工具修改了文件，更新 diff 面板
                if tool_name == "write_file" and "file_path" in parameters:
                    file_path = parameters["file_path"]
                    original = self.tool_executor.read_file(file_path).output
                    modified = parameters.get("content", "")
                    
                    diff_panel = self.query_one("#diff_panel", DiffPanel)
                    diff_panel.show_diff(file_path, original, modified)
                
            except json.JSONDecodeError as e:
                chat.add_system_message(f"Tool parse error: {e}")
    
    def _show_error(self, message: str):
        """显示错误."""
        chat = self.query_one("#chat_panel", ChatPanel)
        chat.add_system_message(f"Error: {message}")
    
    def action_refresh(self):
        """刷新."""
        self.notify("Refreshed", severity="information")
    
    def action_toggle_diff(self):
        """切换 diff 面板."""
        diff_panel = self.query_one("#diff_panel", DiffPanel)
        if diff_panel.display:
            diff_panel.display = False
        else:
            diff_panel.display = True
    
    def action_quit(self):
        """退出."""
        self._exit()
