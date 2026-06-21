import httpx
import pytest

from app.kroger.client import KrogerAuthError, KrogerClient, KrogerError


def _client(handler):
    http = httpx.Client(base_url="https://api.kroger.com", transport=httpx.MockTransport(handler))
    return KrogerClient(http=http, client_id="c", client_secret="s", redirect_uri="u")


def test_add_to_cart_sends_put_with_items_array():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["json"] = request.read().decode()
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(204)

    _client(handler).add_to_cart("tok", upc="0001", quantity=2, modality="PICKUP")
    assert seen["method"] == "PUT"
    assert seen["path"] == "/v1/cart/add"
    assert seen["auth"] == "Bearer tok"
    assert '"upc": "0001"' in seen["json"] or '"upc":"0001"' in seen["json"]
    assert "PICKUP" in seen["json"]


def test_add_to_cart_invalid_upc_raises_kroger_error():
    def handler(request):
        return httpx.Response(400, json={"errors": {"reason": "Invalid.UPC"}})

    with pytest.raises(KrogerError):
        _client(handler).add_to_cart("tok", upc="bad", quantity=1, modality="PICKUP")


def test_add_to_cart_401_raises_auth_error():
    def handler(request):
        return httpx.Response(401, json={"error": "unauthorized"})

    with pytest.raises(KrogerAuthError):
        _client(handler).add_to_cart("tok", upc="0001", quantity=1, modality="PICKUP")
