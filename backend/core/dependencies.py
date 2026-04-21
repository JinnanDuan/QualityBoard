from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import verify_token
from backend.services.auth_service import get_user_role

bearer_scheme = HTTPBearer(auto_error=False)


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
