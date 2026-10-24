from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.providers.models import ProviderCapability, ProviderConfig, ProviderPublicView
from app.providers.registry import ProviderRegistry

router = APIRouter(prefix="/admin/providers", tags=["admin-providers"])
registry = ProviderRegistry()


def require_admin(x_admin_api_key: str | None = Header(default=None)) -> None:
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Gestão administrativa não configurada no servidor",
        )
    if x_admin_api_key is None or x_admin_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial administrativa inválida",
        )


class ProviderProbeRequest(BaseModel):
    capability: ProviderCapability
    path: str = "/"


@router.get(
    "",
    response_model=list[ProviderPublicView],
    dependencies=[Depends(require_admin)],
)
async def list_providers() -> list[ProviderPublicView]:
    return [ProviderPublicView.from_config(p) for p in await registry.list()]


@router.put(
    "/{provider_id}",
    response_model=ProviderPublicView,
    dependencies=[Depends(require_admin)],
)
async def save_provider(provider_id: str, config: ProviderConfig) -> ProviderPublicView:
    if provider_id != config.id:
        raise HTTPException(
            status_code=400,
            detail="O ID da URL deve corresponder ao ID da configuração",
        )
    await registry.upsert(config)
    return ProviderPublicView.from_config(config)


@router.delete(
    "/{provider_id}",
    dependencies=[Depends(require_admin)],
)
async def delete_provider(provider_id: str) -> dict[str, bool]:
    if not await registry.remove(provider_id):
        raise HTTPException(status_code=404, detail="Provedor não encontrado")
    return {"deleted": True}


@router.post("/probe", dependencies=[Depends(require_admin)])
async def probe_provider(request: ProviderProbeRequest) -> dict[str, object]:
    result = await registry.execute_get(request.capability, request.path)
    return {
        "status": result.status,
        "provider_id": result.provider_id,
        "attempts": [
            {
                "provider_id": attempt.provider_id,
                "status": attempt.status,
                "detail": attempt.detail,
                "attempted_at": attempt.attempted_at.isoformat(),
            }
            for attempt in result.attempts
        ],
    }
