from app.matching.purchase import compute_purchase_qty, parse_package_size


def test_parse_package_size_number_and_unit():
    assert parse_package_size("5 lb") == (5.0, "lb")
    assert parse_package_size("16.9 fl oz") == (16.9, "fl oz")
    assert parse_package_size("6 ct") == (6.0, "ct")


def test_parse_package_size_no_number_returns_none():
    assert parse_package_size("each") is None
    assert parse_package_size(None) is None
    assert parse_package_size("") is None


def test_compute_purchase_qty_compatible_ceils():
    assert compute_purchase_qty(3.0, "lb", "1 lb") == (3, False)
    assert compute_purchase_qty(2.5, "lb", "1 lb") == (3, False)
    assert compute_purchase_qty(32.0, "oz", "1 lb") == (2, False)


def test_compute_purchase_qty_total_none_is_estimated_one():
    assert compute_purchase_qty(None, None, "5 lb") == (1, True)


def test_compute_purchase_qty_incompatible_units_estimated_one():
    assert compute_purchase_qty(3.0, "cup", "5 lb") == (1, True)


def test_compute_purchase_qty_unparseable_package_estimated_one():
    assert compute_purchase_qty(3.0, "lb", "each") == (1, True)
    assert compute_purchase_qty(3.0, "lb", None) == (1, True)


def test_compute_purchase_qty_floor_is_at_least_one():
    assert compute_purchase_qty(0.1, "lb", "5 lb") == (1, False)
