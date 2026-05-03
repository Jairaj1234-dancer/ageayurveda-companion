import uuid
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import logger


class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.monotonic()

        response = await call_next(request)

        elapsed = (time.monotonic() - start) * 1000
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({elapsed:.0f}ms)"
        )
        response.headers["X-Request-Id"] = request_id
        return response
