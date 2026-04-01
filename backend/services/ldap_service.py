"""LDAP 域账号认证服务。"""

import asyncio
import logging

from ldap3 import Connection, SCHEMA, Server

from backend.core.config import settings

logger = logging.getLogger(__name__)


def _build_bind_user(domain_account: str) -> str:
    """构建 LDAP bind 用户标识。"""
    if settings.LDAP_DOMAIN:
        return f"{domain_account}@{settings.LDAP_DOMAIN}"
    return domain_account


def _verify_ldap_sync(domain_account: str, password: str) -> bool:
    """同步执行 LDAP bind 校验（在线程池中调用）。"""
    if not password:
        return False
    bind_user = _build_bind_user(domain_account)
    server = Server(
        settings.LDAP_HOST,
        port=settings.LDAP_PORT,
        use_ssl=False,
        get_info=SCHEMA,
    )
    conn = Connection(server, user=bind_user, password=password)
    try:
        return conn.bind()
    except Exception as e:
        logger.debug("LDAP bind 异常 domain_account=%s: %s", domain_account, e)
        return False
    finally:
        try:
            conn.unbind()
        except Exception:
            pass


async def verify_ldap_credentials(domain_account: str, password: str) -> bool:
    """
    校验域账号与密码是否通过 LDAP 认证。

    :param domain_account: 域账号（比工号多首字母）
    :param password: 域密码
    :return: True 表示校验通过，False 表示失败
    """
    # Python 3.8 无 asyncio.to_thread（3.9+）；用默认线程池等同语义
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _verify_ldap_sync, domain_account, password
    )
