from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.rate_limit as rate_limit


class FakeRedis:
    def __init__(self):
        self.calls = 0

    async def eval(self, *_args):
        self.calls += 1
        if self.calls > 5:
            return [0, 5, 60_000]
        return [1, self.calls, 0]


class BrokenRedis:
    async def eval(self, *_args):
        raise ConnectionError("simulated Redis outage")


def _app():
    app = FastAPI()
    app.add_middleware(rate_limit.InMemoryRateLimitMiddleware)

    @app.post("/auth/admin/login")
    def login():
        return {"ok": True}

    return app


def test_redis_rate_limit_returns_429_after_five_requests(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rate_limit.settings, "redis_url", "redis://redis-test:6379")
    monkeypatch.setattr(rate_limit.Redis, "from_url", lambda *_args, **_kwargs: fake)

    client = TestClient(_app())
    responses = [client.post("/auth/admin/login") for _ in range(6)]

    assert all(response.status_code == 200 for response in responses[:5])
    assert responses[0].headers["X-RateLimit-Limit"] == "5"
    assert responses[0].headers["X-RateLimit-Remaining"] == "4"
    assert responses[5].status_code == 429
    assert responses[5].headers["Retry-After"] == "60"
    assert responses[5].headers["X-RateLimit-Remaining"] == "0"


def test_configured_redis_outage_fails_closed(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "redis_url", "redis://redis-test:6379")
    monkeypatch.setattr(rate_limit.Redis, "from_url", lambda *_args, **_kwargs: BrokenRedis())

    response = TestClient(_app()).post("/auth/admin/login")

    assert response.status_code == 503
    assert response.json()["detail"] == "Proteção de requisições indisponível"
