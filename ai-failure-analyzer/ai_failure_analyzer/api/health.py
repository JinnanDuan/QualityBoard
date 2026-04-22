"""健康检查。"""

from fastapi import APIRouter, Depends

from ai_failure_analyzer.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz(settings: Settings = Depends(get_settings)) -> dict:
    if settings.aifa_llm_mock:
        llm_status = "ok"
    elif settings.aifa_llm_base_url and settings.aifa_llm_api_key:
        llm_status = "ok"
    else:
        llm_status = "not_configured"

    return {
        "status": "ok",
        "checks": {
            "process": "ok",
            "report_fetch": "skipped",
            "codehub": "skipped",
            "llm": llm_status,
        },
    }
