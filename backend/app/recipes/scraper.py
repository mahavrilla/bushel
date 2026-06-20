"""Scrape a recipe URL into {title, servings, raw_lines}. Library-first, LLM fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from recipe_scrapers import scrape_html

from app.llm.client import LLMClient, LLMUnavailableError

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BushelBot/1.0)"}
_DIGITS = re.compile(r"\d+")


class ScrapeError(RuntimeError):
    """Raised when neither the library nor the LLM could produce a usable recipe."""


@dataclass(frozen=True)
class ScrapedRecipe:
    title: str
    servings: int | None
    raw_lines: list[str]


def _fetch_html(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def _yields_to_int(yields: str | None) -> int | None:
    if not yields:
        return None
    m = _DIGITS.search(yields)
    return int(m.group()) if m else None


def scrape_url(url: str, llm: LLMClient) -> ScrapedRecipe:
    try:
        html = _fetch_html(url)
    except requests.RequestException as exc:
        raise ScrapeError(f"could not fetch URL: {exc}") from exc

    try:
        scraper = scrape_html(html, org_url=url)
        lines = [line.strip() for line in scraper.ingredients() if line.strip()]
        if lines:
            return ScrapedRecipe(
                title=scraper.title() or url,
                servings=_yields_to_int(scraper.yields()),
                raw_lines=lines,
            )
    except Exception:  # noqa: BLE001 — library raises various site-specific errors
        pass

    try:
        llm_result = llm.scrape_recipe(html, url)
    except LLMUnavailableError as exc:
        raise ScrapeError("site unsupported and LLM unavailable") from exc

    lines = [line.strip() for line in llm_result.raw_lines if line.strip()]
    if not lines:
        raise ScrapeError("no ingredients found")
    return ScrapedRecipe(title=llm_result.title or url, servings=llm_result.servings, raw_lines=lines)
