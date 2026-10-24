from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator


class ProviderCapability(StrEnum):
    VEHICLE_REFERENCE = "vehicle_reference"
    DEBTS = "debts"
    ZIP_CODE = "zip_code"
    MESSAGING = "messaging"


class ProviderConfig(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    base_url: HttpUrl
    capabilities: set[ProviderCapability] = Field(min_length=1)
    priority: int = Field(default=100, ge=1, le=10000)
    enabled: bool = True
    timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    # Token mascarado pelo Pydantic e nunca incluído na resposta pública.
    api_key: SecretStr | None = None
    health_path: str | None = Field(default=None, max_length=200)

    @field_validator("health_path")
    @classmethod
    def validate_relative_health_path(cls, value: str | None) -> str | None:
        if value is not None and (not value.startswith("/") or value.startswith("//")):
            raise ValueError("health_path deve ser um caminho relativo iniciado por '/'")
        return value


class ProviderPublicView(BaseModel):
    id: str
    name: str
    base_url: str
    capabilities: set[ProviderCapability]
    priority: int
    enabled: bool
    timeout_seconds: float
    has_api_key: bool
    health_path: str | None

    @classmethod
    def from_config(cls, config: ProviderConfig) -> "ProviderPublicView":
        return cls(
            id=config.id,
            name=config.name,
            base_url=str(config.base_url),
            capabilities=config.capabilities,
            priority=config.priority,
            enabled=config.enabled,
            timeout_seconds=config.timeout_seconds,
            has_api_key=bool(config.api_key and config.api_key.get_secret_value()),
            health_path=config.health_path,
        )
