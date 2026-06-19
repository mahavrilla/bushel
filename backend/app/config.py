from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    # Populated in later phases; optional so the app boots without them.
    kroger_client_id: str = ""
    kroger_client_secret: str = ""
    kroger_redirect_uri: str = "http://localhost:8000/auth/callback"
    anthropic_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
