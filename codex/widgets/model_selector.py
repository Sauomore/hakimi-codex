"""模型选择器组件."""

from typing import Callable, Optional, List

from textual.widgets import Static, DataTable, Button
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.app import ComposeResult

from ..core.models import ModelConfig, ProviderType


class ModelSelectorWidget(Vertical):
    """模型选择与管理组件."""
    
    DEFAULT_CSS = """
    ModelSelectorWidget {
        width: 100%;
        height: 100%;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
    }
    ModelSelectorWidget > .selector-header {
        height: 1;
        content-align: center middle;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }
    ModelSelectorWidget > DataTable {
        width: 100%;
        height: 1fr;
        border: none;
        background: transparent;
    }
    ModelSelectorWidget > DataTable:focus {
        background: $primary-darken-3;
    }
    ModelSelectorWidget > DataTable > .datatable--cursor {
        background: $primary-darken-2;
    }
    ModelSelectorWidget > Horizontal.button-bar {
        height: auto;
        border-top: solid $primary-darken-2;
        padding: 0 1;
        content-align: center middle;
    }
    ModelSelectorWidget > Horizontal.button-bar > Button {
        margin: 0 1;
    }
    """
    
    selected_model = reactive[Optional[ModelConfig]](None)
    
    def __init__(
        self,
        models: List[ModelConfig],
        on_select: Optional[Callable] = None,
        on_add: Optional[Callable] = None,
        on_edit: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
        **kwargs
    ):
        self.models = models
        self.on_model_select = on_select
        self.on_model_add = on_add
        self.on_model_edit = on_edit
        self.on_model_delete = on_delete
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        """组装组件."""
        yield Static("[模型] 模型管理", classes="selector-header")
        
        table = DataTable(id="model_table", cursor_type="row")
        table.add_columns("状态", "名称", "提供商", "模型ID", "上下文")
        yield table
        
        with Horizontal(classes="button-bar"):
            yield Button("[+] 添加", id="btn_add_model", variant="success")
            yield Button("[*] 编辑", id="btn_edit_model", variant="primary")
            yield Button("[-] 删除", id="btn_delete_model", variant="error")
            yield Button("[选择]", id="btn_select_model", variant="primary")
    
    def on_mount(self):
        """挂载后加载数据."""
        self.refresh_table()
    
    def refresh_table(self):
        """刷新模型列表."""
        table = self.query_one("#model_table", DataTable)
        table.clear()
        
        provider_icons = {
            ProviderType.OPENAI: "[O]",
            ProviderType.ANTHROPIC: "[A]",
            ProviderType.GOOGLE: "[G]",
            ProviderType.DEEPSEEK: "[D]",
            ProviderType.MISTRAL: "[M]",
            ProviderType.OLLAMA: "[L]",
            ProviderType.OPENROUTER: "[R]",
            ProviderType.CUSTOM: "[C]",
        }
        
        for i, model in enumerate(self.models):
            status = "[启用]" if model.enabled else "[禁用]"
            if model.is_default:
                status += " [默认]"
            
            icon = provider_icons.get(model.provider, "[C]")
            provider = f"{icon} {model.provider}"
            
            context = f"{model.context_window // 1000}K"
            
            table.add_row(
                status,
                model.name,
                provider,
                model.model_id,
                context,
                key=str(i)
            )
    
    def update_models(self, models: List[ModelConfig]):
        """更新模型列表."""
        self.models = models
        self.refresh_table()
    
    def get_selected_model(self) -> Optional[ModelConfig]:
        """获取选中的模型."""
        table = self.query_one("#model_table", DataTable)
        row = table.cursor_row
        if row is not None and 0 <= row < len(self.models):
            return self.models[row]
        return None
    
    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        btn_id = event.button.id
        
        if btn_id == "btn_add_model":
            if self.on_model_add:
                self.on_model_add()
        
        elif btn_id == "btn_edit_model":
            model = self.get_selected_model()
            if model and self.on_model_edit:
                self.on_model_edit(model)
        
        elif btn_id == "btn_delete_model":
            model = self.get_selected_model()
            if model and self.on_model_delete:
                self.on_model_delete(model)
        
        elif btn_id == "btn_select_model":
            model = self.get_selected_model()
            if model:
                self.selected_model = model
                if self.on_model_select:
                    self.on_model_select(model)
