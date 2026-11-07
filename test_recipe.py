"""Tests for recipe scaling. Run with: python3 -m unittest"""

import unittest
from dataclasses import replace

from recipe import EXAMPLE_RECIPE, scale_recipe, scale_to_servings


def quantities(recipe):
    return [ing.quantity for ing in recipe.ingredients]


class ScaleToServingsTest(unittest.TestCase):
    def test_scale_up_4_to_6(self):
        scaled = scale_to_servings(EXAMPLE_RECIPE, 6)
        self.assertEqual(scaled.servings, 6)
        for got, want in zip(quantities(scaled), [300, 450, 150, 1.5]):
            self.assertAlmostEqual(got, want)

    def test_scale_down_4_to_2(self):
        scaled = scale_to_servings(EXAMPLE_RECIPE, 2)
        self.assertEqual(scaled.servings, 2)
        for got, want in zip(quantities(scaled), [100, 150, 50, 0.5]):
            self.assertAlmostEqual(got, want)

    def test_same_servings_returns_equal_recipe(self):
        self.assertEqual(scale_to_servings(EXAMPLE_RECIPE, 4), EXAMPLE_RECIPE)

    def test_original_is_unchanged(self):
        before = quantities(EXAMPLE_RECIPE)
        scale_to_servings(EXAMPLE_RECIPE, 10)
        self.assertEqual(quantities(EXAMPLE_RECIPE), before)
        self.assertEqual(EXAMPLE_RECIPE.servings, 4)

    def test_names_and_units_preserved(self):
        scaled = scale_to_servings(EXAMPLE_RECIPE, 6)
        self.assertEqual(scaled.name, EXAMPLE_RECIPE.name)
        self.assertEqual(
            [(i.name, i.unit) for i in scaled.ingredients],
            [(i.name, i.unit) for i in EXAMPLE_RECIPE.ingredients],
        )

    def test_servings_set_exactly(self):
        # 0.7 * (3 / 0.7) == 2.9999999999999996; result must still be 3.
        recipe = replace(EXAMPLE_RECIPE, servings=0.7)
        self.assertEqual(scale_to_servings(recipe, 3).servings, 3)

    def test_zero_or_negative_servings_raise(self):
        for bad in (0, -2):
            with self.subTest(servings=bad):
                with self.assertRaises(ValueError):
                    scale_to_servings(EXAMPLE_RECIPE, bad)


class ScaleRecipeTest(unittest.TestCase):
    def test_scales_servings_too(self):
        self.assertAlmostEqual(
            scale_recipe(EXAMPLE_RECIPE, 0.85).servings, 3.4)

    def test_non_positive_factor_raises(self):
        for bad in (0, -1.5):
            with self.subTest(factor=bad):
                with self.assertRaises(ValueError):
                    scale_recipe(EXAMPLE_RECIPE, bad)


if __name__ == "__main__":
    unittest.main()
