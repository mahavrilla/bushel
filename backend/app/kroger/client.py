"""The only module that performs network I/O to Kroger. No DB access here.

Tests inject an httpx.Client backed by httpx.MockTransport, so request building is
exercised without real network calls.
"""

from __future__ import annotations

import base64
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.kroger.schemas import TokenResp

PROD_BASE = "https://api.kroger.com"
_SCOPES = "product.compact cart.basic:write profile.compact"


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
