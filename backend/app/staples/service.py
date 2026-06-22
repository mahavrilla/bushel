"""Saved staples catalog + per-trip links. Pure DB except canonicalize (LLM) for new names."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consolidate.service import get_or_create_draft, recompute_draft
from app.ingredients.canonicalize import canonicalize_names
from app.llm.client import LLMClient
from app.models import GroceryListStaple, Ingredient, Staple
from app.staples.schemas import StapleRead, StapleView


class StapleNotFoundError(Exception):
    """The staple id does not exist."""


def _get_staple(db: Session, staple_id: int) -> Staple:
    s = db.get(Staple, staple_id)
    if s is None:
        raise StapleNotFoundError(f"staple {staple_id} not found")
    return s


def add_staple(db: Session, name: str, llm: LLMClient) -> Staple:
    """Resolve the name to a canonical ingredient and save it as a staple (one per ingredient)."""
    result = canonicalize_names([name], db, llm)[name]
    existing = db.execute(
        select(Staple).where(Staple.ingredient_id == result.ingredient_id)
    ).scalars().first()
    if existing is not None:
        return existing
    staple = Staple(ingredient_id=result.ingredient_id)
    db.add(staple)
    db.flush()
    return staple


def remove_staple(db: Session, staple_id: int) -> None:
    staple = _get_staple(db, staple_id)
    db.delete(staple)
    db.flush()
    recompute_draft(db)


def set_auto_add(db: Session, staple_id: int, auto_add: bool) -> None:
    staple = _get_staple(db, staple_id)
    staple.auto_add = auto_add
    db.flush()


def _link(db: Session, list_id: int, staple_id: int) -> GroceryListStaple | None:
    return db.execute(
        select(GroceryListStaple).where(
            GroceryListStaple.list_id == list_id, GroceryListStaple.staple_id == staple_id
        )
    ).scalars().first()


def sync_draft(db: Session, draft) -> None:
    """Seed auto_add staples onto the draft once (idempotent thereafter)."""
    if draft.staples_seeded:
        return
    autos = db.execute(select(Staple).where(Staple.auto_add.is_(True))).scalars().all()
    for s in autos:
        if _link(db, draft.id, s.id) is None:
            db.add(GroceryListStaple(list_id=draft.id, staple_id=s.id))
    draft.staples_seeded = True
    db.flush()
    if autos:
        recompute_draft(db)


def add_to_trip(db: Session, staple_id: int) -> None:
    _get_staple(db, staple_id)
    draft = get_or_create_draft(db)
    if _link(db, draft.id, staple_id) is None:
        db.add(GroceryListStaple(list_id=draft.id, staple_id=staple_id))
        db.flush()
        recompute_draft(db)


def remove_from_trip(db: Session, staple_id: int) -> None:
    draft = get_or_create_draft(db)
    link = _link(db, draft.id, staple_id)
    if link is not None:
        db.delete(link)
        db.flush()
        recompute_draft(db)


def get_view(db: Session) -> StapleView:
    draft = get_or_create_draft(db)
    sync_draft(db, draft)
    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    on_trip_ids = {
        l.staple_id
        for l in db.execute(
            select(GroceryListStaple).where(GroceryListStaple.list_id == draft.id)
        ).scalars().all()
    }
    staples = db.execute(select(Staple).order_by(Staple.id)).scalars().all()
    return StapleView(
        staples=[
            StapleRead(
                id=s.id,
                ingredient_id=s.ingredient_id,
                ingredient_name=ing_by_id[s.ingredient_id].canonical_name
                if s.ingredient_id in ing_by_id
                else None,
                auto_add=s.auto_add,
                on_trip=s.id in on_trip_ids,
            )
            for s in staples
        ]
    )
