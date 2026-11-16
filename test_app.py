"""Tests for the JSON API. Needs Flask: uv run python -m unittest"""

import tempfile
import unittest
from pathlib import Path
from typing import Any

from app import create_app
from recipe import EXAMPLE_RECIPE, Ingredient, Recipe
from storage import save_book

LEMON_BARS = Recipe(
    name="Lemon Bars",  # has a space: tests URL decoding
    servings=8,
    ingredients=(Ingredient("lemon", 3, "pieces"),),
)


class ApiTestCase(unittest.TestCase):
    """Each test gets its own book file and app (Flask's test client:
    requests go straight to the app, no server or browser)."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "book.json"
        save_book(self.path, [EXAMPLE_RECIPE, LEMON_BARS])
        self.client = create_app(self.path).test_client()

    def get(self, url: str) -> tuple[int, Any]:
        """GET url; return the status code and the parsed JSON body."""
        response = self.client.get(url)
        return response.status_code, response.get_json()

    def get_ok(self, url: str) -> Any:
        status, body = self.get(url)
        self.assertEqual(status, 200, body)
        return body

    def assert_error(self, url: str, status: int, message: str) -> None:
        got_status, body = self.get(url)
        self.assertEqual(got_status, status)
        self.assertIn(message, body["error"])


class PageTest(ApiTestCase):
    def test_index_serves_the_page(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<title>Recipe Scaler</title>", response.data)
        response.close()  # static files are streamed; close the handle

    def test_static_files_are_served(self) -> None:
        for path in ("/static/app.js", "/static/style.css"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()


class ListTest(ApiTestCase):
    def test_lists_names_in_file_order(self) -> None:
        body = self.get_ok("/api/recipes")
        self.assertEqual(body, {"recipes": ["Shortbread", "Lemon Bars"]})


class GetRecipeTest(ApiTestCase):
    def test_unscaled(self) -> None:
        body = self.get_ok("/api/recipes/Shortbread")
        self.assertEqual(body["name"], "Shortbread")
        self.assertEqual(body["servings"], 4)
        self.assertEqual(body["servings_display"], "4")
        self.assertEqual(
            body["ingredients"][0],
            {
                "name": "butter",
                "quantity": 200,
                "unit": "g",
                "amount": "200",
                "label": "g butter",
                "display": "200 g butter",
            },
        )
        self.assertEqual(body["ingredients"][3]["display"], "1 egg")

    def test_name_ignores_case_and_is_url_decoded(self) -> None:
        body = self.get_ok("/api/recipes/lemon%20BARS")
        self.assertEqual(body["name"], "Lemon Bars")

    def test_unknown_recipe_is_404(self) -> None:
        self.assert_error("/api/recipes/Brownies", 404, "no recipe named")


class ScaleTest(ApiTestCase):
    def test_by_servings(self) -> None:
        body = self.get_ok("/api/recipes/Shortbread?servings=6")
        self.assertEqual(body["servings"], 6)
        self.assertEqual(body["ingredients"][0]["quantity"], 300)
        egg = body["ingredients"][3]
        self.assertEqual(egg["display"], "1.5 eggs (≈ 2)")
        # amount + label split the same line for the page's input boxes
        self.assertEqual(egg["amount"], "1.5")
        self.assertEqual(egg["label"], "eggs (≈ 2)")

    def test_by_ingredient(self) -> None:
        body = self.get_ok(
            "/api/recipes/Shortbread?ingredient=Butter&quantity=170"
        )
        self.assertEqual(body["servings_display"], "3.4")
        self.assertEqual(body["ingredients"][0]["quantity"], 170)
        self.assertEqual(body["ingredients"][1]["display"], "255 g flour")

    def test_bad_input_is_400(self) -> None:
        base = "/api/recipes/Shortbread?"
        cases = [
            ("servings=abc", '"servings" must be a number'),
            ("servings=nan", "finite"),
            ("servings=0", "servings must be positive"),
            ("servings=4&ingredient=butter&quantity=1", "not both"),
            ("ingredient=butter", 'needs a "quantity"'),
            ("quantity=150", 'needs an "ingredient"'),
            ("ingredient=chocolate&quantity=5", "no ingredient named"),
            ("ingredient=butter&quantity=-5", "must be positive"),
        ]
        for query, message in cases:
            with self.subTest(query=query):
                self.assert_error(base + query, 400, message)

    def test_book_file_is_never_modified(self) -> None:
        before = self.path.read_bytes()
        self.get_ok("/api/recipes/Shortbread?servings=10")
        self.get_ok("/api/recipes/Shortbread?ingredient=egg&quantity=3")
        self.assertEqual(self.path.read_bytes(), before)

    def test_scaling_does_not_leak_between_requests(self) -> None:
        # The book is loaded once and shared by all visitors: one
        # visitor's scaling must not change what the next one sees.
        self.get_ok("/api/recipes/Shortbread?servings=10")
        body = self.get_ok("/api/recipes/Shortbread")
        self.assertEqual(body["servings"], 4)


if __name__ == "__main__":
    unittest.main()
