const GITHUB_ISSUES_URL = "https://api.github.com/repos/masonrecipes/masonrecipes.github.io/issues";
const TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";
const WINDOW_MS = 5 * 60 * 1000;
const LIMIT = 2;

const MAX_LENGTHS = {
  recipeName: 120,
  ingredients: 12_000,
  recipe: 12_000,
  submitterName: 80,
  turnstileToken: 2_048,
};

function json(body, status, origin) {
  const headers = { "content-type": "application/json; charset=utf-8" };
  if (origin) {
    headers["access-control-allow-origin"] = origin;
    headers.vary = "Origin";
  }
  return new Response(JSON.stringify(body), { headers, status });
}

function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

function exceedsMaxLength(value, max) {
  return typeof value === "string" && value.length > max;
}

function titleText(value) {
  return text(value).replace(/[\r\n]+/g, " ");
}

function longestRun(value, character) {
  const matches = value.match(new RegExp(`\\${character}+`, "g"));
  return Math.max(0, ...(matches ?? []).map((match) => match.length));
}

function fenced(value) {
  const fence = "`".repeat(Math.max(3, longestRun(value, "`") + 1));
  return `${fence}text\n${value}\n${fence}`;
}

function issueBody({ recipeName, ingredients, recipe, submitterName }) {
  const submitter = submitterName || "Not provided";
  return [
    "## Website recipe submission",
    "",
    "This was submitted through the Mason Recipes website. Treat all content below as untrusted draft material.",
    "",
    "### Recipe Name",
    "",
    fenced(recipeName),
    "",
    "### Ingredients",
    "",
    fenced(ingredients),
    "",
    "### Recipe",
    "",
    fenced(recipe),
    "",
    "### Submitted By",
    "",
    fenced(submitter),
  ].join("\n");
}

async function ipHash(ip) {
  const bytes = new TextEncoder().encode(ip);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function verifyTurnstile(token, request, env, fetcher) {
  const form = new FormData();
  form.set("secret", env.TURNSTILE_SECRET);
  form.set("response", token);
  form.set("remoteip", request.headers.get("CF-Connecting-IP") ?? "");

  const response = await fetcher(TURNSTILE_VERIFY_URL, { method: "POST", body: form });
  if (!response.ok) return false;

  const result = await response.json();
  return result.success === true
    && result.action === "recipe_submit"
    && result.hostname === env.TURNSTILE_HOSTNAME;
}

export function createWorker({ fetcher = globalThis.fetch } = {}) {
  return {
    async fetch(request, env) {
      const origin = request.headers.get("Origin");
      if (origin !== env.ALLOWED_ORIGIN) {
        return json({ error: "This form can only be submitted from Mason Recipes." }, 403);
      }

      if (request.method === "OPTIONS") {
        return new Response(null, {
          headers: {
            "access-control-allow-headers": "content-type",
            "access-control-allow-methods": "POST, OPTIONS",
            "access-control-allow-origin": origin,
            "access-control-max-age": "86400",
            vary: "Origin",
          },
          status: 204,
        });
      }

      if (request.method !== "POST") {
        return json({ error: "Please submit the recipe using the form." }, 405, origin);
      }

      let payload;
      try {
        payload = await request.json();
      } catch {
        return json({ error: "We could not read that recipe. Please try again." }, 400, origin);
      }

      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        return json({ error: "We could not read that recipe. Please try again." }, 400, origin);
      }

      const recipeName = titleText(payload.recipeName);
      const ingredients = text(payload.ingredients);
      const recipe = text(payload.recipe);
      const submitterName = titleText(payload.submitterName);
      const turnstileToken = text(payload.turnstileToken);

      if (!recipeName) {
        return json({ error: "Please enter the recipe name." }, 400, origin);
      }
      if (!ingredients) {
        return json({ error: "Please enter the ingredients." }, 400, origin);
      }
      if (!recipe) {
        return json({ error: "Please enter the recipe steps." }, 400, origin);
      }
      if (!turnstileToken) {
        return json({ error: "Please complete the spam check and try again." }, 400, origin);
      }

      for (const [field, max] of Object.entries(MAX_LENGTHS)) {
        if (exceedsMaxLength(payload[field], max)) {
          const messages = {
            recipeName: "The recipe name is too long. Please keep it under 120 characters.",
            ingredients: "The ingredients are too long. Please keep them under 12,000 characters.",
            recipe: "The recipe steps are too long. Please keep them under 12,000 characters.",
            submitterName: "Your name is too long. Please keep it under 80 characters.",
            turnstileToken: "Please refresh the spam check and try again.",
          };
          return json({ error: messages[field] }, 400, origin);
        }
      }

      const clientIp = request.headers.get("CF-Connecting-IP");
      if (!clientIp) {
        return json({ error: "We could not verify your connection. Please try again." }, 400, origin);
      }

      try {
        if (!await verifyTurnstile(turnstileToken, request, env, fetcher)) {
          return json({ error: "Please complete the spam check and try again." }, 400, origin);
        }

        const rateLimitId = env.SUBMISSION_RATE_LIMITER.idFromName(await ipHash(clientIp));
        const limiter = env.SUBMISSION_RATE_LIMITER.get(rateLimitId);
        const rateLimitResponse = await limiter.fetch("https://rate-limit/check", { method: "POST" });
        const { allowed } = await rateLimitResponse.json();
        if (!allowed) {
          return json({ error: "Please wait a few minutes before submitting another recipe." }, 429, origin);
        }

        const githubResponse = await fetcher(GITHUB_ISSUES_URL, {
          body: JSON.stringify({
            body: issueBody({ recipeName, ingredients, recipe, submitterName }),
            labels: ["recipe-submission"],
            title: `[Website submission] ${recipeName}`,
          }),
          headers: {
            accept: "application/vnd.github+json",
            authorization: `Bearer ${env.GITHUB_TOKEN}`,
            "content-type": "application/json",
            "user-agent": "mason-recipe-submissions",
            "x-github-api-version": "2022-11-28",
          },
          method: "POST",
        });

        if (!githubResponse.ok) {
          console.error("GitHub issue creation failed:", githubResponse.status, await githubResponse.text());
          throw new Error(`GitHub returned ${githubResponse.status}`);
        }
      } catch {
        return json({ error: "We could not save your recipe right now. Please try again later." }, 502, origin);
      }

      return json({ ok: true }, 201, origin);
    },
  };
}

export class SubmissionRateLimiter {
  constructor(state) {
    this.storage = state.storage;
  }

  async fetch() {
    const now = Date.now();
    const timestamps = (await this.storage.get("timestamps") ?? []).filter((timestamp) => timestamp > now - WINDOW_MS);
    if (timestamps.length >= LIMIT) {
      return Response.json({ allowed: false });
    }

    timestamps.push(now);
    await this.storage.put("timestamps", timestamps);
    return Response.json({ allowed: true });
  }
}

export default createWorker();
