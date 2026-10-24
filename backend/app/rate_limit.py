from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Process-local sliding-window limits for expensive/public POST endpoints.

    For multi-instance production deployments, replace the in-memory store with a
    shared store (for example Redis) so requests are counted across instances.
    """

    def __init__(self, app):
        super().__init__(app)
        self._windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
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
        # Use the socket peer address, not a caller-controlled X-Forwarded-For header.
        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, request.url.path)
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
                    headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limit)},
                )
            bucket.append(now)
            # Bound stale keys so a long-running process does not grow forever.
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
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(self._windows[key])))
        return response
