"""Pantry 'still have it?' logic: flag recently-bought ingredients and record keep/skip
decisions. Pure DB — no Kroger/LLM. Reads the self-tracked purchase_log."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.consolidate.service import get_or_create_draft
from app.models import GroceryListItem, Ingredient, PurchaseLog
from app.pantry.schemas import PantryItemRead, PantryView


class ItemNotFoundError(Exception):
    """The grocery_list_item id does not exist."""


def _recent_window_start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=get_settings().pantry_recent_days)


def _last_purchase(db: Session, ingredient_id: int, since: datetime) -> PurchaseLog | None:
    return db.execute(
        select(PurchaseLog)
        .where(PurchaseLog.ingredient_id == ingredient_id, PurchaseLog.purchased_at >= since)
        .order_by(PurchaseLog.purchased_at.desc())
    ).scalars().first()


def evaluate(db: Session) -> None:
    """Flag needed+unresolved items as maybe_have when bought within the recent window."""
    since = _recent_window_start()
    draft = get_or_create_draft(db)
    items = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == draft.id)
    ).scalars().all()
    for item in items:
        if item.pantry_resolved or item.pantry_status != "needed":
            continue
        if _last_purchase(db, item.ingredient_id, since) is not None:
            item.pantry_status = "maybe_have"
    db.flush()


def get_view(db: Session) -> PantryView:
    """Run evaluation and return every draft item with its pantry state + prompt data."""
    evaluate(db)
    since = _recent_window_start()
    draft = get_or_create_draft(db)
    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    items = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == draft.id)
    ).scalars().all()

    out: list[PantryItemRead] = []
    now = datetime.now(timezone.utc)
    for item in items:
        last = (
            _last_purchase(db, item.ingredient_id, since)
            if item.pantry_status == "maybe_have"
            else None
        )
        out.append(
            PantryItemRead(
                item_id=item.id,
                ingredient_id=item.ingredient_id,
                ingredient_name=ing_by_id[item.ingredient_id].canonical_name,
                pantry_status=item.pantry_status,
                last_qty=last.qty if last else None,
                last_unit=last.unit if last else None,
                purchased_at=last.purchased_at if last else None,
                days_ago=(now - last.purchased_at).days if last else None,
            )
        )
    return PantryView(items=out)


def set_decision(db: Session, item_id: int, keep: bool) -> None:
    item = db.get(GroceryListItem, item_id)
    if item is None:
        raise ItemNotFoundError(f"grocery_list_item {item_id} not found")
    item.pantry_status = "needed" if keep else "skipped"
    item.pantry_resolved = True
    db.flush()
