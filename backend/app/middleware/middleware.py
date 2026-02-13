import time
from typing import Callable

from fastapi import Request, Response
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings
from ..utils.logger import logger
from ..utils.redis_client import redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.requests_per_window = settings.RATE_LIMIT_REQUESTS
        self.window_seconds = settings.RATE_LIMIT_PERIOD

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        user_id = request.headers.get("X-User-ID")
        key = f"ratelimit:{user_id or client_ip}"

        current = None
        try:
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, self.window_seconds)
        except Exception as exc:
            logger.warning(f"Rate limit middleware failed, bypassing: {exc}")
            current = None

        if current is not None and current > self.requests_per_window:
            return Response(
                content='{"error":"Too many requests"}',
                status_code=429,
                media_type="application/json",
            )

        response = await call_next(request)
        if current is not None:
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_window)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self.requests_per_window - current))
            try:
                response.headers["X-RateLimit-Reset"] = str(await redis_client.ttl(key))
            except Exception:
                pass
        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        started = time.time()
        request_id = request.headers.get("X-Request-ID") or str(int(started * 1000))
        try:
            response = await call_next(request)
            elapsed = time.time() - started
            logger.info(f"[{request_id}] {request.method} {request.url.path} {response.status_code} {elapsed:.3f}s")
            response.headers["X-Process-Time"] = f"{elapsed:.3f}s"
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            elapsed = time.time() - started
            logger.exception(f"[{request_id}] {request.method} {request.url.path} failed after {elapsed:.3f}s")
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def get_middleware() -> list:
    return [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=settings.CORS_ALLOW_HEADERS,
        ),
        Middleware(GZipMiddleware, minimum_size=1000),
        Middleware(LoggingMiddleware),
        Middleware(SecurityHeadersMiddleware),
        Middleware(RateLimitMiddleware),
    ]
