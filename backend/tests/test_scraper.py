from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.recipes.scraper import ScrapedRecipe, ScrapeError, scrape_url
from app.llm.client import LLMUnavailableError, ScrapedRecipeLLM


def _scraper(title, yields, ingredients):
    s = SimpleNamespace()
    s.title = lambda: title
    s.yields = lambda: yields
    s.ingredients = lambda: ingredients
    return s


@patch("app.recipes.scraper._fetch_html", return_value="<html>ok</html>")
@patch("app.recipes.scraper.scrape_html")
def test_library_scrape_success(mock_scrape, _fetch):
    mock_scrape.return_value = _scraper("Pancakes", "4 servings", ["2 cups flour", "1 egg"])
    llm = MagicMock()
    result = scrape_url("https://example.com/pancakes", llm)
    assert result == ScrapedRecipe(title="Pancakes", servings=4, raw_lines=["2 cups flour", "1 egg"])
    llm.scrape_recipe.assert_not_called()


@patch("app.recipes.scraper._fetch_html", return_value="<html>ok</html>")
@patch("app.recipes.scraper.scrape_html", side_effect=Exception("unsupported site"))
def test_unsupported_site_falls_back_to_llm(mock_scrape, _fetch):
    llm = MagicMock()
    llm.scrape_recipe.return_value = ScrapedRecipeLLM(title="Bread", servings=2, raw_lines=["3 cups flour"])
    result = scrape_url("https://blog.example/bread", llm)
    assert result == ScrapedRecipe(title="Bread", servings=2, raw_lines=["3 cups flour"])
    llm.scrape_recipe.assert_called_once()


@patch("app.recipes.scraper._fetch_html", return_value="<html>ok</html>")
@patch("app.recipes.scraper.scrape_html", side_effect=Exception("unsupported"))
def test_unsupported_and_llm_unavailable_raises(mock_scrape, _fetch):
    llm = MagicMock()
    llm.scrape_recipe.side_effect = LLMUnavailableError("no key")
    try:
        scrape_url("https://blog.example/bread", llm)
        assert False, "expected ScrapeError"
    except ScrapeError:
        pass
