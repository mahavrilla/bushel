import pytest
from pydantic import ValidationError

from app.recipes.schemas import ImportRequest, ManualRecipeRequest, IngredientUpdate


def test_import_request_requires_url():
    assert ImportRequest(url="https://example.com").url == "https://example.com"
    with pytest.raises(ValidationError):
        ImportRequest()


def test_manual_request_rejects_blank_title():
    with pytest.raises(ValidationError):
        ManualRecipeRequest(title="  ", servings=2, raw_lines=["1 egg"])


def test_manual_request_drops_blank_lines():
    req = ManualRecipeRequest(title="X", servings=2, raw_lines=["1 egg", "  ", "", "2 cups flour"])
    assert req.raw_lines == ["1 egg", "2 cups flour"]


def test_ingredient_update_all_optional():
    upd = IngredientUpdate(qty=3.0)
    assert upd.qty == 3.0
