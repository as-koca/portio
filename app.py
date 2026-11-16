"""Web layer: a read-only JSON API over the recipe book.

This is the only module that uses Flask; recipe, display and storage stay
standard library only. Run locally with:
    uv run flask --app app run --debug
(Flask finds create_app() by name and calls it with its defaults.)
"""

import math
from pathlib import Path

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from display import (
    format_amount,
    format_ingredient,
    format_label,
    format_servings,
)
from recipe import Recipe, scale_by_ingredient, scale_to_servings
from storage import find_recipe, load_book, recipe_names

DEFAULT_BOOK = Path(__file__).parent / "recipes.json"


def _recipe_to_api(recipe: Recipe) -> dict[str, object]:
    """Recipe as JSON for the page.

    Each ingredient comes with its raw quantity plus display text from
    display.py: "amount" (rounded, for the input box), "label" (the rest of
    the line) and "display" (the whole line). Rounding and plural rules
    live in Python only; the page never re-implements them.
    """
    return {
        "name": recipe.name,
        "servings": recipe.servings,
        "servings_display": format_servings(recipe.servings),
        "ingredients": [
            {
                "name": ing.name,
                "quantity": ing.quantity,
                "unit": ing.unit,
                "amount": format_amount(ing.quantity, ing.unit),
                "label": format_label(ing),
                "display": format_ingredient(ing),
            }
            for ing in recipe.ingredients
        ],
    }


def _error(message: str, status: int) -> ResponseReturnValue:
    return jsonify({"error": message}), status


def _number_arg(name: str) -> float:
    """Read a query parameter as a number, or raise ValueError."""
    raw = request.args[name]
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f'"{name}" must be a number, got {raw!r}') from None
    # float() accepts "nan" and "inf"; neither is a real amount.
    if not math.isfinite(value):
        raise ValueError(f'"{name}" must be a finite number, got {raw!r}')
    return value


def _scale_from_args(recipe: Recipe) -> Recipe:
    """Apply ?servings=N or ?ingredient=NAME&quantity=N, if given."""
    args = request.args
    if "servings" in args and "ingredient" in args:
        raise ValueError('give either "servings" or "ingredient", not both')
    if "servings" in args:
        return scale_to_servings(recipe, _number_arg("servings"))
    if "ingredient" in args:
        if "quantity" not in args:
            raise ValueError('"ingredient" needs a "quantity"')
        return scale_by_ingredient(
            recipe, args["ingredient"], _number_arg("quantity")
        )
    if "quantity" in args:
        raise ValueError('"quantity" needs an "ingredient"')
    return recipe


def create_app(book_path: str | Path = DEFAULT_BOOK) -> Flask:
    """Build the app around one recipe book file.

    A factory (instead of a global app) lets tests pass a temporary book.
    The book is loaded once and never written: visitors only read and
    scale, so nothing one visitor does can affect another.
    """
    app = Flask(__name__)
    book = load_book(book_path)

    @app.get("/")
    def index() -> ResponseReturnValue:
        # The page is static; it gets all its data from the API below.
        return app.send_static_file("index.html")

    # GET for everything: nothing changes on the server, and a scaled
    # recipe gets a URL that can be bookmarked or shared.
    @app.get("/api/recipes")
    def list_recipes() -> ResponseReturnValue:
        return jsonify({"recipes": recipe_names(book)})

    @app.get("/api/recipes/<name>")
    def get_recipe(name: str) -> ResponseReturnValue:
        try:
            recipe = find_recipe(book, name)
        except ValueError as e:
            return _error(str(e), 404)
        try:
            scaled = _scale_from_args(recipe)
        except ValueError as e:
            # Bad input: the messages are the ones recipe.py already writes.
            return _error(str(e), 400)
        return jsonify(_recipe_to_api(scaled))

    return app
