from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.integrations.buscafipe import BuscaFipeClient, BuscaFipeError

router = APIRouter(prefix="/integrations/buscafipe", tags=["BuscaFIPE"])
client = BuscaFipeClient(timeout_seconds=settings.request_timeout_seconds)


class PlateRequest(BaseModel):
    placa: str = Field(min_length=7, max_length=10)


class CnpjRequest(BaseModel):
    cnpj: str = Field(min_length=11, max_length=18)


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, BuscaFipeError):
        # Não declarar ausência de débitos quando o fornecedor falha.
        return HTTPException(status_code=502, detail={"status": "indisponivel", "message": str(exc)})
    return HTTPException(status_code=502, detail={"status": "indisponivel", "message": "Falha na integração externa"})


@router.get("/fipe")
async def get_fipe(
    action: str = Query(pattern="^(marcas|modelos|anos|valor)$"),
    tipo: str | None = None,
    marca: str | None = None,
    modelo: str | None = None,
    ano: str | None = None,
    codigo: str | None = None,
) -> dict[str, object]:
    params = {key: value for key, value in {
        "tipo": tipo, "marca": marca, "modelo": modelo, "ano": ano, "codigo": codigo
    }.items() if value is not None}
    try:
        data = await client.fipe(action, **params)
    except (ValueError, BuscaFipeError) as exc:
        raise _translate_error(exc) from exc
    return {"source": "BuscaFIPE", "status": "success", "data": data}


@router.post("/placa")
async def get_plate(request: PlateRequest) -> dict[str, object]:
    try:
        data = await client.plate(request.placa)
    except (ValueError, BuscaFipeError) as exc:
        raise _translate_error(exc) from exc
    return {"source": "BuscaFIPE", "status": "success", "data": data}


@router.post("/cnpj")
async def get_cnpj(request: CnpjRequest) -> dict[str, object]:
    try:
        data = await client.cnpj(request.cnpj)
    except (ValueError, BuscaFipeError) as exc:
        raise _translate_error(exc) from exc
    return {"source": "BuscaFIPE", "status": "success", "data": data}


@router.get("/ipva")
async def get_ipva(uf: str = Query(min_length=2, max_length=2)) -> dict[str, object]:
    try:
        data = await client.ipva(uf)
    except (ValueError, BuscaFipeError) as exc:
        raise _translate_error(exc) from exc
    return {"source": "BuscaFIPE", "status": "success", "data": data}
