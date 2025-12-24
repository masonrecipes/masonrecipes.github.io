#!/usr/bin/env python3
"""
Update mkdocs.yml to add a new recipe to the navigation.
"""

import os
import sys
import re


def add_recipe_to_nav(mkdocs_path, recipe_file, recipe_title, category, category_folder):
    """Add the new recipe to the appropriate category in mkdocs.yml."""

    try:
        # Read the file as text to preserve formatting and custom YAML tags
        with open(mkdocs_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: {mkdocs_path} not found", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading {mkdocs_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not content.strip():
        print(f"Error: {mkdocs_path} is empty", file=sys.stderr)
        sys.exit(1)

    # Find the category section
    # Pattern: finds "    - Category Name:" followed by recipe entries
    category_pattern = rf"^(    - {re.escape(category)}:)\s*$"

    lines = content.split("\n")
    category_line_idx = None

    # Find the line with the category
    for idx, line in enumerate(lines):
        if re.match(category_pattern, line):
            category_line_idx = idx
            break

    if category_line_idx is None:
        print(f"Error: Category '{category}' not found in mkdocs.yml", file=sys.stderr)
        print("Available categories in mkdocs.yml:", file=sys.stderr)
        # Try to list available categories for debugging
        for line in lines:
            if re.match(r"^    - .+:$", line):
                print(f"  {line.strip()}", file=sys.stderr)
        sys.exit(1)

    # Find where this category's recipes end (next category or section)
    category_end_idx = category_line_idx + 1
    for idx in range(category_line_idx + 1, len(lines)):
        # Check if we hit another category or main section
        if re.match(r"^    - \w", lines[idx]) or re.match(r"^  - \w", lines[idx]):
            category_end_idx = idx
            break
        # If we hit a non-recipe line (like empty or different section)
        if lines[idx] and not lines[idx].startswith("      - "):
            category_end_idx = idx
            break
    else:
        # We reached the end of the file
        category_end_idx = len(lines)

    # Extract existing recipes in this category
    recipes = []
    for idx in range(category_line_idx + 1, category_end_idx):
        line = lines[idx]
        if line.strip() and line.startswith("      - "):
            recipes.append((idx, line))

    # Add the new recipe with category folder path
    new_recipe_line = f"      - {recipe_title}: recipes/{category_folder}/{recipe_file}"
    recipes.append((None, new_recipe_line))

    # Sort recipes alphabetically by title (extract title from "      - Title: path")
    def get_recipe_title(recipe_tuple):
        _, line = recipe_tuple
        match = re.match(r"\s*- ([^:]+):", line)
        if match:
            return match.group(1).strip().lower()
        return ""

    recipes.sort(key=get_recipe_title)

    # Find where to insert the new recipe
    insert_idx = None
    for idx, (original_idx, line) in enumerate(recipes):
        if line == new_recipe_line:
            # This is our new recipe, find where to insert it
            if idx == 0:
                # Insert at the beginning
                insert_idx = category_line_idx + 1
            else:
                # Insert after the previous recipe
                prev_original_idx = recipes[idx - 1][0]
                if prev_original_idx is not None:
                    insert_idx = prev_original_idx + 1
                else:
                    # Previous recipe was also new (shouldn't happen)
                    insert_idx = category_line_idx + 1
            break

    # Insert the new recipe at the correct position
    if insert_idx is not None:
        lines.insert(insert_idx, new_recipe_line)
    else:
        print("Error: Could not determine where to insert the recipe", file=sys.stderr)
        sys.exit(1)

    # Write back to file
    try:
        # First write to a backup file
        backup_path = mkdocs_path + ".backup"
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Then write the updated content
        with open(mkdocs_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"✓ Added '{recipe_title}' to '{category}' category in mkdocs.yml")

        # Remove backup if successful
        try:
            os.remove(backup_path)
        except:
            pass  # Ignore errors removing backup

    except IOError as e:
        print(f"Error writing to {mkdocs_path}: {e}", file=sys.stderr)
        # Try to restore from backup
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_content = f.read()
                with open(mkdocs_path, "w", encoding="utf-8") as f:
                    f.write(backup_content)
                print("Restored mkdocs.yml from backup", file=sys.stderr)
            except:
                pass
        sys.exit(1)


def main():
    try:
        recipe_file = os.environ.get("RECIPE_FILE")
        recipe_title = os.environ.get("RECIPE_TITLE")
        category = os.environ.get("CATEGORY")

        # Validate inputs
        if not recipe_file:
            print("Error: RECIPE_FILE environment variable is not set", file=sys.stderr)
            sys.exit(1)

        if not recipe_title:
            print("Error: RECIPE_TITLE environment variable is not set", file=sys.stderr)
            sys.exit(1)

        if not category:
            print("Error: CATEGORY environment variable is not set", file=sys.stderr)
            sys.exit(1)

        # Validate filename
        if not recipe_file.endswith(".md"):
            print(f"Error: Recipe file '{recipe_file}' must end with .md", file=sys.stderr)
            sys.exit(1)

        if "/" in recipe_file or "\\" in recipe_file:
            print(
                f"Error: Recipe file '{recipe_file}' should be a filename, not a path",
                file=sys.stderr,
            )
            sys.exit(1)

        # Map category to folder name
        category_folders = {
            "Appetizers & Dips": "appetizers_and_dips",
            "Main Courses": "main_courses",
            "Sides & Soups": "sides_and_soups",
            "Desserts": "desserts",
            "Beverages": "beverages",
            "Sauces & Condiments": "sauces_and_condiments",
            "Breakfast": "breakfast",
            "Breads & Extras": "breads_and_extras",
        }

        category_folder = category_folders.get(category)
        if not category_folder:
            print(f"Error: Unknown category '{category}'", file=sys.stderr)
            sys.exit(1)

        mkdocs_path = "mkdocs.yml"

        if not os.path.exists(mkdocs_path):
            print(f"Error: {mkdocs_path} not found in current directory", file=sys.stderr)
            print(f"Current directory: {os.getcwd()}", file=sys.stderr)
            sys.exit(1)

        print(f"Processing recipe: {recipe_title}")
        print(f"  File: {recipe_file}")
        print(f"  Category: {category}")
        print(f"  Folder: {category_folder}")

        add_recipe_to_nav(mkdocs_path, recipe_file, recipe_title, category, category_folder)

    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
