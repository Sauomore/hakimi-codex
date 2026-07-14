"""工具调用解析器.

针对 DeepSeek 等模型在 Agent 模式下的输出特点做兼容：
- DeepSeek R1 没有原生 Function Call，常在 content 中输出 DSML 标记
- JSON 格式容易混入注释、尾部逗号、多余文本
- 模型可能把工具调用写成 ```json 或普通内联 JSON
"""

import json
import re
from typing import Any, Dict, List, Tuple


def _strip_json_comments(text: str) -> str:
    """移除 JSON 中的 // 和 /* */ 注释."""
    # 先移除 /* */ 注释（不支持嵌套）
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # 再移除 // 行注释
    lines = []
    for line in text.split("\n"):
        cleaned = line
        in_string = False
        i = 0
        while i < len(cleaned):
            ch = cleaned[i]
            if ch == '"' and (i == 0 or cleaned[i - 1] != "\\"):
                in_string = not in_string
            elif not in_string and cleaned[i:i + 2] == "//":
                cleaned = cleaned[:i]
                break
            i += 1
        lines.append(cleaned)
    return "\n".join(lines)


def _strip_trailing_commas(text: str) -> str:
    """移除 JSON 中对象/数组末尾的多余逗号."""
    # 在 } 或 ] 之前的 ,\s* 去掉
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _repair_json(text: str) -> str:
    """常见 JSON 修复."""
    text = text.strip()
    text = _strip_json_comments(text)
    text = _strip_trailing_commas(text)
    return text


def _extract_json_objects(text: str) -> List[Dict[str, Any]]:
    """从文本中扫描所有独立的 JSON 对象/数组.

    返回所有包含 "tool" 或 "command" 键的字典（支持对象数组展开）.
    """
    decoder = json.JSONDecoder()
    objects: List[Dict[str, Any]] = []
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx] not in "{[":
            idx += 1
        if idx >= len(text):
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
            if isinstance(obj, dict) and ("tool" in obj or "command" in obj):
                objects.append(obj)
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict) and ("tool" in item or "command" in item):
                        objects.append(item)
            idx = end
        except json.JSONDecodeError:
            idx += 1
    return objects


def _extract_dsml_tool_calls(text: str) -> List[str]:
    """提取 DeepSeek DSML 工具调用块中的原始文本."""
    pattern = re.compile(
        r"<‖dsml‖tool_calls>\s*(.*?)\s*</‖dsml‖tool_calls>",
        re.DOTALL,
    )
    return [m.group(1).strip() for m in pattern.finditer(text)]


def _extract_code_blocks(text: str) -> List[Tuple[str, str]]:
    """提取 ```language ... ``` 代码块.

    返回 [(language, content), ...].

    针对 write_file 等工具的 content 字段内部也可能包含 ``` 的情况做兼容：
    逐个尝试可能的结束标记，直到能解析出合法的工具调用 JSON。
    """
    pattern = re.compile(r"```\s*(\w*)\s*\n", re.IGNORECASE)
    blocks: List[Tuple[str, str]] = []

    for match in pattern.finditer(text):
        lang = match.group(1).strip().lower()
        start = match.end()

        # 收集所有可能的代码块结束位置
        end_positions = [m.start() for m in re.finditer(r"\n\s*```", text[start:])]
        end_positions = [start + p for p in end_positions]

        for end in end_positions:
            block = text[start:end].strip()
            if not block:
                continue
            # 快速过滤：合法 JSON 对象/数组应以 } 或 ] 结尾
            if block[-1] not in "}]":
                continue
            repaired = _repair_json(block)
            if _extract_json_objects(repaired):
                blocks.append((lang, block))
                break

    return blocks


def parse_tool_calls(content: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """解析内容中的所有工具调用.

    返回 (成功解析的调用列表, 解析失败的原始片段列表).
    """
    tool_calls: List[Dict[str, Any]] = []
    errors: List[str] = []
    seen = set()

    def add_call(call: Dict[str, Any], raw: str) -> None:
        key = json.dumps(call, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            tool_calls.append(call)

    def record_error(raw: str) -> None:
        snippet = raw.strip().replace("\n", " ")[:120]
        if snippet and snippet not in errors:
            errors.append(snippet)

    # 1. 标准代码块：```tool / ```json
    for lang, block in _extract_code_blocks(content):
        if lang not in ("tool", "json", ""):
            continue
        repaired = _repair_json(block)
        calls = _extract_json_objects(repaired)
        if not calls and block.strip():
            record_error(block)
        for call in calls:
            add_call(call, block)

    # 2. DeepSeek DSML 格式
    for block in _extract_dsml_tool_calls(content):
        repaired = _repair_json(block)
        calls = _extract_json_objects(repaired)
        if not calls and block.strip():
            record_error(block)
        for call in calls:
            add_call(call, block)

    # 3. 全文中内联 JSON（兜底，避免模型忘记加代码块）
    repaired = _repair_json(content)
    for call in _extract_json_objects(repaired):
        add_call(call, content)

    return tool_calls, errors
