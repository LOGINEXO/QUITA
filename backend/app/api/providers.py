import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, model_validator

from app.api.admin_auth import verify_admin_token
from app.config import settings
from app.providers.models import ProviderCapability, ProviderConfig, ProviderPublicView
from app.providers.persistence import PersistentProviderStore, secret_environment_name

router = APIRouter(prefix="/admin/providers", tags=["admin-providers"])
store = PersistentProviderStore()


def require_admin(
    x_admin_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token and verify_admin_token(token):
            return

    expected = settings.admin_api_key
    if expected and x_admin_api_key and hmac.compare_digest(x_admin_api_key, expected):
        return
    if not expected and not settings.admin_token_secret:
        raise HTTPException(
            status_code=503,
            detail="Gestão administrativa não configurada no servidor",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credencial administrativa inválida",
    )


class ProviderProbeRequest(BaseModel):
    capability: ProviderCapability
    path: str = "/"


class ProviderSaveRequest(ProviderConfig):
    @model_validator(mode="after")
    def require_secret_out_of_band(self):
        if self.api_key is not None:
            raise ValueError(
                "Não envie chaves no corpo da API. Configure a variável de ambiente "
                f"{secret_environment_name(self.id)} no Render."
            )
        return self


@router.get(
    "",
    response_model=list[ProviderPublicView],
    dependencies=[Depends(require_admin)],
)
async def list_providers() -> list[ProviderPublicView]:
    return [ProviderPublicView.from_config(p) for p in store.list_configs()]


@router.put(
    "/{provider_id}",
    response_model=ProviderPublicView,
    dependencies=[Depends(require_admin)],
)
async def save_provider(provider_id: str, config: ProviderSaveRequest) -> ProviderPublicView:
    if provider_id != config.id:
        raise HTTPException(
            status_code=400,
            detail="O ID da URL deve corresponder ao ID da configuração",
        )
    saved = store.save_config(config)
    return ProviderPublicView.from_config(saved)


@router.delete(
    "/{provider_id}",
    dependencies=[Depends(require_admin)],
)
async def delete_provider(provider_id: str) -> dict[str, bool]:
    if not store.delete_config(provider_id):
        raise HTTPException(status_code=404, detail="Provedor não encontrado")
    return {"deleted": True}


@router.post("/probe", dependencies=[Depends(require_admin)])
async def probe_provider(request: ProviderProbeRequest) -> dict[str, object]:
    result = await store.execute_get(request.capability, request.path)
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
