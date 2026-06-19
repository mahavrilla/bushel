from sqlalchemy import text

from app.db import Base, engine


def test_base_has_metadata():
    assert Base.metadata is not None


def test_engine_connects():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
