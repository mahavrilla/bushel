from unittest.mock import MagicMock

import pytest

from app.kroger.schemas import Product, TokenResp
from app.matching import service
from app.matching.schemas import ConfirmRequest
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    IngredientProductMap,
)
from app.settings import service as settings_service


def _draft_with_item(db, total_qty=3.0, total_unit="lb", store="L1"):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking",
                     default_purchase_unit="bag")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id=store)
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id,
                           total_qty=total_qty, total_unit=total_unit, pantry_status="needed")
    db.add(item)
    db.flush()
    return gl, ing, item


def test_get_match_state_reports_items_and_store(db_session):
    gl, ing, item = _draft_with_item(db_session)
    settings_service.set_home_store(db_session, "L1", None)
    state = service.get_match_state(db_session)
    assert state.connected is False
    assert state.store_location_id == "L1"
    assert state.items[0].ingredient_name == "flour"
    assert state.items[0].kroger_upc is None


def test_get_match_state_skips_skipped_items(db_session):
    gl, ing, item = _draft_with_item(db_session)
    item.pantry_status = "skipped"
    db_session.flush()
    assert service.get_match_state(db_session).items == []


def test_get_match_state_current_from_mapping_by_ingredient(db_session):
    gl, ing, item = _draft_with_item(db_session)
    item.kroger_upc = "0001"
    db_session.add(IngredientProductMap(ingredient_id=ing.id, kroger_upc="0001",
                                        kroger_description="AP Flour", package_size="5 lb"))
    db_session.flush()
    current = service.get_match_state(db_session).items[0].current
    assert current is not None
    assert current.upc == "0001"
    assert current.description == "AP Flour"
    assert current.size == "5 lb"


def test_confirm_product_persists_map_and_recomputes_qty(db_session):
    gl, ing, item = _draft_with_item(db_session, total_qty=3.0, total_unit="lb")
    service.confirm_product(
        db_session, item.id,
        ConfirmRequest(kroger_upc="0001", kroger_description="AP Flour", package_size="1 lb"),
    )
    db_session.flush()
    assert item.kroger_upc == "0001"
    assert item.purchase_qty == 3
    assert item.purchase_qty_estimated is False
    mapping = db_session.query(IngredientProductMap).filter_by(ingredient_id=ing.id).one()
    assert mapping.kroger_upc == "0001"
    assert mapping.package_size == "1 lb"


def test_confirm_product_updates_existing_map_row(db_session):
    gl, ing, item = _draft_with_item(db_session)
    db_session.add(IngredientProductMap(ingredient_id=ing.id, kroger_upc="old",
                                        kroger_description="Old", package_size="2 lb"))
    db_session.flush()
    service.confirm_product(db_session, item.id,
                            ConfirmRequest(kroger_upc="new", package_size="1 lb"))
    db_session.flush()
    rows = db_session.query(IngredientProductMap).filter_by(ingredient_id=ing.id).all()
    assert len(rows) == 1
    assert rows[0].kroger_upc == "new"


def test_confirm_product_estimated_when_units_incompatible(db_session):
    gl, ing, item = _draft_with_item(db_session, total_qty=3.0, total_unit="cup")
    service.confirm_product(db_session, item.id,
                            ConfirmRequest(kroger_upc="0001", package_size="5 lb"))
    db_session.flush()
    assert item.purchase_qty == 1
    assert item.purchase_qty_estimated is True


def test_confirm_product_unknown_item_raises(db_session):
    with pytest.raises(service.ItemNotFoundError):
        service.confirm_product(db_session, 9999, ConfirmRequest(kroger_upc="x"))


def test_search_item_products_uses_store_and_canonical_name(db_session):
    gl, ing, item = _draft_with_item(db_session)
    settings_service.set_home_store(db_session, "L1", None)
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = [
        Product(upc="0001", description="AP Flour", size="5 lb", price=3.49,
                stock_level="HIGH", brand="Gold Medal", image_url="img.jpg")
    ]
    choices = service.search_item_products(db_session, kroger, item.id, query=None)
    assert choices[0].upc == "0001"
    assert choices[0].brand == "Gold Medal"
    assert choices[0].image_url == "img.jpg"
    kroger.search_products.assert_called_once_with("ct", "flour", "L1", limit=24, start=0)


def test_search_item_products_forwards_start_and_limit(db_session):
    gl, ing, item = _draft_with_item(db_session)
    settings_service.set_home_store(db_session, "L1", None)
    kroger = MagicMock()
    kroger.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    kroger.search_products.return_value = []
    service.search_item_products(db_session, kroger, item.id, query="jif", start=24, limit=24)
    kroger.search_products.assert_called_once_with("ct", "jif", "L1", limit=24, start=24)


def test_search_item_products_no_store_raises(db_session):
    gl, ing, item = _draft_with_item(db_session, store=None)
    with pytest.raises(service.NoStoreSelectedError):
        service.search_item_products(db_session, MagicMock(), item.id, query=None)


def test_set_store_persists_to_settings(db_session):
    gl, ing, item = _draft_with_item(db_session, store=None)
    state = service.set_store(db_session, "L99")
    assert state.store_location_id == "L99"
    db_session.flush()
    loc, _name = settings_service.get_home_store(db_session)
    assert loc == "L99"
