from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db import get_db
from app.kroger.schemas import Product, TokenResp
from app.kroger.router import get_kroger_client
from app.main import app
from app.models import GroceryList, GroceryListItem, Ingredient, KrogerAuth
from app.settings import service as settings_service


def _seed(db, store="L1", upc=None):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id=store)
    db.add(gl)
    db.flush()
    it = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=3.0,
                         total_unit="lb", purchase_qty=1, kroger_upc=upc, pantry_status="needed")
    db.add(it)
    db.flush()
    return gl, ing, it


def _client(db, kroger=None):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_kroger_client] = lambda: kroger or MagicMock()
    return TestClient(app)


def test_get_match(db_session):
    _seed(db_session)
    settings_service.set_home_store(db_session, "L1", None)
    client = _client(db_session)
    body = client.get("/list/match").json()
    assert body["store_location_id"] == "L1"
    assert body["items"][0]["ingredient_name"] == "flour"
    app.dependency_overrides.clear()


def test_search_products_endpoint(db_session):
    gl, ing, it = _seed(db_session)
    settings_service.set_home_store(db_session, "L1", None)
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = [Product(upc="0001", description="Flour", size="5 lb")]
    client = _client(db_session, kroger)
    body = client.get(f"/list/items/{it.id}/products", params={"q": "flour"}).json()
    assert body[0]["upc"] == "0001"
    app.dependency_overrides.clear()


def test_confirm_product_endpoint(db_session):
    gl, ing, it = _seed(db_session)
    client = _client(db_session)
    resp = client.post(f"/list/items/{it.id}/product",
                       json={"kroger_upc": "0001", "package_size": "1 lb"})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["kroger_upc"] == "0001"
    app.dependency_overrides.clear()


def test_send_endpoint_requires_connection(db_session):
    _seed(db_session, upc="0001")
    client = _client(db_session)
    resp = client.post("/list/send", json={"modality": "PICKUP"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "reauth_required"
    app.dependency_overrides.clear()


def test_send_endpoint_success(db_session):
    gl, ing, it = _seed(db_session, upc="0001")
    db_session.add(KrogerAuth(access_token="a", refresh_token="r",
                              expires_at=datetime.now(timezone.utc) + timedelta(hours=1), scopes=[]))
    db_session.flush()
    kroger = MagicMock()
    client = _client(db_session, kroger)
    resp = client.post("/list/send", json={"modality": "PICKUP"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent_to_kroger"
    app.dependency_overrides.clear()


def test_set_store_endpoint(db_session):
    _seed(db_session, store=None)
    client = _client(db_session)
    resp = client.post("/list/store", json={"location_id": "L42"})
    assert resp.status_code == 200
    assert resp.json()["store_location_id"] == "L42"
    app.dependency_overrides.clear()


def test_search_products_auth_error_is_502(db_session):
    from app.kroger.client import KrogerAuthError

    gl, ing, it = _seed(db_session)
    settings_service.set_home_store(db_session, "L1", None)
    kroger = MagicMock()
    kroger.fetch_client_token.side_effect = KrogerAuthError("bad client credentials")
    client = _client(db_session, kroger)
    resp = client.get(f"/list/items/{it.id}/products", params={"q": "flour"})
    assert resp.status_code == 502
    app.dependency_overrides.clear()
