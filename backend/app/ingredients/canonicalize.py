"""Resolve parsed ingredient names to canonical Ingredient rows.

Deterministic for known ingredients (normalized name + alias lookup); the LLM is
consulted once, batched, only for names with no local match.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingredients.normalize import normalize_name
from app.llm.client import LLMClient, LLMUnavailableError
from app.models import Ingredient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanonResult:
    ingredient_id: int
    is_new: bool


def _lookup(normalized: str, ingredients: list[Ingredient]) -> Ingredient | None:
    for ing in ingredients:
        if ing.canonical_name == normalized:
            return ing
        if normalized in (ing.aliases or []):
            return ing
    return None


def _create_new(
    db: Session, canonical_name: str, category: str | None = None, purchase_unit: str | None = None
) -> Ingredient:
    ing = Ingredient(
        canonical_name=canonical_name,
        aliases=[],
        category=category,
        default_purchase_unit=purchase_unit,
    )
    db.add(ing)
    db.flush()
    return ing


def canonicalize_names(
    queries: list[str], db: Session, llm: LLMClient
) -> dict[str, CanonResult]:
    # De-duplicate so each unique name is resolved/created exactly once; callers
    # look up results by name, so duplicate input lines share one result.
    unique_queries = list(dict.fromkeys(queries))
    ingredients = list(db.execute(select(Ingredient)).scalars())
    results: dict[str, CanonResult] = {}
    misses: list[str] = []
    miss_normalized: dict[str, str] = {}

    for q in unique_queries:
        normalized = normalize_name(q)
        hit = _lookup(normalized, ingredients)
        if hit is not None:
            results[q] = CanonResult(ingredient_id=hit.id, is_new=False)
        else:
            misses.append(q)
            miss_normalized[q] = normalized

    if not misses:
        return results

    existing_payload = [{"id": i.id, "canonical_name": i.canonical_name} for i in ingredients]
    try:
        classified = llm.canonicalize_ingredients(misses, existing_payload)
        by_query = {c.query: c for c in classified.results}
    except LLMUnavailableError:
        by_query = {}

    for q in misses:
        decision = by_query.get(q)
        if decision is not None and decision.alias_of is not None:
            existing = db.get(Ingredient, decision.alias_of)
            if existing is not None:
                normalized = miss_normalized[q]
                if normalized not in (existing.aliases or []):
                    existing.aliases = [*(existing.aliases or []), normalized]
                    db.flush()
                results[q] = CanonResult(ingredient_id=existing.id, is_new=False)
                continue
            logger.warning(
                "LLM returned alias_of=%s for %r but no such ingredient exists; creating new",
                decision.alias_of,
                q,
            )
        if decision is not None and decision.new is not None:
            created = _create_new(
                db,
                normalize_name(decision.new.canonical_name),
                decision.new.category,
                decision.new.default_purchase_unit,
            )
        else:
            created = _create_new(db, miss_normalized[q])
        results[q] = CanonResult(ingredient_id=created.id, is_new=True)

    return results
