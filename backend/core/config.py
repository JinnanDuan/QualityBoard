from pathlib import Path
from typing import Any, List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings

# 项目根目录，确保 .env 无论从何处启动都能正确加载
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _parse_bool(v: Any) -> bool:
    """显式解析布尔值，避免 pydantic 对 'False' 等字符串的解析差异。"""
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("true", "1", "yes", "on")


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:root@127.0.0.1:3306/dt_infra"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ADMIN_EMPLOYEE_IDS: List[str] = []
    MVP_LOGIN_PASSWORD: str = "dt_report_2026"
    CORS_ORIGINS: List[str] = ["*"]
    WELINK_API_URL: str = ""
    WELINK_APP_ID: str = ""
    WELINK_APP_SECRET: str = ""

    # LDAP 域登录（LDAP_HOST 留空则使用 MVP 密码模式）
    LDAP_HOST: str = ""
    LDAP_PORT: int = 389
    LDAP_DOMAIN: str = ""  # 可选，用于拼接 domain_account@LDAP_DOMAIN，空则原样 bind

    # 日志配置
    ENV: str = "development"
    LOG_LEVEL: Optional[str] = None  # 空则随 ENV：development=DEBUG, production=INFO
    LOG_DIR: str = ""
    LOG_APP_MAX_BYTES: int = 10485760
    LOG_APP_BACKUP_COUNT: int = 5
    LOG_ACCESS_MAX_BYTES: int = 10485760
    LOG_ACCESS_BACKUP_COUNT: int = 3
    LOG_SQL: bool = False  # 为 True 时在 app.log 中打印所有 SQL（调试用）

    @field_validator("LOG_SQL", mode="before")
    @classmethod
    def _parse_log_sql(cls, v: Any) -> bool:
        return _parse_bool(v)

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
