# Mason Recipes submission worker

This Cloudflare Worker accepts the simple recipe form on the Mason Recipes site and creates a `recipe-submission` GitHub issue. Website-created issues stay open for later AI or human formatting; turning an issue into a recipe page is a follow-up, not part of this Worker.

The worker rejects requests from origins other than `https://masonrecipes.github.io`, requires a verified Turnstile token, ignores a filled honeypot field, caps each field, and allows a client IP only two submission attempts in five minutes. The Durable Object binding serializes the per-IP counter so simultaneous requests cannot exceed that limit.

## One-time deployment

1. In Cloudflare Turnstile, create a managed widget for `masonrecipes.github.io`. Keep its site key for the public site configuration and its secret key for the Worker.
2. Create a fine-grained GitHub personal access token owned by an account that can create issues in `masonrecipes/masonrecipes.github.io`. Limit its repository access to that one repository and grant only **Issues: Read and write**. Do not grant Contents, Actions, or administration access.
3. Confirm that the repository has the `recipe-submission` label. The Worker uses it to make submissions easy to identify.
4. From this directory, install dependencies and authenticate Wrangler:

   ```sh
   npm ci
   npx wrangler login
   ```

5. Store the two secrets. Paste each value only into Wrangler's secret prompt; never add either value to this repository or the site configuration.

   ```sh
   npx wrangler secret put GITHUB_TOKEN
   npx wrangler secret put TURNSTILE_SECRET
   ```

6. Deploy and copy the HTTPS Worker URL printed by Wrangler:

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
