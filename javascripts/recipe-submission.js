(() => {
  const config = window.MASON_RECIPE_SUBMISSION_CONFIG;
  if (!config?.endpoint || !config?.turnstileSiteKey || !config.endpoint.startsWith("https://")) return;

  const button = document.createElement("button");
  button.className = "recipe-submission-header-trigger md-header__button";
  button.type = "button";
  button.title = "Submit a recipe";
  button.setAttribute("aria-haspopup", "dialog");
  button.setAttribute("aria-label", "Submit a recipe");
  button.innerHTML = `
    <svg class="md-icon" aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
    <span class="recipe-submission-header-label">Submit a recipe</span>`;

  const dialog = document.createElement("dialog");
  dialog.className = "recipe-submission-dialog";
  dialog.setAttribute("aria-labelledby", "recipe-submission-title");
  dialog.innerHTML = `
    <form class="recipe-submission-form" novalidate>
      <div class="recipe-submission-heading">
        <h2 id="recipe-submission-title">Share a recipe</h2>
        <button class="recipe-submission-close" type="button" aria-label="Close recipe form">×</button>
      </div>
      <p>Send us the recipe in whatever form you have it. We will take it from there. Found it online? Paste the link and press Fill from link to copy the ingredients and steps into the form for you to check, or just send the link and we will read it later.</p>
      <label for="recipe-submission-name">Recipe name <span aria-hidden="true">*</span></label>
      <input id="recipe-submission-name" name="recipeName" maxlength="120" required autocomplete="off">
      <label for="recipe-submission-source">Inspired by (link) <span class="recipe-submission-optional">(optional)</span></label>
      <div class="recipe-submission-link-row">
        <input id="recipe-submission-source" name="sourceUrl" type="url" maxlength="2048" autocomplete="url" inputmode="url" placeholder="https://example.com/recipe">
        <button class="recipe-submission-fill md-button" type="button" disabled>Fill from link</button>
      </div>
      <label for="recipe-submission-ingredients">Ingredients <span class="recipe-submission-required" aria-hidden="true">*</span></label>
      <textarea id="recipe-submission-ingredients" name="ingredients" maxlength="12000" required rows="8" placeholder="One ingredient per line"></textarea>
      <label for="recipe-submission-recipe">Recipe <span class="recipe-submission-required" aria-hidden="true">*</span></label>
      <textarea id="recipe-submission-recipe" name="recipe" maxlength="12000" required rows="12" placeholder="Describe the steps"></textarea>
      <label for="recipe-submission-submitter">Your name <span class="recipe-submission-optional">(optional, shown publicly)</span></label>
      <input id="recipe-submission-submitter" name="submitterName" maxlength="80" autocomplete="name" aria-describedby="recipe-submission-submitter-note">
      <p id="recipe-submission-submitter-note" class="recipe-submission-optional">If you add your name, it will appear publicly with your recipe.</p>
      <div class="recipe-submission-turnstile" aria-label="Spam check"></div>
      <p class="recipe-submission-status" role="status" aria-live="polite"></p>
      <button class="recipe-submission-send md-button md-button--primary" type="submit">Send recipe</button>
    </form>`;

  // Zensical scopes form typography under .md-typeset.
  const root = document.createElement("div");
  root.className = "md-typeset";
  root.append(dialog);
  document.body.append(root);

  const header = document.querySelector("[data-md-component='header'] .md-header__inner");
  const searchToggle = header?.querySelector("label[for='__search']");
  if (!header) return;
  header.insertBefore(button, searchToggle ?? null);

  const form = dialog.querySelector("form");
  const sourceInput = dialog.querySelector("#recipe-submission-source");
  const recipeText = [dialog.querySelector("#recipe-submission-ingredients"), dialog.querySelector("#recipe-submission-recipe")];
  const closeButton = dialog.querySelector(".recipe-submission-close");
  const sendButton = dialog.querySelector(".recipe-submission-send");
  const fillButton = dialog.querySelector(".recipe-submission-fill");
  const status = dialog.querySelector(".recipe-submission-status");
  let turnstileToken = "";
  let filling = false;
  let widgetId;

  // A valid http(s) link lets us read the ingredients and steps from that page.
  function syncRequired() {
    const hasLink = sourceInput.validity.valid && /^https?:\/\/\S+$/i.test(sourceInput.value.trim());
    for (const field of recipeText) field.required = !hasLink;
    for (const mark of dialog.querySelectorAll(".recipe-submission-required")) mark.hidden = hasLink;
    fillButton.disabled = !hasLink || filling;
  }

  function setFilling(active) {
    filling = active;
    fillButton.textContent = active ? "Reading page…" : "Fill from link";
    if (active) fillButton.setAttribute("aria-busy", "true");
    else fillButton.removeAttribute("aria-busy");
    for (const field of recipeText) field.readOnly = active;
    syncRequired();
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function resetTurnstile() {
    turnstileToken = "";
    if (widgetId !== undefined && window.turnstile) window.turnstile.reset(widgetId);
  }

  function renderTurnstile() {
    if (!window.turnstile || widgetId !== undefined) return;
    widgetId = window.turnstile.render(dialog.querySelector(".recipe-submission-turnstile"), {
      action: "recipe_submit",
      appearance: "interaction-only",
      callback: (token) => { turnstileToken = token; },
      "error-callback": () => setStatus("The spam check did not load. Please try again."),
      sitekey: config.turnstileSiteKey,
      theme: "auto",
    });
  }

  function loadTurnstile() {
    const script = document.createElement("script");
    script.async = true;
    script.defer = true;
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.addEventListener("load", renderTurnstile);
    script.addEventListener("error", () => setStatus("The spam check did not load. Please try again."));
    document.head.append(script);
  }

  function openDialog() {
    if (typeof dialog.showModal !== "function") return;
    dialog.showModal();
    renderTurnstile();
    dialog.querySelector("#recipe-submission-name").focus();
  }

  const FILL_FAILED = "We couldn't read this page. You can still send the link.";
  const nameInput = dialog.querySelector("#recipe-submission-name");
  const [ingredientsInput, recipeInput] = recipeText;

  // Fill reads the linked page into the boxes; the person still reviews and presses Send.
  async function fillFromLink() {
    const typed = recipeText.some((field) => field.value.trim());
    if (typed && !window.confirm("Replace the ingredients and recipe you have typed with the ones from this page?")) return;
    if (!turnstileToken) {
      setStatus("The spam check is still loading. Please try again in a moment.");
      return;
    }
    // Turnstile tokens are single-use: this one is spent on Fill, and Send gets a fresh one.
    const token = turnstileToken;
    resetTurnstile();
    setFilling(true);
    setStatus("Reading the recipe from that page…");
    let filled = false;
    try {
      const response = await fetch(new URL("/fill", config.endpoint), {
        body: JSON.stringify({ url: sourceInput.value.trim(), recipeName: nameInput.value.trim(), turnstileToken: token }),
        headers: { "content-type": "application/json" },
        method: "POST",
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !Array.isArray(result.ingredients) || !Array.isArray(result.steps)) {
        throw new Error(result.error || FILL_FAILED);
      }
      ingredientsInput.value = result.ingredients.join("\n");
      recipeInput.value = result.steps.join("\n");
      if (!nameInput.value.trim() && typeof result.title === "string") nameInput.value = result.title.slice(0, 120);
      setStatus("Filled in from the page. Please check the ingredients and steps, then send your recipe.");
      filled = true;
    } catch (error) {
      setStatus(error instanceof TypeError || !error.message ? FILL_FAILED : error.message);
    } finally {
      setFilling(false);
      // The button was disabled while working, which drops keyboard focus; put it somewhere useful.
      (filled ? ingredientsInput : fillButton).focus();
    }
  }

  sourceInput.addEventListener("input", syncRequired);
  fillButton.addEventListener("click", fillFromLink);
  button.addEventListener("click", openDialog);
  closeButton.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    button.focus();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (!turnstileToken) {
      setStatus("Please complete the spam check before sending your recipe.");
      return;
    }

    const fields = new FormData(form);
    sendButton.disabled = true;
    setStatus("Sending your recipe…");
    try {
      const response = await fetch(config.endpoint, {
        body: JSON.stringify({
          recipeName: fields.get("recipeName"),
          ingredients: fields.get("ingredients"),
          recipe: fields.get("recipe"),
          submitterName: fields.get("submitterName"),
          sourceUrl: fields.get("sourceUrl"),
          turnstileToken,
        }),
        headers: { "content-type": "application/json" },
        method: "POST",
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || "We could not send your recipe. Please try again later.");

      form.reset();
      syncRequired();
      resetTurnstile();
      setStatus("Thank you! Your recipe was sent to the Mason Recipes family.");
    } catch (error) {
      setStatus(error instanceof TypeError || !error.message ? "We could not send your recipe. Please try again later." : error.message);
      resetTurnstile();
    } finally {
      sendButton.disabled = false;
    }
  });

  loadTurnstile();
})();
