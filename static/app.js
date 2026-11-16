"use strict";

// The page never computes quantities itself. Every change is one API call
// that scales from the *original* recipe ("butter = 250"), so values never
// drift from repeated rounding, and all real logic stays in tested Python.
//
// Recipe text is always inserted with textContent, never innerHTML: a
// recipe named "<script>..." is then shown as text instead of running.

const DEBOUNCE_MS = 300; // wait this long after the last keystroke

const els = {
  list: document.getElementById("recipe-list"),
  error: document.getElementById("error"),
  placeholder: document.getElementById("placeholder"),
  recipe: document.getElementById("recipe"),
  name: document.getElementById("recipe-name"),
  servings: document.getElementById("servings"),
  minus: document.getElementById("servings-minus"),
  plus: document.getElementById("servings-plus"),
  reset: document.getElementById("reset"),
  ingredients: document.getElementById("ingredients"),
};

const state = {
  recipeName: null, // name of the open recipe, as the API spells it
  servings: null, // servings currently shown (a number)
  rows: [], // one {input, label} per ingredient, in recipe order
  latestRequest: 0, // id of the most recent API call
  timer: null, // pending debounced call
};

// --- Talking to the API ---------------------------------------------------

async function getJson(url) {
  const response = await fetch(url);
  let body = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON (e.g. a server crash page): fall through to the error below.
  }
  if (!response.ok) {
    throw new Error(body?.error ?? `Server error (${response.status})`);
  }
  return body;
}

function apiUrl(name, params) {
  const query = new URLSearchParams(params).toString();
  const path = `/api/recipes/${encodeURIComponent(name)}`;
  return query ? `${path}?${query}` : path;
}

// The address bar mirrors what is shown, so a link reopens the same view.
function pageUrl(name, params) {
  return `?${new URLSearchParams({ recipe: name, ...params })}`;
}

// Fetch a recipe (scaled by params) and show it.
// push: add a browser history entry (opening a recipe) instead of
//       replacing the current one (rescaling), so Back goes to the
//       previous recipe rather than through every keystroke.
// source: the field that triggered the call, marked red on error.
async function show(name, params = {}, { push = false, source = null } = {}) {
  clearTimeout(state.timer); // a direct call wins over a pending one
  const id = ++state.latestRequest;
  let recipe;
  try {
    recipe = await getJson(apiUrl(name, params));
  } catch (err) {
    if (id === state.latestRequest) showError(err.message, source);
    return;
  }
  // Replies can arrive out of order. If a newer request was started while
  // this one was in flight, drop this reply: typing "250" quickly must not
  // end up showing the result for "25".
  if (id !== state.latestRequest) return;

  clearError();
  if (recipe.name !== state.recipeName) buildRecipe(recipe);
  updateValues(recipe);

  const url = pageUrl(recipe.name, params);
  if (push) history.pushState(null, "", url);
  else history.replaceState(null, "", url);
}

// Wait until the user pauses typing, then call show().
function scheduleScale(params, source) {
  clearTimeout(state.timer);
  const value = params.quantity ?? params.servings;
  // An empty field means the user is about to type a new number (or typed
  // something that isn't one; type="number" reports that as ""): wait.
  if (value === "") return;
  state.timer = setTimeout(
    () => show(state.recipeName, params, { source }),
    DEBOUNCE_MS,
  );
}

// --- Drawing the page -----------------------------------------------------

// Build the ingredient rows once per recipe. Later updates only change
// values (updateValues), so the field being typed in is never replaced.
function buildRecipe(recipe) {
  state.recipeName = recipe.name;
  els.name.textContent = recipe.name;
  document.title = `${recipe.name} · Recipe Scaler`;

  state.rows = recipe.ingredients.map((ing) => {
    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.step = "any"; // allow decimals like 0.75
    input.inputMode = "decimal"; // number keypad on phones
    input.setAttribute("aria-label", `Amount of ${ing.name}`);
    input.addEventListener("input", () =>
      scheduleScale({ ingredient: ing.name, quantity: input.value }, input),
    );

    const amountCell = document.createElement("td");
    amountCell.append(input);
    const label = document.createElement("td");
    const row = document.createElement("tr");
    row.append(amountCell, label);
    return { row, input, label };
  });
  els.ingredients.replaceChildren(...state.rows.map((r) => r.row));

  els.placeholder.hidden = true;
  els.recipe.hidden = false;
  highlightCurrent();
}

function updateValues(recipe) {
  state.servings = recipe.servings;
  setUnlessEditing(els.servings, recipe.servings_display);
  els.minus.disabled = recipe.servings <= 1;

  // Same order as buildRecipe: the API keeps the recipe's order.
  recipe.ingredients.forEach((ing, i) => {
    setUnlessEditing(state.rows[i].input, ing.amount);
    state.rows[i].label.textContent = ing.label;
  });
}

// Don't overwrite the field the user is typing in: it would jump the
// cursor and could replace "250" with the rounded "250" mid-keystroke.
function setUnlessEditing(input, value) {
  if (document.activeElement !== input) input.value = value;
}

function showClosed() {
  state.recipeName = null;
  els.recipe.hidden = true;
  els.placeholder.hidden = false;
  document.title = "Recipe Scaler";
  highlightCurrent();
}

function highlightCurrent() {
  for (const link of els.list.querySelectorAll("a")) {
    if (link.dataset.name === state.recipeName) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
}

function showError(message, source) {
  clearError();
  els.error.textContent = message;
  els.error.hidden = false;
  source?.setAttribute("aria-invalid", "true");
}

function clearError() {
  els.error.hidden = true;
  for (const field of document.querySelectorAll("[aria-invalid]")) {
    field.removeAttribute("aria-invalid");
  }
}

// --- Recipe list and servings controls --------------------------------------

async function loadList() {
  const { recipes } = await getJson("/api/recipes");
  const items = recipes.map((name) => {
    // A real link: works without JS and with "open in new tab".
    const link = document.createElement("a");
    link.href = pageUrl(name, {});
    link.textContent = name;
    link.dataset.name = name;
    link.addEventListener("click", (event) => {
      // Ctrl/Cmd/Shift-click: let the browser open a new tab or window.
      if (event.ctrlKey || event.metaKey || event.shiftKey) return;
      event.preventDefault();
      show(name, {}, { push: true });
    });
    const item = document.createElement("li");
    item.append(link);
    return item;
  });
  els.list.replaceChildren(...items);
}

// −/+ step to the next whole number: 3.4 goes to 4 or 3, not 4.4 or 2.4.
function stepServings(direction) {
  const s = state.servings;
  const next = direction > 0 ? Math.floor(s) + 1 : Math.ceil(s) - 1;
  show(state.recipeName, { servings: String(Math.max(1, next)) });
}

els.servings.addEventListener("input", () =>
  scheduleScale({ servings: els.servings.value }, els.servings),
);
els.plus.addEventListener("click", () => stepServings(+1));
els.minus.addEventListener("click", () => stepServings(-1));
els.reset.addEventListener("click", () => show(state.recipeName));

// --- Start-up ---------------------------------------------------------------

// Open whatever the address bar describes, e.g. ?recipe=Shortbread&servings=6
async function openFromAddress() {
  const query = new URLSearchParams(location.search);
  const name = query.get("recipe");
  if (!name) {
    showClosed();
    return;
  }
  const params = {};
  for (const key of ["servings", "ingredient", "quantity"]) {
    if (query.has(key)) params[key] = query.get(key);
  }
  await show(name, params);
}

// Back/Forward buttons: re-read the address bar.
window.addEventListener("popstate", openFromAddress);

(async () => {
  try {
    await loadList();
  } catch (err) {
    showError(`Could not load recipes: ${err.message}`);
  }
  await openFromAddress();
})();
