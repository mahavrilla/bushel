from unittest.mock import MagicMock

import pytest

from app.kroger.schemas import Product, TokenResp
from app.matching import service
from app.models import GroceryList, GroceryListItem, Ingredient
from app.settings import service as settings_service


def _draft_with_item(db):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft")
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=3.0,
                           total_unit="lb", pantry_status="needed")
    db.add(item)
    db.flush()
    return gl, ing, item


def test_set_store_persists_to_settings_with_name(db_session):
    _draft_with_item(db_session)
    state = service.set_store(db_session, "L1", "Kroger Downtown")
    assert state.store_location_id == "L1"
    assert state.store_name == "Kroger Downtown"
    assert settings_service.get_home_store(db_session) == ("L1", "Kroger Downtown")


def test_home_store_persists_across_new_draft(db_session):
    gl, ing, item = _draft_with_item(db_session)
    service.set_store(db_session, "L1", "Kroger Downtown")
    gl.status = "sent_to_kroger"
    db_session.flush()
    state = service.get_match_state(db_session)
    assert state.store_location_id == "L1"
    assert state.store_name == "Kroger Downtown"


def test_search_uses_settings_home_store(db_session):
    gl, ing, item = _draft_with_item(db_session)
    settings_service.set_home_store(db_session, "L1", "Kroger Downtown")
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = [Product(upc="0001", description="Flour")]
    service.search_item_products(db_session, kroger, item.id, query=None)
    kroger.search_products.assert_called_once_with("ct", "flour", "L1", limit=24, start=0)


def test_search_no_home_store_raises(db_session):
    gl, ing, item = _draft_with_item(db_session)
    with pytest.raises(service.NoStoreSelectedError):
        service.search_item_products(db_session, MagicMock(), item.id, query=None)
