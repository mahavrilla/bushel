import httpx

from app.kroger.client import KrogerClient


def _client(handler):
    http = httpx.Client(base_url="https://api.kroger.com", transport=httpx.MockTransport(handler))
    return KrogerClient(http=http, client_id="c", client_secret="s", redirect_uri="u")


def test_search_locations_parses_data():
    def handler(request):
        assert request.url.path == "/v1/locations"
        assert request.url.params["filter.zipCode.near"] == "45202"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"data": [
            {"locationId": "L1", "name": "Kroger Downtown",
             "address": {"addressLine1": "1 Main St", "city": "Cincinnati", "state": "OH", "zipCode": "45202"}},
        ]})

    locs = _client(handler).search_locations("tok", "45202")
    assert locs[0].location_id == "L1"
    assert "1 Main St" in locs[0].address
    assert "Cincinnati" in locs[0].address


def test_search_products_parses_first_item_fields():
    def handler(request):
        assert request.url.path == "/v1/products"
        assert request.url.params["filter.term"] == "flour"
        assert request.url.params["filter.locationId"] == "L1"
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "AP Flour",
             "items": [{"size": "5 lb", "price": {"regular": 3.49}, "inventory": {"stockLevel": "HIGH"}}]},
            {"upc": "0002", "description": "Bread Flour", "items": []},
        ]})

    prods = _client(handler).search_products("tok", "flour", "L1")
    assert prods[0].upc == "0001"
    assert prods[0].size == "5 lb"
    assert prods[0].price == 3.49
    assert prods[0].stock_level == "HIGH"
    assert prods[1].upc == "0002"
    assert prods[1].size is None
    assert prods[1].price is None
