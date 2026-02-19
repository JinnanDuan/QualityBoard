from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:root@127.0.0.1:3306/dt_infra"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ADMIN_EMPLOYEE_IDS: List[str] = []
    CORS_ORIGINS: List[str] = ["*"]
    WELINK_API_URL: str = ""
    WELINK_APP_ID: str = ""
    WELINK_APP_SECRET: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
