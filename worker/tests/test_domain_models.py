from domain_models import Recipe, UrlStatus
from datetime import datetime, timezone


def test_url_status_default_last_modified_is_none():
    status = UrlStatus(url="https://example.com/recipe")
    assert status.url == "https://example.com/recipe"
    assert status.last_modified is None


def test_url_status_with_last_modified():
    dt = datetime.now(timezone.utc)
    status = UrlStatus(url="https://example.com/recipe", last_modified=dt)
    assert status.last_modified == dt


def test_recipe_creation():
    recipe = Recipe(
        canonical_url="https://example.com/recipe",
        json_data={"name": "Test Recipe"},
        last_scraped=datetime.now(timezone.utc),
    )
    assert recipe.canonical_url == "https://example.com/recipe"
    assert recipe.json_data == {"name": "Test Recipe"}
    assert recipe.last_scraped is not None
