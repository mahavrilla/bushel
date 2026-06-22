"""The only module that performs network I/O to Kroger. No DB access here.

Tests inject an httpx.Client backed by httpx.MockTransport, so request building is
exercised without real network calls.
"""

from __future__ import annotations

import base64
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.kroger.schemas import Location, Product, TokenResp

PROD_BASE = "https://api.kroger.com"
_SCOPES = "product.compact cart.basic:write profile.compact"


def _extract_image_url(images: list | None) -> str | None:
    """Pick a product image URL: prefer the featured image, then the front perspective,
    else the first; within it prefer the medium size, else the first available URL."""
    if not images:
        return None
    chosen = next((i for i in images if i.get("featured")), None)
    if chosen is None:
        chosen = next((i for i in images if i.get("perspective") == "front"), None)
    if chosen is None:
        chosen = images[0]
    sizes = chosen.get("sizes") or []
    medium = next((s for s in sizes if s.get("size") == "medium" and s.get("url")), None)
    if medium:
        return medium["url"]
    return next((s["url"] for s in sizes if s.get("url")), None)


class KrogerError(Exception):
    """Any Kroger API failure."""


class KrogerAuthError(KrogerError):
    """401/403 — credentials or token rejected; caller should re-auth."""


class KrogerUnavailableError(KrogerError):
    """429/5xx — transient; caller should surface 'try later'."""


class KrogerClient:
    def __init__(
        self,
        http: httpx.Client | None = None,
        *,
        base_url: str = PROD_BASE,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        s = get_settings()
        self._base = base_url
        self._http = http or httpx.Client(base_url=base_url, timeout=10.0)
        self._client_id = client_id if client_id is not None else s.kroger_client_id
        self._client_secret = client_secret if client_secret is not None else s.kroger_client_secret
        self._redirect_uri = redirect_uri if redirect_uri is not None else s.kroger_redirect_uri

    # --- helpers -------------------------------------------------------------
    def _basic_auth(self) -> str:
        raw = f"{self._client_id}:{self._client_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code in (401, 403):
            raise KrogerAuthError(f"Kroger auth failed: {resp.status_code} {resp.text}")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise KrogerUnavailableError(f"Kroger unavailable: {resp.status_code}")
        if resp.status_code >= 400:
            raise KrogerError(f"Kroger error: {resp.status_code} {resp.text}")

    def _token_request(self, data: dict[str, str]) -> TokenResp:
        resp = self._http.post(
            "/v1/connect/oauth2/token",
            data=data,
            headers={
                "Authorization": self._basic_auth(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        self._raise_for_status(resp)
        return TokenResp(**resp.json())

    # --- auth ----------------------------------------------------------------
    def authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "scope": _SCOPES,
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "state": state,
            }
        )
        return f"{self._base}/v1/connect/oauth2/authorize?{query}"

    def fetch_client_token(self) -> TokenResp:
        return self._token_request({"grant_type": "client_credentials", "scope": "product.compact"})

    def exchange_code(self, code: str) -> TokenResp:
        return self._token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self._redirect_uri}
        )

    def refresh(self, refresh_token: str) -> TokenResp:
        return self._token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})

    # --- catalog -------------------------------------------------------------
    def search_locations(self, token: str, zip_code: str, limit: int = 10) -> list[Location]:
        resp = self._http.get(
            "/v1/locations",
            params={"filter.zipCode.near": zip_code, "filter.limit": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        self._raise_for_status(resp)
        out: list[Location] = []
        for row in resp.json().get("data", []):
            location_id = row.get("locationId")
            if not location_id:  # skip malformed records rather than crash the whole list
                continue
            addr = row.get("address", {})
            parts = [addr.get("addressLine1"), addr.get("city"), addr.get("state"), addr.get("zipCode")]
            out.append(
                Location(
                    location_id=location_id,
                    name=row.get("name", ""),
                    address=", ".join(p for p in parts if p),
                )
            )
        return out

    # --- cart ----------------------------------------------------------------
    def add_to_cart(self, token: str, *, upc: str, quantity: int, modality: str) -> None:
        """PUT a single item to the customer's cart. Raises on any non-2xx. One item per
        call so callers get truthful per-item success/failure (cart is write-only)."""
        resp = self._http.put(
            "/v1/cart/add",
            json={"items": [{"upc": upc, "quantity": quantity, "modality": modality}]},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        self._raise_for_status(resp)

    def search_products(
        self, token: str, term: str, location_id: str, limit: int = 24, start: int = 0
    ) -> list[Product]:
        params = {"filter.term": term, "filter.locationId": location_id, "filter.limit": limit}
        if start > 0:
            params["filter.start"] = start
        resp = self._http.get(
            "/v1/products",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        self._raise_for_status(resp)
        out: list[Product] = []
        for row in resp.json().get("data", []):
            upc = row.get("upc")
            if not upc:  # skip malformed records rather than crash the whole list
                continue
            items = row.get("items") or []
            first = items[0] if items else {}
            price = (first.get("price") or {}).get("regular")
            stock = (first.get("inventory") or {}).get("stockLevel")
            out.append(
                Product(
                    upc=upc,
                    description=row.get("description", ""),
                    size=first.get("size"),
                    price=price,
                    stock_level=stock,
                    brand=row.get("brand"),
                    image_url=_extract_image_url(row.get("images")),
                )
            )
        return out
