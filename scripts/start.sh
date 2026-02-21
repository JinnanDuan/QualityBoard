#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_DIR/.pid"
LOG_FILE="$PROJECT_DIR/app.log"
PORT=8000

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[dt-report] 已在运行 (PID: $OLD_PID, 端口: $PORT)"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

echo "[dt-report] 启动中..."
cd "$PROJECT_DIR"

nohup "$PROJECT_DIR/.venv/bin/python" -m backend.run > /dev/null 2>&1 &

echo $! > "$PID_FILE"
sleep 2

if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[dt-report] 启动成功 (PID: $(cat "$PID_FILE"), 端口: $PORT)"
    echo "[dt-report] 日志: app.log, access.log"
else
    echo "[dt-report] 启动失败，请检查 app.log"
    rm -f "$PID_FILE"
    exit 1
fi
