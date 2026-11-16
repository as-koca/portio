"""Tests for loading and saving the recipe book. Run: python3 -m unittest"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from recipe import EXAMPLE_RECIPE, Ingredient, Recipe
from storage import find_recipe, load_book, recipe_names, save_book

PANCAKES = Recipe(
    name="Pancakes",
    servings=2,
    ingredients=(
        Ingredient("milk", 250, "ml"),
        Ingredient("jalapeño", 1.5, "pieces"),
        Ingredient("bay leaf", 2, "pieces", plural="bay leaves"),
    ),
)


class StorageTestCase(unittest.TestCase):
    """Gives every test its own empty folder, deleted afterwards."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "book.json"

    def write(self, data: object) -> None:
        self.path.write_text(json.dumps(data), encoding="utf-8")


class RoundTripTest(StorageTestCase):
    def test_save_then_load_gives_equal_recipes(self) -> None:
        save_book(self.path, [EXAMPLE_RECIPE, PANCAKES])
        self.assertEqual(load_book(self.path), (EXAMPLE_RECIPE, PANCAKES))

    def test_plural_written_only_when_set(self) -> None:
        save_book(self.path, [PANCAKES])
        ingredients = json.loads(self.path.read_text("utf-8"))["recipes"][0][
            "ingredients"
        ]
        self.assertNotIn("plural", ingredients[0])
        self.assertEqual(ingredients[2]["plural"], "bay leaves")

    def test_non_ascii_written_readably(self) -> None:
        save_book(self.path, [PANCAKES])
        self.assertIn("jalapeño", self.path.read_text("utf-8"))

    def test_save_replaces_and_leaves_no_temp_files(self) -> None:
        save_book(self.path, [EXAMPLE_RECIPE])
        save_book(self.path, [PANCAKES])
        self.assertEqual(load_book(self.path), (PANCAKES,))
        self.assertEqual(os.listdir(self.dir), ["book.json"])

    def test_failed_save_keeps_old_file(self) -> None:
        save_book(self.path, [EXAMPLE_RECIPE])
        bad = Recipe("Bad", 1, (Ingredient("x", float("nan"), "g"),))
        with self.assertRaises(ValueError):
            save_book(self.path, [bad])
        self.assertEqual(load_book(self.path), (EXAMPLE_RECIPE,))
        self.assertEqual(os.listdir(self.dir), ["book.json"])

    def test_save_rejects_duplicate_names(self) -> None:
        with self.assertRaises(ValueError):
            save_book(self.path, [PANCAKES, PANCAKES])


class LoadErrorsTest(StorageTestCase):
    def assert_load_error(self, data: object, message: str) -> None:
        self.write(data)
        with self.assertRaises(ValueError) as ctx:
            load_book(self.path)
        self.assertIn(message, str(ctx.exception))

    @staticmethod
    def book(**ingredient_overrides: object) -> Any:
        """A valid one-recipe book, with ingredient fields overridden.

        Any: this is raw JSON test data, indexed freely below.
        """
        ingredient: dict[str, object] = {
            "name": "egg", "quantity": 1, "unit": "pieces"
        }
        ingredient.update(ingredient_overrides)
        return {"recipes": [
            {"name": "Test", "servings": 2, "ingredients": [ingredient]}
        ]}

    def test_missing_file_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_book(self.dir / "nope.json")

    def test_invalid_json(self) -> None:
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            load_book(self.path)
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_top_level_must_have_recipes_list(self) -> None:
        self.assert_load_error([], "must be a JSON object")
        self.assert_load_error({}, '"recipes" must be a list')

    def test_missing_field_names_its_location(self) -> None:
        data = self.book()
        del data["recipes"][0]["ingredients"][0]["unit"]
        self.assert_load_error(
            data, 'recipe 1 ("Test"), ingredient 1: "unit" must be'
        )

    def test_wrong_types(self) -> None:
        cases: list[tuple[str, object, str]] = [
            ("quantity", "200", '"quantity" must be a number'),
            ("quantity", True, '"quantity" must be a number'),
            ("name", "", '"name" must be a non-empty string'),
            ("plural", None, '"plural" must be a non-empty string'),
        ]
        for key, value, message in cases:
            with self.subTest(key=key, value=value):
                self.assert_load_error(self.book(**{key: value}), message)

    def test_negative_quantity(self) -> None:
        self.assert_load_error(self.book(quantity=-1), "must not be negative")

    def test_zero_quantity_is_allowed(self) -> None:
        self.write(self.book(quantity=0))
        self.assertEqual(load_book(self.path)[0].ingredients[0].quantity, 0)

    def test_nan_rejected(self) -> None:
        self.path.write_text(
            json.dumps(self.book()).replace(
                '"quantity": 1', '"quantity": NaN'
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError) as ctx:
            load_book(self.path)
        self.assertIn("finite", str(ctx.exception))

    def test_servings_must_be_positive(self) -> None:
        data = self.book()
        data["recipes"][0]["servings"] = 0
        self.assert_load_error(data, '"servings" must be positive')

    def test_duplicate_names_ignoring_case(self) -> None:
        recipe = self.book()["recipes"][0]
        other = dict(recipe, name="TEST")
        self.assert_load_error(
            {"recipes": [recipe, other]}, "duplicate recipe name"
        )


class BrowseTest(unittest.TestCase):
    BOOK = (EXAMPLE_RECIPE, PANCAKES)

    def test_recipe_names(self) -> None:
        self.assertEqual(recipe_names(self.BOOK), ["Shortbread", "Pancakes"])

    def test_find_recipe_ignores_case(self) -> None:
        self.assertIs(find_recipe(self.BOOK, "pANCAKES"), PANCAKES)

    def test_find_unknown_recipe_lists_names(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            find_recipe(self.BOOK, "Brownies")
        self.assertIn("Shortbread, Pancakes", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
