import pytest

from app.ingredients.normalize import normalize_name


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("All-Purpose Flour", "all purpose flour"),
        ("  AP   Flour ", "ap flour"),
        ("Eggs", "egg"),
        ("Tomatoes", "tomato"),
        ("Cherry Tomatoes", "cherry tomato"),
        ("olive oil,", "olive oil"),
        ("Boneless Chicken Breasts", "boneless chicken breast"),
        ("Asparagus", "asparagus"),
        ("Citrus", "citrus"),
        ("Couscous", "couscous"),
        ("Cook's Salt", "cook salt"),
        ("Berries", "berry"),
        ("Pies", "pie"),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected
