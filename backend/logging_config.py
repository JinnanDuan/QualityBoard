# ============================================================
# 日志配置 — dictConfig 结构，供 uvicorn 与应用使用
# ============================================================

import logging
import logging.config
from pathlib import Path
from typing import Any, Dict

from backend.core.config import settings
from backend.core.request_id import get_request_endpoint, get_request_id


class RequestIdFilter(logging.Filter):
    """从 contextvars 读取 request_id、endpoint 注入到 LogRecord。"""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = get_request_id()
        record.request_id = f"[req:{rid}]" if rid else "-"
        ep = get_request_endpoint()
        record.endpoint = f"[{ep}]" if ep else "-"
        return True


class SqlEchoFilter(logging.Filter):
    """过滤 sqlalchemy.engine 的日志：保留自定义的「SQL + [query took]」格式及事务边界（BEGIN/ROLLBACK）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = getattr(record, "msg", "") or ""
        if not isinstance(msg, str):
            return True
        # 保留：自定义格式、事务边界
        stripped = msg.strip()
        return (
            "[query took" in msg
            or stripped == "ROLLBACK"
            or stripped == "BEGIN (implicit)"
            or stripped == "COMMIT"
        )


class SensitiveDataFilter(logging.Filter):
    """对 message 中的敏感信息做脱敏替换。"""

    _PATTERNS = [
        (r"password['\"]?\s*[:=]\s*['\"]?[^\s'\"]+", "password=***"),
        (r"Authorization:\s*Bearer\s+\S+", "Authorization: ***"),
        (r"token['\"]?\s*[:=]\s*['\"]?[^\s'\"]+", "token=***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        import re

        msg = getattr(record, "msg", "") or ""
        if isinstance(msg, str):
            for pattern, replacement in self._PATTERNS:
                msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
            record.msg = msg
        return True


def _resolve_log_dir() -> Path:
    """解析日志目录路径。"""
    if settings.LOG_DIR:
        base = Path(settings.LOG_DIR)
    else:
        base = Path(__file__).resolve().parent.parent
    base.mkdir(parents=True, exist_ok=True)
    return base


def _get_log_level() -> str:
    """根据 ENV 和 LOG_LEVEL 确定日志级别。"""
    if settings.LOG_LEVEL:
        return settings.LOG_LEVEL.upper()
    return "DEBUG" if settings.ENV == "development" else "INFO"


def _get_uvicorn_error_level() -> str:
    """生产环境 uvicorn.error 使用 WARNING。"""
    return "INFO" if settings.ENV == "development" else "WARNING"


def get_logging_config() -> Dict[str, Any]:
    """构建 logging dictConfig，供 dictConfig 或 uvicorn 使用。"""
    log_dir = _resolve_log_dir()
    level = _get_log_level()
    uvicorn_error_level = _get_uvicorn_error_level()

    app_log_path = str(log_dir / "app.log")
    access_log_path = str(log_dir / "access.log")

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": "backend.logging_config.RequestIdFilter",
            },
            "sensitive": {
                "()": "backend.logging_config.SensitiveDataFilter",
            },
            "sql_echo": {
                "()": "backend.logging_config.SqlEchoFilter",
            },
        },
        "formatters": {
            "default": {
                "format": "%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(request_id)s %(endpoint)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "format": "%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(request_id)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "null": {
                "class": "logging.NullHandler",
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": app_log_path,
                "maxBytes": settings.LOG_APP_MAX_BYTES,
                "backupCount": settings.LOG_APP_BACKUP_COUNT,
                "formatter": "default",
                "filters": ["request_id", "sensitive"],
                "encoding": "utf-8",
            },
            "sqlalchemy_app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": app_log_path,
                "maxBytes": settings.LOG_APP_MAX_BYTES,
                "backupCount": settings.LOG_APP_BACKUP_COUNT,
                "formatter": "default",
                "filters": ["request_id", "sensitive", "sql_echo"],
                "encoding": "utf-8",
            },
            "access_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": access_log_path,
                "maxBytes": settings.LOG_ACCESS_MAX_BYTES,
                "backupCount": settings.LOG_ACCESS_BACKUP_COUNT,
                "formatter": "access",
                "filters": ["request_id"],
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "uvicorn": {"level": level, "handlers": ["app_file"], "propagate": False},
            "uvicorn.access": {"level": "INFO", "handlers": ["null"], "propagate": False},
            "uvicorn.error": {"level": uvicorn_error_level, "handlers": ["app_file"], "propagate": False},
            "backend": {"level": level, "handlers": ["app_file"], "propagate": False},
            "access": {"level": "INFO", "handlers": ["access_file"], "propagate": False},
            "sqlalchemy.engine": {
                "level": "INFO" if settings.LOG_SQL else "CRITICAL",
                "handlers": ["sqlalchemy_app_file"],
                "propagate": False,
            },
        },
        "root": {"level": level, "handlers": ["app_file"]},
    }

    if settings.ENV == "development":
        config["handlers"]["console"] = {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["request_id", "sensitive"],
            "stream": "ext://sys.stdout",
        }
        config["handlers"]["sqlalchemy_console"] = {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["request_id", "sensitive", "sql_echo"],
            "stream": "ext://sys.stdout",
        }
        for logger_name in ["uvicorn", "uvicorn.error", "backend", "root"]:
            logger_config = config["loggers"].get(logger_name) or config.get("root", {})
            handlers = logger_config.get("handlers", ["app_file"])
            if "console" not in handlers:
                handlers = list(handlers) + ["console"]
            if logger_name == "root":
                config["root"]["handlers"] = handlers
            else:
                config["loggers"][logger_name]["handlers"] = handlers
        # sqlalchemy.engine 使用带 sql_echo 过滤的 console
        sql_handlers = list(config["loggers"]["sqlalchemy.engine"]["handlers"])
        if "sqlalchemy_console" not in sql_handlers:
            config["loggers"]["sqlalchemy.engine"]["handlers"] = sql_handlers + ["sqlalchemy_console"]

    return config
