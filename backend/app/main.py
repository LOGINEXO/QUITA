from fastapi import FastAPI

from app.api.buscafipe import router as buscafipe_router
from app.api.providers import router as providers_router

app = FastAPI(
    title="QUITA API",
    version="0.2.0",
    description=(
        "API do QUITA. Integração BuscaFIPE server-side e gestão administrativa "
        "inicial de provedores. Consulte /docs para os endpoints disponíveis."
    ),
)
app.include_router(providers_router)
app.include_router(buscafipe_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
