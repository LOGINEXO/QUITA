from fastapi import FastAPI

from app.api.admin_auth import router as admin_auth_router
from app.api.buscafipe import router as buscafipe_router
from app.api.providers import router as providers_router
from app.db.health import router as database_health_router

app = FastAPI(
    title="QUITA API",
    version="0.4.0",
    description=(
        "API do QUITA com integração BuscaFIPE, autenticação administrativa, "
        "gestão de provedores e persistência PostgreSQL."
    ),
)
app.include_router(admin_auth_router)
app.include_router(providers_router)
app.include_router(buscafipe_router)
app.include_router(database_health_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness sem dependência do banco, útil para orquestradores."""
    return {"status": "ok"}
