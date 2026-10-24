from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    admin_api_key: str = ""
    request_timeout_seconds: float = 8.0
    max_retries_per_provider: int = 1

    model_config = SettingsConfigDict(env_prefix="QUITA_", env_file=".env", extra="ignore")


settings = Settings()
