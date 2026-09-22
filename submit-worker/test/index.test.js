import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createWorker, SubmissionRateLimiter } from "../src/index.js";

const ORIGIN = "https://masonrecipes.github.io";

function spy(implementation) {
  const wrapped = (...arguments_) => {
    wrapped.calls.push(arguments_);
    return implementation(...arguments_);
  };
  wrapped.calls = [];
  return wrapped;
}

function request(body = {}, origin = ORIGIN) {
  return new Request("https://submit.example.workers.dev/submit", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "CF-Connecting-IP": "203.0.113.12",
      origin,
    },
    body: JSON.stringify({
      recipeName: "Grandma's Cookies",
      recipeText: "Mix, bake, and share.",
      submitterName: "Mason",
      turnstileToken: "valid-turnstile-token",
      ...body,
    }),
  });
}

function limiter(allowed = true) {
  return {
    idFromName: spy(() => "rate-limit-id"),
    get: spy(() => ({
      fetch: spy(() => Response.json({ allowed })),
    })),
  };
}

function environment(rateLimiter = limiter()) {
  return {
    ALLOWED_ORIGIN: ORIGIN,
    GITHUB_TOKEN: "token",
    SUBMISSION_RATE_LIMITER: rateLimiter,
    TURNSTILE_HOSTNAME: "masonrecipes.github.io",
    TURNSTILE_SECRET: "turnstile-secret",
  };
}

function successfulFetch() {
  return spy(async (url) => {
    if (url === "https://challenges.cloudflare.com/turnstile/v0/siteverify") {
      return Response.json({
        action: "recipe_submit",
        hostname: "masonrecipes.github.io",
        success: true,
      });
    }

    return new Response(null, { status: 201 });
  });
}

describe("recipe submission worker", () => {
  it("creates a labelled GitHub issue for a valid submission", async () => {
    const fetchMock = successfulFetch();
    const response = await createWorker({ fetcher: fetchMock }).fetch(request(), environment());

    assert.equal(response.status, 201);
    assert.deepEqual(await response.json(), { ok: true });
    assert.equal(fetchMock.calls.length, 2);

    const [, githubRequest] = fetchMock.calls[1];
    assert.equal(githubRequest.headers.authorization, "Bearer token");
    const issue = JSON.parse(githubRequest.body);
    assert.deepEqual(issue.labels, ["recipe-submission"]);
    assert.equal(issue.title, "[Website submission] Grandma's Cookies");
    assert.match(issue.body, /### Recipe Text\n\n```text\nMix, bake, and share\.\n```/);
  });

  it("refuses the third submission in a five-minute window", async () => {
    const fetchMock = successfulFetch();
    const values = new Map();
    const durableLimiter = new SubmissionRateLimiter({
      storage: {
        get: spy(async (key) => values.get(key)),
        put: spy(async (key, value) => values.set(key, value)),
      },
    });
    const rateLimiter = {
      idFromName: spy(() => "rate-limit-id"),
      get: spy(() => durableLimiter),
    };
    const testWorker = createWorker({ fetcher: fetchMock });

    assert.equal((await testWorker.fetch(request(), environment(rateLimiter))).status, 201);
    assert.equal((await testWorker.fetch(request(), environment(rateLimiter))).status, 201);
    const response = await testWorker.fetch(request(), environment(rateLimiter));

    assert.equal(response.status, 429);
    assert.deepEqual(await response.json(), { error: "Please wait a few minutes before submitting another recipe." });
    assert.equal(fetchMock.calls.length, 5);
  });

  it("rejects a submission without the recipe text", async () => {
    const fetchMock = successfulFetch();
    const response = await createWorker({ fetcher: fetchMock }).fetch(request({ recipeText: "" }), environment());

    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: "Please enter the recipe details." });
    assert.equal(fetchMock.calls.length, 0);
  });

  it("rejects fields that exceed their length limits", async () => {
    const fetchMock = successfulFetch();
    const response = await createWorker({ fetcher: fetchMock }).fetch(request({ recipeText: "a".repeat(12_001) }), environment());

    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: "The recipe details are too long. Please keep them under 12,000 characters." });
    assert.equal(fetchMock.calls.length, 0);
  });

  it("rejects requests from another website", async () => {
    const fetchMock = successfulFetch();
    const response = await createWorker({ fetcher: fetchMock }).fetch(request({}, "https://example.com"), environment());

    assert.equal(response.status, 403);
    assert.deepEqual(await response.json(), { error: "This form can only be submitted from Mason Recipes." });
    assert.equal(fetchMock.calls.length, 0);
  });

  it("does not count failed spam checks toward the rate limit", async () => {
    const rateLimiter = limiter();
    const fetchMock = spy(async () => Response.json({ success: false }));
    const response = await createWorker({ fetcher: fetchMock }).fetch(request(), environment(rateLimiter));

    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: "Please complete the spam check and try again." });
    assert.equal(rateLimiter.get.calls.length, 0);
  });

  it("returns a CORS-readable error when an upstream call throws", async () => {
    const fetchMock = spy(async () => { throw new TypeError("network down"); });
    const response = await createWorker({ fetcher: fetchMock }).fetch(request(), environment());

    assert.equal(response.status, 502);
    assert.equal(response.headers.get("access-control-allow-origin"), ORIGIN);
    assert.deepEqual(await response.json(), { error: "We could not save your recipe right now. Please try again later." });
  });
});
