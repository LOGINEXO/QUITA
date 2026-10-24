from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

try:
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover - dependency is installed in production
    Redis = None


_REDIS_SLIDING_WINDOW = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry_ms = window_ms
  if oldest[2] then retry_ms = math.max(1, window_ms - (now_ms - tonumber(oldest[2]))) end
  redis.call('PEXPIRE', key, window_ms)
  return {0, count, retry_ms}
end
redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms)
return {1, count + 1, 0}
"""


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limits; uses shared Redis when QUITA_REDIS_URL is configured.

    Without Redis, the fallback is process-local and is suitable only for a
    single instance. If configured Redis is unavailable, requests fail closed
    with 503 rather than silently bypassing the shared limit.
    """

    def __init__(self, app):
        super().__init__(app)
        self._windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url and Redis else None
        self._redis_configured = bool(settings.redis_url)
        self._rules = {
            ("/auth/admin/login", "POST"): (5, 60),
            ("/leads", "POST"): (10, 60),
            ("/consultations/vehicle", "POST"): (5, 60),
            ("/integrations/buscafipe/placa", "POST"): (5, 60),
            ("/integrations/buscafipe/cnpj", "POST"): (5, 60),
        }

    async def dispatch(self, request: Request, call_next):
        rule = self._rules.get((request.url.path, request.method.upper()))
        if rule is None:
            return await call_next(request)

        limit, window_seconds = rule
        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, request.url.path)

        if self._redis_configured:
            if self._redis is None:
                return JSONResponse(status_code=503, content={"detail": "Proteção de requisições indisponível"})
            try:
                now_ms = time.time_ns() // 1_000_000
                digest = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
                allowed, count, retry_ms = await self._redis.eval(
                    _REDIS_SLIDING_WINDOW,
                    1,
                    f"quita:ratelimit:{digest}:{request.url.path}",
                    now_ms,
                    window_seconds * 1000,
                    limit,
                    f"{now_ms}:{time.time_ns()}",
                )
            except Exception:
                return JSONResponse(status_code=503, content={"detail": "Proteção de requisições indisponível"})
            if not allowed:
                retry_after = max(1, (int(retry_ms) + 999) // 1000)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Limite de requisições excedido. Tente novamente em instantes."},
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )
            remaining = max(0, limit - int(count))
        else:
            now = time.monotonic()
            with self._lock:
                bucket = self._windows[key]
                cutoff = now - window_seconds
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if len(bucket) >= limit:
                    retry_after = max(1, int(window_seconds - (now - bucket[0])))
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Limite de requisições excedido. Tente novamente em instantes."},
                        headers={
                            "Retry-After": str(retry_after),
                            "X-RateLimit-Limit": str(limit),
                            "X-RateLimit-Remaining": "0",
                        },
                    )
                bucket.append(now)
                remaining = max(0, limit - len(bucket))
                if len(self._windows) > 10_000:
                    stale_before = now - max(rule[1] for rule in self._rules.values())
                    for stale_key in list(self._windows):
                        entries = self._windows[stale_key]
                        while entries and entries[0] <= stale_before:
                            entries.popleft()
                        if not entries:
                            self._windows.pop(stale_key, None)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
