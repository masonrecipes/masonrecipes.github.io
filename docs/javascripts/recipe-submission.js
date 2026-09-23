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
      <p>Send us the recipe in whatever form you have it. We will take it from there. Found it online? Paste the link and we can read the ingredients and steps from the page.</p>
      <label for="recipe-submission-name">Recipe name <span aria-hidden="true">*</span></label>
      <input id="recipe-submission-name" name="recipeName" maxlength="120" required autocomplete="off">
      <label for="recipe-submission-source">Inspired by (link) <span class="recipe-submission-optional">(optional)</span></label>
      <input id="recipe-submission-source" name="sourceUrl" type="url" maxlength="2048" autocomplete="url" inputmode="url" placeholder="https://example.com/recipe">
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
  const status = dialog.querySelector(".recipe-submission-status");
  let turnstileToken = "";
  let widgetId;

  // A valid http(s) link lets us read the ingredients and steps from that page.
  function syncRequired() {
    const hasLink = sourceInput.validity.valid && /^https?:\/\/\S+$/i.test(sourceInput.value.trim());
    for (const field of recipeText) field.required = !hasLink;
    for (const mark of dialog.querySelectorAll(".recipe-submission-required")) mark.hidden = hasLink;
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

  sourceInput.addEventListener("input", syncRequired);
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
