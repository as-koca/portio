"""Recipe data model and scaling: a recipe with base servings and ingredients."""

from dataclasses import dataclass, replace


# frozen=True makes instances immutable, so later scaling functions must
# return a new Recipe instead of changing the original.
@dataclass(frozen=True)
class Ingredient:
    name: str
    quantity: float
    unit: str


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
    """Return a new recipe with servings and every quantity multiplied by factor.

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


def format_recipe(recipe: Recipe) -> str:
    """Return a human-readable text version of the recipe."""
    lines = [f"{recipe.name} (serves {recipe.servings:g})"]
    for ing in recipe.ingredients:
        # :g drops trailing zeros (200.0 -> 200);
        # proper per-unit rounding is Step 4.
        lines.append(f"  - {ing.quantity:g} {ing.unit} {ing.name}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_recipe(EXAMPLE_RECIPE))
