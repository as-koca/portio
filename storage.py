"""Storage: load and save the recipe book as a JSON file.

File format:
    {"recipes": [{"name": ..., "servings": ..., "ingredients": [
        {"name": ..., "quantity": ..., "unit": ..., "plural": ...}, ...]}]}
"plural" is optional. Unknown keys are ignored.
"""

import json
import math
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

from recipe import Ingredient, Recipe

# --- Loading -------------------------------------------------------------
# json.load() returns untyped data, so every field is checked before it
# becomes a Recipe. The checks also narrow the types for mypy (no casts).


def _get_str(data: dict[str, object], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{where}: "{key}" must be a non-empty string')
    return value


def _get_number(data: dict[str, object], key: str, where: str) -> float:
    value = data.get(key)
    # bool is a subclass of int in Python (isinstance(True, int) is True),
    # so without this "quantity": true would load as 1.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{where}: "{key}" must be a number')
    # Python's json accepts NaN and Infinity, which are not real amounts.
    if not math.isfinite(value):
        raise ValueError(f'{where}: "{key}" must be a finite number')
    return value


def _get_object(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: must be a JSON object")
    return value


def _get_list(data: dict[str, object], key: str, where: str) -> list[object]:
    value = data.get(key)
    if not isinstance(value, list):
        raise ValueError(f'{where}: "{key}" must be a list')
    return value


def _ingredient_from_json(value: object, where: str) -> Ingredient:
    data = _get_object(value, where)
    quantity = _get_number(data, "quantity", where)
    # 0 is allowed ("salt: 0 g, to taste"); scale_by_ingredient handles it.
    if quantity < 0:
        raise ValueError(f'{where}: "quantity" must not be negative')
    plural = _get_str(data, "plural", where) if "plural" in data else None
    return Ingredient(
        name=_get_str(data, "name", where),
        quantity=quantity,
        unit=_get_str(data, "unit", where),
        plural=plural,
    )


def _recipe_from_json(value: object, where: str) -> Recipe:
    data = _get_object(value, where)
    name = _get_str(data, "name", where)
    where = f'{where} ("{name}")'  # name the recipe in later errors
    servings = _get_number(data, "servings", where)
    # Must be > 0: scale_to_servings divides by it.
    if servings <= 0:
        raise ValueError(f'{where}: "servings" must be positive')
    ingredients = tuple(
        _ingredient_from_json(item, f"{where}, ingredient {i}")
        for i, item in enumerate(_get_list(data, "ingredients", where), 1)
    )
    return Recipe(name=name, servings=servings, ingredients=ingredients)


def _check_unique_names(recipes: Iterable[Recipe]) -> None:
    """Raise if two recipes share a name (ignoring case).

    find_recipe() looks recipes up by name, so duplicates would make it
    ambiguous.
    """
    seen: set[str] = set()
    for recipe in recipes:
        key = recipe.name.casefold()
        if key in seen:
            raise ValueError(f"duplicate recipe name: {recipe.name!r}")
        seen.add(key)


def load_book(path: str | Path) -> tuple[Recipe, ...]:
    """Load all recipes from a JSON file.

    Raises FileNotFoundError if the file is missing (the caller decides
    what to tell the user) and ValueError if the content is invalid.
    """
    with open(path, encoding="utf-8") as f:
        try:
            raw: object = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}: not valid JSON ({e})") from e

    data = _get_object(raw, str(path))
    book = tuple(
        _recipe_from_json(item, f"recipe {i}")
        for i, item in enumerate(_get_list(data, "recipes", str(path)), 1)
    )
    _check_unique_names(book)
    return book


# --- Saving --------------------------------------------------------------


def _ingredient_to_json(ing: Ingredient) -> dict[str, object]:
    data: dict[str, object] = {
        "name": ing.name,
        "quantity": ing.quantity,
        "unit": ing.unit,
    }
    if ing.plural is not None:  # only written when set, keeps files short
        data["plural"] = ing.plural
    return data


def _recipe_to_json(recipe: Recipe) -> dict[str, object]:
    return {
        "name": recipe.name,
        "servings": recipe.servings,
        "ingredients": [_ingredient_to_json(i) for i in recipe.ingredients],
    }


def save_book(path: str | Path, recipes: Iterable[Recipe]) -> None:
    """Write all recipes to a JSON file, replacing it safely."""
    path = Path(path)
    recipes = tuple(recipes)  # iterated twice below
    _check_unique_names(recipes)
    # Build the whole text before touching the disk, so a bad value fails
    # here and leaves no files behind. allow_nan=False refuses NaN, which
    # would otherwise be written as invalid JSON.
    text = json.dumps(
        {"recipes": [_recipe_to_json(r) for r in recipes]},
        indent=2,
        ensure_ascii=False,  # write "jalapeño", not "jalapeño"
        allow_nan=False,
    )

    # Write to a temporary file next to the real one, then swap it in.
    # os.replace is atomic (on the same filesystem, hence dir=path.parent):
    # a crash mid-write leaves the old file intact, never a half-written one.
    fd, tmp = tempfile.mkstemp(
        dir=path.parent, prefix=path.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


# --- Browsing ------------------------------------------------------------


def recipe_names(book: Iterable[Recipe]) -> list[str]:
    """Return the names of all recipes in the book, in file order."""
    return [recipe.name for recipe in book]


def find_recipe(book: Iterable[Recipe], name: str) -> Recipe:
    """Return the recipe called name (ignoring case)."""
    book = tuple(book)
    wanted = name.casefold()
    for recipe in book:
        if recipe.name.casefold() == wanted:
            return recipe
    available = ", ".join(recipe_names(book))
    raise ValueError(f"no recipe named {name!r}; available: {available}")
