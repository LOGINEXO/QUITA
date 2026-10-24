from fastapi import FastAPI

from app.api.providers import router as providers_router

app = FastAPI(
    title="QUITA API",
    version="0.1.0",
    description="Base inicial do QUITA. Consulte /docs para a API de desenvolvimento.",
)
app.include_router(providers_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
