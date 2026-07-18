"""Token 使用统计.

记录每次 LLM 调用的 token 消耗。
支持会话级累计和按日持久化累计。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

from .models import ModelConfig
from ..utils.logger import debug as log_debug


@dataclass
class TokenUsage:
    """单次 LLM 调用的 token 使用情况."""

    prompt: int = 0
    completion: int = 0
    total: int = 0
    model_id: str = ""
    provider: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_storage_dict(self) -> Dict:
        return {
            "date": self.timestamp.strftime("%Y-%m-%d"),
            "prompt": self.prompt,
            "completion": self.completion,
            "total": self.total,
            "model_id": self.model_id,
            "provider": self.provider,
            "timestamp": self.timestamp.isoformat(),
        }


class TokenTracker:
    """Token 使用统计器."""

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path).resolve()
        self.storage_path = self._resolve_storage_path()
        self.session_usage = TokenUsage()
        self.today_usage = TokenUsage()
        self.last_usage: Optional[TokenUsage] = None
        self._load_today()

    def _resolve_storage_path(self) -> Path:
        """决定 token 使用记录的保存路径."""
        local_dir = self.project_path / ".hakimi"
        try:
            local_dir.mkdir(parents=True, exist_ok=True)
            return local_dir / "token_usage.jsonl"
        except Exception:
            pass
        fallback_dir = Path.home() / ".config" / "hakimi" / "usage"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / "token_usage.jsonl"

    def _load_today(self) -> None:
        """从本地加载今日累计."""
        today_str = date.today().isoformat()
        prompt = completion = total = 0
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("date") == today_str:
                            prompt += data.get("prompt", 0)
                            completion += data.get("completion", 0)
                            total += data.get("total", 0)
                    except Exception as e:
                        log_debug(f"token usage load parse error: {e}")
        except Exception as e:
            log_debug(f"token usage load failed: {e}")

        self.today_usage = TokenUsage(
            prompt=prompt,
            completion=completion,
            total=total,
        )

    def add_usage(
        self,
        model: Optional[ModelConfig],
        usage: Dict[str, int],
    ) -> TokenUsage:
        """记录一次 LLM 调用的 token 使用."""
        prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total = usage.get("total_tokens") or (prompt + completion)
        provider = model.provider if model else "custom"
        model_id = model.id if model else ""

        entry = TokenUsage(
            prompt=prompt,
            completion=completion,
            total=total,
            model_id=model_id,
            provider=provider,
        )
        self.last_usage = entry

        # 累计到会话和今日
        self.session_usage.prompt += prompt
        self.session_usage.completion += completion
        self.session_usage.total += total

        self.today_usage.prompt += prompt
        self.today_usage.completion += completion
        self.today_usage.total += total

        self._save(entry)
        return entry

    def _save(self, entry: TokenUsage) -> None:
        """持久化单条使用记录."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_storage_dict(), ensure_ascii=False) + "\n")
            log_debug(f"token usage saved: {entry.total} tokens")
        except Exception as e:
            log_debug(f"token usage save failed: {e}")

    def format_last_usage(self) -> str:
        """格式化最近一次调用消耗."""
        if not self.last_usage:
            return ""
        u = self.last_usage
        return (
            f"[#888888]本轮消耗: prompt={u.prompt} / completion={u.completion} / "
            f"total={u.total}[/#888888]"
        )

    def format_cumulative(self) -> str:
        """格式化会话与今日累计."""
        return (
            f"session: {self.session_usage.total}\n"
            f"today: {self.today_usage.total}"
        )
