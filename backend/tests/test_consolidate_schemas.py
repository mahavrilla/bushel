import pytest
from pydantic import ValidationError

from app.consolidate.schemas import AddRecipeRequest, SetServingsRequest


def test_add_recipe_request_servings_optional():
    assert AddRecipeRequest(recipe_id=5).servings is None
    assert AddRecipeRequest(recipe_id=5, servings=8).servings == 8


def test_set_servings_requires_servings():
    assert SetServingsRequest(servings=4).servings == 4
    with pytest.raises(ValidationError):
        SetServingsRequest()
