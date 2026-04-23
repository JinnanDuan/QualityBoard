"""环境变量与全局配置。"""

from typing import List, Optional, Union

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
    aifa_fetch_connect_timeout_seconds: float = Field(
        default=3.0,
        validation_alias="AIFA_FETCH_CONNECT_TIMEOUT_SECONDS",
    )
    aifa_fetch_read_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="AIFA_FETCH_READ_TIMEOUT_SECONDS",
    )
    aifa_report_max_chars: int = Field(default=20000, validation_alias="AIFA_REPORT_MAX_CHARS")
    aifa_screenshot_max_bytes: int = Field(
        default=2_000_000,
        validation_alias="AIFA_SCREENSHOT_MAX_BYTES",
    )
    aifa_screenshot_max_images: int = Field(
        default=10,
        validation_alias="AIFA_SCREENSHOT_MAX_IMAGES",
    )
    aifa_fetch_url_max_length: int = Field(
        default=2048,
        validation_alias="AIFA_FETCH_URL_MAX_LENGTH",
    )
    aifa_fetch_allowed_hosts: List[str] = Field(
        default_factory=list,
        validation_alias="AIFA_FETCH_ALLOWED_HOSTS",
    )
    aifa_codehub_base_url: Optional[str] = Field(
        default=None,
        validation_alias="AIFA_CODEHUB_BASE_URL",
    )
    aifa_codehub_token: Optional[str] = Field(
        default=None,
        validation_alias="AIFA_CODEHUB_TOKEN",
    )
    aifa_codehub_connect_timeout_seconds: float = Field(
        default=3.0,
        validation_alias="AIFA_CODEHUB_CONNECT_TIMEOUT_SECONDS",
    )
    aifa_codehub_read_timeout_seconds: float = Field(
        default=15.0,
        validation_alias="AIFA_CODEHUB_READ_TIMEOUT_SECONDS",
    )
    aifa_codehub_list_limit: int = Field(
        default=30,
        validation_alias="AIFA_CODEHUB_LIST_LIMIT",
    )
    aifa_codehub_diff_max_lines: int = Field(
        default=500,
        validation_alias="AIFA_CODEHUB_DIFF_MAX_LINES",
    )
    aifa_codehub_diff_top_n: int = Field(
        default=5,
        validation_alias="AIFA_CODEHUB_DIFF_TOP_N",
    )
    aifa_codehub_fallback_window_days: int = Field(
        default=7,
        validation_alias="AIFA_CODEHUB_FALLBACK_WINDOW_DAYS",
    )
    aifa_max_tokens_per_request: int = Field(
        default=80000,
        validation_alias="AIFA_MAX_TOKENS_PER_REQUEST",
    )
    aifa_price_per_1k_input: float = Field(
        default=0.0,
        validation_alias="AIFA_PRICE_PER_1K_INPUT",
    )
    aifa_price_per_1k_output: float = Field(
        default=0.0,
        validation_alias="AIFA_PRICE_PER_1K_OUTPUT",
    )
    aifa_trace_log_path: str = Field(
        default="trace.log",
        validation_alias="AIFA_TRACE_LOG_PATH",
    )
    aifa_max_concurrent_analyses: int = Field(
        default=8,
        validation_alias="AIFA_MAX_CONCURRENT_ANALYSES",
    )

    @field_validator("aifa_llm_mock", mode="before")
    @classmethod
    def _validate_mock(cls, v: object) -> bool:
        return _parse_bool_mock(v)  # type: ignore[arg-type]

    @field_validator("aifa_fetch_allowed_hosts", mode="before")
    @classmethod
    def _validate_allowed_hosts(cls, v: object) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            out: List[str] = []
            for item in v:
                text = str(item).strip().lower()
                if text:
                    out.append(text)
            return out
        text = str(v).strip()
        if not text:
            return []
        return [host.strip().lower() for host in text.split(",") if host.strip()]


def get_settings() -> Settings:
    """每次调用重新读取环境（便于测试与热更新配置）。"""
    return Settings()
