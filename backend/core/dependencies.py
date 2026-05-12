import hmac
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import verify_token
from backend.services.auth_service import get_user_role

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)
_ut_gate_bearer = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncSession:  # type: ignore[misc]
    async with get_db() as session:
        yield session


async def get_current_user(token=Depends(bearer_scheme)) -> dict:
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return verify_token(token.credentials)


async def require_apply_failure_reason_permission(
    payload: dict = Depends(get_current_user),
) -> dict:
    """
    A4 写库权限依赖。
    当前策略：登录用户（user/admin）均可执行；保留显式授权检查点，便于后续收紧。
    """
    employee_id = str(payload.get("sub", "")).strip()
    if not employee_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    role = get_user_role(employee_id)
    if role not in ("user", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限执行该操作")
    return payload


async def verify_ut_gate_integration_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_ut_gate_bearer),
) -> None:
    """
    UT 门禁 Jenkins 上报专用：Bearer 与 UT_GATE_INTEGRATION_TOKEN 一致（spec/16 §3）。
    Token 未配置或非 Bearer 时返回 401；不在日志中输出 Token。
    """
    expected = (settings.UT_GATE_INTEGRATION_TOKEN or "").strip()
    if not expected:
        logger.warning("UT 门禁上报被拒绝：UT_GATE_INTEGRATION_TOKEN 未配置")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="UT 门禁上报未启用或密钥未配置",
        )
    if credentials is None or (credentials.scheme or "").lower() != "bearer":
        logger.warning("UT 门禁上报鉴权失败：缺少或非法的 Authorization")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或不存在的认证信息",
        )
    received = credentials.credentials or ""
    try:
        ok = hmac.compare_digest(received.encode("utf-8"), expected.encode("utf-8"))
    except ValueError:
        ok = False
    if not ok:
        logger.warning("UT 门禁上报鉴权失败：Token 不匹配")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
        )
