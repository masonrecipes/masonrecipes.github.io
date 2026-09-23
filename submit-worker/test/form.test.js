import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { JSDOM } from "jsdom";

// The real site script, run in a page shaped like the Zensical header it attaches to.
const FORM_SCRIPT = readFileSync(new URL("../../docs/javascripts/recipe-submission.js", import.meta.url), "utf8");
const ENDPOINT = "https://mason-recipe-submissions.example.workers.dev";
const LINK = "https://kitchen.example/recipes/cookies";

function spy(implementation) {
  const wrapped = (...arguments_) => {
    wrapped.calls.push(arguments_);
    return implementation(...arguments_);
  };
  wrapped.calls = [];
  return wrapped;
}

function openForm({ fetch = spy(async () => Response.json({ ok: true }, { status: 201 })), confirm = spy(() => true) } = {}) {
  const { window } = new JSDOM(
    "<div data-md-component='header'><div class='md-header__inner'><label for='__search'></label></div></div>",
    { runScripts: "outside-only", url: "https://masonrecipes.github.io/" },
  );
  window.MASON_RECIPE_SUBMISSION_CONFIG = { endpoint: ENDPOINT, turnstileSiteKey: "site-key" };
  // Turnstile hands out a fresh single-use token on render and after every reset.
  let issued = 0;
  let deliver;
  window.turnstile = {
    render: (element, options) => {
      deliver = options.callback;
      deliver(`token-${++issued}`);
      return "widget";
    },
    reset: () => deliver(`token-${++issued}`),
  };
  window.fetch = fetch;
  window.confirm = confirm;
  window.HTMLDialogElement.prototype.showModal ??= function showModal() { this.open = true; };
  window.eval(FORM_SCRIPT);
  window.document.querySelector(".recipe-submission-header-trigger").click();

  const $ = (selector) => window.document.querySelector(selector);
  const fields = {
    name: $("#recipe-submission-name"),
    link: $("#recipe-submission-source"),
    ingredients: $("#recipe-submission-ingredients"),
    recipe: $("#recipe-submission-recipe"),
  };
  const type = (field, value) => {
    field.value = value;
    field.dispatchEvent(new window.Event("input", { bubbles: true }));
  };
  const fillButton = [...window.document.querySelectorAll("button")].find((button) => button.textContent.trim() === "Fill from link");
  return { window, $, fields, type, fillButton, fetch, confirm };
}

describe("recipe form: fill from link", () => {
  it("offers Fill from link only while the link box holds an http(s) address", () => {
    const { fields, type, fillButton } = openForm();

    assert.ok(fillButton, "the form has a Fill from link button");
    assert.equal(fillButton.disabled, true);
    for (const [value, enabled] of [["Grandma's cookbook", false], ["ftp://kitchen.example/r", false], [LINK, true], ["", false]]) {
      type(fields.link, value);
      assert.equal(fillButton.disabled, !enabled, value);
    }
  });

  it("fills the boxes from the page, keeps Send as the next step, and saves a fresh spam-check token for it", async () => {
    const fetch = spy(async (url) => (String(url).endsWith("/fill")
      ? Response.json({ title: "Chewy Cookies", ingredients: ["2 cups flour", "1 cup sugar"], steps: ["Mix.", "Bake 10 minutes."] })
      : Response.json({ ok: true }, { status: 201 })));
    const { $, fields, type, fillButton } = openForm({ fetch });
    type(fields.link, LINK);

    fillButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(fetch.calls.length, 1, "Fill does not send the recipe");
    const [url, init] = fetch.calls[0];
    assert.equal(String(url), `${ENDPOINT}/fill`);
    assert.equal(init.method, "POST");
    assert.deepEqual(JSON.parse(init.body), { url: LINK, recipeName: "", turnstileToken: "token-1" });
    assert.equal(fields.ingredients.value, "2 cups flour\n1 cup sugar");
    assert.equal(fields.recipe.value, "Mix.\nBake 10 minutes.");
    assert.equal(fields.name.value, "Chewy Cookies");
    assert.match($(".recipe-submission-status").textContent, /check/i);

    $(".recipe-submission-form").requestSubmit();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(fetch.calls.length, 2);
    const sent = JSON.parse(fetch.calls[1][1].body);
    assert.equal(sent.turnstileToken, "token-2", "single-use tokens are not reused");
    assert.equal(sent.ingredients, "2 cups flour\n1 cup sugar");
  });

  it("never replaces a recipe name the person already typed", async () => {
    const fetch = spy(async () => Response.json({ title: "Chewy Cookies", ingredients: ["flour"], steps: ["Bake."] }));
    const { fields, type, fillButton } = openForm({ fetch });
    type(fields.name, "Nana's Cookies");
    type(fields.link, LINK);

    fillButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(JSON.parse(fetch.calls[0][1].body).recipeName, "Nana's Cookies");
    assert.equal(fields.name.value, "Nana's Cookies");
  });

  it("asks before replacing ingredients or steps the person typed, and keeps them if they say no", async () => {
    const page = () => Response.json({ title: "", ingredients: ["flour"], steps: ["Bake."] });

    const empty = openForm({ fetch: spy(page) });
    empty.type(empty.fields.link, LINK);
    empty.fillButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(empty.confirm.calls.length, 0, "empty boxes are filled without asking");

    const declined = openForm({ fetch: spy(page), confirm: spy(() => false) });
    declined.type(declined.fields.recipe, "My own steps");
    declined.type(declined.fields.link, LINK);
    declined.fillButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(declined.confirm.calls.length, 1);
    assert.equal(declined.fetch.calls.length, 0);
    assert.equal(declined.fields.recipe.value, "My own steps");

    const accepted = openForm({ fetch: spy(page), confirm: spy(() => true) });
    accepted.type(accepted.fields.ingredients, "My own list");
    accepted.type(accepted.fields.link, LINK);
    accepted.fillButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(accepted.confirm.calls.length, 1);
    assert.equal(accepted.fields.ingredients.value, "flour");
  });

  it("shows a working state while it reads the page and locks the boxes it is about to fill", async () => {
    let answer;
    const fetch = spy(() => new Promise((resolve) => { answer = resolve; }));
    const { fields, type, fillButton } = openForm({ fetch });
    type(fields.link, LINK);

    fillButton.click();
    assert.equal(fillButton.disabled, true);
    assert.equal(fillButton.getAttribute("aria-busy"), "true");
    assert.match(fillButton.textContent, /Reading/);
    assert.equal(fields.ingredients.readOnly, true);
    assert.equal(fields.recipe.readOnly, true);
    type(fields.link, "https://kitchen.example/other");
    assert.equal(fillButton.disabled, true, "editing the link does not re-enable a running fill");

    answer(Response.json({ ingredients: ["flour"], steps: ["Bake."] }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(fillButton.disabled, false);
    assert.equal(fillButton.hasAttribute("aria-busy"), false);
    assert.equal(fillButton.textContent.trim(), "Fill from link");
    assert.equal(fields.ingredients.readOnly, false);
    assert.equal(fields.recipe.readOnly, false);
  });

  it("is a keyboard-reachable button right after the link box that never submits the form", () => {
    const { window, fields, type, fillButton, fetch } = openForm();
    type(fields.link, LINK);

    assert.equal(fillButton.tagName, "BUTTON");
    assert.equal(fillButton.type, "button");
    const focusable = [...window.document.querySelectorAll(".recipe-submission-form input, .recipe-submission-form textarea, .recipe-submission-form button:not(:disabled)")];
    assert.equal(focusable[focusable.indexOf(fields.link) + 1], fillButton, "Tab moves from the link box to Fill");
    fillButton.click();
    assert.ok(fetch.calls.every(([url]) => String(url).endsWith("/fill")));
  });

  it("explains a failed read, leaves the boxes alone and hands focus back", async (t) => {
    const fetch = spy(async () => Response.json({ error: "We couldn't read this page. You can still send the link." }, { status: 422 }));
    const { window, $, fields, type, fillButton } = openForm({ fetch });
    type(fields.ingredients, "");
    type(fields.link, LINK);

    fillButton.focus();
    fillButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal($(".recipe-submission-status").textContent, "We couldn't read this page. You can still send the link.");
    assert.equal(fields.ingredients.value, "");
    assert.equal(window.document.activeElement, fillButton);
  });

  it("moves focus to the filled ingredients so the person can review them", async () => {
    const { window, fields, type, fillButton } = openForm({ fetch: spy(async () => Response.json({ ingredients: ["flour"], steps: ["Bake."] })) });
    type(fields.link, LINK);

    fillButton.focus();
    fillButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(window.document.activeElement, fields.ingredients);
  });
});
