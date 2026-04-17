"""环境变量与全局配置。"""

from typing import Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_bool_mock(v: Union[str, bool, None]) -> bool:
    if v is None or v is False:
        return False
    if v is True:
        return True
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "on")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    aifa_internal_token: str = Field(default="", validation_alias="AIFA_INTERNAL_TOKEN")
    aifa_llm_base_url: Optional[str] = Field(default=None, validation_alias="AIFA_LLM_BASE_URL")
    aifa_llm_api_key: Optional[str] = Field(default=None, validation_alias="AIFA_LLM_API_KEY")
    aifa_llm_model: str = Field(default="gpt-4o-mini", validation_alias="AIFA_LLM_MODEL")
    aifa_llm_mock: bool = Field(default=False, validation_alias="AIFA_LLM_MOCK")
    aifa_port: int = Field(default=8080, validation_alias="AIFA_PORT")

    @field_validator("aifa_llm_mock", mode="before")
    @classmethod
    def _validate_mock(cls, v: object) -> bool:
        return _parse_bool_mock(v)  # type: ignore[arg-type]


def get_settings() -> Settings:
    """每次调用重新读取环境（便于测试与热更新配置）。"""
    return Settings()
