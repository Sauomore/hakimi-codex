"""测试聊天记录导出导入."""

import json
import tempfile
from pathlib import Path

from codex.core.chat_history import ChatHistory
from codex.core.command_handler import CommandHandler


def test_export_import():
    with tempfile.TemporaryDirectory() as tmp:
        history = ChatHistory(Path(tmp), max_context_messages=10)
        history.add("user", "你好")
        history.add("assistant", "你好！有什么可以帮你的？")
        history.add("tool", "ok", tool_name="read_file")

        # 导出为 text
        text_path = history.export_to(Path(tmp) / "chat.txt", fmt="text")
        assert text_path.exists()
        content = text_path.read_text(encoding="utf-8")
        assert "User:" in content
        assert "AI:" in content
        assert "Tool read_file:" in content

        # 导出为 jsonl
        json_path = history.export_to(Path(tmp) / "chat.jsonl", fmt="jsonl")
        assert json_path.exists()
        lines = json_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            data = json.loads(line)
            assert "id" in data
            assert "role" in data
            assert "content" in data
            assert "timestamp" in data

        # 导入到新 history（替换）
        history2 = ChatHistory(Path(tmp) / "other", max_context_messages=10)
        count = history2.import_from(json_path, merge=False)
        assert count == 3
        assert len(history2.messages) == 3
        assert history2.messages[0].role == "user"
        assert history2.messages[0].content == "你好"

        # 导入并追加
        history3 = ChatHistory(Path(tmp) / "other2", max_context_messages=10)
        history3.add("user", "已有消息")
        count = history3.import_from(json_path, merge=True)
        assert count == 3
        assert len(history3.messages) == 4
        assert history3.messages[0].content == "已有消息"

        print("export/import test passed")


def test_command_parse():
    handler = CommandHandler()

    r = handler.handle("/export")
    assert r.success and r.action == "export_history"
    assert r.data["format"] == "text"
    assert r.data["path"] == ""

    r = handler.handle("/export json")
    assert r.data["format"] == "jsonl"
    assert r.data["path"] == ""

    r = handler.handle("/export text ./backup/chat.txt")
    assert r.data["format"] == "text"
    assert r.data["path"] == "./backup/chat.txt"

    r = handler.handle("/import ./backup/chat.jsonl")
    assert r.success and r.action == "import_history"
    assert r.data["path"] == "./backup/chat.jsonl"
    assert r.data["merge"] is False

    r = handler.handle("/import ./backup/chat.jsonl --merge")
    assert r.data["merge"] is True

    r = handler.handle("/import")
    assert not r.success

    print("command parse test passed")


if __name__ == "__main__":
    test_export_import()
    test_command_parse()
