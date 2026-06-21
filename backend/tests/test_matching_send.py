from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.kroger.client import KrogerAuthError, KrogerError
from app.matching import service
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    KrogerAuth,
    PurchaseLog,
)


def _connected(db):
    db.add(KrogerAuth(access_token="a", refresh_token="r",
                      expires_at=datetime.now(timezone.utc) + timedelta(hours=1), scopes=[]))
    db.flush()


def _draft_with_items(db, upcs):
    ing = Ingredient(canonical_name="flour", aliases=[], category="baking")
    db.add(ing)
    db.flush()
    gl = GroceryList(name="Draft", status="draft", store_location_id="L1")
    db.add(gl)
    db.flush()
    items = []
    for upc in upcs:
        it = GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=3.0,
                             total_unit="lb", purchase_qty=2, kroger_upc=upc,
                             pantry_status="needed")
        db.add(it)
        items.append(it)
    db.flush()
    return gl, ing, items


def test_send_pushes_each_item_and_logs_success(db_session):
    _connected(db_session)
    gl, ing, items = _draft_with_items(db_session, ["0001", "0002"])
    kroger = MagicMock()
    result = service.send_to_cart(db_session, kroger, modality="PICKUP")
    db_session.flush()
    assert all(r.ok for r in result.results)
    assert kroger.add_to_cart.call_count == 2
    assert gl.status == "sent_to_kroger"
    assert gl.sent_at is not None
    assert db_session.query(PurchaseLog).count() == 2


def test_send_skips_items_without_upc(db_session):
    _connected(db_session)
    gl, ing, items = _draft_with_items(db_session, ["0001"])
    db_session.add(GroceryListItem(list_id=gl.id, ingredient_id=ing.id, total_qty=1.0,
                                   total_unit="lb", purchase_qty=1, kroger_upc=None,
                                   pantry_status="needed"))
    db_session.flush()
    kroger = MagicMock()
    result = service.send_to_cart(db_session, kroger, modality="PICKUP")
    assert len(result.results) == 1
    assert kroger.add_to_cart.call_count == 1


def test_send_partial_failure_logs_only_successes(db_session):
    _connected(db_session)
    gl, ing, items = _draft_with_items(db_session, ["good", "bad"])
    kroger = MagicMock()

    def add(token, *, upc, quantity, modality):
        if upc == "bad":
            raise KrogerError("Invalid.UPC")

    kroger.add_to_cart.side_effect = add
    result = service.send_to_cart(db_session, kroger, modality="PICKUP")
    db_session.flush()
    by_upc = {r.upc: r for r in result.results}
    assert by_upc["good"].ok is True
    assert by_upc["bad"].ok is False and by_upc["bad"].error
    assert db_session.query(PurchaseLog).count() == 1
    assert gl.status == "sent_to_kroger"


def test_send_auth_failure_aborts_with_error(db_session):
    _connected(db_session)
    gl, ing, items = _draft_with_items(db_session, ["0001"])
    kroger = MagicMock()
    kroger.add_to_cart.side_effect = KrogerAuthError("token revoked")
    with pytest.raises(KrogerAuthError):
        service.send_to_cart(db_session, kroger, modality="PICKUP")


def test_send_not_connected_raises(db_session):
    gl, ing, items = _draft_with_items(db_session, ["0001"])
    with pytest.raises(service.kroger_auth.NotConnectedError):
        service.send_to_cart(db_session, MagicMock(), modality="PICKUP")
