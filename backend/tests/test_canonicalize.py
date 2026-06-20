from unittest.mock import MagicMock

from app.ingredients.canonicalize import CanonResult, canonicalize_names
from app.llm.client import (
    CanonicalizeOne,
    CanonicalizeResult,
    LLMUnavailableError,
    NewIngredientLLM,
)
from app.models import Ingredient


def test_exact_normalized_hit_reuses_existing(db_session):
    existing = Ingredient(canonical_name="all purpose flour", aliases=[])
    db_session.add(existing)
    db_session.flush()
    llm = MagicMock()

    results = canonicalize_names(["All-Purpose Flour"], db_session, llm)

    assert results["All-Purpose Flour"] == CanonResult(ingredient_id=existing.id, is_new=False)
    llm.canonicalize_ingredients.assert_not_called()


def test_alias_hit_reuses_existing(db_session):
    existing = Ingredient(canonical_name="all purpose flour", aliases=["ap flour"])
    db_session.add(existing)
    db_session.flush()
    llm = MagicMock()

    results = canonicalize_names(["AP Flour"], db_session, llm)

    assert results["AP Flour"].ingredient_id == existing.id
    assert results["AP Flour"].is_new is False
    llm.canonicalize_ingredients.assert_not_called()


def test_miss_creates_new_with_metadata(db_session):
    llm = MagicMock()
    llm.canonicalize_ingredients.return_value = CanonicalizeResult(
        results=[
            CanonicalizeOne(
                query="saffron",
                new=NewIngredientLLM(
                    canonical_name="saffron", category="spice", default_purchase_unit="jar"
                ),
            )
        ]
    )

    results = canonicalize_names(["saffron"], db_session, llm)

    new_id = results["saffron"].ingredient_id
    assert results["saffron"].is_new is True
    created = db_session.get(Ingredient, new_id)
    assert created.canonical_name == "saffron"
    assert created.category == "spice"
    assert created.default_purchase_unit == "jar"


def test_miss_alias_of_existing_adds_alias(db_session):
    existing = Ingredient(canonical_name="all purpose flour", aliases=[])
    db_session.add(existing)
    db_session.flush()
    llm = MagicMock()
    llm.canonicalize_ingredients.return_value = CanonicalizeResult(
        results=[CanonicalizeOne(query="plain flour", alias_of=existing.id)]
    )

    results = canonicalize_names(["plain flour"], db_session, llm)

    assert results["plain flour"].ingredient_id == existing.id
    assert results["plain flour"].is_new is False
    db_session.refresh(existing)
    assert "plain flour" in existing.aliases


def test_llm_unavailable_creates_new_flagged(db_session):
    llm = MagicMock()
    llm.canonicalize_ingredients.side_effect = LLMUnavailableError("no key")

    results = canonicalize_names(["dragonfruit"], db_session, llm)

    assert results["dragonfruit"].is_new is True
    created = db_session.get(Ingredient, results["dragonfruit"].ingredient_id)
    assert created.canonical_name == "dragonfruit"
