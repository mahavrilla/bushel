from app.matching import pricing


def test_to_cents_rounds_and_passes_none():
    assert pricing.to_cents(5.49) == 549
    assert pricing.to_cents(4.295) == 430
    assert pricing.to_cents(None) is None


def test_effective_prefers_promo_when_lower():
    assert pricing.effective_cents(549, 429) == 429


def test_effective_ignores_promo_when_not_lower():
    assert pricing.effective_cents(549, 549) == 549
    assert pricing.effective_cents(549, 600) == 549


def test_effective_uses_regular_when_no_promo():
    assert pricing.effective_cents(549, None) == 549


def test_effective_none_when_no_regular_and_no_promo():
    assert pricing.effective_cents(None, None) is None
    assert pricing.effective_cents(None, 429) == 429


def test_on_sale_true_only_when_promo_below_regular():
    assert pricing.is_on_sale(549, 429) is True
    assert pricing.is_on_sale(549, 549) is False
    assert pricing.is_on_sale(549, None) is False
    assert pricing.is_on_sale(None, 429) is False


def test_unit_price_divides_by_parsed_size():
    dollars, unit = pricing.unit_price(549, "32 fl oz")
    assert round(dollars, 4) == 0.1716
    assert unit == "fl oz"


def test_unit_price_none_when_size_unparseable_or_no_price():
    assert pricing.unit_price(549, "family size") is None
    assert pricing.unit_price(None, "32 fl oz") is None
    assert pricing.unit_price(549, None) is None
