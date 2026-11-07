"""Tests for recipe display. Run with: python3 -m unittest"""

import unittest

from display import (
    format_amount,
    format_ingredient,
    format_recipe,
    pluralize,
)
from recipe import EXAMPLE_RECIPE, Ingredient, scale_by_ingredient


class FormatAmountTest(unittest.TestCase):
    def check(self, cases: list[tuple[float, str, str]]) -> None:
        for quantity, unit, want in cases:
            with self.subTest(quantity=quantity, unit=unit):
                self.assertEqual(format_amount(quantity, unit), want)

    def test_grams_and_ml(self) -> None:
        self.check([
            (337.5, "g", "338"),    # whole numbers from 10 up, half rounds up
            (200.0, "g", "200"),
            (7.25, "g", "7.3"),     # 1 decimal under 10
            (9.96, "ml", "10"),
            (1.15, "ml", "1.2"),    # float trap: naive floor gives 1.1
        ])

    def test_spoons_round_to_quarters(self) -> None:
        self.check([
            (0.8, "tsp", "0.75"),
            (1.1, "tsp", "1"),
            (0.875, "tbsp", "1"),   # exactly halfway between 0.75 and 1
            (2.5, "tbsp", "2.5"),
        ])

    def test_pieces_and_unknown_units_two_decimals(self) -> None:
        self.check([
            (1.5, "pieces", "1.5"),
            (4 / 3, "pieces", "1.33"),
            (4 / 3, "cup", "1.33"),
        ])

    def test_positive_amount_never_shows_zero(self) -> None:
        self.check([
            (0.1, "tsp", "0.1"),
            (0.04, "g", "0.04"),
            (0.004, "pieces", "0.004"),
        ])

    def test_zero_shows_zero(self) -> None:
        self.check([(0, "g", "0")])


class PluralizeTest(unittest.TestCase):
    def test_rules(self) -> None:
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

    def test_irregular_list(self) -> None:
        cases = {
            "leaf": "leaves",
            "bay leaf": "bay leaves",   # matched on the last word
            "Leaf": "Leaves",           # capital kept
            "avocado": "avocados",      # beats the "o -> es" rule
            "fish": "fish",
        }
        for word, want in cases.items():
            with self.subTest(word=word):
                self.assertEqual(pluralize(word), want)


class FormatIngredientTest(unittest.TestCase):
    def test_measured_unit(self) -> None:
        self.assertEqual(
            format_ingredient(Ingredient("butter", 337.5, "g")), "338 g butter"
        )

    def test_one_piece_is_singular_without_unit_word(self) -> None:
        self.assertEqual(
            format_ingredient(Ingredient("egg", 1, "pieces")), "1 egg"
        )

    def test_singular_decided_by_displayed_amount(self) -> None:
        self.assertEqual(
            format_ingredient(Ingredient("egg", 0.999, "pieces")), "1 egg"
        )

    def test_whole_plural_has_no_hint(self) -> None:
        self.assertEqual(
            format_ingredient(Ingredient("egg", 2, "pieces")), "2 eggs"
        )

    def test_fractional_pieces_get_rounded_hint(self) -> None:
        self.assertEqual(
            format_ingredient(Ingredient("egg", 1.5, "pieces")),
            "1.5 eggs (≈ 2)",
        )
        self.assertEqual(
            format_ingredient(Ingredient("egg", 2.5, "pieces")),
            "2.5 eggs (≈ 3)",
        )

    def test_hint_is_at_least_one(self) -> None:
        self.assertEqual(
            format_ingredient(Ingredient("egg", 0.3, "pieces")),
            "0.3 eggs (≈ 1)",
        )

    def test_explicit_plural_wins(self) -> None:
        ing = Ingredient("bay leaf", 3, "pieces", plural="bay leaves")
        self.assertEqual(format_ingredient(ing), "3 bay leaves")

    def test_explicit_plural_not_used_for_one(self) -> None:
        ing = Ingredient("bay leaf", 1, "pieces", plural="bay leaves")
        self.assertEqual(format_ingredient(ing), "1 bay leaf")


class FormatRecipeTest(unittest.TestCase):
    def test_example_recipe(self) -> None:
        self.assertEqual(
            format_recipe(EXAMPLE_RECIPE),
            "Shortbread (serves 4)\n"
            "  - 200 g butter\n"
            "  - 300 g flour\n"
            "  - 100 g sugar\n"
            "  - 1 egg",
        )

    def test_scaled_recipe(self) -> None:
        scaled = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 170)
        self.assertEqual(
            format_recipe(scaled),
            "Shortbread (serves 3.4)\n"
            "  - 170 g butter\n"
            "  - 255 g flour\n"
            "  - 85 g sugar\n"
            "  - 0.85 eggs (≈ 1)",
        )

    def test_rounding_is_display_only(self) -> None:
        # Butter 200 -> 7 g makes flour 10.5 g, displayed as "11 g".
        # If that rounding leaked into the data, going back to 200 g butter
        # would give 314 g flour instead of 300.
        small = scale_by_ingredient(EXAMPLE_RECIPE, "butter", 7)
        self.assertIn("11 g flour", format_recipe(small))
        back = scale_by_ingredient(small, "butter", 200)
        for got, want in zip(back.ingredients, EXAMPLE_RECIPE.ingredients):
            self.assertAlmostEqual(got.quantity, want.quantity)


if __name__ == "__main__":
    unittest.main()
