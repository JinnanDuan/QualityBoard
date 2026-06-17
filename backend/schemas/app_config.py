# ============================================================
# 前端只读配置 — Schema
# ============================================================

from typing import Optional

from pydantic import BaseModel, Field


class FrontendConfigResponse(BaseModel):
    """GET /app/frontend-config：Drawer 外部链接等前端展示用配置（来自 .env）。"""

    test_code_repo_url: Optional[str] = Field(
        None, description="测试代码仓地址；未配置则为 None"
    )
    package_init_url: Optional[str] = Field(
        None,
        description="取包链接模板，占位符 code_branch / start_time / package_name",
    )
    package_name_mac: Optional[str] = Field(None, description="mac 平台包名")
    package_name_oh: Optional[str] = Field(None, description="oh 平台包名")
