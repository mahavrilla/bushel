from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.kroger.schemas import Product, TokenResp
from app.matching import price_cache
from app.models import PriceCache

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)


def _client(products: dict[str, Product]) -> MagicMock:
    c = MagicMock()
    c.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    c.get_product_by_id.side_effect = lambda tok, upc, loc: products[upc]
    return c


def test_fresh_cache_row_is_used_without_fetching(db_session):
    db_session.add(PriceCache(kroger_upc="0001", location_id="L1", regular_cents=549,
                              promo_cents=None, size_text="32 fl oz", stock_level="HIGH",
                              fetched_at=NOW - timedelta(hours=11)))
    db_session.flush()
    client = _client({})
    out = price_cache.get_prices(db_session, client, ["0001"], "L1", now=NOW)
    assert out["0001"].regular_cents == 549
    client.get_product_by_id.assert_not_called()


def test_stale_row_is_refetched_and_upserted(db_session):
    db_session.add(PriceCache(kroger_upc="0001", location_id="L1", regular_cents=999,
                              promo_cents=None, size_text="32 fl oz", stock_level="HIGH",
                              fetched_at=NOW - timedelta(hours=13)))
    db_session.flush()
    client = _client({"0001": Product(upc="0001", description="C", size="32 fl oz",
                                      price=5.49, promo=4.29, stock_level="LOW")})
    out = price_cache.get_prices(db_session, client, ["0001"], "L1", now=NOW)
    assert out["0001"].regular_cents == 549
    assert out["0001"].promo_cents == 429
    assert out["0001"].stock_level == "LOW"
    row = db_session.query(PriceCache).filter_by(kroger_upc="0001", location_id="L1").one()
    assert row.regular_cents == 549
    assert row.fetched_at == NOW


def test_missing_upc_is_fetched(db_session):
    client = _client({"0001": Product(upc="0001", description="C", size="25 fl oz",
                                      price=5.99, promo=None, stock_level="HIGH")})
    out = price_cache.get_prices(db_session, client, ["0001"], "L1", now=NOW)
    assert out["0001"].regular_cents == 599
    assert db_session.query(PriceCache).filter_by(kroger_upc="0001").count() == 1


def test_kroger_error_for_a_upc_is_skipped(db_session):
    from app.kroger.client import KrogerUnavailableError

    client = MagicMock()
    client.fetch_client_token.return_value = TokenResp(access_token="ct", expires_in=1800)
    client.get_product_by_id.side_effect = KrogerUnavailableError("boom")
    out = price_cache.get_prices(db_session, client, ["0001"], "L1", now=NOW)
    assert "0001" not in out


def test_no_client_returns_only_cached(db_session):
    db_session.add(PriceCache(kroger_upc="0001", location_id="L1", regular_cents=549,
                              promo_cents=None, size_text=None, stock_level=None,
                              fetched_at=NOW))
    db_session.flush()
    out = price_cache.get_prices(db_session, None, ["0001", "0002"], "L1", now=NOW)
    assert "0001" in out and "0002" not in out


def test_token_failure_degrades_to_cached(db_session):
    """fetch_client_token raising KrogerUnavailableError must NOT propagate; the already-fresh
    cached row for '0001' must be returned and '0002' (not cached) must simply be absent."""
    from app.kroger.client import KrogerUnavailableError

    db_session.add(PriceCache(kroger_upc="0001", location_id="L1", regular_cents=299,
                              promo_cents=None, size_text="16 oz", stock_level="HIGH",
                              fetched_at=NOW - timedelta(hours=1)))  # fresh
    db_session.flush()

    client = MagicMock()
    client.fetch_client_token.side_effect = KrogerUnavailableError("down")

    out = price_cache.get_prices(db_session, client, ["0001", "0002"], "L1", now=NOW)

    assert not client.get_product_by_id.called, "get_product_by_id must not be called after token failure"
    assert "0001" in out, "cached fresh row must still be returned"
    assert out["0001"].regular_cents == 299
    assert "0002" not in out, "uncached UPC must be absent, not raise"
