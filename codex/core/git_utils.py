"""Git 工具函数."""

import subprocess
import os
from pathlib import Path
from typing import Optional, List, Tuple


def is_git_repo(path: str) -> bool:
    """检查路径是否为 Git 仓库."""
    git_dir = Path(path) / ".git"
    return git_dir.exists()


def init_git_repo(path: str) -> bool:
    """初始化 Git 仓库."""
    try:
        subprocess.run(
            ["git", "init"],
            cwd=path,
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_git_status(path: str) -> List[Tuple[str, str]]:
    """获取 Git 状态."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True
        )
        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                status = line[:2].strip()
                filename = line[3:].strip()
                files.append((status, filename))
        return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def get_git_diff(path: str, file: Optional[str] = None) -> str:
    """获取 Git diff."""
    try:
        cmd = ["git", "diff"]
        if file:
            cmd.append(file)
        result = subprocess.run(
            cmd,
            cwd=path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def git_add(path: str, files: List[str]) -> bool:
    """添加文件到暂存区."""
    try:
        subprocess.run(
            ["git", "add"] + files,
            cwd=path,
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def git_commit(path: str, message: str) -> bool:
    """提交更改."""
    try:
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=path,
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_git_branch(path: str) -> str:
    """获取当前分支."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_git_log(path: str, n: int = 5) -> List[Tuple[str, str, str]]:
    """获取最近的 Git 提交记录."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={n}", "--format=%H|%s|%an|%ar"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True
        )
        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) >= 3:
                    commits.append((parts[0][:8], parts[1], parts[3] if len(parts) > 3 else ""))
        return commits
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def run_git_command(path: str, args: List[str]) -> Tuple[int, str, str]:
    """执行任意 Git 命令并返回 (exit_code, stdout, stderr).

    使用参数列表传递，避免 shell 注入。
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", "git 命令未找到，请确认已安装 Git 并加入 PATH"
    except Exception as exc:
        return 1, "", f"执行 git 命令时出错: {exc}"
