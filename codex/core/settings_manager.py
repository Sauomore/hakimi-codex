"""设置管理器 - 统一管理所有可配置参数."""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field


SETTINGS_DIR = Path.home() / ".config" / "hakimi"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


@dataclass
class UISettings:
    """界面设置."""
    font_size: int = 12
    theme: str = "dark"  # dark / light
    think_color: str = "#6b7280"  # 思考内容颜色 (灰色)
    output_color: str = "#e5e7eb"  # 正式输出颜色 (白色)
    user_color: str = "#60a5fa"  # 用户消息颜色 (蓝色)
    system_color: str = "#f59e0b"  # 系统消息颜色 (橙色)
    diff_add_color: str = "#22c55e"  # 添加行颜色 (绿色)
    diff_del_color: str = "#ef4444"  # 删除行颜色 (红色)
    diff_ctx_color: str = "#6b7280"  # 上下文行颜色 (灰色)
    background_color: str = "#1f2937"  # 背景色
    panel_border_color: str = "#374151"  # 面板边框色


@dataclass
class AISettings:
    """AI 设置."""
    stream: bool = True  # 流式输出
    think_mode: bool = True  # 思考模式 (显示 thinking 标签内容)
    think_fold: bool = True  # 思考内容默认折叠
    think_lines: int = 2  # 折叠时显示的行数
    temperature: float = 0.7
    max_tokens: int = 4096
    context_window: int = 8192
    auto_analyze: bool = True  # 启动时自动分析项目
    show_tool_results: bool = True  # 显示工具执行结果


@dataclass
class EditorSettings:
    """编辑器设置."""
    tab_size: int = 4
    word_wrap: bool = True
    show_line_numbers: bool = True
    highlight_syntax: bool = True
    auto_save: bool = False


@dataclass
class GitSettings:
    """Git 设置."""
    auto_commit: bool = False  # AI 修改后自动提交
    commit_message_template: str = "Hakimi: {description}"
    show_diff_before_commit: bool = True


@dataclass
class Settings:
    """全局设置."""
    version: str = "0.1.0"
    ui: UISettings = field(default_factory=UISettings)
    ai: AISettings = field(default_factory=AISettings)
    editor: EditorSettings = field(default_factory=EditorSettings)
    git: GitSettings = field(default_factory=GitSettings)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "version": self.version,
            "ui": asdict(self.ui),
            "ai": asdict(self.ai),
            "editor": asdict(self.editor),
            "git": asdict(self.git),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        """从字典创建."""
        return cls(
            version=data.get("version", "0.1.0"),
            ui=UISettings(**data.get("ui", {})),
            ai=AISettings(**data.get("ai", {})),
            editor=EditorSettings(**data.get("editor", {})),
            git=GitSettings(**data.get("git", {})),
        )


def ensure_settings_dir() -> None:
    """确保设置目录存在."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    """加载设置."""
    ensure_settings_dir()
    
    if not SETTINGS_FILE.exists():
        settings = Settings()
        save_settings(settings)
        return settings
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Settings.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        # 解析失败，返回默认设置
        return Settings()


def save_settings(settings: Settings) -> None:
    """保存设置."""
    ensure_settings_dir()
    
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)


def get_settings_path() -> Path:
    """获取设置文件路径."""
    return SETTINGS_FILE
