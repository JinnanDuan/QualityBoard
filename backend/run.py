# ============================================================
# 应用启动入口 — 加载日志配置后启动 uvicorn
# ============================================================

import asyncio
import logging.config
import os
import sys

import uvicorn

from backend.core.config import settings
from backend.logging_config import get_logging_config
from backend.services.schema_check_service import (
    format_diff_report,
    run_schema_check,
)

if __name__ == "__main__":
    logging.config.dictConfig(get_logging_config())
    logger = logging.getLogger("backend.run")

    if settings.DB_SCHEMA_CHECK_ENABLED:
        try:
            ok, diffs = asyncio.run(run_schema_check())
            if not ok:
                report = format_diff_report(diffs)
                logger.error(report)
                sys.stderr.write(report + "\n")
                if settings.DB_SCHEMA_CHECK_FAIL_FAST:
                    sys.exit(1)
                logger.warning("DB Schema Check 发现不一致，继续启动（DB_SCHEMA_CHECK_FAIL_FAST=false）")
            else:
                logger.info("DB Schema Check 通过，10 张表结构一致")
        except Exception as e:
            logger.exception("DB Schema Check 异常: %s", e)
            sys.exit(1)

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        log_config=get_logging_config(),
    )
