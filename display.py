"""Display: turn a Recipe into readable text.

Rounding happens only here, never in the stored quantities, so scaling
4 -> 6 -> 4 servings gets back exactly the original recipe.
"""

from decimal import ROUND_HALF_UP, Decimal

from recipe import EXAMPLE_RECIPE, Ingredient, Recipe

COUNTABLE_UNIT = "pieces"

# Plurals the spelling rules in pluralize() get wrong, keyed by the
# singular in lowercase. Matched against the last word of the name, so
# "bay leaf" -> "bay leaves". Add common ingredients here; one-off cases
# belong in Ingredient.plural instead.
IRREGULAR_PLURALS: dict[str, str] = {
    "leaf": "leaves",
    "loaf": "loaves",
    "half": "halves",
    "avocado": "avocados",   # rule would give "avocadoes"
    "jalapeño": "jalapeños",
    "fish": "fish",
    "shrimp": "shrimp",
}


def _round_half_up(value: float, step: str) -> Decimal:
    """Round value to the nearest multiple of step, halves going up.

    Not round(): it uses banker's rounding (round(2.5) == 2).
    Not floor(value / step + 0.5): float error makes 1.15 / 0.1 come out
    just under 11.5, so 1.15 would round to 1.1. Decimal(str(value))
    works on the number as written (1.15), so halves are real halves.
    """
    step_d = Decimal(step)
    steps = (Decimal(str(value)) / step_d).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    return steps * step_d


def _strip_zeros(number: Decimal) -> str:
    """Format a Decimal without trailing zeros: 1.50 -> "1.5", 3.00 -> "3"."""
    text = f"{number:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_amount(quantity: float, unit: str) -> str:
    """Return the quantity as display text, rounded sensibly for its unit."""
    if unit in ("g", "ml"):
        step = "1" if quantity >= 10 else "0.1"
    elif unit in ("tsp", "tbsp"):
        step = "0.25"
    else:  # pieces and any unit we don't know: up to 2 decimals
        step = "0.01"

    rounded = _round_half_up(quantity, step)
    if rounded == 0 and quantity > 0:
        # Never show 0 for something that is in the recipe: fall back to
        # 2 significant digits (0.1 tsp stays "0.1", not "0").
        return f"{quantity:.2g}"
    return _strip_zeros(rounded)


def pluralize(name: str) -> str:
    """Return the English plural of name.

    Only the last word changes ("cherry tomato" -> "cherry tomatoes").
    IRREGULAR_PLURALS is checked first, then common spelling rules.
    Phrases like "clove of garlic" need Ingredient.plural instead.
    """
    # rpartition splits at the last space: "bay leaf" -> ("bay", " ", "leaf");
    # a single word gives ("", "", "leaf"), so head + sep is just "".
    head, sep, last = name.rpartition(" ")
    irregular = IRREGULAR_PLURALS.get(last.casefold())
    if irregular is not None:
        if last[:1].isupper():  # keep "Leaf" -> "Leaves"
            irregular = irregular[:1].upper() + irregular[1:]
        return head + sep + irregular

    lower = name.casefold()
    if len(lower) >= 2 and lower.endswith("y") and lower[-2] not in "aeiou":
        return name[:-1] + "ies"  # cherry -> cherries (but day -> days)
    if lower.endswith(("s", "x", "z", "ch", "sh", "o")):
        return name + "es"  # peach -> peaches, tomato -> tomatoes
    return name + "s"


def format_ingredient(ing: Ingredient) -> str:
    """Return one ingredient line, e.g. "338 g butter" or "1.5 eggs (≈ 2)"."""
    amount = format_amount(ing.quantity, ing.unit)
    if ing.unit != COUNTABLE_UNIT:
        return f"{amount} {ing.unit} {ing.name}"

    # Decide singular/plural from what is *displayed*: 0.999 shows as "1",
    # so it should read "1 egg", not "1 eggs".
    if amount == "1":
        label = ing.name
    else:
        label = ing.plural or pluralize(ing.name)
    line = f"{amount} {label}"

    # You can't crack 1.5 eggs: add a whole-number hint when not whole.
    if "." in amount:
        # At least 1: if it's in the recipe, "≈ 0 eggs" would be misleading.
        hint = max(_round_half_up(ing.quantity, "1"), 1)
        line += f" (≈ {hint})"
    return line


def format_recipe(recipe: Recipe) -> str:
    """Return a human-readable text version of the recipe."""
    servings = _strip_zeros(_round_half_up(recipe.servings, "0.1"))
    lines = [f"{recipe.name} (serves {servings})"]
    for ing in recipe.ingredients:
        lines.append(f"  - {format_ingredient(ing)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_recipe(EXAMPLE_RECIPE))
