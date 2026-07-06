"""模型定义与配置管理."""

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
        pass
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


class AppConfig(BaseModel):
    """应用全局配置."""
    
    version: str = Field(default="0.1.0")
    models: list[ModelConfig] = Field(default_factory=list)
    projects: list[ProjectConfig] = Field(default_factory=list)
    active_model_id: Optional[str] = Field(default=None)
    active_project_path: Optional[str] = Field(default=None)
