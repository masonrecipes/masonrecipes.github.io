# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.

## Recipe submissions

- The browser form is supplied through the `extra_javascript` and `extra_css` hooks in `mkdocs.yml`; its public endpoint and Turnstile site key live in `docs/javascripts/recipe-submission-config.js`, and the button stays hidden if either is blank.
- `submit-worker/README.md` is the authoritative deployment and secret-configuration runbook. `.github/workflows/process_recipe_submission.yml` processes only the richer GitHub issue template submissions.
- Website-created issues are drafted into review-only PRs by `.github/workflows/process_website_submission.yml` (model on Azure AI Foundry via OIDC; setup in README "AI drafting for website submissions"). The model returns strict JSON only; `.github/scripts/website_recipe.py` owns paths, tags, escaping and fail-closed checks. Tests: `python3 -m unittest discover -s .github/scripts -p 'test_*.py'`. The issue body format it parses is defined by `issueBody()` in `submit-worker/src/index.js`; change both together. Link-only submissions are fetched and parsed by `.github/scripts/link_import.py` (SSRF-guarded; tests fake DNS and sockets, HTML fixtures live in `.github/scripts/fixtures/`).

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
