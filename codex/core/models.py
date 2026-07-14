"""配置模型定义."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    """支持的 LLM 提供商."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    MISTRAL = "mistral"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"


class ModelConfig(BaseModel):
    """单个模型的配置."""

    id: str = Field(..., description="模型唯一标识")
    name: str = Field(..., description="显示名称")
    provider: ProviderType = Field(..., description="提供商")
    model_id: str = Field(..., description="API 模型ID")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    api_base: Optional[str] = Field(default=None, description="自定义API基础URL")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    context_window: int = Field(default=8192, ge=1024)
    is_default: bool = Field(default=False)
    enabled: bool = Field(default=True)

    class Config:
        use_enum_values = True


class ProjectConfig(BaseModel):
    """项目级配置."""

    project_path: str = Field(default=".", description="项目路径")
    auto_commit: bool = Field(default=True, description="是否自动提交Git")
    show_diff: bool = Field(default=True, description="是否显示代码diff")
    theme: str = Field(default="dark", description="主题")
    language: str = Field(default="zh", description="界面语言")
    editor: str = Field(default="default", description="默认编辑器")
    ignored_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.pyc", "__pycache__", ".git", "node_modules",
            ".env", "*.log", "dist", "build", ".idea", ".vscode"
        ]
    )


class UISettings(BaseModel):
    """界面设置."""

    font_size: int = Field(default=12, ge=8, le=24)
    theme: str = Field(default="dark")
    think_color: str = Field(default="#6b7280")
    output_color: str = Field(default="#e5e7eb")
    user_color: str = Field(default="#60a5fa")
    system_color: str = Field(default="#f59e0b")
    diff_add_color: str = Field(default="#22c55e")
    diff_del_color: str = Field(default="#ef4444")
    diff_ctx_color: str = Field(default="#6b7280")
    background_color: str = Field(default="#1f2937")
    panel_border_color: str = Field(default="#374151")


class AISettings(BaseModel):
    """AI 设置."""

    stream: bool = Field(default=True)
    think_mode: bool = Field(default=True)
    think_fold: bool = Field(default=True)
    think_lines: int = Field(default=2, ge=1, le=10)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    context_window: int = Field(default=8192, ge=1024)
    auto_analyze: bool = Field(default=True)
    show_tool_results: bool = Field(default=True)
    tool_results_fold: bool = Field(default=True)
    markdown_render: bool = Field(default=True)
    confirm_tool_execution: bool = Field(default=True)
    confirm_command_execution: bool = Field(default=True)
    confirm_write_file: bool = Field(default=True)
    max_tool_rounds: int = Field(default=10, ge=1, le=50)
    debug_mode: bool = Field(default=False, description="启用调试模式，在项目根目录输出日志")
    agent_mode: bool = Field(default=False, description="启用多 Agent 协作模式")
    agent_run_tests: bool = Field(default=True, description="Agent 流水线是否自动运行测试")
    agent_fold_output: bool = Field(default=True, description="折叠 Agent 输出（仅显示错误），关闭则显示完整输出")
    planner_model: Optional[str] = Field(default=None, description="Planner Agent 使用的模型 ID，空则使用主模型")
    coder_model: Optional[str] = Field(default=None, description="Coder Agent 使用的模型 ID，空则使用主模型")
    reviewer_model: Optional[str] = Field(default=None, description="Reviewer Agent 使用的模型 ID，空则使用主模型")
    tester_model: Optional[str] = Field(default=None, description="Tester Agent 使用的模型 ID，空则使用主模型")


class EditorSettings(BaseModel):
    """编辑器设置."""

    tab_size: int = Field(default=4, ge=1, le=8)
    word_wrap: bool = Field(default=True)
    show_line_numbers: bool = Field(default=True)
    highlight_syntax: bool = Field(default=True)
    auto_save: bool = Field(default=False)


class GitSettings(BaseModel):
    """Git 设置."""

    auto_commit: bool = Field(default=False)
    commit_message_template: str = Field(default="Hakimi: {description}")
    show_diff_before_commit: bool = Field(default=True)


class AppConfig(BaseModel):
    """应用全局配置."""

    version: str = Field(default="0.3.0")
    models: list[ModelConfig] = Field(default_factory=list)
    projects: list[ProjectConfig] = Field(default_factory=list)
    active_model_id: Optional[str] = Field(default=None)
    active_project_path: Optional[str] = Field(default=None)
    ui: UISettings = Field(default_factory=UISettings)
    ai: AISettings = Field(default_factory=AISettings)
    editor: EditorSettings = Field(default_factory=EditorSettings)
    git: GitSettings = Field(default_factory=GitSettings)
