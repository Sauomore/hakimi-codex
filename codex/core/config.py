"""配置持久化管理."""

import os
import toml
from pathlib import Path
from typing import Optional

from .models import AppConfig, ModelConfig, ProjectConfig, PRESET_MODELS


CONFIG_DIR = Path.home() / ".config" / "codex"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def ensure_config_dir() -> None:
    """确保配置目录存在."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    """加载配置文件."""
    ensure_config_dir()
    
    if not CONFIG_FILE.exists():
        # 创建默认配置
        config = AppConfig()
        # 添加预设模型（不带API key）
        config.models = [m.model_copy(update={"api_key": None}) for m in PRESET_MODELS]
        save_config(config)
        return config
    
    try:
        data = toml.load(CONFIG_FILE)
        return AppConfig(**data)
    except Exception:
        # 如果解析失败，返回默认配置
        return AppConfig(models=[m.model_copy(update={"api_key": None}) for m in PRESET_MODELS])


def save_config(config: AppConfig) -> None:
    """保存配置文件."""
    ensure_config_dir()
    
    # 转换为字典
    data = config.model_dump()
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        toml.dump(data, f)


def get_active_model(config: AppConfig) -> Optional[ModelConfig]:
    """获取当前激活的模型."""
    if config.active_model_id:
        for model in config.models:
            if model.id == config.active_model_id and model.enabled:
                return model
    
    # 返回第一个启用的模型
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
    """添加新模型."""
    # 检查是否已存在
    existing = [m for m in config.models if m.id == model.id]
    if existing:
        # 更新现有模型
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
