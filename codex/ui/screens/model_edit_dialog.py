"""模型编辑对话框."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Input, Select, Button, Static

from codex.core.models import ModelConfig, ProviderType


class ModelEditDialog(ModalScreen[ModelConfig]):
    """模型编辑/添加对话框."""

    CSS = """
    ModelEditDialog {
        align: center middle;
        background: $background 70%;
    }
    ModelEditDialog > Container {
        width: 90;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    ModelEditDialog Container > Static.title {
        text-style: bold;
        text-align: center;
        color: $primary-lighten-2;
        height: 1;
        margin-bottom: 1;
    }
    ModelEditDialog Container > Input {
        margin: 1 0;
    }
    ModelEditDialog Container > Select {
        margin: 1 0;
    }
    ModelEditDialog Container > Horizontal {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    ModelEditDialog Container > Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, model: ModelConfig = None, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.is_edit = model is not None

    def compose(self) -> ComposeResult:
        with Container():
            title = "[*] 编辑模型" if self.is_edit else "[+] 添加模型"
            yield Static(title, classes="title")

            yield Input(
                placeholder="模型唯一ID (如: gpt-4o)",
                value=self.model.id if self.is_edit else "",
                id="input_id"
            )
            yield Input(
                placeholder="显示名称 (如: GPT-4o)",
                value=self.model.name if self.is_edit else "",
                id="input_name"
            )

            provider_options = [(p.value, p) for p in ProviderType]
            current_provider = self.model.provider if self.is_edit else ProviderType.OPENAI
            yield Select(
                provider_options,
                value=current_provider,
                id="select_provider",
                prompt="选择提供商"
            )

            yield Input(
                placeholder="API 模型ID (如: gpt-4o)",
                value=self.model.model_id if self.is_edit else "",
                id="input_model_id"
            )
            yield Input(
                placeholder="API Key (留空使用环境变量)",
                value=self.model.api_key if self.is_edit else "",
                id="input_api_key",
                password=True
            )
            yield Input(
                placeholder="自定义 API Base URL (可选)",
                value=self.model.api_base if self.is_edit else "",
                id="input_api_base"
            )
            yield Input(
                placeholder="Temperature (0.0-2.0, 默认: 0.7)",
                value=str(self.model.temperature) if self.is_edit else "0.7",
                id="input_temperature"
            )
            yield Input(
                placeholder="最大Token数 (默认: 4096)",
                value=str(self.model.max_tokens) if self.is_edit else "4096",
                id="input_max_tokens"
            )
            yield Input(
                placeholder="上下文窗口大小 (默认: 8192)",
                value=str(self.model.context_window) if self.is_edit else "8192",
                id="input_context"
            )

            with Horizontal():
                yield Button("[保存]", id="btn_save", variant="success")
                yield Button("[取消]", id="btn_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        """按钮点击事件."""
        if event.button.id == "btn_cancel":
            self.dismiss(None)
            return

        if event.button.id == "btn_save":
            self._save_model()

    def _save_model(self):
        """保存模型配置."""
        try:
            model_id = self.query_one("#input_id", Input).value.strip()
            name = self.query_one("#input_name", Input).value.strip()
            provider = self.query_one("#select_provider", Select).value
            model_id_api = self.query_one("#input_model_id", Input).value.strip()
            api_key = self.query_one("#input_api_key", Input).value.strip() or None
            api_base = self.query_one("#input_api_base", Input).value.strip() or None
            temperature = float(self.query_one("#input_temperature", Input).value or 0.7)
            max_tokens = int(self.query_one("#input_max_tokens", Input).value or 4096)
            context_window = int(self.query_one("#input_context", Input).value or 8192)

            if not all([model_id, name, model_id_api]):
                self.notify("请填写所有必填字段", severity="error")
                return

            model = ModelConfig(
                id=model_id,
                name=name,
                provider=provider,
                model_id=model_id_api,
                api_key=api_key,
                api_base=api_base,
                temperature=temperature,
                max_tokens=max_tokens,
                context_window=context_window,
                is_default=self.model.is_default if self.is_edit else False,
                enabled=self.model.enabled if self.is_edit else True,
            )

            self.dismiss(model)

        except ValueError as e:
            self.notify(f"输入格式错误: {e}", severity="error")
