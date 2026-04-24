"""FastAPI 应用入口。"""

import logging

from fastapi import FastAPI

from ai_failure_analyzer.api.health import router as health_router
from ai_failure_analyzer.api.v1.analyze import router as analyze_v1_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="ai-failure-analyzer",
    description="AIFA — AI 辅助失败原因分析（Phase A1）",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(analyze_v1_router, prefix="/v1")
