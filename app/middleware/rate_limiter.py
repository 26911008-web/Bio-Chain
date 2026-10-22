"""Rate limiter middleware — Redis sliding window counter.

Melindungi API dari abuse. Setiap IP dibatasi RATE_LIMIT_REQUESTS
per RATE_LIMIT_WINDOW_SECONDS. Health check & docs dikecualikan.
Fail-open: jika Redis down, request tetap diizinkan.
"""

import os
import socket
import time
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import settings

EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json", "/redoc"}
LOGIN_PATH = "/api/v1/auth/login"
TRUSTED_PROXIES = {ip.strip() for ip in settings.TRUSTED_PROXIES.split(",") if ip.strip()}
ON_VERCEL = bool(os.getenv("VERCEL"))


def client_ip(request: Request) -> str:
    """IP klien asli. X-Forwarded-For hanya dipercaya bila request datang dari reverse proxy kita;
    diambil entri paling kanan yang bukan proxy (entri kiri bisa dipalsukan klien)."""
    peer = request.client.host if request.client else "unknown"
    xff = request.headers.get("x-forwarded-for")
    if ON_VERCEL and xff:
        # Edge Vercel menimpa X-Forwarded-For dengan IP klien asli (tidak bisa dipalsukan klien)
        return xff.split(",")[0].strip()
    if peer not in TRUSTED_PROXIES or not xff:
        return peer
    for hop in reversed([h.strip() for h in xff.split(",") if h.strip()]):
        if hop not in TRUSTED_PROXIES:
            return hop
    return peer


def _is_redis_port_open(url: str) -> bool:
    try:
        p = urlparse(url)
        host = p.hostname or "localhost"
        port = p.port or 6379
        with socket.create_connection((host, port), timeout=0.08):
            return True
    except OSError:
        return False


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._redis = None
        self._redis_available = None
        self._last_checked = 0.0
        self.max_requests = settings.RATE_LIMIT_REQUESTS
        self.window = settings.RATE_LIMIT_WINDOW_SECONDS

    async def _get_redis(self):
        now = time.time()
        # Jika sebelumnya diketahui down, jangan coba lagi sebelum 60 detik
        if self._redis_available is False and (now - self._last_checked) < 60.0:
            return None

        if self._redis is None:
            self._last_checked = now
            if not _is_redis_port_open(settings.REDIS_URL):
                self._redis_available = False
                return None
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=0.2,
                    socket_timeout=0.2,
                )
                self._redis_available = True
            except Exception:
                self._redis_available = False
                return None
        return self._redis

    async def dispatch(self, request: Request, call_next):
        # Skip exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Skip static files and root
        if request.url.path == "/" or request.url.path.startswith("/static"):
            return await call_next(request)

        redis_client = await self._get_redis()
        if redis_client is None:
            # Fail open: no Redis = no rate limiting, zero latency penalty
            return await call_next(request)

        ip = client_ip(request)
        is_login = request.url.path == LOGIN_PATH
        # Request ber-token dihitung per PENGGUNA, bukan per IP: di desa puluhan petani berbagi satu wifi KUD
        # atau CGNAT operator seluler — kunci per IP membuat semuanya kena 429 bersamaan (mis. flush antrean pagi).
        bucket = _user_bucket(request.headers.get("authorization")) or ip
        now = time.time()
        member = f"{now}:{id(request)}"            # unik walau dua request di mikrodetik yang sama

        try:
            pipe = redis_client.pipeline()
            prefix = f"{settings.REDIS_KEY_PREFIX}rl:"
            for key in (f"{prefix}{bucket}", f"{prefix}login:{ip}") if is_login else (f"{prefix}{bucket}",):
                pipe.zremrangebyscore(key, 0, now - self.window)
                pipe.zadd(key, {member: now})
                pipe.zcard(key)
                pipe.expire(key, self.window)
            results = await pipe.execute()
            request_count = results[2]
            if is_login and results[6] > settings.LOGIN_RATE_LIMIT:
                request_count = self.max_requests + 1   # brute force login → 429 lebih awal
        except Exception:
            # Mark Redis as temporarily down and fail open
            self._redis_available = False
            self._last_checked = time.time()
            return await call_next(request)

        if request_count > self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Terlalu banyak permintaan. Coba lagi nanti."},
                headers={
                    "Retry-After": str(self.window),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.max_requests - request_count)
        )
        return response


def _user_bucket(auth_header: str | None) -> str | None:
    """'u:<id>' dari JWT yang valid (tanda tangan diverifikasi); None → pakai IP."""
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    try:
        import jwt
        payload = jwt.decode(auth_header[7:], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return f"u:{payload.get('sub')}" if payload.get("sub") is not None else None
    except Exception:
        return None
