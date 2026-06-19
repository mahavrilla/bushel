from app.config import Settings


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/bushel")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://u:p@localhost:5432/bushel"


def test_settings_has_kroger_and_llm_fields(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/bushel")
    monkeypatch.setenv("KROGER_CLIENT_ID", "cid")
    monkeypatch.setenv("KROGER_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    settings = Settings()
    assert settings.kroger_client_id == "cid"
    assert settings.kroger_client_secret == "secret"
    assert settings.anthropic_api_key == "sk-ant"
