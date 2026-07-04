@echo off
REM Hakimi CLI 启动脚本
REM 用法: hakimi [path] [--version] [--help] [--no-git] [--model MODEL]

cd /d "%~dp0"
py -m codex %*
