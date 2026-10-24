from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApiProvider
from app.db.session import get_session_factory
from app.providers.models import ProviderCapability, ProviderConfig
from app.providers.registry import ProviderRegistry


def secret_environment_name(provider_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9]", "_", provider_id).upper()
    return f"QUITA_PROVIDER_{safe_id}_API_KEY"


def config_from_row(row: ApiProvider) -> ProviderConfig:
    secret_ref = row.secret_ref
    api_key = None
    if secret_ref and secret_ref.startswith("env:"):
        value = os.getenv(secret_ref.removeprefix("env:"), "")
        if value:
            from pydantic import SecretStr
            api_key = SecretStr(value)
    return ProviderConfig(
        id=row.id,
        name=row.name,
        base_url=row.base_url,
        capabilities={ProviderCapability(value) for value in row.capabilities},
        priority=row.priority,
        enabled=row.enabled,
        timeout_seconds=row.timeout_seconds,
        api_key=api_key,
        health_path=row.health_path,
    )


class PersistentProviderStore:
    """Persistência SQL para provedores; segredos são referenciados por variável de ambiente."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory or get_session_factory()

    def list_configs(self) -> list[ProviderConfig]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ApiProvider).order_by(ApiProvider.priority, ApiProvider.id)
            ).all()
            return [config_from_row(row) for row in rows]

    def get_config(self, provider_id: str) -> ProviderConfig | None:
        with self._session_factory() as session:
            row = session.get(ApiProvider, provider_id)
            return config_from_row(row) if row else None

    def save_config(self, config: ProviderConfig) -> ProviderConfig:
        # A chave nunca é escrita no banco. O operador a define no Render como
        # QUITA_PROVIDER_<ID>_API_KEY; o registro guarda somente o nome da variável.
        with self._session_factory() as session:
            row = session.get(ApiProvider, config.id)
            secret_ref = f"env:{secret_environment_name(config.id)}"
            values: dict[str, Any] = {
                "id": config.id,
                "name": config.name,
                "base_url": str(config.base_url),
                "capabilities": sorted(cap.value for cap in config.capabilities),
                "priority": config.priority,
                "enabled": config.enabled,
                "timeout_seconds": int(config.timeout_seconds),
                "secret_ref": secret_ref,
                "health_path": config.health_path,
            }
            if row is None:
                row = ApiProvider(**values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return config_from_row(row)

    def delete_config(self, provider_id: str) -> bool:
        with self._session_factory() as session:
            row = session.get(ApiProvider, provider_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    async def execute_get(self, capability: ProviderCapability, path: str):
        registry = ProviderRegistry()
        for config in self.list_configs():
            await registry.upsert(config)
        return await registry.execute_get(capability, path)
