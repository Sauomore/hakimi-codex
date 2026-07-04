#!/bin/bash
# Hakimi CLI 启动脚本 (Unix/Linux/macOS)
# 用法: hakimi [path] [--version] [--help] [--no-git] [--model MODEL]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
python3 -m codex "$@"
