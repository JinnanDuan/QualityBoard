# ============================================================
# Request ID / Endpoint — 请求追踪的 contextvars
# ============================================================

from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
request_endpoint_var: ContextVar[Optional[str]] = ContextVar("request_endpoint", default=None)


def get_request_id() -> Optional[str]:
    """获取当前请求的 request_id，无请求上下文时返回 None。"""
    return request_id_var.get()


def set_request_id(rid: str) -> None:
    """设置当前请求的 request_id。"""
    request_id_var.set(rid)


def clear_request_id() -> None:
    """清除当前请求的 request_id（请求结束时调用）。"""
    request_id_var.set(None)


def get_request_endpoint() -> Optional[str]:
    """获取当前请求的 endpoint（触发接口），无请求上下文时返回 None。"""
    return request_endpoint_var.get()


def set_request_endpoint(endpoint: str) -> None:
    """设置当前请求的 endpoint。"""
    request_endpoint_var.set(endpoint)


def clear_request_endpoint() -> None:
    """清除当前请求的 endpoint（请求结束时调用）。"""
    request_endpoint_var.set(None)
