# Mason Recipes

A collection of delicious family recipes, beautifully organized and accessible at [masonrecipes.github.io](https://masonrecipes.github.io).

## About

This repository contains the source files for the Mason Recipes website, built with [MkDocs](https://www.mkdocs.org/) and the [Material theme](https://squidfunk.github.io/mkdocs-material/). All recipes are stored as markdown files and automatically deployed to GitHub Pages.

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

To build and preview the site locally:

```bash
# Install dependencies
pip install mkdocs mkdocs-material pymdown-extensions

# Preview the site
mkdocs serve

# Build the site
mkdocs build
```

The site will be available at `http://localhost:8000`.

## Deployment

The site is automatically deployed to GitHub Pages whenever changes are pushed to the `main` branch. The GitHub Actions workflow builds the mkdocs site and publishes it to the `gh-pages` branch.

## License

Feel free to use these recipes for personal use and sharing!

## Issues or Requests

For any issues or requests, please navigate to [our issues](https://github.com/masonrecipes/masonrecipes.github.io/issues/new/choose) and fill out the appropriate template.
