---
name: recipe-style
description: Format or review Mason Recipes pages with the repository's deterministic house style.
---

# Recipe style

`submit-worker/recipe-style.json` is the single source for headings, units, spelling, proper nouns, acronyms, title casing and first-person handling. It lives under `submit-worker/` so the Worker deploy archive includes it. Do not copy its rules into a prompt or a hand-written checklist.

Format a recipe or all recipes with `scripts/format-recipes.sh [path]`; use `scripts/format-recipes.sh --check [path]` to review without writing changes. The formatter preserves every numeric token and rejects a change that would not.

For website drafts, `submit-worker/src/index.js` reads the same JSON to build the model instruction and `.github/scripts/website_recipe.py` applies the deterministic normalizer before rendering. Keep first-person wording written by the family. Move a copied source blogger's aside from an ingredient line to a neutral `Notes` item by hand; the formatter rejects an ingredient line containing a word from `first_person.rejected_in_ingredients`.
