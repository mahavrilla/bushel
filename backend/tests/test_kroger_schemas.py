from app.kroger.schemas import Location, Product, TokenResp


def test_token_resp_defaults():
    t = TokenResp(access_token="a", expires_in=1800)
    assert t.refresh_token is None
    assert t.scope == ""


def test_product_and_location_construct():
    p = Product(upc="0001", description="Flour", size="5 lb", price=3.49, stock_level="HIGH")
    assert p.upc == "0001"
    loc = Location(location_id="L1", name="Store", address="1 Main St")
    assert loc.location_id == "L1"
