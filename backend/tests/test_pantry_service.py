from datetime import datetime, timedelta, timezone

import pytest

from app.pantry import service
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    PurchaseLog,
)


def _draft_item(db, *, status="needed", resolved=False):
    ing = Ingredient(canonical_name="rice", aliases=[], category="pantry")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft")
    db.add(gl)
    db.flush()
    item = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=2.0, total_unit="lb",
                           pantry_status=status, pantry_resolved=resolved)
    db.add(item)
    db.flush()
    return gl, ing, item


def _purchase(db, ingredient_id, days_ago, qty=2.0, unit="lb"):
    db.add(PurchaseLog(ingredient_id=ingredient_id, kroger_upc="0001", qty=qty, unit=unit,
                       purchased_at=datetime.now(timezone.utc) - timedelta(days=days_ago)))
    db.flush()


def test_evaluate_flags_recent_purchase(db_session):
    gl, ing, item = _draft_item(db_session)
    _purchase(db_session, ing.id, days_ago=6)
    service.evaluate(db_session)
    assert item.pantry_status == "maybe_have"


def test_evaluate_ignores_old_purchase(db_session):
    gl, ing, item = _draft_item(db_session)
    _purchase(db_session, ing.id, days_ago=60)
    service.evaluate(db_session)
    assert item.pantry_status == "needed"


def test_evaluate_skips_resolved_items(db_session):
    gl, ing, item = _draft_item(db_session, resolved=True)
    _purchase(db_session, ing.id, days_ago=3)
    service.evaluate(db_session)
    assert item.pantry_status == "needed"


def test_get_view_includes_prompt_data_for_flagged(db_session):
    gl, ing, item = _draft_item(db_session)
    _purchase(db_session, ing.id, days_ago=6, qty=5.0, unit="lb")
    view = service.get_view(db_session)
    flagged = next(i for i in view.items if i.item_id == item.id)
    assert flagged.pantry_status == "maybe_have"
    assert flagged.last_qty == 5.0
    assert flagged.last_unit == "lb"
    assert flagged.days_ago == 6


def test_set_decision_keep(db_session):
    gl, ing, item = _draft_item(db_session, status="maybe_have")
    service.set_decision(db_session, item.id, keep=True)
    assert item.pantry_status == "needed"
    assert item.pantry_resolved is True


def test_set_decision_skip(db_session):
    gl, ing, item = _draft_item(db_session, status="maybe_have")
    service.set_decision(db_session, item.id, keep=False)
    assert item.pantry_status == "skipped"
    assert item.pantry_resolved is True


def test_set_decision_unknown_item_raises(db_session):
    with pytest.raises(service.ItemNotFoundError):
        service.set_decision(db_session, 9999, keep=True)
