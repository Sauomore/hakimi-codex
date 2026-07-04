"""主工作界面."""

import asyncio
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Button, Header, Footer, RichLog, DataTable, ContentSwitcher, Input, TabbedContent, TabPane
from textual.reactive import reactive
from textual.worker import Worker, get_current_worker

from ..core.models import ModelConfig
from ..core.config import AppConfig, get_active_model, add_model, remove_model
from ..core.llm_client import LLMClient
from ..core import git_utils
from ..core.tools import ToolExecutor, ToolResultStatus
from ..widgets.file_tree import FileTreeWidget
from ..widgets.chat_panel import ChatPanel
from ..widgets.model_selector import ModelSelectorWidget
from ..widgets.code_view import CodeViewerWidget
from ..widgets.terminal_panel import TerminalPanel
from .model_edit_dialog import ModelEditDialog


class MainScreen(Screen):
    """主工作界面."""
    
    CSS = """
    MainScreen {
        layout: horizontal;
        width: 100%;
        height: 100%;
        background: $surface-darken-1;
    }
    
    /* 左侧面板 */
    #left_panel {
        width: 25%;
        height: 100%;
        layout: vertical;
        border: solid $primary-darken-2;
    }
    
    #left_panel FileTreeWidget {
        height: 60%;
    }
    
    #left_panel TabbedContent {
        height: 40%;
    }
    
    #left_panel TabbedContent > TabPane {
        padding: 0;
    }
    
    #left_panel DataTable {
        width: 100%;
        height: 100%;
        border: none;
        background: transparent;
    }
    
    #left_panel DataTable:focus {
        background: $primary-darken-3;
    }
    
    #left_panel .git-header {
        height: 1;
        content-align: center middle;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }
    
    /* 中间面板 */
    #center_panel {
        width: 50%;
        height: 100%;
        layout: vertical;
        border: solid $primary-darken-2;
    }
    
    #center_panel CodeViewerWidget {
        height: 50%;
    }
    
    #center_panel ChatPanel {
        height: 50%;
    }
    
    /* 右侧面板 */
    #right_panel {
        width: 25%;
        height: 100%;
        layout: vertical;
        border: solid $primary-darken-2;
    }
    
    #right_panel ModelSelectorWidget {
        height: 100%;
    }
    """
    
    app_config = reactive[AppConfig](AppConfig())
    current_project_path = reactive[str](".")
    is_processing = reactive(False)
    
    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = Path(project_path).resolve()
        self.llm_client: Optional[LLMClient] = None
        self.tool_executor = ToolExecutor(str(self.project_path))
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        """组装主界面."""
        # 左侧：文件树 + Git/终端 Tab
        with Vertical(id="left_panel"):
            yield FileTreeWidget(
                root_path=str(self.project_path),
                on_select=self._on_file_selected,
                id="file_tree_panel"
            )
            
            with TabbedContent(id="tools_tabs"):
                with TabPane("📊 Git 状态", id="git_tab"):
                    yield self._create_git_panel()
                
                with TabPane("💻 终端", id="terminal_tab"):
                    yield TerminalPanel(
                        project_path=str(self.project_path),
                        id="terminal_panel"
                    )
        
        # 中间：代码查看器 + 聊天
        with Vertical(id="center_panel"):
            yield CodeViewerWidget(id="code_viewer")
            yield ChatPanel(
                on_send=self._on_chat_send,
                id="chat_panel"
            )
        
        # 右侧：模型管理
        with Vertical(id="right_panel"):
            yield ModelSelectorWidget(
                models=self.app_config.models,
                on_select=self._on_model_selected,
                on_add=self._on_model_add,
                on_edit=self._on_model_edit,
                on_delete=self._on_model_delete,
                id="model_panel"
            )
    
    def _create_git_panel(self):
        """创建 Git 状态面板."""
        panel = Vertical(id="git_panel_container")
        
        header = Static("📊 Git 状态", classes="git-header")
        header.styles.height = 1
        header.styles.content_align = "center middle"
        header.styles.background = "$primary-darken-2"
        header.styles.color = "$text"
        header.styles.text_style = "bold"
        
        table = DataTable(id="git_table", cursor_type="row")
        table.add_columns("状态", "文件")
        table.styles.width = "100%"
        table.styles.height = "1fr"
        table.styles.border = "none"
        table.styles.background = "transparent"
        
        panel.mount(header)
        panel.mount(table)
        
        return panel
    
    def on_mount(self):
        """挂载后初始化."""
        from ..core.config import load_config
        self.app_config = load_config()
        
        # 更新模型面板
        model_panel = self.query_one("#model_panel", ModelSelectorWidget)
        model_panel.update_models(self.app_config.models)
        
        # 刷新 Git 状态
        self._refresh_git_status()
        
        # 显示欢迎信息和项目分析
        chat = self.query_one("#chat_panel", ChatPanel)
        chat.add_system_message(f"📂 项目路径: {self.project_path}")
        
        # 自动分析项目
        try:
            from ..core.project_analyzer import ProjectAnalyzer
            analyzer = ProjectAnalyzer(str(self.project_path))
            summary = analyzer.get_summary()
            chat.add_system_message(f"📊 项目分析:\n{summary}")
        except Exception:
            pass
        
        active_model = get_active_model(self.app_config)
        if active_model:
            chat.add_system_message(f"🤖 当前模型: {active_model.name}")
        else:
            chat.add_system_message("⚠️ 请先配置并选择一个模型")
        
        chat.add_system_message(
            "💡 快捷键: [bold]q[/bold]退出 [bold]r[/bold]刷新 [bold]Ctrl+T[/bold]终端\n"
            "   AI 支持工具: 执行命令、读写文件、代码搜索、项目分析、代码执行"
        )
    
    def _on_file_selected(self, file_path: str):
        """文件选择回调."""
        viewer = self.query_one("#code_viewer", CodeViewerWidget)
        viewer.current_file = file_path
    
    def _on_model_selected(self, model: ModelConfig):
        """模型选择回调."""
        from ..core.config import set_active_model
        set_active_model(self.app_config, model.id)
        
        chat = self.query_one("#chat_panel", ChatPanel)
        chat.add_system_message(f"✅ 已切换到模型: {model.name}")
        
        self.llm_client = LLMClient(model)
    
    def _on_model_add(self):
        """添加模型回调."""
        self.push_screen(ModelEditDialog(), self._on_model_saved)
    
    def _on_model_edit(self, model: ModelConfig):
        """编辑模型回调."""
        self.push_screen(ModelEditDialog(model=model), self._on_model_saved)
    
    def _on_model_delete(self, model: ModelConfig):
        """删除模型回调."""
        if remove_model(self.app_config, model.id):
            model_panel = self.query_one("#model_panel", ModelSelectorWidget)
            model_panel.update_models(self.app_config.models)
            
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message(f"🗑️ 已删除模型: {model.name}")
    
    def _on_model_saved(self, result: Optional[ModelConfig]):
        """模型保存回调."""
        if result:
            add_model(self.app_config, result)
            
            model_panel = self.query_one("#model_panel", ModelSelectorWidget)
            model_panel.update_models(self.app_config.models)
            
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message(f"💾 已保存模型: {result.name}")
    
    def _on_chat_send(self, content: str):
        """聊天发送回调."""
        active_model = get_active_model(self.app_config)
        
        if not active_model:
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message("⚠️ 请先选择一个模型！")
            return
        
        if not active_model.api_key:
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_system_message("⚠️ 请为当前模型配置 API Key！")
            return
        
        # 启动后台任务处理消息
        self.run_worker(self._process_chat_message(content))
    
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
        
        # 获取消息历史
        messages = chat.get_messages()
        api_messages = []
        for msg in messages:
            if msg["role"] in ("user", "assistant"):
                api_messages.append({"role": msg["role"], "content": msg["content"]})
        
        # 构建系统提示词（包含工具描述）
        system_prompt = self._build_system_prompt()
        
        # 收集流式响应
        full_response = ""
        
        try:
            async for chunk in self.llm_client.chat(api_messages, system_prompt=system_prompt):
                if worker.is_cancelled:
                    break
                full_response += chunk
                
                # 每累积一定内容更新显示
                if len(full_response) % 100 < 10:
                    self.app.call_from_thread(
                        self._update_streaming_display,
                        full_response
                    )
            
            if not worker.is_cancelled:
                self.app.call_from_thread(self._finish_response, full_response)
                
        except Exception as e:
            self.app.call_from_thread(
                self._show_error,
                f"请求失败: {str(e)}"
            )
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词（包含工具描述和项目分析）."""
        tools_desc = self.tool_executor.get_tools_description()
        tools_json = "\n".join([
            f"  - {t['name']}: {t['description'][:60]}..." 
            for t in tools_desc
        ])
        
        # 获取项目分析上下文
        project_context = ""
        try:
            from ..core.project_analyzer import ProjectAnalyzer
            analyzer = ProjectAnalyzer(str(self.project_path))
            project_context = analyzer.get_system_context()
        except Exception:
            pass
        
        return f"""你是一个专业的代码助手 Agent，正在协助用户在项目 {self.project_path.name} 中进行开发。

{project_context}

当前项目路径: {self.project_path}

## 可用工具（8个）

你可以使用以下工具来帮助用户（通过返回 JSON 格式调用）：

{tools_json}

## 工具调用格式

当你需要执行工具时，在回复中返回以下 JSON 格式（会被自动执行并返回结果）：

```tool
{{"tool": "工具名", "parameters": {{"参数": "值"}}}}
```

例如：
```tool
{{"tool": "execute_command", "parameters": {{"command": "python -m pytest"}}}}
```

## Agent 工作模式

1. **分析阶段**: 先使用 analyze_project 了解项目概况
2. **计划阶段**: 根据用户请求制定执行计划
3. **执行阶段**: 按需调用工具完成代码读写、命令执行、搜索等
4. **验证阶段**: 运行测试或检查确认修改正确

## 规则

1. 用中文回答，代码注释可以用英文
2. 回答简洁、专业，优先给出可执行方案
3. 需要执行命令时，先说明计划，然后使用工具
4. 读取文件后，分析内容并给出具体修改建议
5. 写文件前，建议先用 diff 预览变更（如用户要求）
6. 修改后主动运行测试验证
7. 对于复杂任务，分步骤执行并汇报进度"""
    
    def _update_streaming_display(self, content: str):
        """更新流式显示."""
        pass
    
    def _finish_response(self, content: str):
        """完成响应显示."""
        # 检查是否包含工具调用
        import re
        import json
        
        # 提取工具调用
        tool_pattern = r'```tool\s*\n(.*?)\n```'
        tool_matches = list(re.finditer(tool_pattern, content, re.DOTALL))
        
        if tool_matches:
            # 有工具调用，分离消息和工具调用
            # 先显示 AI 的普通回复部分
            clean_content = re.sub(tool_pattern, '', content, flags=re.DOTALL).strip()
            if clean_content:
                chat = self.query_one("#chat_panel", ChatPanel)
                chat.add_ai_message(clean_content)
            
            # 执行每个工具调用
            for match in tool_matches:
                try:
                    tool_call = json.loads(match.group(1).strip())
                    self._execute_tool_call(tool_call)
                except json.JSONDecodeError as e:
                    chat = self.query_one("#chat_panel", ChatPanel)
                    chat.add_system_message(f"⚠️ 工具调用格式错误: {e}")
        else:
            # 没有工具调用，直接显示
            chat = self.query_one("#chat_panel", ChatPanel)
            chat.add_ai_message(content)
    
    def _execute_tool_call(self, tool_call: dict):
        """执行工具调用."""
        tool_name = tool_call.get("tool", "")
        parameters = tool_call.get("parameters", {})
        
        chat = self.query_one("#chat_panel", ChatPanel)
        chat.add_system_message(
            f"🔧 执行工具: [bold]{tool_name}[/bold]\n"
            f"参数: {parameters}"
        )
        
        result = self.tool_executor.execute_tool(tool_name, parameters)
        
        # 显示工具结果
        if result.status == ToolResultStatus.SUCCESS:
            chat.add_system_message(f"✅ 工具执行成功\n{result.output[:500]}")
        else:
            chat.add_system_message(f"❌ 工具执行失败\n{result.output}")
        
        # 如果终端面板可见，也在终端中显示
        terminal = self.query_one("#terminal_panel", TerminalPanel)
        if terminal and hasattr(terminal, 'query_one'):
            log = terminal.query_one("#terminal_log", RichLog)
            if log:
                log.write(f"\n[dim]➡️ AI 工具: {tool_name}[/dim]")
                log.write(f"[dim]   参数: {parameters}[/dim]")
                log.write(f"[dim]   结果: {result.status.value}[/dim]")
    
    def _show_error(self, message: str):
        """显示错误."""
        chat = self.query_one("#chat_panel", ChatPanel)
        chat.add_system_message(f"❌ {message}")
    
    def _refresh_git_status(self):
        """刷新 Git 状态."""
        if not git_utils.is_git_repo(str(self.project_path)):
            return
        
        try:
            table = self.query_one("#git_table", DataTable)
            table.clear()
            
            status_map = {
                "M": ("📝", "修改"),
                "A": ("➕", "新增"),
                "D": ("🗑️", "删除"),
                "??": ("❓", "未跟踪"),
                "R": ("📝", "重命名"),
            }
            
            files = git_utils.get_git_status(str(self.project_path))
            for status, filename in files:
                icon, label = status_map.get(status, ("📄", status))
                table.add_row(f"{icon} {label}", filename)
            
            if not files:
                table.add_row("✅", "工作区干净")
                
        except Exception:
            pass
    
    def action_refresh(self):
        """刷新操作."""
        self._refresh_git_status()
        
        tree = self.query_one("#file_tree_panel", FileTreeWidget)
        tree.refresh_tree()
        
        self.notify("已刷新", severity="information")
    
    def action_toggle_terminal(self):
        """切换终端面板."""
        tabs = self.query_one("#tools_tabs", TabbedContent)
        active = tabs.active
        if active == "git_tab":
            tabs.active = "terminal_tab"
            terminal = self.query_one("#terminal_panel", TerminalPanel)
            if terminal:
                terminal.query_one("#terminal_input", Input).focus()
        else:
            tabs.active = "git_tab"
    
    def action_quit(self):
        """退出操作."""
        if self.llm_client:
            asyncio.create_task(self.llm_client.close())
        self.app.exit()
