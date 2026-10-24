from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.providers.models import ProviderCapability, ProviderConfig


@dataclass(frozen=True)
class ProviderAttempt:
    provider_id: str
    status: str
    detail: str
    attempted_at: datetime


@dataclass(frozen=True)
class ProviderResult:
    status: str  # success | unavailable
    provider_id: str | None
    data: Any = None
    attempts: tuple[ProviderAttempt, ...] = ()


class ProviderRegistry:
    """Registro em memória; persistência durável será adicionada na próxima etapa."""

    def __init__(self, requester: Callable[..., Awaitable[httpx.Response]] | None = None) -> None:
        self._providers: dict[str, ProviderConfig] = {}
        self._lock = asyncio.Lock()
        self._requester = requester or self._default_requester

    @staticmethod
    async def _default_requester(
        url: str, *, timeout: float, headers: dict[str, str]
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            return await client.get(url, headers=headers)

    async def upsert(self, config: ProviderConfig) -> None:
        async with self._lock:
            self._providers[config.id] = config

    async def remove(self, provider_id: str) -> bool:
        async with self._lock:
            return self._providers.pop(provider_id, None) is not None

    async def get(self, provider_id: str) -> ProviderConfig | None:
        async with self._lock:
            return self._providers.get(provider_id)

    async def list(self) -> list[ProviderConfig]:
        async with self._lock:
            return sorted(self._providers.values(), key=lambda item: (item.priority, item.id))

    async def execute_get(
        self, capability: ProviderCapability, path: str
    ) -> ProviderResult:
        """Tenta provedores compatíveis; falhas nunca são interpretadas como ausência de débitos."""
        if not path.startswith("/") or path.startswith("//") or ".." in path.split("/"):
            raise ValueError("path deve ser um caminho relativo seguro")

        providers = await self.list()
        candidates = [p for p in providers if p.enabled and capability in p.capabilities]
        attempts: list[ProviderAttempt] = []

        for provider in candidates:
            headers: dict[str, str] = {"Accept": "application/json"}
            if provider.api_key:
                headers["Authorization"] = (
                    f"Bearer {provider.api_key.get_secret_value()}"
                )
            url = f"{str(provider.base_url).rstrip('/')}{path}"
            try:
                response = await self._requester(
                    url, timeout=provider.timeout_seconds, headers=headers
                )
                if response.status_code == 429:
                    status, detail = (
                        "rate_limited",
                        "O provedor informou limite de requisições",
                    )
                elif response.status_code in (401, 403):
                    status, detail = (
                        "authentication_error",
                        "Falha de autenticação/autorização do provedor",
                    )
                elif response.status_code >= 500:
                    status, detail = (
                        "provider_error",
                        "O provedor retornou erro temporário",
                    )
                elif response.status_code >= 400:
                    status, detail = (
                        "request_error",
                        f"O provedor rejeitou a solicitação (HTTP {response.status_code})",
                    )
                else:
                    try:
                        payload = response.json()
                    except ValueError:
                        status, detail = (
                            "invalid_response",
                            "Resposta não contém JSON válido",
                        )
                    else:
                        attempts.append(
                            ProviderAttempt(
                                provider.id,
                                "success",
                                "Resposta válida",
                                datetime.now(timezone.utc),
                            )
                        )
                        return ProviderResult(
                            "success", provider.id, payload, tuple(attempts)
                        )
                attempts.append(
                    ProviderAttempt(
                        provider.id, status, detail, datetime.now(timezone.utc)
                    )
                )
            except (httpx.TimeoutException, httpx.NetworkError, TimeoutError):
                attempts.append(
                    ProviderAttempt(
                        provider.id,
                        "unavailable",
                        "Timeout ou falha de rede",
                        datetime.now(timezone.utc),
                    )
                )
            except Exception:
                # Não vazar detalhes técnicos nem interromper a cadeia por um adaptador.
                attempts.append(
                    ProviderAttempt(
                        provider.id,
                        "provider_error",
                        "Falha inesperada no adaptador",
                        datetime.now(timezone.utc),
                    )
                )

        return ProviderResult("unavailable", None, None, tuple(attempts))
