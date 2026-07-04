"""CLI 入口."""

import sys
import argparse
from pathlib import Path


def main():
    """主入口函数."""
    parser = argparse.ArgumentParser(
        prog="hakimi",
        description="Hakimi Codex - AI Coding Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hakimi                    # Launch in current directory
  hakimi /path/to/project   # Launch in project directory
  hakimi --version          # Show version
        """
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project path (default: current directory)"
    )
    parser.add_argument(
        "-v", "--version",
        action="store_true",
        help="Show version information"
    )
    
    args = parser.parse_args()
    
    if args.version:
        from codex import __version__
        print(f"Hakimi Codex v{__version__}")
        sys.exit(0)
    
    project_path = Path(args.path).resolve()
    if not project_path.exists():
        print(f"Error: Path does not exist: {project_path}")
        sys.exit(1)
    
    if not project_path.is_dir():
        print(f"Error: Not a directory: {project_path}")
        sys.exit(1)
    
    try:
        from codex.app import HakimiApp
        app = HakimiApp(project_path=str(project_path))
        app.run()
    except ImportError as e:
        print(f"Error: Missing dependency - {e}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExited")
        sys.exit(0)


if __name__ == "__main__":
    main()
