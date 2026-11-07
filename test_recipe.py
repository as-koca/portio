"""Tests for recipe scaling. Run with: python3 -m unittest"""

import unittest
from dataclasses import replace

from recipe import (
    EXAMPLE_RECIPE,
    Ingredient,
    Recipe,
    scale_by_ingredient,
    scale_recipe,
    scale_to_servings,
)


def quantities(recipe: Recipe) -> list[float]:
    return [ing.quantity for ing in recipe.ingredients]


class ScaleToServingsTest(unittest.TestCase):
    def test_scale_up_4_to_6(self) -> None:
        scaled = scale_to_servings(EXAMPLE_RECIPE, 6)
        self.assertEqual(scaled.servings, 6)
        for got, want in zip(quantities(scaled), [300, 450, 150, 1.5]):
            self.assertAlmostEqual(got, want)

    def test_scale_down_4_to_2(self) -> None:
        scaled = scale_to_servings(EXAMPLE_RECIPE, 2)
        self.assertEqual(scaled.servings, 2)
        for got, want in zip(quantities(scaled), [100, 150, 50, 0.5]):
            self.assertAlmostEqual(got, want)

    def test_same_servings_returns_equal_recipe(self) -> None:
        self.assertEqual(scale_to_servings(EXAMPLE_RECIPE, 4), EXAMPLE_RECIPE)

    def test_original_is_unchanged(self) -> None:
        before = quantities(EXAMPLE_RECIPE)
        scale_to_servings(EXAMPLE_RECIPE, 10)
        self.assertEqual(quantities(EXAMPLE_RECIPE), before)
        self.assertEqual(EXAMPLE_RECIPE.servings, 4)

    def test_names_and_units_preserved(self) -> None:
        scaled = scale_to_servings(EXAMPLE_RECIPE, 6)
        self.assertEqual(scaled.name, EXAMPLE_RECIPE.name)
        self.assertEqual(
            [(i.name, i.unit) for i in scaled.ingredients],
            [(i.name, i.unit) for i in EXAMPLE_RECIPE.ingredients],
        )

    def test_servings_set_exactly(self) -> None:
        # 0.7 * (3 / 0.7) == 2.9999999999999996; result must still be 3.
        recipe = replace(EXAMPLE_RECIPE, servings=0.7)
        self.assertEqual(scale_to_servings(recipe, 3).servings, 3)

    def test_zero_or_negative_servings_raise(self) -> None:
        for bad in (0, -2):
            with self.subTest(servings=bad):
                with self.assertRaises(ValueError):
                    scale_to_servings(EXAMPLE_RECIPE, bad)


class ScaleRecipeTest(unittest.TestCase):
    def test_scales_servings_too(self) -> None:
        self.assertAlmostEqual(
            scale_recipe(EXAMPLE_RECIPE, 0.85).servings, 3.4)

    def test_non_positive_factor_raises(self) -> None:
        for bad in (0, -1.5):
            with self.subTest(factor=bad):
                with self.assertRaises(ValueError):
                    scale_recipe(EXAMPLE_RECIPE, bad)


class ScaleByIngredientTest(unittest.TestCase):
    def test_butter_200_to_150(self) -> None:
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 150)
        self.assertAlmostEqual(scaled.servings, 3)
        for got, want in zip(quantities(scaled), [150, 225, 75, 0.75]):
            self.assertAlmostEqual(got, want)

    def test_fractional_servings(self) -> None:
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 170)
        self.assertAlmostEqual(scaled.servings, 3.4)

    def test_scale_up_by_egg(self) -> None:
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "egg", 2)
        self.assertAlmostEqual(scaled.servings, 8)
        for got, want in zip(quantities(scaled), [400, 600, 200, 2]):
            self.assertAlmostEqual(got, want)

    def test_chosen_ingredient_is_exact(self) -> None:
        # 200 * (7 / 200) == 7.000000000000001 in floating point; the
        # ingredient the user set must still be exactly 7.
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 7)
        self.assertEqual(scaled.ingredients[0].quantity, 7)

    def test_name_is_case_insensitive(self) -> None:
        for name in ("Butter", "BUTTER", "bUtTeR"):
            with self.subTest(name=name):
                scaled = scale_by_ingredient(EXAMPLE_RECIPE, name, 150)
                self.assertEqual(scaled.ingredients[0].quantity, 150)

    def test_original_is_unchanged(self) -> None:
        before = quantities(EXAMPLE_RECIPE)
        scale_by_ingredient(EXAMPLE_RECIPE, "butter", 150)
        self.assertEqual(quantities(EXAMPLE_RECIPE), before)
        self.assertEqual(EXAMPLE_RECIPE.servings, 4)

    def test_unknown_ingredient_raises(self) -> None:
        with self.assertRaises(ValueError):
            scale_by_ingredient(EXAMPLE_RECIPE, "chocolate", 50)

    def test_old_quantity_zero_raises(self) -> None:
        recipe = Recipe(
            name="Salted",
            servings=2,
            ingredients=(
                Ingredient("salt", 0, "g"),
                Ingredient("flour", 100, "g"),
            ),
        )
        with self.assertRaises(ValueError):
            scale_by_ingredient(recipe, "salt", 5)

    def test_new_quantity_zero_or_negative_raises(self) -> None:
        for bad in (0, -50):
            with self.subTest(new_quantity=bad):
                with self.assertRaises(ValueError):
                    scale_by_ingredient(EXAMPLE_RECIPE, "butter", bad)


if __name__ == "__main__":
    unittest.main()
