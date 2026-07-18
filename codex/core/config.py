"""配置持久化管理."""

import os
import toml
from pathlib import Path
from typing import Optional

from .models import AppConfig, ModelConfig, ProjectConfig


CONFIG_DIR = Path.home() / ".config" / "hakimi"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def ensure_config_dir() -> None:
    """确保配置目录存在."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _migrate_from_legacy(data: dict) -> dict:
    """兼容旧版 JSON settings 中可能存在的顶层字段."""
    legacy_map = {
        "ui": ["font_size", "theme", "think_color", "output_color",
               "user_color", "system_color", "diff_add_color", "diff_del_color",
               "diff_ctx_color", "background_color", "panel_border_color"],
        "ai": ["stream", "think_mode", "think_fold", "think_lines",
               "temperature", "max_tokens", "context_window", "auto_analyze",
               "show_tool_results", "tool_results_fold", "markdown_render",
               "confirm_tool_execution", "confirm_command_execution",
               "confirm_write_file", "max_tool_rounds", "debug_mode"],
        "editor": ["tab_size", "word_wrap", "show_line_numbers",
                   "highlight_syntax", "auto_save"],
        "git": ["auto_commit", "commit_message_template", "show_diff_before_commit"],
    }

    for section, keys in legacy_map.items():
        section_data = data.get(section, {})
        for key in keys:
            if key in data and key not in section_data:
                section_data[key] = data.pop(key)
        if section_data:
            data[section] = section_data

    # 移除已废弃的计费相关字段，避免新版模型校验失败
    data.get("ai", {}).pop("token_prices", None)

    return data


def load_config() -> AppConfig:
    """加载配置文件."""
    ensure_config_dir()

    if not CONFIG_FILE.exists():
        config = AppConfig()
        save_config(config)
        return config

    try:
        data = toml.load(CONFIG_FILE)
        data = _migrate_from_legacy(data)
        return AppConfig(**data)
    except Exception:
        return AppConfig()


def save_config(config: AppConfig) -> None:
    """保存配置文件."""
    ensure_config_dir()

    data = config.model_dump()

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        toml.dump(data, f)


def get_active_model(config: AppConfig) -> Optional[ModelConfig]:
    """获取当前激活的模型."""
    if config.active_model_id:
        for model in config.models:
            if model.id == config.active_model_id and model.enabled:
                return model

    for model in config.models:
        if model.enabled:
            return model

    return None


def set_active_model(config: AppConfig, model_id: str) -> bool:
    """设置激活的模型."""
    for model in config.models:
        if model.id == model_id:
            config.active_model_id = model_id
            save_config(config)
            return True
    return False


def add_model(config: AppConfig, model: ModelConfig) -> None:
    """添加或更新模型."""
    existing = [m for m in config.models if m.id == model.id]
    if existing:
        idx = config.models.index(existing[0])
        config.models[idx] = model
    else:
        config.models.append(model)

    save_config(config)


def remove_model(config: AppConfig, model_id: str) -> bool:
    """删除模型."""
    original_len = len(config.models)
    config.models = [m for m in config.models if m.id != model_id]

    if len(config.models) < original_len:
        if config.active_model_id == model_id:
            config.active_model_id = None
        save_config(config)
        return True
    return False


def get_project_config(config: AppConfig, path: str) -> Optional[ProjectConfig]:
    """获取项目配置."""
    abs_path = str(Path(path).resolve())
    for proj in config.projects:
        if str(Path(proj.project_path).resolve()) == abs_path:
            return proj
    return None


def add_or_update_project(config: AppConfig, project: ProjectConfig) -> None:
    """添加或更新项目配置."""
    abs_path = str(Path(project.project_path).resolve())

    existing = None
    for i, proj in enumerate(config.projects):
        if str(Path(proj.project_path).resolve()) == abs_path:
            existing = i
            break

    if existing is not None:
        config.projects[existing] = project
    else:
        config.projects.append(project)

    config.active_project_path = abs_path
    save_config(config)
