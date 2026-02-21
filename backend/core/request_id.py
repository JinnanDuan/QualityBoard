# ============================================================
# Request ID — 请求追踪的 contextvars
# ============================================================

from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """获取当前请求的 request_id，无请求上下文时返回 None。"""
    return request_id_var.get()


def set_request_id(rid: str) -> None:
    """设置当前请求的 request_id。"""
    request_id_var.set(rid)


def clear_request_id() -> None:
    """清除当前请求的 request_id（请求结束时调用）。"""
    request_id_var.set(None)
