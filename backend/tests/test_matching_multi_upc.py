from datetime import datetime, timedelta, timezone

import pytest

from app.matching import service
from app.matching.schemas import AddAlternativeRequest
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    IngredientProductMap,
    PurchaseLog,
)
from app.settings import service as settings_service


def _draft_with_item(db, total_qty=1.0, total_unit="bottle", store="L1"):
    ing = Ingredient(canonical_name="creamer", aliases=[], category="dairy",
                     default_purchase_unit="bottle")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id=store)
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id,
                           total_qty=total_qty, total_unit=total_unit, pantry_status="needed")
    db.add(item)
    db.flush()
    settings_service.set_home_store(db, store, None) if store else None
    return gl, ing, item


def _two_alts(db, ing):
    db.add_all([
        IngredientProductMap(ingredient_id=ing.id, kroger_upc="REG",
                             kroger_description="Regular", package_size="32 fl oz", is_default=True),
        IngredientProductMap(ingredient_id=ing.id, kroger_upc="ORG",
                             kroger_description="Organic", package_size="25 fl oz", is_default=False),
    ])
    db.flush()


def test_resolve_default_prefers_last_purchased(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    now = datetime.now(timezone.utc)
    db_session.add_all([
        PurchaseLog(ingredient_id=ing.id, kroger_upc="REG", purchased_at=now - timedelta(days=5)),
        PurchaseLog(ingredient_id=ing.id, kroger_upc="ORG", purchased_at=now - timedelta(days=1)),
    ])
    db_session.flush()
    assert service._resolve_default_upc(db_session, ing.id) == "ORG"


def test_resolve_default_falls_back_to_is_default(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    assert service._resolve_default_upc(db_session, ing.id) == "REG"


def test_resolve_default_falls_back_to_first_when_no_default(db_session):
    gl, ing, item = _draft_with_item(db_session)
    db_session.add_all([
        IngredientProductMap(ingredient_id=ing.id, kroger_upc="A", package_size="1 ct", is_default=False),
        IngredientProductMap(ingredient_id=ing.id, kroger_upc="B", package_size="1 ct", is_default=False),
    ])
    db_session.flush()
    assert service._resolve_default_upc(db_session, ing.id) == "A"


def test_resolve_default_ignores_purchase_of_non_acceptable_upc(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    db_session.add(PurchaseLog(ingredient_id=ing.id, kroger_upc="GONE",
                               purchased_at=datetime.now(timezone.utc)))
    db_session.flush()
    assert service._resolve_default_upc(db_session, ing.id) == "REG"  # is_default, not GONE


def test_apply_remembered_uses_resolved_default(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    db_session.add(PurchaseLog(ingredient_id=ing.id, kroger_upc="ORG",
                               purchased_at=datetime.now(timezone.utc)))
    db_session.flush()
    service.apply_remembered_products(db_session)
    db_session.refresh(item)
    assert item.kroger_upc == "ORG"


def test_apply_remembered_keeps_existing_pick(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "ORG"  # user already switched
    db_session.flush()
    service.apply_remembered_products(db_session)
    db_session.refresh(item)
    assert item.kroger_upc == "ORG"


def test_current_choice_matches_item_upc_not_first_row(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "ORG"
    db_session.flush()
    current = service.get_match_state(db_session).items[0].current
    assert current.upc == "ORG"
    assert current.description == "Organic"


def test_add_alternative_appends_row_without_changing_pick(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    service.add_alternative(db_session, item.id,
                            AddAlternativeRequest(kroger_upc="VAN", kroger_description="Vanilla",
                                                  package_size="32 fl oz"))
    db_session.flush()
    upcs = {m.kroger_upc for m in service._acceptable_maps(db_session, ing.id)}
    assert upcs == {"REG", "ORG", "VAN"}
    db_session.refresh(item)
    assert item.kroger_upc == "REG"  # pick unchanged


def test_add_alternative_is_idempotent_on_duplicate_upc(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    service.add_alternative(db_session, item.id, AddAlternativeRequest(kroger_upc="REG"))
    db_session.flush()
    assert len(service._acceptable_maps(db_session, ing.id)) == 2


def test_switch_pick_sets_item_upc_and_recomputes_qty(db_session):
    gl, ing, item = _draft_with_item(db_session, total_qty=2.0, total_unit="bottle")
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    service.switch_pick(db_session, item.id, "ORG")
    db_session.refresh(item)
    assert item.kroger_upc == "ORG"
    assert item.purchase_qty >= 1


def test_switch_pick_rejects_non_acceptable_upc(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    with pytest.raises(service.UpcNotAcceptableError):
        service.switch_pick(db_session, item.id, "NOPE")


def test_switch_pick_does_not_write_purchase_log(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)
    item.kroger_upc = "REG"
    db_session.flush()
    service.switch_pick(db_session, item.id, "ORG")
    assert db_session.query(PurchaseLog).count() == 0


def test_remove_alternative_repoints_pick_when_removing_current(db_session):
    gl, ing, item = _draft_with_item(db_session)
    _two_alts(db_session, ing)  # REG is_default
    item.kroger_upc = "ORG"
    db_session.flush()
    service.remove_alternative(db_session, item.id, "ORG")
    db_session.refresh(item)
    assert item.kroger_upc == "REG"  # re-resolved to remaining default
    assert {m.kroger_upc for m in service._acceptable_maps(db_session, ing.id)} == {"REG"}


def test_remove_last_alternative_clears_pick(db_session):
    gl, ing, item = _draft_with_item(db_session)
    db_session.add(IngredientProductMap(ingredient_id=ing.id, kroger_upc="ONLY",
                                        package_size="1 ct", is_default=True))
    db_session.flush()
    item.kroger_upc = "ONLY"
    db_session.flush()
    service.remove_alternative(db_session, item.id, "ONLY")
    db_session.refresh(item)
    assert item.kroger_upc is None
