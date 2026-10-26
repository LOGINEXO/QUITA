from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.config import settings
from app.rate_limit import InMemoryRateLimitMiddleware
from app.api.admin_auth import router as admin_auth_router
from app.api.customers import router as customers_router
from app.api.leads import router as leads_router
from app.db.health import router as database_health_router

app = FastAPI(title="QUITA API", version="0.8.0", description="QUITA para captação e gestão manual de solicitações.")
app.add_middleware(InMemoryRateLimitMiddleware)


@app.middleware("http")
async def production_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith(("/admin", "/auth/admin", "/admin/customers", "/admin/leads")):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response
app.include_router(admin_auth_router)
app.include_router(customers_router)
app.include_router(leads_router)
app.include_router(database_health_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")

@app.get("/", include_in_schema=False)
async def public_frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "public.html")

@app.get("/admin", include_in_schema=False)
@app.get("/admin/login", include_in_schema=False)
async def admin_frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/health/rate-limit", tags=["health"])
async def rate_limit_health() -> dict[str, str | bool]:
    if not settings.redis_url:
        raise HTTPException(status_code=503, detail={"status": "degraded", "backend": "in-memory", "redis_configured": False, "redis_reachable": False})
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception:
        raise HTTPException(status_code=503, detail={"status": "degraded", "backend": "redis", "redis_configured": True, "redis_reachable": False})
    finally:
        await client.aclose()
    return {"status": "ok", "backend": "redis", "redis_configured": True, "redis_reachable": True}
