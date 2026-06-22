from app.matching import service
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    IngredientProductMap,
)


def _draft_item(db, *, kroger_upc=None, total_qty=3.0, total_unit="lb", with_map=True):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id="L1")
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=total_qty,
                           total_unit=total_unit, kroger_upc=kroger_upc, pantry_status="needed")
    db.add(item)
    if with_map:
        db.add(IngredientProductMap(ingredient_id=ing.id, kroger_upc="0001",
                                    kroger_description="AP Flour", package_size="1 lb"))
    db.flush()
    return gl, ing, item


def test_apply_resolves_unmapped_item_from_map(db_session):
    gl, ing, item = _draft_item(db_session, total_qty=3.0, total_unit="lb")
    service.apply_remembered_products(db_session)
    db_session.flush()
    assert item.kroger_upc == "0001"
    assert item.purchase_qty == 3
    assert item.purchase_qty_estimated is False


def test_apply_skips_items_already_resolved(db_session):
    gl, ing, item = _draft_item(db_session, kroger_upc="EXISTING")
    service.apply_remembered_products(db_session)
    assert item.kroger_upc == "EXISTING"


def test_apply_skips_items_with_no_mapping(db_session):
    gl, ing, item = _draft_item(db_session, with_map=False)
    service.apply_remembered_products(db_session)
    assert item.kroger_upc is None


def test_apply_is_idempotent(db_session):
    gl, ing, item = _draft_item(db_session)
    service.apply_remembered_products(db_session)
    service.apply_remembered_products(db_session)
    assert item.kroger_upc == "0001"


def test_get_match_state_auto_resolves(db_session):
    gl, ing, item = _draft_item(db_session)
    state = service.get_match_state(db_session)
    matched = next(i for i in state.items if i.item_id == item.id)
    assert matched.kroger_upc == "0001"
    assert matched.current is not None and matched.current.upc == "0001"
