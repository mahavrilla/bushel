"""Orchestrates scrape → parse → canonicalize → persist. The only writer of Recipe rows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ingredients.canonicalize import canonicalize_names
from app.ingredients.parser import parse_line
from app.llm.client import LLMClient
from app.models import Recipe, RecipeIngredient
from app.recipes.scraper import scrape_url

_LOW_CONFIDENCE_SOURCE = "library_low_confidence"


def _build_recipe(
    *, title: str, servings: int, source_url: str | None, raw_lines: list[str],
    db: Session, llm: LLMClient,
) -> Recipe:
    parsed = [(raw, parse_line(raw, llm)) for raw in raw_lines]
    canon = canonicalize_names([p.name for _, p in parsed], db, llm)

    recipe = Recipe(title=title, default_servings=servings, source_url=source_url)
    db.add(recipe)
    db.flush()

    # canon is keyed by ingredient name; lines that share a name share one entry.
    for raw, p in parsed:
        result = canon[p.name]
        needs_review = (
            p.source == _LOW_CONFIDENCE_SOURCE
            or p.source == "llm"
            or p.qty is None  # unparseable quantity
            or result.is_new
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                raw_text=raw,
                qty=p.qty,
                unit=p.unit,
                ingredient_id=result.ingredient_id,
                parse_source="manual" if source_url is None and p.source == "library" else p.source,
                needs_review=needs_review,
            )
        )
    db.flush()
    return recipe


def import_from_url(url: str, *, db: Session, llm: LLMClient) -> Recipe:
    scraped = scrape_url(url, llm)
    return _build_recipe(
        title=scraped.title,
        servings=scraped.servings or 1,
        source_url=url,
        raw_lines=scraped.raw_lines,
        db=db,
        llm=llm,
    )


def create_from_manual(
    *, title: str, servings: int, raw_lines: list[str], db: Session, llm: LLMClient
) -> Recipe:
    return _build_recipe(
        title=title, servings=servings, source_url=None, raw_lines=raw_lines, db=db, llm=llm
    )
