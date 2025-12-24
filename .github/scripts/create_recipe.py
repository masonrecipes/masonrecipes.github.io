#!/usr/bin/env python3
"""
Parse GitHub issue body and create a recipe markdown file.
"""

import os
import re
import sys


def parse_issue_body(body):
    """Parse the issue body to extract recipe fields."""
    fields = {}

    # Parse each field from the issue template format
    patterns = {
        'recipe_name': r'### Recipe Name\s*\n\s*(.+?)(?=\n###|\Z)',
        'category': r'### Recipe Category\s*\n\s*(.+?)(?=\n###|\Z)',
        'ingredients': r'### Ingredients\s*\n\s*(.+?)(?=\n###|\Z)',
        'instructions': r'### Instructions\s*\n\s*(.+?)(?=\n###|\Z)',
        'prep_time': r'### Prep Time \(optional\)\s*\n\s*(.+?)(?=\n###|\Z)',
        'cook_time': r'### Cook Time \(optional\)\s*\n\s*(.+?)(?=\n###|\Z)',
        'notes': r'### Notes \(optional\)\s*\n\s*(.+?)(?=\n###|\Z)',
        'author': r'### Recipe Author \(optional\)\s*\n\s*(.+?)(?=\n###|\Z)',
        'source': r'### Recipe Source \(optional\)\s*\n\s*(.+?)(?=\n###|\Z)',
        'contact': r'### Your Name/Contact \(optional\)\s*\n\s*(.+?)(?=\n###|\Z)',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, body, re.DOTALL)
        if match:
            value = match.group(1).strip()
            # Skip if it's just "_No response_" or empty
            if value and value != "_No response_":
                fields[key] = value

    return fields


def sanitize_filename(name):
    """Convert recipe name to a valid filename.

    Removes special characters, apostrophes, and other problematic characters.
    Converts spaces and hyphens to underscores.
    """
    # Remove apostrophes and other punctuation (David's -> Davids)
    filename = name.replace("'", "").replace('"', "")

    # Convert to lowercase
    filename = filename.lower()

    # Remove any characters that aren't alphanumeric, spaces, hyphens, or underscores
    filename = re.sub(r'[^\w\s-]', '', filename)

    # Replace spaces and hyphens with underscores
    filename = re.sub(r'[-\s]+', '_', filename)

    # Remove any leading/trailing underscores
    filename = filename.strip('_')

    # Ensure we have a valid filename (not empty)
    if not filename:
        filename = 'untitled_recipe'

    return filename + '.md'


def create_recipe_markdown(fields):
    """Generate the recipe markdown content."""
    recipe_name = fields.get('recipe_name', 'Untitled Recipe')
    category = fields.get('category', 'Uncategorized')

    # Start with YAML frontmatter
    content = "---\n"

    # Add tags based on category
    category_tags = {
        'Appetizers & Dips': ['appetizers', 'dips'],
        'Main Courses': ['main-course', 'entree'],
        'Sides & Soups': ['sides', 'soups'],
        'Desserts': ['desserts', 'sweets'],
        'Beverages': ['beverages', 'drinks'],
        'Sauces & Condiments': ['sauces', 'condiments'],
        'Breakfast': ['breakfast'],
        'Breads & Extras': ['breads', 'baking']
    }

    tags = category_tags.get(category, ['recipe'])
    content += "tags:\n"
    for tag in tags:
        content += f"  - {tag}\n"

    # Add author from dedicated field
    if 'author' in fields:
        content += f"author: {fields['author']}\n"
    else:
        content += "author:\n"

    # Add source from dedicated field
    if 'source' in fields:
        content += f"source: {fields['source']}\n"
    else:
        content += "source:\n"

    # Add prep and cook time if provided
    if 'prep_time' in fields:
        content += f"prep_time: {fields['prep_time']}\n"

    if 'cook_time' in fields:
        content += f"cook_time: {fields['cook_time']}\n"

    content += "---\n\n"

    # Start with the recipe title
    content += f"# {recipe_name}\n\n"

    # Add ingredients section
    if 'ingredients' in fields:
        content += "## Ingredients\n\n"
        content += f"{fields['ingredients']}\n\n"

    # Add instructions section
    if 'instructions' in fields:
        content += "## Instructions\n\n"
        content += f"{fields['instructions']}\n\n"

    # Add notes if provided
    if 'notes' in fields:
        content += "## Notes\n\n"
        content += f"{fields['notes']}\n\n"

    # Add submitter credit at the end if provided
    if 'contact' in fields:
        content += f"*Submitted by: {fields['contact']}*\n"

    return content


def main():
    try:
        # Get environment variables
        issue_body = os.environ.get('ISSUE_BODY', '')
        issue_title = os.environ.get('ISSUE_TITLE', '')

        if not issue_body:
            print("Error: ISSUE_BODY environment variable is empty", file=sys.stderr)
            sys.exit(1)

        # Parse the issue
        fields = parse_issue_body(issue_body)

        if 'recipe_name' not in fields:
            print("Error: Recipe name not found in issue", file=sys.stderr)
            print("Issue body:", issue_body[:500], file=sys.stderr)
            sys.exit(1)

        if 'category' not in fields:
            print("Error: Category not found in issue", file=sys.stderr)
            print("Available fields:", list(fields.keys()), file=sys.stderr)
            sys.exit(1)

        # Validate category is one of the allowed categories
        allowed_categories = {
            'Appetizers & Dips': 'appetizers_and_dips',
            'Main Courses': 'main_courses',
            'Sides & Soups': 'sides_and_soups',
            'Desserts': 'desserts',
            'Beverages': 'beverages',
            'Sauces & Condiments': 'sauces_and_condiments',
            'Breakfast': 'breakfast',
            'Breads & Extras': 'breads_and_extras'
        }

        if fields['category'] not in allowed_categories:
            print(f"Error: Invalid category '{fields['category']}'", file=sys.stderr)
            print(f"Allowed categories: {list(allowed_categories.keys())}", file=sys.stderr)
            sys.exit(1)

        # Get the folder name for the category
        category_folder = allowed_categories[fields['category']]

        # Generate filename
        filename = sanitize_filename(fields['recipe_name'])
        filepath = f"docs/recipes/{category_folder}/{filename}"

        # Ensure the category directory exists
        os.makedirs(f"docs/recipes/{category_folder}", exist_ok=True)

        # Check if file already exists
        if os.path.exists(filepath):
            print(f"Warning: Recipe file already exists at {filepath}", file=sys.stderr)
            # Add a number suffix to make it unique
            base_filename = filename[:-3]  # Remove .md
            counter = 1
            while os.path.exists(f"docs/recipes/{category_folder}/{base_filename}_{counter}.md"):
                counter += 1
            filename = f"{base_filename}_{counter}.md"
            filepath = f"docs/recipes/{category_folder}/{filename}"
            print(f"Using alternative filename: {filename}", file=sys.stderr)

        # Create the recipe markdown
        recipe_content = create_recipe_markdown(fields)

        # Write the file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(recipe_content)

        print(f"Created recipe file: {filepath}")

        # Set outputs for GitHub Actions
        # Remove "[RECIPE]: " prefix from title if present
        clean_title = re.sub(r'^\[RECIPE\]:\s*', '', fields['recipe_name'])

        github_output = os.environ.get('GITHUB_OUTPUT', '/dev/stdout')
        with open(github_output, 'a') as f:
            f.write(f"recipe_file={filename}\n")
            f.write(f"recipe_title={clean_title}\n")
            f.write(f"category={fields['category']}\n")

        print(f"✓ Successfully created recipe: {clean_title}")
        print(f"✓ Category: {fields['category']}")
        print(f"✓ Filename: {filename}")

    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
