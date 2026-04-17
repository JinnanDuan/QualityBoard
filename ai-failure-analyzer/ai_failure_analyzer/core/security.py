"""内部 Service Token 校验。"""

import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from typing_extensions import Annotated

from ai_failure_analyzer.core.config import Settings, get_settings


def verify_bearer(
    authorization: Annotated[Optional[str], Header(include_in_schema=False)] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """校验 ``Authorization: Bearer <AIFA_INTERNAL_TOKEN>``。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权：缺少或非法的 Authorization",
        )
    token = authorization[len("Bearer ") :].strip()
    expected = settings.aifa_internal_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权：服务未配置内部令牌",
        )
    if not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权：令牌无效",
        )
