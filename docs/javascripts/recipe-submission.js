(() => {
  const config = window.MASON_RECIPE_SUBMISSION_CONFIG;
  if (!config?.endpoint || !config?.turnstileSiteKey || !config.endpoint.startsWith("https://")) return;

  const button = document.createElement("button");
  button.className = "recipe-submission-trigger md-button md-button--primary";
  button.type = "button";
  button.textContent = "Submit a recipe";
  button.setAttribute("aria-haspopup", "dialog");

  const dialog = document.createElement("dialog");
  dialog.className = "recipe-submission-dialog";
  dialog.setAttribute("aria-labelledby", "recipe-submission-title");
  dialog.innerHTML = `
    <form class="recipe-submission-form" novalidate>
      <div class="recipe-submission-heading">
        <h2 id="recipe-submission-title">Share a recipe</h2>
        <button class="recipe-submission-close" type="button" aria-label="Close recipe form">×</button>
      </div>
      <p>Send us the recipe in whatever form you have it. We will take it from there.</p>
      <label for="recipe-submission-name">Recipe name <span aria-hidden="true">*</span></label>
      <input id="recipe-submission-name" name="recipeName" maxlength="120" required autocomplete="off">
      <label for="recipe-submission-text">Recipe <span aria-hidden="true">*</span></label>
      <textarea id="recipe-submission-text" name="recipeText" maxlength="12000" required rows="12"></textarea>
      <label for="recipe-submission-submitter">Your name <span class="recipe-submission-optional">(optional, shown publicly)</span></label>
      <input id="recipe-submission-submitter" name="submitterName" maxlength="80" autocomplete="name" aria-describedby="recipe-submission-submitter-note">
      <p id="recipe-submission-submitter-note" class="recipe-submission-optional">If you add your name, it will appear publicly with your recipe.</p>
      <div class="recipe-submission-turnstile" aria-label="Spam check"></div>
      <p class="recipe-submission-status" role="status" aria-live="polite"></p>
      <button class="recipe-submission-send md-button md-button--primary" type="submit">Send recipe</button>
    </form>`;

  // Zensical scopes .md-button and form typography under .md-typeset.
  const root = document.createElement("div");
  root.className = "md-typeset";
  root.append(button, dialog);
  document.body.append(root);

  const form = dialog.querySelector("form");
  const closeButton = dialog.querySelector(".recipe-submission-close");
  const sendButton = dialog.querySelector(".recipe-submission-send");
  const status = dialog.querySelector(".recipe-submission-status");
  let turnstileToken = "";
  let widgetId;

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

  button.addEventListener("click", () => {
    if (typeof dialog.showModal !== "function") return;
    dialog.showModal();
    renderTurnstile();
    dialog.querySelector("#recipe-submission-name").focus();
  });
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
          recipeText: fields.get("recipeText"),
          submitterName: fields.get("submitterName"),
          turnstileToken,
        }),
        headers: { "content-type": "application/json" },
        method: "POST",
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || "We could not send your recipe. Please try again later.");

      form.reset();
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
