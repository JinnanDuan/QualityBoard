# ============================================================
# API 路由层 — 应用级前端配置（/api/v1/app）
# ============================================================

from typing import Optional

from fastapi import APIRouter, Depends

from backend.core.config import settings
from backend.core.dependencies import get_current_user
from backend.schemas.app_config import FrontendConfigResponse

router = APIRouter(prefix="/app", tags=["应用配置"])


def _opt_str(val: str) -> Optional[str]:
    s = (val or "").strip()
    return s if s else None


@router.get("/frontend-config", response_model=FrontendConfigResponse)
async def get_frontend_config(_: dict = Depends(get_current_user)):
    """返回前端展示用只读配置（测试代码仓、取包地址模板等），值来自 .env。"""
    return FrontendConfigResponse(
        test_code_repo_url=_opt_str(settings.TEST_CODE_REPO_URL),
        package_init_url=_opt_str(settings.PACKAGE_INIT_URL),
        package_name_mac=_opt_str(settings.PACKAGE_NAME_MAC),
        package_name_oh=_opt_str(settings.PACKAGE_NAME_OH),
    )
