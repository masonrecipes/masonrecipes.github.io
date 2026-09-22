# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.

## Recipe submissions

- The browser form is supplied through the `extra_javascript` and `extra_css` hooks in `mkdocs.yml`; its public endpoint and Turnstile site key stay blank in `docs/javascripts/recipe-submission-config.js` until the Worker has been deployed.
- `submit-worker/README.md` is the authoritative deployment and secret-configuration runbook. Website-created issues deliberately remain open for later AI or human recipe formatting; `.github/workflows/process_recipe_submission.yml` continues to process only the richer GitHub issue template submissions.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
