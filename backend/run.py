# ============================================================
# 应用启动入口 — 加载日志配置后启动 uvicorn
# ============================================================

import logging.config
import os

import uvicorn

from backend.logging_config import get_logging_config

if __name__ == "__main__":
    logging.config.dictConfig(get_logging_config())
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        log_config=get_logging_config(),
    )
