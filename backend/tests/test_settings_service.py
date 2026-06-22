from app.settings import service
from app.models import AppSettings


def test_get_settings_row_creates_single_row(db_session):
    row1 = service.get_settings_row(db_session)
    row2 = service.get_settings_row(db_session)
    assert row1.id == row2.id
    assert db_session.query(AppSettings).count() == 1


def test_set_home_store_upserts(db_session):
    service.set_home_store(db_session, "L1", "Kroger Downtown")
    service.set_home_store(db_session, "L2", "Kroger Uptown")
    rows = db_session.query(AppSettings).all()
    assert len(rows) == 1
    assert rows[0].home_store_location_id == "L2"
    assert rows[0].home_store_name == "Kroger Uptown"


def test_get_home_store_returns_id_and_name(db_session):
    service.set_home_store(db_session, "L9", "Test Store")
    assert service.get_home_store(db_session) == ("L9", "Test Store")


def test_get_home_store_unset_returns_none(db_session):
    assert service.get_home_store(db_session) == (None, None)
