"""Recipe data model and scaling:
a recipe with base servings and ingredients."""

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal


# frozen=True makes instances immutable, so later scaling functions must
# return a new Recipe instead of changing the original.
@dataclass(frozen=True)
class Ingredient:
    name: str
    quantity: float
    unit: str
    # Only needed for countable ingredients whose plural the spelling rules
    # in pluralize() get wrong (e.g. "leaf" -> "leaves"). Filled in by
    # whoever writes the recipe; None means "use the rules".
    plural: str | None = None


@dataclass(frozen=True)
class Recipe:
    name: str
    # float, not int: scaling by an ingredient (e.g. butter 200 -> 170 g)
    # can give fractional servings like 3.4.
    servings: float
    # A tuple (not a list) so the ingredient collection is immutable too.
    ingredients: tuple[Ingredient, ...]


EXAMPLE_RECIPE = Recipe(
    name="Shortbread",
    servings=4,
    ingredients=(
        Ingredient("butter", 200, "g"),
        Ingredient("flour", 300, "g"),
        Ingredient("sugar", 100, "g"),
        Ingredient("egg", 1, "pieces"),
    ),
)


def scale_recipe(recipe: Recipe, factor: float) -> Recipe:
    """Return a new recipe with servings and every quantity multiplied
    by factor.

    This is the single scaling mechanism; scaling by servings or by one
    ingredient only differs in how the factor is computed.
    """
    if factor <= 0:
        raise ValueError(f"scale factor must be positive, got {factor}")
    return replace(
        recipe,
        servings=recipe.servings * factor,
        ingredients=tuple(
            replace(ing, quantity=ing.quantity * factor)
            for ing in recipe.ingredients
        ),
    )


def scale_to_servings(recipe: Recipe, new_servings: float) -> Recipe:
    """Return a new recipe scaled from recipe.servings to new_servings."""
    if new_servings <= 0:
        raise ValueError(f"servings must be positive, got {new_servings}")
    scaled = scale_recipe(recipe, new_servings / recipe.servings)
    # Set servings exactly rather than trusting servings * factor, which can
    # pick up float error once servings are fractional
    # (e.g. 0.7 * (3 / 0.7) == 2.9999999999999996).
    return replace(scaled, servings=new_servings)


def scale_by_ingredient(
    recipe: Recipe, ingredient_name: str, new_quantity: float
) -> Recipe:
    """Return a new recipe scaled so ingredient_name has new_quantity.

    Every other ingredient (and servings) scales by the same ratio,
    new_quantity / old_quantity. Name matching ignores case.
    """
    # casefold() is a stronger lower():
    # it also matches e.g. German "ß" with "ss".
    wanted = ingredient_name.casefold()
    # First match wins if two ingredients share a name.
    index = next(
        (i for i, ing in enumerate(recipe.ingredients)
         if ing.name.casefold() == wanted),
        None,
    )
    if index is None:
        available = ", ".join(ing.name for ing in recipe.ingredients)
        raise ValueError(
            f"no ingredient named {ingredient_name!r}; available: {available}"
        )

    old_quantity = recipe.ingredients[index].quantity
    if old_quantity == 0:
        raise ValueError(
            f"cannot scale by {ingredient_name!r}: its quantity is 0, "
            "so there is no ratio to compute"
        )

    # A new_quantity <= 0 gives factor <= 0, which scale_recipe rejects.
    scaled = scale_recipe(recipe, new_quantity / old_quantity)
    # Same float-safety trick as scale_to_servings: the ingredient the user
    # set must come out exactly as typed (150, not 150.00000000000003).
    ingredients = list(scaled.ingredients)
    ingredients[index] = replace(ingredients[index], quantity=new_quantity)
    return replace(scaled, ingredients=tuple(ingredients))


# --- Display -------------------------------------------------------------
# Rounding happens only here, never in the stored quantities, so scaling
# 4 -> 6 -> 4 servings gets back exactly the original recipe.

COUNTABLE_UNIT = "pieces"


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
    """Return the English plural of name using common spelling rules.

    Only the last word changes ("cherry tomato" -> "cherry tomatoes").
    Irregular words (leaf, avocado, "clove of garlic") need
    Ingredient.plural instead.
    """
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
