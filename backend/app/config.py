from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    admin_api_key: str = ""
    admin_email: str = "usernovapagina@gmail.com"
    admin_password: str = ""
    admin_token_secret: str = ""
    admin_token_ttl_minutes: int = 30
    request_timeout_seconds: float = 8.0
    max_retries_per_provider: int = 1
    redis_url: str = ""

    model_config = SettingsConfigDict(env_prefix="QUITA_", env_file=".env", extra="ignore")


settings = Settings()
