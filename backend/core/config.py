from typing import List, Optional

from pydantic_settings import BaseSettings


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

    # 日志配置
    ENV: str = "development"
    LOG_LEVEL: Optional[str] = None  # 空则随 ENV：development=DEBUG, production=INFO
    LOG_DIR: str = ""
    LOG_APP_MAX_BYTES: int = 10485760
    LOG_APP_BACKUP_COUNT: int = 5
    LOG_ACCESS_MAX_BYTES: int = 10485760
    LOG_ACCESS_BACKUP_COUNT: int = 3
    LOG_SQL: bool = False  # 为 True 时在 app.log 中打印所有 SQL（调试用）

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
