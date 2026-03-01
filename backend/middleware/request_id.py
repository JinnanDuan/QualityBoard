# ============================================================
# Request ID 中间件 — 为每个请求生成并传递 request_id、endpoint
# ============================================================

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.request_id import (
    clear_request_endpoint,
    clear_request_id,
    set_request_endpoint,
    set_request_id,
)

_ENDPOINT_MAX_LEN = 256


def _build_endpoint(request: Request) -> str:
    """组装 endpoint：{METHOD} {path}，与 access.log 格式一致，超长截断。"""
    path = request.url.path
    if request.query_params:
        path = f"{path}?{request.query_params}"
    endpoint = f"{request.method.upper()} {path}"
    if len(endpoint) > _ENDPOINT_MAX_LEN:
        endpoint = endpoint[: _ENDPOINT_MAX_LEN - 3] + "..."
    return endpoint


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求生成 UUID 作为 request_id，注入 contextvars 并写入响应头；同时注入 endpoint 供日志展示。"""

    async def dispatch(self, request: Request, call_next: callable) -> Response:
        rid = str(uuid.uuid4())
        set_request_id(rid)
        set_request_endpoint(_build_endpoint(request))
        request.state.request_id = rid
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            clear_request_id()
            clear_request_endpoint()
