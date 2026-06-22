from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    # Browser origins allowed to call the API (the Vite dev server / web container).
    cors_origins: list[str] = ["http://localhost:5173"]

    # Populated in later phases; optional so the app boots without them.
    kroger_client_id: str = ""
    kroger_client_secret: str = ""
    kroger_redirect_uri: str = "http://localhost:8000/auth/callback"
    anthropic_api_key: str = ""

    # Pantry "still have it?" — flag ingredients bought within this many days.
    pantry_recent_days: int = 14


@lru_cache
def get_settings() -> Settings:
    return Settings()
