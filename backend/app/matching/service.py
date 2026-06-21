"""Matching + send orchestration. The only writer of ingredient_product_map for picks,
and of grocery_list_items.kroger_upc / purchase_qty / purchase_qty_estimated."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consolidate.service import get_or_create_draft
from app.kroger import auth as kroger_auth
from app.kroger.client import KrogerAuthError, KrogerClient, KrogerError
from app.matching.purchase import compute_purchase_qty
from app.matching.schemas import (
    ConfirmRequest,
    MatchItemRead,
    MatchRead,
    ProductChoice,
    SendItemResult,
    SendResult,
)
from app.models import GroceryList, GroceryListItem, Ingredient, IngredientProductMap, PurchaseLog


class ItemNotFoundError(Exception):
    """The grocery_list_item id does not exist."""


class NoStoreSelectedError(Exception):
    """A store must be chosen on the draft before searching products."""


def _kept_items(db: Session, list_id: int) -> list[GroceryListItem]:
    rows = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == list_id)
    ).scalars().all()
    return [r for r in rows if r.pantry_status != "skipped"]


def _current_choice(db: Session, item: GroceryListItem) -> ProductChoice | None:
    if item.kroger_upc is None:
        return None
    mapping = db.execute(
        select(IngredientProductMap).where(IngredientProductMap.kroger_upc == item.kroger_upc)
    ).scalars().first()
    if mapping is None:
        return ProductChoice(upc=item.kroger_upc, description="")
    return ProductChoice(
        upc=mapping.kroger_upc,
        description=mapping.kroger_description or "",
        size=mapping.package_size,
    )


def get_match_state(db: Session) -> MatchRead:
    draft = get_or_create_draft(db)
    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    items = [
        MatchItemRead(
            item_id=it.id,
            ingredient_id=it.ingredient_id,
            ingredient_name=ing_by_id[it.ingredient_id].canonical_name,
            total_qty=it.total_qty,
            total_unit=it.total_unit,
            purchase_qty=it.purchase_qty,
            purchase_qty_estimated=it.purchase_qty_estimated,
            kroger_upc=it.kroger_upc,
            current=_current_choice(db, it),
        )
        for it in _kept_items(db, draft.id)
    ]
    return MatchRead(
        connected=kroger_auth.get_auth(db) is not None,
        store_location_id=draft.store_location_id,
        items=items,
    )


def _get_item(db: Session, item_id: int) -> GroceryListItem:
    item = db.get(GroceryListItem, item_id)
    if item is None:
        raise ItemNotFoundError(f"grocery_list_item {item_id} not found")
    return item


def confirm_product(db: Session, item_id: int, req: ConfirmRequest) -> None:
    item = _get_item(db, item_id)

    mapping = db.execute(
        select(IngredientProductMap).where(
            IngredientProductMap.ingredient_id == item.ingredient_id
        )
    ).scalars().first()
    if mapping is None:
        mapping = IngredientProductMap(ingredient_id=item.ingredient_id)
        db.add(mapping)
    mapping.kroger_upc = req.kroger_upc
    mapping.kroger_description = req.kroger_description
    mapping.package_size = req.package_size
    mapping.is_default = True

    item.kroger_upc = req.kroger_upc
    qty, estimated = compute_purchase_qty(item.total_qty, item.total_unit, req.package_size)
    item.purchase_qty = qty
    item.purchase_qty_estimated = estimated
    db.flush()


def search_item_products(
    db: Session, client: KrogerClient, item_id: int, query: str | None
) -> list[ProductChoice]:
    item = _get_item(db, item_id)
    gl = db.get(GroceryList, item.list_id)
    if gl is None or gl.store_location_id is None:
        raise NoStoreSelectedError("pick a store before searching products")

    ingredient = db.get(Ingredient, item.ingredient_id)
    term = query or (ingredient.canonical_name if ingredient else "")
    token = client.fetch_client_token()
    products = client.search_products(token.access_token, term, gl.store_location_id)
    return [
        ProductChoice(
            upc=p.upc, description=p.description, size=p.size,
            price=p.price, stock_level=p.stock_level,
        )
        for p in products
    ]


def send_to_cart(db: Session, client: KrogerClient, modality: str = "PICKUP") -> SendResult:
    """Push each item with a UPC to the cart, one PUT per item. Logs only successes to
    purchase_log. Raises NotConnectedError/KrogerAuthError if the token is unusable."""
    draft = get_or_create_draft(db)
    token = kroger_auth.get_valid_token(db, client)  # NotConnected/Auth errors propagate

    results: list[SendItemResult] = []
    any_success = False
    for item in _kept_items(db, draft.id):
        if item.kroger_upc is None:
            continue
        try:
            client.add_to_cart(
                token, upc=item.kroger_upc, quantity=item.purchase_qty, modality=modality
            )
        except KrogerAuthError:
            raise  # token died mid-send: abort so the user re-auths, no partial lie
        except KrogerError as exc:
            results.append(SendItemResult(upc=item.kroger_upc, ok=False, error=str(exc)))
            continue
        any_success = True
        db.add(
            PurchaseLog(
                ingredient_id=item.ingredient_id,
                kroger_upc=item.kroger_upc,
                qty=item.total_qty,
                unit=item.total_unit,
                source_list_id=draft.id,
            )
        )
        results.append(SendItemResult(upc=item.kroger_upc, ok=True, error=None))

    if any_success:
        draft.status = "sent_to_kroger"
        draft.sent_at = datetime.now(timezone.utc)
    db.flush()
    return SendResult(status=draft.status, results=results)
