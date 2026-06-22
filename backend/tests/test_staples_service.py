from unittest.mock import MagicMock

import pytest

from app.consolidate.service import get_or_create_draft
from app.ingredients.canonicalize import CanonResult
from app.models import GroceryListStaple, Ingredient, Staple
from app.staples import service


def _ingredient(db, name="peanut butter"):
    ing = Ingredient(canonical_name=name, aliases=[], category="pantry")
    db.add(ing)
    db.flush()
    return ing


def test_add_staple_creates_for_resolved_ingredient(db_session, monkeypatch):
    ing = _ingredient(db_session)
    monkeypatch.setattr(service, "canonicalize_names",
                        lambda names, db, llm: {names[0]: CanonResult(ingredient_id=ing.id, is_new=False)})
    s = service.add_staple(db_session, "peanut butter", MagicMock())
    assert s.ingredient_id == ing.id
    assert db_session.query(Staple).count() == 1


def test_add_staple_is_idempotent_per_ingredient(db_session, monkeypatch):
    ing = _ingredient(db_session)
    monkeypatch.setattr(service, "canonicalize_names",
                        lambda names, db, llm: {names[0]: CanonResult(ingredient_id=ing.id, is_new=False)})
    service.add_staple(db_session, "peanut butter", MagicMock())
    service.add_staple(db_session, "peanut butter", MagicMock())
    assert db_session.query(Staple).count() == 1


def test_set_auto_add_and_remove(db_session):
    ing = _ingredient(db_session)
    s = Staple(ingredient_id=ing.id)
    db_session.add(s)
    db_session.flush()
    service.set_auto_add(db_session, s.id, False)
    assert s.auto_add is False
    service.remove_staple(db_session, s.id)
    assert db_session.query(Staple).count() == 0


def test_sync_draft_seeds_auto_staples_once(db_session):
    ing = _ingredient(db_session)
    s = Staple(ingredient_id=ing.id, auto_add=True)
    db_session.add(s)
    db_session.flush()
    draft = get_or_create_draft(db_session)

    service.sync_draft(db_session, draft)
    assert db_session.query(GroceryListStaple).filter_by(list_id=draft.id).count() == 1
    assert draft.staples_seeded is True

    service.remove_from_trip(db_session, s.id)
    service.sync_draft(db_session, draft)
    assert db_session.query(GroceryListStaple).filter_by(list_id=draft.id).count() == 0


def test_add_and_remove_from_trip(db_session):
    ing = _ingredient(db_session)
    s = Staple(ingredient_id=ing.id, auto_add=False)
    db_session.add(s)
    db_session.flush()
    service.add_to_trip(db_session, s.id)
    draft = get_or_create_draft(db_session)
    assert db_session.query(GroceryListStaple).filter_by(list_id=draft.id, staple_id=s.id).count() == 1
    service.remove_from_trip(db_session, s.id)
    assert db_session.query(GroceryListStaple).filter_by(list_id=draft.id, staple_id=s.id).count() == 0


def test_get_view_reports_on_trip_and_auto(db_session):
    ing = _ingredient(db_session)
    s = Staple(ingredient_id=ing.id, auto_add=True)
    db_session.add(s)
    db_session.flush()
    view = service.get_view(db_session)
    row = next(r for r in view.staples if r.id == s.id)
    assert row.ingredient_name == "peanut butter"
    assert row.auto_add is True
    assert row.on_trip is True


def test_remove_staple_unknown_raises(db_session):
    with pytest.raises(service.StapleNotFoundError):
        service.remove_staple(db_session, 9999)
