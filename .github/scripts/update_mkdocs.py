#!/usr/bin/env python3
"""
Update mkdocs.yml to add a new recipe to the navigation.
"""

import os
import sys
import yaml


def find_category_index(nav_items, category):
    """Find the index and item for a given category in the Recipes section."""
    recipes_section = None

    # Find the Recipes section
    for item in nav_items:
        if isinstance(item, dict) and 'Recipes' in item:
            recipes_section = item['Recipes']
            break

    if recipes_section is None:
        print("Error: Could not find Recipes section in navigation", file=sys.stderr)
        sys.exit(1)

    # Find the category within Recipes
    for idx, section in enumerate(recipes_section):
        if isinstance(section, dict) and category in section:
            return idx, section[category]

    print(f"Error: Could not find category '{category}' in navigation", file=sys.stderr)
    sys.exit(1)


def add_recipe_to_nav(mkdocs_path, recipe_file, recipe_title, category):
    """Add the new recipe to the appropriate category in mkdocs.yml."""

    # Load the mkdocs.yml file
    with open(mkdocs_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Find the Recipes section
    nav = config.get('nav', [])
    recipes_section = None
    recipes_index = None

    for idx, item in enumerate(nav):
        if isinstance(item, dict) and 'Recipes' in item:
            recipes_section = item['Recipes']
            recipes_index = idx
            break

    if recipes_section is None:
        print("Error: Could not find Recipes section", file=sys.stderr)
        sys.exit(1)

    # Find the category
    category_found = False
    for section in recipes_section:
        if isinstance(section, dict) and category in section:
            category_list = section[category]
            # Add the new recipe
            new_entry = {recipe_title: f"recipes/{recipe_file}"}
            category_list.append(new_entry)
            # Sort the category alphabetically by recipe title
            section[category] = sorted(category_list, key=lambda x: list(x.keys())[0] if isinstance(x, dict) else x)
            category_found = True
            break

    if not category_found:
        print(f"Error: Category '{category}' not found", file=sys.stderr)
        sys.exit(1)

    # Write back to mkdocs.yml
    with open(mkdocs_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Added '{recipe_title}' to '{category}' category in mkdocs.yml")


def main():
    recipe_file = os.environ.get('RECIPE_FILE')
    recipe_title = os.environ.get('RECIPE_TITLE')
    category = os.environ.get('CATEGORY')

    if not all([recipe_file, recipe_title, category]):
        print("Error: Missing required environment variables", file=sys.stderr)
        sys.exit(1)

    mkdocs_path = 'mkdocs.yml'

    if not os.path.exists(mkdocs_path):
        print(f"Error: {mkdocs_path} not found", file=sys.stderr)
        sys.exit(1)

    add_recipe_to_nav(mkdocs_path, recipe_file, recipe_title, category)


if __name__ == '__main__':
    main()
