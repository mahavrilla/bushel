import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base

# Import models so they register on Base.metadata.
import app.models  # noqa: F401


def _require_test_database(database_url: str) -> None:
    """Abort the run unless the target database name ends in '_test'.

    The session fixture below calls Base.metadata.drop_all on teardown, which destroys
    every table. Pointing DATABASE_URL at the dev database (e.g. .../bushel on :5432)
    would therefore wipe real data — that has happened. This guard makes drop_all reachable
    only for an explicitly-named throwaway test DB (e.g. bushel_test on :5544)."""
    name = make_url(database_url).database or ""
    if not name.endswith("_test"):
        pytest.exit(
            f"Refusing to run tests against database {name!r}: the test DB name must end in "
            "'_test' (e.g. bushel_test on localhost:5544). The suite drops ALL tables on "
            "teardown — running it against the dev DB wipes real data. "
            "See README → Running tests.",
            returncode=1,
        )


@pytest.fixture(scope="session")
def test_engine():
    """Engine pointed at the configured database. Creates all tables once."""
    database_url = get_settings().database_url
    _require_test_database(database_url)
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    """A session wrapped in a transaction that is rolled back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
