"""Markdown / 代码块解析辅助."""

import re
from typing import Dict, Any, List, Optional


def parse_content(content: str) -> List[Dict[str, Any]]:
    """解析内容，提取文本、diff 块和代码块."""
    parts = []
    remaining = content

    # 更宽松的代码块匹配：允许 ```lang 后任意空白再换行
    code_fence_re = re.compile(r'```(\w+)?\s*\n(.*?)```', re.DOTALL)
    diff_fence_re = re.compile(r'```diff\s*\n(.*?)```', re.DOTALL)

    while remaining:
        diff_match = diff_fence_re.search(remaining)
        code_match = code_fence_re.search(remaining)

        matches = []
        if diff_match:
            matches.append(("diff", diff_match))
        if code_match:
            matches.append(("code", code_match))

        if not matches:
            parts.append({"type": "text", "content": remaining.strip()})
            break

        matches.sort(key=lambda x: x[1].start())
        block_type, match = matches[0]

        if match.start() > 0:
            text = remaining[:match.start()].strip()
            if text:
                parts.append({"type": "text", "content": text})

        if block_type == "diff":
            parts.append({"type": "diff", "content": match.group(1)})
        elif block_type == "code":
            lang = match.group(1) or ""
            parts.append({"type": "code", "content": match.group(2), "language": lang})

        remaining = remaining[match.end():]

    return parts


def strip_code_blocks(content: str, block_type: str = "tool") -> str:
    """移除指定类型的代码块."""
    pattern = rf'```{block_type}\s*\n.*?\n```'
    return re.sub(pattern, '', content, flags=re.DOTALL).strip()


def extract_thinking_tags(content: str) -> tuple[str, str]:
    """提取 thinking 标签内容并返回 (thinking, stripped_content)."""
    thinking_parts = []
    pattern = re.compile(r'<thinking>(.*?)</thinking>', re.DOTALL)
    for match in pattern.finditer(content):
        thinking_parts.append(match.group(1))
    stripped = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL)
    return "".join(thinking_parts), stripped
