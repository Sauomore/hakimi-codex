"""聊天记录管理.

提供带时间戳的消息存储、上下文裁剪、本地持久化加载/保存，
以及供 UI 复制使用的纯文本回溯能力。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import debug as log_debug


@dataclass
class ChatMessage:
    """单条聊天记录."""

    role: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    thinking: Optional[str] = None
    tool_name: Optional[str] = None

    def to_api_dict(self) -> Dict[str, str]:
        """转换为 LLM API 可用的字典."""
        return {"role": self.role, "content": self.content}

    def to_storage_dict(self) -> Dict[str, Any]:
        """转换为可持久化的字典."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "thinking": self.thinking,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_storage_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """从持久化字典恢复."""
        ts_str = data.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
        except Exception:
            timestamp = datetime.now(timezone.utc)
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            role=data.get("role", "system"),
            content=data.get("content", ""),
            thinking=data.get("thinking"),
            tool_name=data.get("tool_name"),
            timestamp=timestamp,
        )


class ChatHistory:
    """聊天记录容器."""

    def __init__(
        self,
        project_path: Path,
        max_context_messages: int = 20,
        context_ttl_hours: Optional[float] = None,
    ):
        self.project_path = Path(project_path).resolve()
        self.max_context_messages = max(2, max_context_messages)
        self.context_ttl_hours = context_ttl_hours
        self.messages: List[ChatMessage] = []
        self.storage_path = self._resolve_storage_path()

    def _resolve_storage_path(self) -> Path:
        """决定聊天记录保存路径.

        优先保存到项目根目录的 .hakimi/chat_history.jsonl，
        如果项目不可写则回退到 ~/.config/hakimi/history/。
        """
        local_dir = self.project_path / ".hakimi"
        try:
            local_dir.mkdir(parents=True, exist_ok=True)
            return local_dir / "chat_history.jsonl"
        except Exception:
            pass

        fallback_dir = Path.home() / ".config" / "hakimi" / "history"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        project_key = self.project_path.name or "default"
        return fallback_dir / f"{project_key}.jsonl"

    def add(
        self,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> ChatMessage:
        """添加一条消息."""
        msg = ChatMessage(
            role=role,
            content=content,
            thinking=thinking,
            tool_name=tool_name,
        )
        self.messages.append(msg)
        self.save()
        return msg

    def clear(self) -> None:
        """清空历史."""
        self.messages.clear()
        self.save()

    def get_context_messages(self, include_system: bool = True) -> List[Dict[str, str]]:
        """获取发送给 LLM 的上下文消息（已做时间/数量裁剪）."""
        candidates = list(self.messages)

        # 按时间过滤
        if self.context_ttl_hours is not None:
            cutoff = datetime.now(timezone.utc).timestamp() - self.context_ttl_hours * 3600
            candidates = [m for m in candidates if m.timestamp.timestamp() >= cutoff]

        # 只保留 user / assistant 角色用于 LLM 对话上下文
        api_messages = [m for m in candidates if m.role in ("user", "assistant")]

        # 数量裁剪：保留最近 max_context_messages 条
        if len(api_messages) > self.max_context_messages:
            api_messages = api_messages[-self.max_context_messages :]

        return [m.to_api_dict() for m in api_messages]

    def get_last_message(self, role: Optional[str] = None) -> Optional[ChatMessage]:
        """获取最后一条消息，可指定角色."""
        for msg in reversed(self.messages):
            if role is None or msg.role == role:
                return msg
        return None

    def pop_last(self, role: Optional[str] = None) -> Optional[ChatMessage]:
        """移除并返回最后一条消息，可指定角色."""
        for i in range(len(self.messages) - 1, -1, -1):
            if role is None or self.messages[i].role == role:
                msg = self.messages.pop(i)
                self.save()
                return msg
        return None

    def search(self, keyword: str) -> List[ChatMessage]:
        """搜索包含关键字的消息（忽略大小写）."""
        keyword_lower = keyword.lower()
        results = []
        for msg in self.messages:
            if keyword_lower in msg.content.lower():
                results.append(msg)
            elif msg.thinking and keyword_lower in msg.thinking.lower():
                results.append(msg)
        return results

    def find_message(self, message_id: str) -> Optional[ChatMessage]:
        """根据 ID 查找消息."""
        for msg in self.messages:
            if msg.id == message_id:
                return msg
        return None

    def get_copy_text(self, message_id: Optional[str] = None) -> str:
        """获取可复制文本."""
        if message_id:
            msg = self.find_message(message_id)
            return msg.content if msg else ""

        # 默认复制最后一条 assistant 消息
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg.content
        return ""

    def get_all_text(self) -> str:
        """获取完整聊天记录纯文本."""
        lines: List[str] = []
        for msg in self.messages:
            ts = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if msg.role == "user":
                lines.append(f"[{ts}] User:\n{msg.content}\n")
            elif msg.role == "assistant":
                lines.append(f"[{ts}] AI:\n{msg.content}\n")
            elif msg.role == "tool":
                lines.append(f"[{ts}] Tool {msg.tool_name or ''}:\n{msg.content}\n")
            else:
                lines.append(f"[{ts}] {msg.role.capitalize()}:\n{msg.content}\n")
        return "\n".join(lines)

    def save(self) -> None:
        """持久化聊天记录."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                for msg in self.messages:
                    f.write(json.dumps(msg.to_storage_dict(), ensure_ascii=False) + "\n")
            log_debug(f"chat history saved: {self.storage_path}")
        except Exception as e:
            log_debug(f"chat history save failed: {e}")

    def load(self) -> List[ChatMessage]:
        """从本地加载聊天记录."""
        loaded: List[ChatMessage] = []
        if not self.storage_path.exists():
            return loaded

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        loaded.append(ChatMessage.from_storage_dict(data))
                    except Exception as e:
                        log_debug(f"chat history load parse error: {e}")
        except Exception as e:
            log_debug(f"chat history load failed: {e}")

        self.messages = loaded
        return loaded

    def export_to(self, path: Path, fmt: str = "jsonl") -> Path:
        """导出聊天记录到文件.

        fmt: "jsonl" 或 "text".
        """
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "text":
            path.write_text(self.get_all_text(), encoding="utf-8")
        else:
            with open(path, "w", encoding="utf-8") as f:
                for msg in self.messages:
                    f.write(json.dumps(msg.to_storage_dict(), ensure_ascii=False) + "\n")
        return path

    def import_from(self, path: Path, merge: bool = False) -> int:
        """从 JSONL 文件导入聊天记录.

        merge: 为 True 时追加到现有记录，否则替换。
        返回导入的消息数量。
        """
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        loaded: List[ChatMessage] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    loaded.append(ChatMessage.from_storage_dict(data))
                except Exception as e:
                    log_debug(f"chat history import parse error: {e}")

        if merge:
            self.messages.extend(loaded)
        else:
            self.messages = loaded
        self.save()
        return len(loaded)
