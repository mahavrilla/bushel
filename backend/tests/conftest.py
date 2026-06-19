import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base

# Import models so they register on Base.metadata.
import app.models  # noqa: F401


@pytest.fixture(scope="session")
def test_engine():
    """Engine pointed at the configured database. Creates all tables once."""
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
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
