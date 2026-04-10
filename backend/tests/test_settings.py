import pytest

from backend.core.config import Settings


def test_parse_bool_env_for_log_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_SQL", "1")
    s = Settings()
    assert s.LOG_SQL is True

    monkeypatch.setenv("LOG_SQL", "false")
    s = Settings()
    assert s.LOG_SQL is False


def test_parse_bool_env_for_schema_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_SCHEMA_CHECK_ENABLED", "yes")
    monkeypatch.setenv("DB_SCHEMA_CHECK_FAIL_FAST", "off")
    s = Settings()
    assert s.DB_SCHEMA_CHECK_ENABLED is True
    assert s.DB_SCHEMA_CHECK_FAIL_FAST is False
