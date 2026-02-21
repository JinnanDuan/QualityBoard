# ============================================================
# Request ID 中间件 — 为每个请求生成并传递 request_id
# ============================================================

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.request_id import clear_request_id, set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求生成 UUID 作为 request_id，注入 contextvars 并写入响应头。"""

    async def dispatch(self, request: Request, call_next: callable) -> Response:
        rid = str(uuid.uuid4())
        set_request_id(rid)
        request.state.request_id = rid
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            clear_request_id()
