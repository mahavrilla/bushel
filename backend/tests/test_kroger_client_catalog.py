import httpx
import pytest

from app.kroger.client import KrogerClient, KrogerUnavailableError


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
        assert request.url.params["filter.limit"] == "24"
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


def test_search_products_skips_records_missing_upc():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"description": "No UPC here"},  # malformed record -> skipped, not crashed
            {"upc": "0001", "description": "Flour", "items": []},
        ]})

    prods = _client(handler).search_products("tok", "flour", "L1")
    assert [p.upc for p in prods] == ["0001"]


def test_search_products_5xx_raises_unavailable():
    def handler(request):
        return httpx.Response(500, json={})

    with pytest.raises(KrogerUnavailableError):
        _client(handler).search_products("tok", "flour", "L1")


def test_search_products_parses_brand_and_image():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "Jif Creamy", "brand": "Jif",
             "images": [
                 {"perspective": "front", "featured": True, "sizes": [
                     {"size": "small", "url": "small.jpg"},
                     {"size": "medium", "url": "medium.jpg"},
                 ]},
             ],
             "items": [{"size": "40 oz"}]},
        ]})

    prods = _client(handler).search_products("tok", "peanut butter", "L1")
    assert prods[0].brand == "Jif"
    assert prods[0].image_url == "medium.jpg"


def test_search_products_image_falls_back_when_no_medium():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "X",
             "images": [{"perspective": "back", "sizes": [{"size": "large", "url": "large.jpg"}]}],
             "items": []},
        ]})

    prods = _client(handler).search_products("tok", "x", "L1")
    assert prods[0].image_url == "large.jpg"
    assert prods[0].brand is None


def test_search_products_handles_missing_images():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "X", "items": []},
        ]})

    prods = _client(handler).search_products("tok", "x", "L1")
    assert prods[0].image_url is None


def test_search_products_sends_filter_start_when_paging():
    def handler(request):
        assert request.url.params["filter.start"] == "24"
        assert request.url.params["filter.limit"] == "24"
        return httpx.Response(200, json={"data": []})

    _client(handler).search_products("tok", "x", "L1", limit=24, start=24)


def test_search_products_omits_filter_start_on_first_page():
    def handler(request):
        assert "filter.start" not in request.url.params
        return httpx.Response(200, json={"data": []})

    _client(handler).search_products("tok", "x", "L1", limit=24, start=0)


def test_search_products_featured_image_without_url_yields_none():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"upc": "0001", "description": "X",
             "images": [{"featured": True, "sizes": [{"size": "medium"}]}],
             "items": []},
        ]})

    prods = _client(handler).search_products("tok", "x", "L1")
    assert prods[0].image_url is None
