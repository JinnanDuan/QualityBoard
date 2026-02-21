import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.security import create_access_token
from backend.models.ums_email import UmsEmail
from backend.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    UserInfo,
)

logger = logging.getLogger(__name__)


def get_user_role(employee_id: str) -> str:
    if employee_id in settings.ADMIN_EMPLOYEE_IDS:
        return "admin"
    return "user"


async def authenticate_user(db: AsyncSession, login_req: LoginRequest) -> LoginResponse:
    stmt = select(UmsEmail).where(UmsEmail.employee_id == login_req.employee_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user is None:
        logger.warning("登录失败 employee_id=%s 原因=账号不存在", login_req.employee_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在")

    if login_req.password != settings.MVP_LOGIN_PASSWORD:
        logger.warning("登录失败 employee_id=%s 原因=密码错误", login_req.employee_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密码错误")

    access_token = create_access_token(subject=user.employee_id)
    role = get_user_role(user.employee_id)

    user_info = UserInfo(
        employee_id=user.employee_id,
        name=user.name,
        email=user.email,
        role=role,
    )

    logger.info("登录成功 employee_id=%s role=%s", user.employee_id, role)
    return LoginResponse(access_token=access_token, user=user_info)


async def get_user_info(db: AsyncSession, employee_id: str) -> CurrentUserResponse:
    stmt = select(UmsEmail).where(UmsEmail.employee_id == employee_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    role = get_user_role(user.employee_id)

    return CurrentUserResponse(
        employee_id=user.employee_id,
        name=user.name,
        email=user.email,
        domain_account=user.domain_account,
        role=role,
    )
