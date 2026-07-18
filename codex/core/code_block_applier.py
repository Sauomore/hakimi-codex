"""AI 输出代码块的 diff 预览与一键应用."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .diff_utils import generate_unified_diff
from .tools import ToolExecutor, ToolResultStatus

if TYPE_CHECKING:
    from .chat_engine import ChatCallbacks


# 常见代码语言，避免被误判为文件路径
_KNOWN_LANGUAGES = {
    "python", "py", "javascript", "js", "typescript", "ts", "jsx", "tsx",
    "java", "cpp", "c", "c++", "cs", "csharp", "go", "golang", "rust", "rs",
    "ruby", "rb", "php", "swift", "kt", "kotlin", "scala", "r", "matlab",
    "html", "htm", "css", "scss", "sass", "less", "xml", "yaml", "yml",
    "json", "toml", "ini", "cfg", "conf", "sh", "bash", "zsh", "powershell",
    "ps1", "sql", "dockerfile", "makefile", "cmake", "lua", "perl", "vim",
    "markdown", "md", "tex", "latex", "rust", "shell", "nginx", "graphql",
    "svg", "plantuml",
}


@dataclass
class CodeBlock:
    """解析出的代码块."""

    language: str
    info: str
    code: str
    start: int
    end: int


_CODE_BLOCK_RE = re.compile(
    r"^```[ \t]*(\S+)?(?:[ \t]+(.+?))?[ \t]*\r?\n(.*?)```\s*$",
    re.MULTILINE | re.DOTALL,
)


def extract_code_blocks(content: str) -> List[CodeBlock]:
    """从内容中提取所有代码块，保留 info 行中的完整信息."""
    blocks: List[CodeBlock] = []
    for match in _CODE_BLOCK_RE.finditer(content):
        first = (match.group(1) or "").strip()
        rest = (match.group(2) or "").strip()
        info = f"{first} {rest}".strip()
        blocks.append(
            CodeBlock(
                language=first.lower(),
                info=info,
                code=match.group(3).rstrip(),
                start=match.start(),
                end=match.end(),
            )
        )
    return blocks


def _looks_like_path(token: str) -> bool:
    """判断一个 token 是否像文件路径."""
    if not token or len(token) < 2:
        return False
    if token.startswith(("http://", "https://", "ftp://", "file://")):
        return False
    # 包含路径分隔符，直接认为是路径
    if "/" in token or "\\" in token:
        return True
    # 包含扩展名且不是单纯的语言名，也认为是路径候选
    if "." in token and token.lower() not in _KNOWN_LANGUAGES:
        return True
    return False


def _normalize_path(token: str) -> str:
    """统一路径分隔符并去除首尾引号."""
    token = token.strip().strip("'\"`")
    return token.replace("\\", "/")


def _path_from_info(info: str) -> Optional[str]:
    """从代码块 info 行解析目标路径."""
    if not info:
        return None

    # 支持 language:path 形式
    if ":" in info and "/" not in info.split(":", 1)[0]:
        lang_part, path_part = info.split(":", 1)
        if _looks_like_path(path_part):
            return _normalize_path(path_part)

    tokens = info.split()
    for token in tokens:
        if _looks_like_path(token):
            return _normalize_path(token)

    return None


def _path_from_preceding_text(text_before: str, project_path: Path) -> Optional[str]:
    """从代码块之前的文本中推断目标路径."""
    # 1. 显式标记：file/path/文件/路径：xxx
    marker_match = re.search(
        r"(?:file|path|文件|路径)\s*[:：]\s*([^\s\n]+)",
        text_before,
        re.IGNORECASE,
    )
    if marker_match:
        candidate = _normalize_path(marker_match.group(1))
        if _looks_like_path(candidate):
            return candidate

    # 2. 从后往前找第一个存在的文件路径
    # 匹配 token：可包含字母数字下划线、连字符、点、路径分隔符，且以扩展名结尾
    for token in reversed(re.findall(r"[A-Za-z0-9_.\-/\\]+\.[A-Za-z0-9_]+", text_before)):
        candidate = _normalize_path(token)
        if not _looks_like_path(candidate):
            continue
        if (project_path / candidate).is_file():
            return candidate

    # 3. 如果都不存在，返回最后一个看起来像路径的候选（可能是新建文件）
    for token in reversed(re.findall(r"[A-Za-z0-9_.\-/\\]+\.[A-Za-z0-9_]+", text_before)):
        candidate = _normalize_path(token)
        if _looks_like_path(candidate):
            return candidate

    return None


def detect_target_file_path(
    block: CodeBlock,
    full_content: str,
    project_path: Path,
) -> Optional[str]:
    """推断代码块想修改的目标文件路径."""
    # 跳过 diff / tool / json 等明显不是完整文件内容的代码块
    if block.language in {"diff", "patch", "tool", "json"}:
        return None

    # 优先从 info 行解析
    path = _path_from_info(block.info)
    if path:
        return path

    # 其次从代码块之前的文本推断
    text_before = full_content[: block.start]
    return _path_from_preceding_text(text_before, project_path)


async def apply_code_blocks(
    content: str,
    tool_executor: ToolExecutor,
    callbacks: ChatCallbacks,
    confirm_write_file: bool = True,
) -> List[Dict[str, Any]]:
    """扫描内容中的代码块，对疑似文件修改的建议进行 diff 预览并支持一键应用.

    返回每次尝试应用的结果列表。
    """
    results: List[Dict[str, Any]] = []
    blocks = extract_code_blocks(content)

    for block in blocks:
        file_path = detect_target_file_path(block, content, tool_executor.project_path)
        if not file_path:
            continue

        read_result = tool_executor.read_file(file_path)
        file_exists = read_result.status == ToolResultStatus.SUCCESS
        old_content = read_result.output if file_exists else ""
        new_content = block.code

        if file_exists and old_content == new_content:
            callbacks.add_system_message(
                f"[#888888]代码块与 {file_path} 内容一致，无需写入。[/#888888]"
            )
            results.append({"file_path": file_path, "applied": False, "reason": "identical"})
            continue

        diff = generate_unified_diff(old_content, new_content, file_path)
        callbacks.show_diff_preview(diff)

        if confirm_write_file:
            confirmed = await callbacks.confirm_action(
                title=f"确认应用代码块到: {file_path}",
                content=diff,
                content_type="diff",
                confirm_label="确认写入",
            )
        else:
            confirmed = True

        if confirmed:
            write_result = tool_executor.write_file(file_path, new_content)
            if write_result.status == ToolResultStatus.SUCCESS:
                action = "覆盖" if file_exists else "创建"
                callbacks.add_system_message(
                    f"[bold green]已{action}文件: {file_path}[/bold green]"
                )
                results.append({"file_path": file_path, "applied": True, "created": not file_exists})
            else:
                callbacks.add_system_message(
                    f"[bold red]写入 {file_path} 失败: {write_result.output}[/bold red]"
                )
                results.append({"file_path": file_path, "applied": False, "reason": write_result.output})
        else:
            callbacks.add_system_message(
                f"[bold yellow]已取消写入 {file_path}[/bold yellow]"
            )
            results.append({"file_path": file_path, "applied": False, "reason": "cancelled"})

    return results
