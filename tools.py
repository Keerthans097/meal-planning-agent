"""Recipe tools, JSON schemas, and name→function registry."""

import json
import re
from pathlib import Path
from typing import Any, Callable

RECIPES_PATH = Path(__file__).parent / "recipes.json"

QUANTITY_PREFIX = re.compile(
    r"^[\d./]+(?:\s*-\s*[\d./]+)?\s*"
    r"(?:g|kg|ml|l|oz|lb|cups?|tbsp|tsp|cloves?|slices?|pieces?|cans?\s+of\s+|can\s+)?\s*",
    re.IGNORECASE,
)
LEADING_NUMBER = re.compile(r"^([\d.]+)\s*(.*)$")

TOOLS: dict[str, Callable[..., dict]] = {}


def _load_recipes() -> list[dict]:
    """Load the local recipe catalog."""
    with RECIPES_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def normalize_ingredient(name: str) -> str:
    """Normalize ingredient names for fuzzy matching."""
    normalized = name.lower().strip()
    if len(normalized) > 3 and normalized.endswith("s") and not normalized.endswith("ss"):
        normalized = normalized[:-1]
    return normalized


def extract_ingredient_name(ingredient_line: str) -> str:
    """Strip leading quantity/units from an ingredient line."""
    without_quantity = QUANTITY_PREFIX.sub("", ingredient_line.strip())
    return normalize_ingredient(without_quantity)


GENERIC_WORDS = {
    "quick",
    "easy",
    "fast",
    "dinner",
    "lunch",
    "breakfast",
    "meal",
    "recipe",
    "food",
    "dish",
    "cook",
    "cooking",
    "make",
    "want",
    "minutes",
    "under",
    "people",
    "serving",
    "servings",
    "tasty",
    "healthy",
    "simple",
    "best",
    "good",
}

DIETARY_WORDS = {
    "vegetarian",
    "vegan",
    "gluten",
    "free",
    "dairy",
}

NAME_WEIGHT = 3
INGREDIENT_WEIGHT = 3
DIETARY_WEIGHT = 1


def _tokenize(text: str) -> set[str]:
    """Split text into normalized word tokens."""
    return {normalize_ingredient(token) for token in re.findall(r"[a-zA-Z]+", text.lower()) if token}


def _token_matches(token: str, candidate: str) -> bool:
    """Return True if tokens are equal or one contains the other."""
    return token == candidate or token in candidate or candidate in token


def _split_query_tokens(query_tokens: set[str]) -> tuple[set[str], set[str]]:
    """Split query tokens into name/ingredient tokens vs dietary tokens."""
    strong: set[str] = set()
    dietary: set[str] = set()
    for token in query_tokens:
        if token in GENERIC_WORDS:
            continue
        if token in DIETARY_WORDS:
            dietary.add(token)
        else:
            strong.add(token)
    return strong, dietary


def _matched_ingredient_lines(recipe: dict, strong_tokens: set[str]) -> list[str]:
    """Return recipe ingredient lines that overlap with the search tokens."""
    matched: list[str] = []
    for line in recipe.get("ingredients", []):
        ingredient_name = extract_ingredient_name(line)
        if any(_token_matches(token, ingredient_name) for token in strong_tokens):
            matched.append(line)
    return matched


def _name_hit_count(recipe: dict, strong_tokens: set[str]) -> int:
    """Count how many search tokens appear in the recipe name."""
    name_tokens = _tokenize(recipe.get("name", ""))
    return sum(
        1
        for token in strong_tokens
        if any(_token_matches(token, name_token) for name_token in name_tokens)
    )


def _dietary_hit_count(recipe: dict, dietary_tokens: set[str]) -> int:
    """Count how many dietary search tokens appear in the recipe tags."""
    tag_tokens = _tokenize(" ".join(recipe.get("dietary_tags", [])))
    return sum(
        1
        for token in dietary_tokens
        if any(_token_matches(token, tag_token) for tag_token in tag_tokens)
    )


def _rank_recipe(recipe: dict, strong_tokens: set[str], dietary_tokens: set[str]) -> dict | None:
    """Score a recipe. Returns None without name or ingredient overlap."""
    name_hits = _name_hit_count(recipe, strong_tokens)
    matched_ingredients = _matched_ingredient_lines(recipe, strong_tokens)
    ingredient_hits = len(matched_ingredients)
    dietary_hits = _dietary_hit_count(recipe, dietary_tokens)

    if name_hits == 0 and ingredient_hits == 0:
        return None

    recipe_ingredient_count = len(recipe.get("ingredients", []))
    overlap_percentage = (
        round((ingredient_hits / recipe_ingredient_count) * 100, 1)
        if recipe_ingredient_count
        else 0.0
    )
    score = (
        NAME_WEIGHT * name_hits
        + INGREDIENT_WEIGHT * ingredient_hits
        + DIETARY_WEIGHT * dietary_hits
    )

    return {
        "name": recipe["name"],
        "ingredients": recipe.get("ingredients", []),
        "servings": recipe.get("servings"),
        "cooking_time_minutes": recipe.get("cooking_time_minutes"),
        "dietary_tags": recipe.get("dietary_tags", []),
        "estimated_cost_eur": recipe.get("estimated_cost_eur"),
        "ingredient_overlap_percentage": overlap_percentage,
        "matched_ingredients": matched_ingredients,
        "_score": score,
    }


def search_recipes(query: str) -> dict:
    """Search the local catalog. Requires name/ingredient overlap for a match."""
    query = query.strip()
    recipes = _load_recipes()

    if not query:
        return {"status": "no_suitable_match", "matches": [], "count": 0}

    strong_tokens, dietary_tokens = _split_query_tokens(_tokenize(query))
    ranked: list[dict] = []
    for recipe in recipes:
        result = _rank_recipe(recipe, strong_tokens, dietary_tokens)
        if result is not None:
            ranked.append(result)

    ranked.sort(key=lambda item: (-item["_score"], item["name"]))
    matches = []
    for item in ranked[:5]:
        item.pop("_score", None)
        matches.append(item)

    if not matches:
        return {"status": "no_suitable_match", "matches": [], "count": 0}

    return {"status": "ok", "matches": matches, "count": len(matches)}


def check_ingredients(recipe: dict, available_ingredients: list[str]) -> dict:
    """Compare recipe ingredients against the user's available items."""
    available = {normalize_ingredient(item) for item in available_ingredients}
    recipe_ingredients = recipe.get("ingredients", [])

    available_matches: list[str] = []
    missing: list[str] = []

    for ingredient_line in recipe_ingredients:
        ingredient_name = extract_ingredient_name(ingredient_line)
        has_match = any(
            item == ingredient_name or item in ingredient_name or ingredient_name in item
            for item in available
        )
        if has_match:
            available_matches.append(ingredient_line)
        else:
            missing.append(ingredient_line)

    total = len(recipe_ingredients)
    match_percentage = round((len(available_matches) / total) * 100, 1) if total else 0.0

    return {
        "available": available_matches,
        "missing": missing,
        "match_percentage": match_percentage,
    }


def scale_recipe(recipe: dict, servings: int) -> dict:
    """Scale leading numeric ingredient quantities to a target serving count."""
    if servings <= 0:
        raise ValueError("servings must be a positive integer")

    base_servings = recipe.get("servings", 1)
    if base_servings <= 0:
        raise ValueError("recipe servings must be a positive integer")

    factor = servings / base_servings
    scaled_ingredients: list[str] = []

    for ingredient_line in recipe.get("ingredients", []):
        match = LEADING_NUMBER.match(ingredient_line.strip())
        if not match:
            scaled_ingredients.append(ingredient_line)
            continue

        amount = float(match.group(1))
        remainder = match.group(2)
        scaled_amount = amount * factor
        if scaled_amount == int(scaled_amount):
            scaled_amount_text = str(int(scaled_amount))
        else:
            scaled_amount_text = f"{scaled_amount:.1f}".rstrip("0").rstrip(".")
        scaled_ingredients.append(f"{scaled_amount_text} {remainder}".strip())

    return {"servings": servings, "scaled_ingredients": scaled_ingredients}


def estimate_cooking_time(recipe: dict) -> dict:
    """Return cooking time from recipe metadata."""
    minutes = recipe.get("cooking_time_minutes", 0)
    return {"minutes": minutes, "within_limit": None}


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_recipes",
        "description": (
            "Search local recipes by dish name and ingredients. "
            "Ranks name/ingredient matches strongly; dietary tags are secondary. "
            "Generic words like quick/dinner/recipe alone do not return recipes. "
            "Returns structured matches or status=no_suitable_match."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms, e.g. 'pasta spinach' or 'tomato garlic pasta'.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_ingredients",
        "description": "Check which recipe ingredients are available and which are missing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe": {
                    "type": "object",
                    "description": "A recipe object returned by search_recipes.",
                },
                "available_ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ingredient names the user already has.",
                },
            },
            "required": ["recipe", "available_ingredients"],
        },
    },
    {
        "name": "scale_recipe",
        "description": "Scale a recipe's ingredient quantities to a target number of servings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe": {
                    "type": "object",
                    "description": "A recipe object to scale.",
                },
                "servings": {
                    "type": "integer",
                    "description": "Desired number of servings.",
                },
            },
            "required": ["recipe", "servings"],
        },
    },
    {
        "name": "estimate_cooking_time",
        "description": "Return the estimated cooking time for a recipe in minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe": {
                    "type": "object",
                    "description": "A recipe object to estimate time for.",
                }
            },
            "required": ["recipe"],
        },
    },
]


def get_tool_schemas() -> list[dict]:
    """Return tool schemas for the LLM client."""
    return TOOL_SCHEMAS


TOOLS.update(
    {
        "search_recipes": search_recipes,
        "check_ingredients": check_ingredients,
        "scale_recipe": scale_recipe,
        "estimate_cooking_time": estimate_cooking_time,
    }
)
