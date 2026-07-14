"""应用日志工具.

支持按项目根目录输出调试日志文件，文件名固定为 hakimi_debug.log.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


class ProjectLogger:
    """按项目维度的日志记录器."""

    _instance: Optional["ProjectLogger"] = None
    _logger: Optional[logging.Logger] = None
    _project_path: Optional[Path] = None
    _file_handler: Optional[logging.FileHandler] = None

    def __new__(cls) -> "ProjectLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def setup(self, project_path: Path, enabled: bool = True) -> logging.Logger:
        """设置或重新设置日志记录器.

        enabled 为 False 时只返回一个输出到 stderr 的 logger.
        """
        if self._logger is None:
            self._logger = logging.getLogger("hakimi")
            self._logger.setLevel(logging.DEBUG)
            # 避免重复添加 handler
            self._logger.handlers.clear()

            # 控制台 handler（INFO 级别）
            console = logging.StreamHandler(sys.stderr)
            console.setLevel(logging.INFO)
            console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            self._logger.addHandler(console)

        project_path = Path(project_path).resolve()

        # 如果项目路径变化或 debug 开关变化，需要重建文件 handler
        need_rebuild = (
            self._project_path != project_path
            or (enabled and self._file_handler is None)
            or (not enabled and self._file_handler is not None)
        )

        if need_rebuild:
            if self._file_handler:
                self._logger.removeHandler(self._file_handler)
                self._file_handler.close()
                self._file_handler = None

            if enabled:
                log_file = project_path / "hakimi_debug.log"
                try:
                    file_handler = logging.FileHandler(
                        log_file, mode="a", encoding="utf-8"
                    )
                    file_handler.setLevel(logging.DEBUG)
                    file_handler.setFormatter(
                        logging.Formatter(
                            "%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                        )
                    )
                    self._logger.addHandler(file_handler)
                    self._file_handler = file_handler
                    self._logger.info(f"Debug logging enabled: {log_file}")
                except Exception as e:
                    self._logger.error(f"Failed to create debug log file: {e}")

            self._project_path = project_path

        return self._logger

    def get(self) -> logging.Logger:
        """获取当前日志记录器."""
        if self._logger is None:
            # 兜底：未初始化时返回默认 logger
            return logging.getLogger("hakimi")
        return self._logger


def get_logger() -> logging.Logger:
    """获取全局 hakimi logger."""
    return ProjectLogger().get()


def setup_logger(project_path: Path, enabled: bool = True) -> logging.Logger:
    """初始化项目日志."""
    return ProjectLogger().setup(project_path, enabled)


def debug(msg: str) -> None:
    """输出 DEBUG 级别日志."""
    ProjectLogger().get().debug(msg)


def info(msg: str) -> None:
    """输出 INFO 级别日志."""
    ProjectLogger().get().info(msg)


def warning(msg: str) -> None:
    """输出 WARNING 级别日志."""
    ProjectLogger().get().warning(msg)


def error(msg: str) -> None:
    """输出 ERROR 级别日志."""
    ProjectLogger().get().error(msg)
