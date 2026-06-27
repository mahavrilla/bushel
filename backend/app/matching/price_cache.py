"""Read and refresh price_cache rows. The only thing that calls KrogerClient.get_product_by_id.
A 12h freshness window keeps the app's rebuild-on-every-change from re-hitting the API and
keeps us well under the 10k/day budget. now is injected so tests are deterministic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kroger.client import KrogerClient, KrogerError
from app.matching.pricing import to_cents
from app.models import PriceCache

FRESH_WINDOW = timedelta(hours=12)


@dataclass
class PriceInfo:
    upc: str
    regular_cents: int | None
    promo_cents: int | None
    size_text: str | None
    stock_level: str | None
    fetched_at: datetime


def _info(row: PriceCache) -> PriceInfo:
    return PriceInfo(
        upc=row.kroger_upc,
        regular_cents=row.regular_cents,
        promo_cents=row.promo_cents,
        size_text=row.size_text,
        stock_level=row.stock_level,
        fetched_at=row.fetched_at,
    )


def get_prices(
    db: Session,
    client: KrogerClient | None,
    upcs: list[str],
    location_id: str,
    *,
    now: datetime,
) -> dict[str, PriceInfo]:
    if not upcs:
        return {}
    rows = db.execute(
        select(PriceCache).where(
            PriceCache.location_id == location_id,
            PriceCache.kroger_upc.in_(upcs),
        )
    ).scalars().all()
    by_upc = {r.kroger_upc: r for r in rows}

    out: dict[str, PriceInfo] = {}
    stale: list[str] = []
    for upc in upcs:
        row = by_upc.get(upc)
        if row is not None and (now - row.fetched_at) < FRESH_WINDOW:
            out[upc] = _info(row)
        else:
            stale.append(upc)

    if stale and client is not None:
        try:
            token = client.fetch_client_token()
        except (KrogerError, httpx.HTTPError):
            return out  # serve cached; missing UPCs surface as "price unavailable"
        for upc in stale:
            try:
                prod = client.get_product_by_id(token.access_token, upc, location_id)
            except (KrogerError, httpx.HTTPError):
                continue  # leave this UPC absent; caller shows "price unavailable"
            row = by_upc.get(upc) or PriceCache(kroger_upc=upc, location_id=location_id)
            row.regular_cents = to_cents(prod.price)
            row.promo_cents = to_cents(prod.promo)
            row.size_text = prod.size
            row.stock_level = prod.stock_level
            row.fetched_at = now
            db.add(row)
            out[upc] = _info(row)
        db.flush()

    return out
