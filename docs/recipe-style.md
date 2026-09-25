# Recipe drafting style

This guide distills the established patterns in `docs/recipes/` for website-submission drafts. The Worker carries these rules as fixed instructions; the renderer in `.github/scripts/website_recipe.py` owns the Markdown structure and metadata.

## Page structure

- Use YAML front matter with category tags, then an optional `By Name` tag and `author` value, and an optional `source` value.
- Use one title-cased `# Recipe Name`, then `## Ingredients` and `## Instructions`. Render `## Notes` only for submitted tips or serving notes.
- Use `###` only when the submission itself names a component such as Cake, Icing, Crust, or Filling. Do not add a headnote, story, image caption, servings, or editorial copy.

## Ingredients and instructions

- Put one ingredient on each plain line. State a submitted quantity and unit before the ingredient, retain its spelling and abbreviation exactly, and never convert, scale, round, add, or remove numbers.
- Write one ordered, concise instruction at a time. Keep the submitted order and use practical, plain-language imperative phrasing when the submitted wording supports it.
- Keep the voice warm, direct, and unadorned, like a family cookbook. Correct only clear capitalization, punctuation, and list formatting; do not add or omit facts.

## Classification and credit

- Choose one existing category only: Appetizers & Dips, Main Courses, Sides & Soups, Desserts, Beverages, Sauces & Condiments, Breakfast, or Breads & Extras. The renderer derives its folder and category tags.
- Preserve the existing submitter credit and HTTPS source-link rules. The model never receives either field.
