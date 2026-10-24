import asyncio

import httpx
import pytest

from app.providers.models import ProviderCapability, ProviderConfig
from app.providers.registry import ProviderRegistry


@pytest.mark.asyncio
async def test_falls_back_after_rate_limit() -> None:
    calls: list[str] = []

    async def requester(
        url: str, *, timeout: float, headers: dict[str, str]
    ) -> httpx.Response:
        calls.append(url)
        if "primary" in url:
            return httpx.Response(429, json={"error": "quota"})
        return httpx.Response(200, json={"vehicle": "example"})

    registry = ProviderRegistry(requester=requester)
    await registry.upsert(
        ProviderConfig(
            id="primary",
            name="Principal",
            base_url="https://primary.example",
            capabilities={ProviderCapability.DEBTS},
            priority=1,
        )
    )
    await registry.upsert(
        ProviderConfig(
            id="backup",
            name="Reserva",
            base_url="https://backup.example",
            capabilities={ProviderCapability.DEBTS},
            priority=2,
        )
    )

    result = await registry.execute_get(ProviderCapability.DEBTS, "/lookup")

    assert result.status == "success"
    assert result.provider_id == "backup"
    assert result.data == {"vehicle": "example"}
    assert [attempt.status for attempt in result.attempts] == ["rate_limited", "success"]
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_never_treats_all_provider_failures_as_zero_debts() -> None:
    async def requester(
        url: str, *, timeout: float, headers: dict[str, str]
    ) -> httpx.Response:
        return httpx.Response(503, json={"error": "down"})

    registry = ProviderRegistry(requester=requester)
    await registry.upsert(
        ProviderConfig(
            id="one",
            name="Indisponível",
            base_url="https://one.example",
            capabilities={ProviderCapability.DEBTS},
        )
    )
    result = await registry.execute_get(ProviderCapability.DEBTS, "/lookup")

    assert result.status == "unavailable"
    assert result.provider_id is None
    assert result.data is None
    assert result.attempts[0].status == "provider_error"


@pytest.mark.asyncio
async def test_skips_provider_without_requested_capability() -> None:
    async def requester(
        url: str, *, timeout: float, headers: dict[str, str]
    ) -> httpx.Response:
        raise AssertionError("Não deveria chamar um provedor incompatível")

    registry = ProviderRegistry(requester=requester)
    await registry.upsert(
        ProviderConfig(
            id="fipe",
            name="Referência veicular",
            base_url="https://fipe.example",
            capabilities={ProviderCapability.VEHICLE_REFERENCE},
        )
    )
    result = await registry.execute_get(ProviderCapability.DEBTS, "/lookup")
    assert result.status == "unavailable"
    assert result.attempts == ()


def test_rejects_unsafe_path() -> None:
    registry = ProviderRegistry()
    with pytest.raises(ValueError):
        asyncio.run(
            registry.execute_get(ProviderCapability.DEBTS, "//evil.example/path")
        )
