# Mason Recipes submission worker

This Cloudflare Worker accepts the simple recipe form on the Mason Recipes site and creates a `recipe-submission` GitHub issue. It also serves `POST /draft`, which the drafting workflow calls to have `openai/gpt-5.6-luna` (Workers AI, through the `AI` binding) format a recipe as strict JSON. `/draft` has no CORS and answers 401 to anything but a valid GitHub Actions OIDC token for this repository's `main` branch with the audience `mason-recipe-submissions`. `openai/gpt-5.6-luna` on Workers AI is billed from the account's prepaid AI Gateway (unified billing) credits; when that balance is empty, every draft fails closed with `model-request-failed`. See "AI drafting for website submissions" in the root `README.md`.

`POST /fill` powers the form's **Fill from link** button. It takes `{ url, recipeName, turnstileToken }`, checks the origin and a Turnstile token like a submission, allows a client IP five fills in five minutes (separate from the two submissions), and fetches the page under the same rules as `.github/scripts/link_import.py`: http/https on default ports, every host resolved through Cloudflare DNS-over-HTTPS and refused unless all its addresses are public, every redirect hop re-checked (at most three), a 2 MB cap and a 10 second timeout. It reads the page's schema.org Recipe JSON-LD first; only without one does it send the page's visible text to Luna, and at most 50 of those AI fallbacks run per day across the whole site. It answers `{ title, ingredients: string[], steps: string[] }` or a plain `error` message telling the person they can still send the link. When the site answers with a bot challenge (403 or 503 with `cf-mitigated: challenge`, or Cloudflare's "Just a moment..." page), the message asks the person to copy the ingredients and steps into the form instead, since no automatic read gets past it; Cloudflare Browser Rendering was tried and is challenged too.

The worker rejects requests from origins other than `https://masonrecipes.github.io`, requires a verified Turnstile token, caps each field, and allows a client IP only two verified submission attempts in five minutes. Failed spam checks do not count toward that limit. The Durable Object binding serializes the per-IP counter so simultaneous requests cannot exceed that limit.

## One-time deployment

1. In Cloudflare Turnstile, create a managed widget for `masonrecipes.github.io`. Keep its site key for the public site configuration and its secret key for the Worker.
2. Create a fine-grained GitHub personal access token owned by an account that can create issues in `masonrecipes/masonrecipes.github.io`. Limit its repository access to that one repository and grant only **Issues: Read and write**. Do not grant Contents, Actions, or administration access.
3. Confirm that the repository has the `recipe-submission` label. The Worker uses it to make submissions easy to identify.
4. From this directory, authenticate Wrangler (`npx` downloads it on first use):

   ```sh
   npx wrangler login
   ```

5. Store the two secrets. Paste each value only into Wrangler's secret prompt; never add either value to this repository or the site configuration.

   ```sh
   npx wrangler secret put GITHUB_TOKEN
   npx wrangler secret put TURNSTILE_SECRET
   ```

6. Deploy and copy the HTTPS Worker URL printed by Wrangler. Redeploy the same way after any change to this directory merges; the `AI` binding needs no secret.

   ```sh
   npx wrangler deploy
   ```

7. In `docs/javascripts/recipe-submission-config.js`, set `endpoint` to that Worker URL and `turnstileSiteKey` to the public Turnstile site key. Commit and deploy the site. Until both values are configured, the button is deliberately absent.

`wrangler.jsonc` restricts the Worker to the production site origin and expects Turnstile tokens for the `recipe_submit` action on `masonrecipes.github.io`. Change those values only when intentionally adding another deployed site hostname.

## Local checks

```sh
npm test
npx wrangler deploy --dry-run
```
