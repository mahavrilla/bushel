import pytest
from unittest.mock import MagicMock, patch

from app.ingredients.parser import ParsedLine
from app.recipes.scraper import ScrapedRecipe
from app.recipes.service import add_ingredient, create_from_manual, import_from_url, RecipeNotFoundError
from app.models import Recipe, RecipeIngredient, Ingredient


def _stub_parse(raw_text, llm):
    table = {
        "2 cups all-purpose flour": ParsedLine(2.0, "cup", "all-purpose flour", "library"),
        "1 egg": ParsedLine(1.0, None, "egg", "library"),
        "a pinch of saffron": ParsedLine(None, None, "saffron", "library_low_confidence"),
    }
    return table[raw_text]


@patch("app.recipes.service.parse_line", side_effect=_stub_parse)
def test_manual_create_persists_recipe_and_flags(mock_parse, db_session):
    llm = MagicMock()
    flour = Ingredient(canonical_name="all purpose flour", aliases=[])
    egg = Ingredient(canonical_name="egg", aliases=[])
    saffron = Ingredient(canonical_name="saffron", aliases=[])
    db_session.add_all([flour, egg, saffron])
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {
            "all-purpose flour": CanonResult(flour.id, False),
            "egg": CanonResult(egg.id, False),
            "saffron": CanonResult(saffron.id, True),
        }
        recipe = create_from_manual(
            title="Test",
            servings=3,
            raw_lines=["2 cups all-purpose flour", "1 egg", "a pinch of saffron"],
            db=db_session,
            llm=llm,
        )

    saved = db_session.get(Recipe, recipe.id)
    assert saved.title == "Test"
    assert saved.default_servings == 3
    items = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
    assert len(items) == 3
    by_text = {i.raw_text: i for i in items}
    assert by_text["a pinch of saffron"].needs_review is True
    assert by_text["1 egg"].needs_review is False


@patch("app.recipes.service.scrape_url")
@patch("app.recipes.service.parse_line", side_effect=_stub_parse)
def test_import_from_url_uses_scraper(mock_parse, mock_scrape, db_session):
    mock_scrape.return_value = ScrapedRecipe(title="Pancakes", servings=4, raw_lines=["1 egg"])
    egg = Ingredient(canonical_name="egg", aliases=[])
    db_session.add(egg)
    db_session.flush()
    llm = MagicMock()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"egg": CanonResult(egg.id, False)}
        recipe = import_from_url("https://example.com/pancakes", db=db_session, llm=llm)

    saved = db_session.get(Recipe, recipe.id)
    assert saved.title == "Pancakes"
    assert saved.source_url == "https://example.com/pancakes"


@patch("app.recipes.service.parse_line")
def test_add_ingredient_appends_parsed_row(mock_parse, db_session):
    mock_parse.return_value = ParsedLine(2.0, "cup", "flour", "library")
    flour = Ingredient(canonical_name="flour", aliases=[])
    db_session.add(flour)
    recipe = Recipe(title="T", default_servings=1)
    db_session.add(recipe)
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"flour": CanonResult(flour.id, False)}
        add_ingredient(db_session, recipe.id, "2 cups flour", llm=MagicMock())

    rows = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
    assert len(rows) == 1
    assert rows[0].qty == 2.0 and rows[0].unit == "cup"
    assert rows[0].ingredient_id == flour.id
    assert rows[0].parse_source == "manual"  # library entry typed by hand
    assert rows[0].needs_review is False


@patch("app.recipes.service.parse_line")
def test_add_ingredient_flags_low_confidence(mock_parse, db_session):
    mock_parse.return_value = ParsedLine(None, None, "saffron", "library_low_confidence")
    saffron = Ingredient(canonical_name="saffron", aliases=[])
    db_session.add(saffron)
    recipe = Recipe(title="T", default_servings=1)
    db_session.add(recipe)
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"saffron": CanonResult(saffron.id, False)}
        add_ingredient(db_session, recipe.id, "a pinch of saffron", llm=MagicMock())

    row = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).one()
    assert row.needs_review is True
    assert row.parse_source == "library_low_confidence"


def test_add_ingredient_missing_recipe_raises(db_session):
    with pytest.raises(RecipeNotFoundError):
        add_ingredient(db_session, 99999, "1 egg", llm=MagicMock())


@patch("app.recipes.service.parse_line")
def test_add_ingredient_normalizes_unit(mock_parse, db_session):
    mock_parse.return_value = ParsedLine(2.0, "tbsp", "olive oil", "library")
    oil = Ingredient(canonical_name="olive oil", aliases=[])
    db_session.add(oil)
    recipe = Recipe(title="T", default_servings=1)
    db_session.add(recipe)
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"olive oil": CanonResult(oil.id, False)}
        add_ingredient(db_session, recipe.id, "2 tbsp olive oil", llm=MagicMock())

    row = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).one()
    assert row.unit == "tablespoon"


@patch("app.recipes.service.parse_line")
def test_build_recipe_normalizes_unit(mock_parse, db_session):
    mock_parse.return_value = ParsedLine(2.0, "tbsp", "olive oil", "library")
    oil = Ingredient(canonical_name="olive oil", aliases=[])
    db_session.add(oil)
    db_session.flush()

    from app.ingredients.canonicalize import CanonResult

    with patch("app.recipes.service.canonicalize_names") as mock_canon:
        mock_canon.return_value = {"olive oil": CanonResult(oil.id, False)}
        recipe = create_from_manual(
            title="T", servings=1, raw_lines=["2 tbsp olive oil"], db=db_session, llm=MagicMock()
        )

    row = db_session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).one()
    assert row.unit == "tablespoon"
