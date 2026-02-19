#!/usr/bin/env bash

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_DIR/.pid"
PORT=8000

echo "====== dt-report 状态 ======"

# 1) 进程检查
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[后端进程]  运行中 (PID: $PID)"
    else
        echo "[后端进程]  已停止（PID 文件残留）"
    fi
else
    echo "[后端进程]  未启动"
fi

# 2) 端口检查
if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "[端口 $PORT] 已监听"
else
    echo "[端口 $PORT] 未监听"
fi

# 3) API 检查
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/docs" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "[API /docs] 正常 (HTTP $HTTP_CODE)"
else
    echo "[API /docs] 异常 (HTTP $HTTP_CODE)"
fi

# 4) 前端检查
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "[前端页面]  正常 (HTTP $HTTP_CODE)"
else
    echo "[前端页面]  异常 (HTTP $HTTP_CODE)"
fi

echo "============================="
