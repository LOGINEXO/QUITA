from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.rate_limit import InMemoryRateLimitMiddleware


def test_rate_limiter_returns_429_and_retry_after():
    app = FastAPI()
    app.add_middleware(InMemoryRateLimitMiddleware)

    @app.post("/leads")
    def create_lead():
        return {"created": True}

    client = TestClient(app)
    responses = [client.post("/leads") for _ in range(11)]

    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[0].headers["X-RateLimit-Limit"] == "10"
    assert responses[0].headers["X-RateLimit-Remaining"] == "9"
    assert responses[10].status_code == 429
    assert int(responses[10].headers["Retry-After"]) >= 1
    assert responses[10].headers["X-RateLimit-Remaining"] == "0"
    assert responses[10].json()["detail"]


def test_rate_limiter_does_not_limit_unconfigured_paths():
    app = FastAPI()
    app.add_middleware(InMemoryRateLimitMiddleware)

    @app.post("/unlimited")
    def unlimited():
        return {"ok": True}

    client = TestClient(app)
    responses = [client.post("/unlimited") for _ in range(15)]
    assert all(response.status_code == 200 for response in responses)
