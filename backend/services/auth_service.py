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


def _is_ldap_enabled() -> bool:
    """LDAP 已配置时启用域登录。"""
    return bool(settings.LDAP_HOST)


def _parse_employee_id_from_domain_account(domain_account: str) -> str:
    """域账号去掉首字母得到工号，如 wW00001 -> W00001。"""
    if len(domain_account) > 1:
        return domain_account[1:]
    return domain_account


async def _build_user_info_from_ums_or_default(
    db: AsyncSession, employee_id: str, domain_account: str
) -> UserInfo:
    """优先从 ums_email 获取用户信息，查不到则用默认值。"""
    stmt = select(UmsEmail).where(UmsEmail.employee_id == employee_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    role = get_user_role(employee_id)
    if user is not None:
        return UserInfo(
            employee_id=user.employee_id,
            name=user.name,
            email=user.email,
            role=role,
        )
    return UserInfo(
        employee_id=employee_id,
        name=domain_account,
        email="",
        role=role,
    )


async def authenticate_user(db: AsyncSession, login_req: LoginRequest) -> LoginResponse:
    domain_account = login_req.employee_id  # 字段名沿用，语义为域账号

    if _is_ldap_enabled():
        from backend.services.ldap_service import verify_ldap_credentials

        ok = await verify_ldap_credentials(domain_account, login_req.password)
        if not ok:
            logger.warning(
                "登录失败 domain_account=%s 原因=LDAP校验失败", domain_account
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误"
            )
        employee_id = _parse_employee_id_from_domain_account(domain_account)
        user_info = await _build_user_info_from_ums_or_default(
            db, employee_id, domain_account
        )
        access_token = create_access_token(subject=employee_id)
        logger.info(
            "登录成功 domain_account=%s employee_id=%s role=%s",
            domain_account,
            employee_id,
            user_info.role,
        )
        return LoginResponse(access_token=access_token, user=user_info)

    # MVP 模式
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

    if user is not None:
        role = get_user_role(user.employee_id)
        return CurrentUserResponse(
            employee_id=user.employee_id,
            name=user.name,
            email=user.email,
            domain_account=user.domain_account,
            role=role,
        )

    # LDAP 用户可能不在 ums_email，返回基础信息
    role = get_user_role(employee_id)
    return CurrentUserResponse(
        employee_id=employee_id,
        name=employee_id,
        email="",
        domain_account=None,
        role=role,
    )
