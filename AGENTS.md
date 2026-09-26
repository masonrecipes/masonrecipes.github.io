# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.

## Recipe submissions

- The browser form is supplied through the `extra_javascript` and `extra_css` hooks in `mkdocs.yml`; its public endpoint and Turnstile site key live in `docs/javascripts/recipe-submission-config.js`, and the button stays hidden if either is blank.
- `submit-worker/README.md` is the authoritative deployment and secret-configuration runbook. `.github/workflows/process_recipe_submission.yml` processes only the richer GitHub issue template submissions.
- Website-created issues are drafted into review-only PRs by `.github/workflows/process_website_submission.yml`. The Action POSTs the recipe text to the Worker's `/draft` with a GitHub OIDC token; the Worker (`submit-worker/src/index.js`) verifies it, holds the model instructions and schema, and calls Workers AI (`openai/gpt-5.6-luna`). Deploy Worker changes after merge using the scratch archive workflow in `submit-worker/README.md`, never from the worktree. The model returns strict JSON only; `.github/scripts/website_recipe.py` owns paths, tags, escaping and fail-closed checks. `submit-worker/test/form.test.js` runs the real form script in jsdom. The issue body format it parses is defined by `issueBody()` in `submit-worker/src/index.js`; change both together. Link-only submissions are fetched and parsed by `.github/scripts/link_import.py` (SSRF-guarded; tests fake DNS and sockets, HTML fixtures live in `.github/scripts/fixtures/`). The form's "Fill from link" button calls the Worker's `/fill`, a JavaScript port of the same fetch and JSON-LD rules that reuses those fixtures; change both together.

## Running tests

- `python3 evals/run.py` is the single green-or-red command (Worker `node --test` plus Python unittest); it installs `requirements-test.txt` into gitignored `.pydeps` and prints `{"pass_rate": ...}` last. `software-success.yaml` points the agent loop at it, and `.github/workflows/tests.yml` runs it on PRs.

## Recipe style

- `submit-worker/recipe-style.json` owns units, spelling, title case and first-person rules for both the formatter and the Worker prompt; see `.agents/skills/recipe-style/SKILL.md`. CI runs `scripts/format-recipes.sh --check`; `recipe-number-baseline.json` pins each cleaned recipe's numbers.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
