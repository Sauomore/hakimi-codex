"""CLI 入口."""

import sys
import argparse
from pathlib import Path


def main():
    """主入口函数."""
    parser = argparse.ArgumentParser(
        prog="hakimi",
        description="Hakimi - 现代化 AI 代码助手 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  hakimi                    # 在当前目录启动
  hakimi /path/to/project   # 在指定项目目录启动
  hakimi --version          # 显示版本
        """
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="项目路径 (默认: 当前目录)"
    )
    parser.add_argument(
        "-v", "--version",
        action="store_true",
        help="显示版本信息"
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="禁用 Git 集成"
    )
    parser.add_argument(
        "--model",
        help="指定使用的模型 ID"
    )
    
    args = parser.parse_args()
    
    if args.version:
        from codex import __version__
        print(f"Hakimi v{__version__}")
        sys.exit(0)
    
    project_path = Path(args.path).resolve()
    if not project_path.exists():
        print(f"错误: 路径不存在: {project_path}")
        sys.exit(1)
    
    if not project_path.is_dir():
        print(f"错误: 不是目录: {project_path}")
        sys.exit(1)
    
    try:
        from codex.app import HakimiApp
        app = HakimiApp(project_path=str(project_path))
        app.run()
    except ImportError as e:
        print(f"错误: 缺少依赖 - {e}")
        print("请运行: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已退出")
        sys.exit(0)


if __name__ == "__main__":
    main()
