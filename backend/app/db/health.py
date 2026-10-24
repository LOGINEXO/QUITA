from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import check_database_connection

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    try:
        if not check_database_connection():
            raise HTTPException(status_code=503, detail="Banco de dados indisponível")
    except (RuntimeError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível") from exc
    return {"status": "ready", "database": "ok"}
