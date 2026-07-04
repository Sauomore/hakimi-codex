@echo off
chcp 65001 >nul
REM Codex 安装脚本 (Windows)

echo ==========================================
echo    Codex CLI 安装程序
echo ==========================================
echo.

REM 检查 Python
py --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python。请先安装 Python 3.9+
    pause
    exit /b 1
)

echo [1/3] 检查 Python 版本...
py -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
    echo [错误] Python 版本过低，需要 3.9+
    pause
    exit /b 1
)
echo     Python 版本检查通过
echo.

echo [2/3] 安装依赖包...
cd /d "%~dp0"
py -m pip install -e . --quiet
if errorlevel 1 (
    echo [错误] 安装失败
    pause
    exit /b 1
)
echo     依赖安装完成
echo.

echo [3/3] 验证安装...
py -c "import codex; print('Codex v' + codex.__version__)"
if errorlevel 1 (
    echo [错误] 验证失败
    pause
    exit /b 1
)
echo     安装验证通过
echo.

echo ==========================================
echo    安装成功！
echo ==========================================
echo.
echo 启动方式：
echo   方式1: 双击 codex.bat 启动
echo   方式2: 在任意目录运行 "py -m codex"
echo   方式3: 将 %~dp0 添加到 PATH 后运行 "codex"
echo.
pause
