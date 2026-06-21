from app.consolidate.units import consolidate, convert_qty


def _q(items):
    return [(r["qty"], r["unit"]) for r in consolidate(items)]


def test_same_unit_sums():
    assert _q([(2.0, "cup"), (1.0, "cup")]) == [(3.0, "cup")]


def test_compatible_units_sum_into_first_seen():
    # 2 cups + 240 ml; 240 ml ≈ 1.014 cups → ≈ 3.014 cups
    result = consolidate([(2.0, "cup"), (240.0, "milliliter")])
    assert len(result) == 1
    assert result[0]["unit"] == "cup"
    assert abs(result[0]["qty"] - 3.014) < 0.01


def test_mass_units_compatible():
    # 100 g + 1 oz ≈ 128.35 g
    result = consolidate([(100.0, "gram"), (1.0, "ounce")])
    assert len(result) == 1
    assert result[0]["unit"] == "gram"
    assert abs(result[0]["qty"] - 128.35) < 0.5


def test_incompatible_units_kept_separate():
    result = _q([(2.0, "clove"), (1.0, "tablespoon")])
    assert (2.0, "clove") in result
    assert (1.0, "tablespoon") in result
    assert len(result) == 2


def test_count_items_no_unit():
    assert _q([(2.0, None), (1.0, None)]) == [(3.0, None)]


def test_aliases_normalized_before_pint():
    assert _q([(1.0, "tbsp"), (1.0, "T")]) == [(2.0, "tablespoon")]
    assert _q([(1.0, "c")]) == [(1.0, "cup")]
    assert _q([(2.0, "t")]) == [(2.0, "teaspoon")]


def test_none_qty_carried_through():
    result = consolidate([(None, "pinch")])
    assert result == [{"qty": None, "unit": "pinch"}]


def test_rounding():
    result = consolidate([(1.0, "cup"), (1.0, "cup"), (0.0001, "cup")])
    assert result[0]["qty"] == 2.0


def test_empty_input():
    assert consolidate([]) == []


def test_plural_unparseable_unit_consolidates():
    # "cloves" and "clove" are the same unit and must sum
    result = consolidate([(2.0, "cloves"), (1.0, "clove")])
    assert result == [{"qty": 3.0, "unit": "clove"}]


def test_plural_parseable_unit_consolidates():
    result = consolidate([(1.0, "tablespoons"), (1.0, "tablespoon")])
    assert len(result) == 1
    assert result[0]["qty"] == 2.0


def test_duplicate_none_qty_single_entry():
    result = consolidate([(None, "pinch"), (None, "pinch")])
    assert result == [{"qty": None, "unit": "pinch"}]


def test_convert_qty_compatible_units():
    assert convert_qty(2, "lb", "oz") == 32.0


def test_convert_qty_same_unit_passthrough():
    assert convert_qty(5, "bag", "bag") == 5


def test_convert_qty_incompatible_returns_none():
    assert convert_qty(2, "cup", "lb") is None


def test_convert_qty_unparseable_unit_returns_none():
    assert convert_qty(2, "clove", "lb") is None


def test_convert_qty_none_unit_returns_none():
    assert convert_qty(2, None, "lb") is None
