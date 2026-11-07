"""Tests for recipe scaling and display. Run with: python3 -m unittest"""

import unittest
from dataclasses import replace

from recipe import (
    EXAMPLE_RECIPE,
    Ingredient,
    Recipe,
    format_amount,
    format_ingredient,
    format_recipe,
    pluralize,
    scale_by_ingredient,
    scale_recipe,
    scale_to_servings,
)


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


class ScaleByIngredientTest(unittest.TestCase):
    def test_butter_200_to_150(self):
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 150)
        self.assertAlmostEqual(scaled.servings, 3)
        for got, want in zip(quantities(scaled), [150, 225, 75, 0.75]):
            self.assertAlmostEqual(got, want)

    def test_fractional_servings(self):
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 170)
        self.assertAlmostEqual(scaled.servings, 3.4)

    def test_scale_up_by_egg(self):
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "egg", 2)
        self.assertAlmostEqual(scaled.servings, 8)
        for got, want in zip(quantities(scaled), [400, 600, 200, 2]):
            self.assertAlmostEqual(got, want)

    def test_chosen_ingredient_is_exact(self):
        # 200 * (7 / 200) == 7.000000000000001 in floating point; the
        # ingredient the user set must still be exactly 7.
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 7)
        self.assertEqual(scaled.ingredients[0].quantity, 7)

    def test_name_is_case_insensitive(self):
        for name in ("Butter", "BUTTER", "bUtTeR"):
            with self.subTest(name=name):
                scaled = scale_by_ingredient(EXAMPLE_RECIPE, name, 150)
                self.assertEqual(scaled.ingredients[0].quantity, 150)

    def test_original_is_unchanged(self):
        before = quantities(EXAMPLE_RECIPE)
        scale_by_ingredient(EXAMPLE_RECIPE, "butter", 150)
        self.assertEqual(quantities(EXAMPLE_RECIPE), before)
        self.assertEqual(EXAMPLE_RECIPE.servings, 4)

    def test_unknown_ingredient_raises(self):
        with self.assertRaises(ValueError):
            scale_by_ingredient(EXAMPLE_RECIPE, "chocolate", 50)

    def test_old_quantity_zero_raises(self):
        recipe = Recipe(
            name="Salted",
            servings=2,
            ingredients=(Ingredient("salt", 0, "g"), Ingredient("flour", 100, "g")),
        )
        with self.assertRaises(ValueError):
            scale_by_ingredient(recipe, "salt", 5)

    def test_new_quantity_zero_or_negative_raises(self):
        for bad in (0, -50):
            with self.subTest(new_quantity=bad):
                with self.assertRaises(ValueError):
                    scale_by_ingredient(EXAMPLE_RECIPE, "butter", bad)


class FormatAmountTest(unittest.TestCase):
    def check(self, cases):
        for quantity, unit, want in cases:
            with self.subTest(quantity=quantity, unit=unit):
                self.assertEqual(format_amount(quantity, unit), want)

    def test_grams_and_ml(self):
        self.check([
            (337.5, "g", "338"),    # whole numbers from 10 up, half rounds up
            (200.0, "g", "200"),
            (7.25, "g", "7.3"),     # 1 decimal under 10
            (9.96, "ml", "10"),
            (1.15, "ml", "1.2"),    # float trap: naive floor gives 1.1
        ])

    def test_spoons_round_to_quarters(self):
        self.check([
            (0.8, "tsp", "0.75"),
            (1.1, "tsp", "1"),
            (0.875, "tbsp", "1"),   # exactly halfway between 0.75 and 1
            (2.5, "tbsp", "2.5"),
        ])

    def test_pieces_and_unknown_units_two_decimals(self):
        self.check([
            (1.5, "pieces", "1.5"),
            (4 / 3, "pieces", "1.33"),
            (4 / 3, "cup", "1.33"),
        ])

    def test_positive_amount_never_shows_zero(self):
        self.check([
            (0.1, "tsp", "0.1"),
            (0.04, "g", "0.04"),
            (0.004, "pieces", "0.004"),
        ])

    def test_zero_shows_zero(self):
        self.check([(0, "g", "0")])


class PluralizeTest(unittest.TestCase):
    def test_rules(self):
        cases = {
            "egg": "eggs",
            "lemon": "lemons",
            "cherry": "cherries",
            "day": "days",              # vowel + y: just +s
            "peach": "peaches",
            "radish": "radishes",
            "box": "boxes",
            "tomato": "tomatoes",
            "cherry tomato": "cherry tomatoes",
            "Egg": "Eggs",
        }
        for word, want in cases.items():
            with self.subTest(word=word):
                self.assertEqual(pluralize(word), want)


class FormatIngredientTest(unittest.TestCase):
    def test_measured_unit(self):
        self.assertEqual(
            format_ingredient(Ingredient("butter", 337.5, "g")), "338 g butter"
        )

    def test_one_piece_is_singular_without_unit_word(self):
        self.assertEqual(format_ingredient(Ingredient("egg", 1, "pieces")), "1 egg")

    def test_singular_decided_by_displayed_amount(self):
        self.assertEqual(
            format_ingredient(Ingredient("egg", 0.999, "pieces")), "1 egg"
        )

    def test_whole_plural_has_no_hint(self):
        self.assertEqual(
            format_ingredient(Ingredient("egg", 2, "pieces")), "2 eggs"
        )

    def test_fractional_pieces_get_rounded_hint(self):
        self.assertEqual(
            format_ingredient(Ingredient("egg", 1.5, "pieces")), "1.5 eggs (≈ 2)"
        )
        self.assertEqual(
            format_ingredient(Ingredient("egg", 2.5, "pieces")), "2.5 eggs (≈ 3)"
        )

    def test_hint_is_at_least_one(self):
        self.assertEqual(
            format_ingredient(Ingredient("egg", 0.3, "pieces")), "0.3 eggs (≈ 1)"
        )

    def test_explicit_plural_wins(self):
        ing = Ingredient("bay leaf", 3, "pieces", plural="bay leaves")
        self.assertEqual(format_ingredient(ing), "3 bay leaves")

    def test_explicit_plural_not_used_for_one(self):
        ing = Ingredient("bay leaf", 1, "pieces", plural="bay leaves")
        self.assertEqual(format_ingredient(ing), "1 bay leaf")


class FormatRecipeTest(unittest.TestCase):
    def test_example_recipe(self):
        self.assertEqual(
            format_recipe(EXAMPLE_RECIPE),
            "Shortbread (serves 4)\n"
            "  - 200 g butter\n"
            "  - 300 g flour\n"
            "  - 100 g sugar\n"
            "  - 1 egg",
        )

    def test_scaled_recipe(self):
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 170)
        self.assertEqual(
            format_recipe(scaled),
            "Shortbread (serves 3.4)\n"
            "  - 170 g butter\n"
            "  - 255 g flour\n"
            "  - 85 g sugar\n"
            "  - 0.85 eggs (≈ 1)",
        )

    def test_rounding_is_display_only(self):
        # Butter 200 -> 7 g makes flour 10.5 g, displayed as "11 g".
        # If that rounding leaked into the data, going back to 200 g butter
        # would give 314 g flour instead of 300.
        small = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 7)
        self.assertIn("11 g flour", format_recipe(small))
        back = scale_by_ingredient(small, "butter", 200)
        for got, want in zip(quantities(back), quantities(EXAMPLE_RECIPE)):
            self.assertAlmostEqual(got, want)


if __name__ == "__main__":
    unittest.main()
