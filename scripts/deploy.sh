#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "====== dt-report 部署 ======"

# 1) 后端依赖
echo ""
echo "[1/3] 安装后端依赖..."
cd "$PROJECT_DIR"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
"$PROJECT_DIR/.venv/bin/pip" install --upgrade pip -q
"$PROJECT_DIR/.venv/bin/pip" install -r backend/requirements.txt -q
echo "  后端依赖安装完成。WeLink 一键通知需手动执行 playwright install chromium，见 docs/03_deployment_guide.md"

# 2) 前端构建
echo ""
echo "[2/3] 构建前端..."
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd "$PROJECT_DIR/frontend"
pnpm install --frozen-lockfile 2>/dev/null || pnpm install
pnpm build
echo "  前端构建完成 -> frontend/dist/"

# 3) 启动后端
echo ""
echo "[3/3] 启动后端..."
"$SCRIPT_DIR/stop.sh" 2>/dev/null || true
"$SCRIPT_DIR/start.sh"

echo ""
echo "====== 部署完成 ======"
echo "访问地址: http://$(hostname -I | awk '{print $1}'):${PORT:-8000}"
