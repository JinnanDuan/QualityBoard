#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_DIR/.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "[dt-report] 未在运行（无 PID 文件）"
    exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    sleep 1
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null || true
    fi
    echo "[dt-report] 已停止 (PID: $PID)"
else
    echo "[dt-report] 进程已不存在 (PID: $PID)"
fi

rm -f "$PID_FILE"
