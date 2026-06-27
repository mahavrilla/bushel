"""Matching + send orchestration. The only writer of ingredient_product_map for picks,
and of grocery_list_items.kroger_upc / purchase_qty / purchase_qty_estimated."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consolidate.service import get_or_create_draft
from app.kroger import auth as kroger_auth
from app.settings import service as settings_service
from app.kroger.client import KrogerAuthError, KrogerClient, KrogerError
from app.matching import pricing
from app.matching.price_cache import PriceInfo, get_prices
from app.matching.purchase import compute_purchase_qty
from app.matching.schemas import (
    AddAlternativeRequest,
    Alternative,
    ConfirmRequest,
    ItemInsight,
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


class UpcNotAcceptableError(Exception):
    """The requested UPC is not in the ingredient's acceptable set."""


def _kept_items(db: Session, list_id: int) -> list[GroceryListItem]:
    rows = db.execute(
        select(GroceryListItem).where(GroceryListItem.list_id == list_id)
    ).scalars().all()
    return [r for r in rows if r.pantry_status != "skipped"]


def _acceptable_maps(db: Session, ingredient_id: int) -> list[IngredientProductMap]:
    return db.execute(
        select(IngredientProductMap)
        .where(IngredientProductMap.ingredient_id == ingredient_id)
        .order_by(IngredientProductMap.id)
    ).scalars().all()


def _resolve_default_upc(db: Session, ingredient_id: int) -> str | None:
    """Default pick = most recently purchased acceptable UPC, else the is_default row,
    else the first row. Purchases of UPCs no longer in the acceptable set are ignored."""
    rows = _acceptable_maps(db, ingredient_id)
    if not rows:
        return None
    acceptable = {r.kroger_upc for r in rows}
    last = db.execute(
        select(PurchaseLog)
        .where(
            PurchaseLog.ingredient_id == ingredient_id,
            PurchaseLog.kroger_upc.in_(acceptable),
        )
        .order_by(PurchaseLog.purchased_at.desc())
    ).scalars().first()
    if last is not None and last.kroger_upc is not None:
        return last.kroger_upc
    default_row = next((r for r in rows if r.is_default), None)
    if default_row is not None:
        return default_row.kroger_upc
    return rows[0].kroger_upc


def _to_alternative(
    m: IngredientProductMap, current_upc: str | None, price: PriceInfo | None
) -> Alternative:
    reg_c = price.regular_cents if price else None
    promo_c = price.promo_cents if price else None
    size = (price.size_text if price and price.size_text else m.package_size)
    eff_c = pricing.effective_cents(reg_c, promo_c)
    up = pricing.unit_price(eff_c, size)
    return Alternative(
        upc=m.kroger_upc,
        description=m.kroger_description or "",
        size=size,
        regular=None if reg_c is None else reg_c / 100.0,
        promo=None if promo_c is None else promo_c / 100.0,
        effective=None if eff_c is None else eff_c / 100.0,
        unit_price=None if up is None else round(up[0], 4),
        unit_label=None if up is None else up[1],
        on_sale=pricing.is_on_sale(reg_c, promo_c),
        stock_level=price.stock_level if price else None,
        is_current=(m.kroger_upc == current_upc),
        price_as_of=price.fetched_at if price else None,
    )


def _build_insight(alts: list[Alternative]) -> ItemInsight:
    cur = next((a for a in alts if a.is_current), None)
    cheaper = None
    if cur is not None and cur.effective is not None:
        priced = [a for a in alts if not a.is_current and a.effective is not None]
        if priced:
            cheapest = min(priced, key=lambda a: a.effective)
            if cheapest.effective < cur.effective:
                cheaper = round((cur.effective - cheapest.effective) * 100)
    return ItemInsight(
        cheaper_delta_cents=cheaper,
        on_sale=any(a.on_sale for a in alts),
        default_out_of_stock=(cur is not None and cur.stock_level == "TEMPORARILY_OUT_OF_STOCK"),
    )


def _current_choice(db: Session, item: GroceryListItem) -> ProductChoice | None:
    if item.kroger_upc is None:
        return None
    mapping = db.execute(
        select(IngredientProductMap).where(
            IngredientProductMap.ingredient_id == item.ingredient_id,
            IngredientProductMap.kroger_upc == item.kroger_upc,
        )
    ).scalars().first()
    if mapping is None:
        return ProductChoice(upc=item.kroger_upc, description="")
    return ProductChoice(
        upc=mapping.kroger_upc,
        description=mapping.kroger_description or "",
        size=mapping.package_size,
    )


def apply_remembered_products(db: Session) -> None:
    """Fill unresolved kept items with the resolved default UPC (last-purchased → is_default →
    first) and recompute purchase_qty from that product's package size. Idempotent; existing
    picks are left untouched so a user's switch survives list rebuilds."""
    draft = get_or_create_draft(db)
    for item in _kept_items(db, draft.id):
        if item.kroger_upc is not None:
            continue
        upc = _resolve_default_upc(db, item.ingredient_id)
        if upc is None:
            continue
        row = next(
            (r for r in _acceptable_maps(db, item.ingredient_id) if r.kroger_upc == upc),
            None,
        )
        item.kroger_upc = upc
        qty, estimated = compute_purchase_qty(
            item.total_qty, item.total_unit, row.package_size if row else None
        )
        item.purchase_qty = qty
        item.purchase_qty_estimated = estimated
    db.flush()


def get_match_state(
    db: Session, client: KrogerClient | None = None, *, now: datetime | None = None
) -> MatchRead:
    apply_remembered_products(db)
    draft = get_or_create_draft(db)
    now = now or datetime.now(timezone.utc)
    ing_by_id = {i.id: i for i in db.execute(select(Ingredient)).scalars().all()}
    loc, store_name = settings_service.get_home_store(db)

    items: list[MatchItemRead] = []
    for it in _kept_items(db, draft.id):
        maps = _acceptable_maps(db, it.ingredient_id)
        alternatives: list[Alternative] = []
        insight: ItemInsight | None = None
        if len(maps) >= 2:
            prices: dict[str, PriceInfo] = {}
            if loc is not None:
                prices = get_prices(db, client, [m.kroger_upc for m in maps], loc, now=now)
            alternatives = [_to_alternative(m, it.kroger_upc, prices.get(m.kroger_upc)) for m in maps]
            insight = _build_insight(alternatives)
        items.append(
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
                alternatives=alternatives,
                insight=insight,
            )
        )

    return MatchRead(
        connected=kroger_auth.get_auth(db) is not None,
        store_location_id=loc,
        store_name=store_name,
        items=items,
    )


def set_store(db: Session, location_id: str, name: str | None = None) -> MatchRead:
    """Persist the chosen Kroger store as the user's home store, then return match state."""
    settings_service.set_home_store(db, location_id, name)
    return get_match_state(db)


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


def add_alternative(db: Session, item_id: int, req: AddAlternativeRequest) -> None:
    """Bless a product as an acceptable alternative for the item's ingredient. No-op if the
    UPC is already mapped. Never changes the current pick."""
    item = _get_item(db, item_id)
    existing = {m.kroger_upc for m in _acceptable_maps(db, item.ingredient_id)}
    if req.kroger_upc in existing:
        return
    db.add(
        IngredientProductMap(
            ingredient_id=item.ingredient_id,
            kroger_upc=req.kroger_upc,
            kroger_description=req.kroger_description,
            package_size=req.package_size,
            is_default=False,
        )
    )
    db.flush()


def switch_pick(db: Session, item_id: int, upc: str) -> None:
    """Set the item's current pick to an acceptable UPC and recompute purchase_qty. Does not
    write purchase history — the last-purchased default only changes when a trip is sent."""
    item = _get_item(db, item_id)
    rows = _acceptable_maps(db, item.ingredient_id)
    row = next((r for r in rows if r.kroger_upc == upc), None)
    if row is None:
        raise UpcNotAcceptableError(f"{upc} is not an acceptable product for this ingredient")
    item.kroger_upc = upc
    qty, estimated = compute_purchase_qty(item.total_qty, item.total_unit, row.package_size)
    item.purchase_qty = qty
    item.purchase_qty_estimated = estimated
    db.flush()


def remove_alternative(db: Session, item_id: int, upc: str) -> None:
    """Drop a UPC from the acceptable set. If it was the current pick, re-resolve the default
    (which may leave the item with no pick)."""
    item = _get_item(db, item_id)
    row = next(
        (r for r in _acceptable_maps(db, item.ingredient_id) if r.kroger_upc == upc), None
    )
    if row is None:
        return
    db.delete(row)
    db.flush()
    if item.kroger_upc == upc:
        new_upc = _resolve_default_upc(db, item.ingredient_id)
        item.kroger_upc = new_upc
        new_row = next(
            (r for r in _acceptable_maps(db, item.ingredient_id) if r.kroger_upc == new_upc),
            None,
        )
        qty, estimated = compute_purchase_qty(
            item.total_qty, item.total_unit, new_row.package_size if new_row else None
        )
        item.purchase_qty = qty
        item.purchase_qty_estimated = estimated
    db.flush()


def search_item_products(
    db: Session, client: KrogerClient, item_id: int, query: str | None,
    start: int = 0, limit: int = 24,
) -> list[ProductChoice]:
    item = _get_item(db, item_id)
    location_id, _name = settings_service.get_home_store(db)
    if location_id is None:
        raise NoStoreSelectedError("pick a store before searching products")

    ingredient = db.get(Ingredient, item.ingredient_id)
    term = query or (ingredient.canonical_name if ingredient else "")
    token = client.fetch_client_token()
    products = client.search_products(token.access_token, term, location_id, limit=limit, start=start)
    return [
        ProductChoice(
            upc=p.upc, description=p.description, size=p.size,
            price=p.price, stock_level=p.stock_level,
            brand=p.brand, image_url=p.image_url,
        )
        for p in products
    ]


def send_to_cart(db: Session, client: KrogerClient, modality: str = "PICKUP") -> SendResult:
    """Push each item with a UPC to the cart, one PUT per item. Logs only successes to
    purchase_log. Raises NotConnectedError/KrogerAuthError if the token is unusable."""
    draft = get_or_create_draft(db)
    apply_remembered_products(db)
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
