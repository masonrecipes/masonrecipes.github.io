# Mason Recipes

A collection of delicious family recipes, beautifully organized and accessible at [masonrecipes.github.io](https://masonrecipes.github.io).

## About

This repository contains the source files for the Mason Recipes website, built with [Zensical](https://zensical.org/), reading the Material-style `mkdocs.yml` configuration. All recipes are stored as markdown files and automatically deployed to GitHub Pages.

## Features

- Clean, modern recipe presentation
- Organized by category for easy navigation
- Search functionality to quickly find recipes
- Responsive design for mobile and desktop
- Automated deployment via GitHub Actions

## Structure

```text
├── docs/
│   ├── index.md           # Site home page
│   ├── recipes/           # Recipe markdown files (organized by category)
│   └── contact.md         # Contact information
├── mkdocs.yml             # MkDocs configuration
└── .github/workflows/     # GitHub Actions automation
```

## Contributing

We welcome contributions! To add a recipe:

1. Fork the repository
2. Create a new branch for your recipe
3. Add your recipe as a markdown file in the `docs/recipes/` folder
4. Update the `mkdocs.yml` file to include your recipe in the appropriate category under the `nav` section
5. Submit a pull request

### Recipe Format

1. Create a `.md` file with a simple structure:

    ```markdown
    # Recipe Name

    ## Ingredients

    - Ingredient 1
    - Ingredient 2

    ## Instructions

    1. Step 1
    2. Step 2
    ```

1. When the file is created, save it.
1. Navigate to the [mkdocs.yml](mkdocs.yml).
1. Add the name of your file under the appropriate section, as if it were a pathway to it (see the structure in the file already)

## Development

To build and preview the site locally, it's recommended to use a virtual environment:

### Using a Virtual Environment (Recommended)

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Preview the site
zensical serve

# Build the site
zensical build
```

### Manual Installation (Alternative)

If you prefer not to use a virtual environment:

```bash
# Install dependencies
pip install zensical==0.0.63

# Preview the site
zensical serve

# Build the site
zensical build
```

The site will be available at `http://localhost:8000`.

## AI drafting for website submissions

When the website form creates a `recipe-submission` issue, `.github/workflows/process_website_submission.yml` drafts a recipe page and opens a pull request for review. It never merges. The model (OpenAI `gpt-5.6-luna` on Cloudflare Workers AI) only tidies the recipe text and picks one of the eight categories through a strict JSON schema; it gets no tools, no repository token, and never sees the submitter's name or source link. Code in `.github/scripts/website_recipe.py` then renders the page, updates navigation, credits a named submitter (a `By Name` tag, `author` metadata, an Authors page entry, and a "Submitted by" line), links an `https` source, and flags an `http` source in the PR for review. The workflow builds the site before opening the PR. If anything looks wrong, such as changed quantities, raw HTML, or a duplicate title, it comments on the issue and leaves it open for manual formatting.

A submitter can also send just a recipe name and a link. The workflow then fetches that page from `.github/scripts/link_import.py`, which only allows `http`/`https` on the default ports. It resolves every host (including each redirect hop) and refuses private, loopback, link-local and metadata addresses. It connects to the address it checked, gives up after 5 redirects, 2 MB or 20 seconds, and never runs the page's scripts. If the page has a schema.org `Recipe` block (JSON-LD), its ingredients and steps are copied over as they are. If not, the page's visible text goes to the model as untrusted data, and every number in the draft must appear on that page. When neither works, no PR is opened and the issue gets a comment asking for the ingredients and steps as text. A site that answers with a bot challenge (such as Cloudflare's "Just a moment..." page) gets a comment naming the site and saying it blocks automatic reading.

Before sending, the form's **Fill from link** button can fill the Ingredients and Recipe boxes from the link so the submitter can review them; see `submit-worker/README.md` for how `/fill` reads the page and its limits.

### How the workflow reaches the model

The workflow does not call the model itself. It asks the recipe submission Worker (`submit-worker/`) to draft the recipe by POSTing the recipe text to the Worker's `/draft` endpoint. It proves who it is with a short-lived GitHub Actions OIDC token minted for the audience `mason-recipe-submissions`. The Worker checks that token's signature against GitHub's published keys and accepts it only from `masonrecipes/masonrecipes.github.io` on `refs/heads/main`. It then calls `openai/gpt-5.6-luna` through its Workers AI binding with the fixed instructions and strict schema, and returns only schema-valid JSON. No API key or cloud credential is stored in GitHub or in the Worker.

The workflow always calls the fixed endpoint `https://mason-recipe-submissions.david-beihl.workers.dev/draft`, so the token can only go to the recipe helper.

Setup is only a Worker redeploy: after a change to `submit-worker/` merges, archive `submit-worker` from merged `HEAD` into a scratch directory and run `npx wrangler deploy` there, never from the repository root. The `AI` binding in `wrangler.jsonc` uses Workers AI on the same Cloudflare account, so there is nothing else to configure.

To retry a submission after a failure, remove and re-add the `recipe-submission` label. If a draft branch `website-recipe-<issue number>` already exists, delete it first.

### Tests

```bash
python3 -m unittest discover -s .github/scripts -p 'test_*.py'
(cd submit-worker && npm ci && npm test)
```

## Deployment

The site is automatically deployed to GitHub Pages whenever changes are pushed to the `main` branch. The GitHub Actions workflow builds the Zensical site and publishes it to the `gh-pages` branch.

## License

This project is licensed under a custom license - see the [LICENSE](LICENSE) file for details. The recipes are available for personal, non-commercial use only.

## Issues or Requests

For any issues or requests, please navigate to [our issues](https://github.com/masonrecipes/masonrecipes.github.io/issues/new/choose) and fill out the appropriate template.
