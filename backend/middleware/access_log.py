# ============================================================
# 访问日志中间件 — 记录每次 HTTP 请求的摘要
# ============================================================

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

ACCESS_LOGGER = logging.getLogger("access")

# 敏感路径：不记录请求体，仅记录摘要
SENSITIVE_PATHS = {"/api/v1/auth/login"}


class AccessLogMiddleware(BaseHTTPMiddleware):
    """记录 method、path、status_code、duration_ms、client_ip、user_agent、request_id。"""

    async def dispatch(self, request: Request, call_next: callable) -> Response:
        start = time.perf_counter()
        method = request.method
        path = request.url.path
        if request.query_params:
            path = f"{path}?{request.query_params}"
        client_ip = request.client.host if request.client else "-"

        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        status_code = response.status_code

        ACCESS_LOGGER.info(
            "%s %s %d %dms %s",
            method,
            path,
            status_code,
            duration_ms,
            client_ip,
        )
        return response
