import base64

import httpx
import pytest

from app.kroger.client import KrogerAuthError, KrogerClient


def _client(handler):
    http = httpx.Client(base_url="https://api.kroger.com", transport=httpx.MockTransport(handler))
    return KrogerClient(http=http, client_id="cid", client_secret="secret",
                        redirect_uri="http://localhost:8000/auth/callback")


def test_fetch_client_token_uses_basic_auth_and_client_credentials():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 1800, "token_type": "bearer"})

    token = _client(handler).fetch_client_token()
    assert token.access_token == "tok"
    expected = "Basic " + base64.b64encode(b"cid:secret").decode()
    assert seen["auth"] == expected
    assert "grant_type=client_credentials" in seen["body"]


def test_exchange_code_returns_refresh_token():
    def handler(request):
        assert "grant_type=authorization_code" in request.content.decode()
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 1800})

    token = _client(handler).exchange_code("the-code")
    assert token.refresh_token == "r"


def test_refresh_uses_refresh_grant():
    def handler(request):
        assert "grant_type=refresh_token" in request.content.decode()
        return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 1800})

    token = _client(handler).refresh("r")
    assert token.access_token == "a2"


def test_token_401_raises_auth_error():
    def handler(request):
        return httpx.Response(401, json={"error": "invalid_client"})

    with pytest.raises(KrogerAuthError):
        _client(handler).fetch_client_token()


def test_authorize_url_includes_scopes_and_state():
    url = _client(lambda r: httpx.Response(200, json={})).authorize_url("xyz")
    assert "response_type=code" in url
    assert "state=xyz" in url
    assert "cart.basic" in url
