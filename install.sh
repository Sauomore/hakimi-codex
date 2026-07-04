#!/bin/bash
# Codex 安装脚本 (Unix/Linux/macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "   Codex CLI 安装程序"
echo "=========================================="
echo

# 检查 Python
echo "[1/3] 检查 Python..."
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3。请先安装 Python 3.9+"
    exit 1
fi

python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" || {
    echo "[错误] Python 版本过低，需要 3.9+"
    exit 1
}
echo "    Python 版本检查通过"
echo

# 安装依赖
echo "[2/3] 安装依赖包..."
cd "$SCRIPT_DIR"
pip3 install -e . --quiet
echo "    依赖安装完成"
echo

# 验证
echo "[3/3] 验证安装..."
python3 -c "import codex; print('Codex v' + codex.__version__)"
echo "    安装验证通过"
echo

echo "=========================================="
echo "   安装成功！"
echo "=========================================="
echo
echo "启动方式："
echo "   方式1: ./codex.sh 启动"
echo "   方式2: python3 -m codex"
echo "   方式3: 添加到 PATH 后运行 'codex'"
echo
