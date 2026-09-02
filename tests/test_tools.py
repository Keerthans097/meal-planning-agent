import pytest

from tools import (
    check_ingredients,
    estimate_cooking_time,
    scale_recipe,
    search_recipes,
)


def test_search_recipes_finds_pasta_spinach_match():
    result = search_recipes("vegetarian pasta spinach")

    assert result["status"] == "ok"
    assert result["count"] >= 1
    names = [recipe["name"] for recipe in result["matches"]]
    assert "Quick Spinach Pasta" in names

    top = result["matches"][0]
    assert "ingredient_overlap_percentage" in top
    assert "matched_ingredients" in top
    assert "cooking_time_minutes" in top
    assert "dietary_tags" in top
    assert any(
        "spinach" in item.lower() or "pasta" in item.lower()
        for item in top["matched_ingredients"]
    )


def test_search_recipes_empty_query_returns_no_matches():
    result = search_recipes("   ")

    assert result == {"status": "no_suitable_match", "matches": [], "count": 0}


def test_search_recipes_unknown_query_returns_no_matches():
    result = search_recipes("xyznonexistent123")

    assert result == {"status": "no_suitable_match", "matches": [], "count": 0}


def test_search_recipes_rejects_generic_only_query():
    result = search_recipes("chocolate dessert quick")

    assert result["status"] == "no_suitable_match"
    assert result["matches"] == []


def test_search_recipes_rejects_dietary_only_query():
    result = search_recipes("vegetarian dinner")

    assert result["status"] == "no_suitable_match"
    assert result["matches"] == []


def test_check_ingredients_reports_available_and_missing():
    recipe = search_recipes("quick spinach pasta")["matches"][0]
    available = ["pasta", "tomatoes", "garlic", "spinach", "olive oil"]

    result = check_ingredients(recipe, available)

    assert len(result["available"]) == 5
    assert "salt" in " ".join(result["missing"]).lower()
    assert result["match_percentage"] == pytest.approx(83.3, abs=0.1)


def test_scale_recipe_doubles_numeric_quantities():
    recipe = {
        "name": "Quick Spinach Pasta",
        "ingredients": ["200 g pasta", "2 tomatoes", "salt"],
        "servings": 2,
        "cooking_time_minutes": 18,
    }

    result = scale_recipe(recipe, servings=4)

    assert result["servings"] == 4
    assert result["scaled_ingredients"][0] == "400 g pasta"
    assert result["scaled_ingredients"][1] == "4 tomatoes"
    assert result["scaled_ingredients"][2] == "salt"


def test_estimate_cooking_time_returns_recipe_minutes():
    recipe = {
        "name": "Quick Spinach Pasta",
        "cooking_time_minutes": 18,
    }

    result = estimate_cooking_time(recipe)

    assert result == {"minutes": 18, "within_limit": None}
