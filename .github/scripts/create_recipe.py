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
    """Convert recipe name to a valid filename."""
    # Remove special characters and convert to lowercase with underscores
    filename = name.lower()
    filename = re.sub(r'[^\w\s-]', '', filename)
    filename = re.sub(r'[-\s]+', '_', filename)
    return filename + '.md'


def create_recipe_markdown(fields):
    """Generate the recipe markdown content."""
    recipe_name = fields.get('recipe_name', 'Untitled Recipe')

    # Start with the recipe title
    content = f"# {recipe_name}\n\n"

    # Add ingredients section
    if 'ingredients' in fields:
        content += "## Ingredients\n\n"
        content += f"{fields['ingredients']}\n\n"

    # Add instructions section
    if 'instructions' in fields:
        content += "## Instructions\n\n"
        content += f"{fields['instructions']}\n\n"

    # Add prep time if provided
    if 'prep_time' in fields:
        content += f"**Prep Time:** {fields['prep_time']}\n\n"

    # Add cook time if provided
    if 'cook_time' in fields:
        content += f"**Cook Time:** {fields['cook_time']}\n\n"

    # Add notes if provided
    if 'notes' in fields:
        content += "## Notes\n\n"
        content += f"{fields['notes']}\n\n"

    # Add credit if provided
    if 'contact' in fields:
        content += f"*Recipe submitted by: {fields['contact']}*\n"

    return content


def main():
    # Get environment variables
    issue_body = os.environ.get('ISSUE_BODY', '')
    issue_title = os.environ.get('ISSUE_TITLE', '')

    # Parse the issue
    fields = parse_issue_body(issue_body)

    if 'recipe_name' not in fields:
        print("Error: Recipe name not found in issue", file=sys.stderr)
        sys.exit(1)

    if 'category' not in fields:
        print("Error: Category not found in issue", file=sys.stderr)
        sys.exit(1)

    # Generate filename
    filename = sanitize_filename(fields['recipe_name'])
    filepath = f"docs/recipes/{filename}"

    # Create the recipe markdown
    recipe_content = create_recipe_markdown(fields)

    # Write the file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(recipe_content)

    print(f"Created recipe file: {filepath}")

    # Set outputs for GitHub Actions
    # Remove "[RECIPE]: " prefix from title if present
    clean_title = re.sub(r'^\[RECIPE\]:\s*', '', fields['recipe_name'])

    with open(os.environ.get('GITHUB_OUTPUT', '/dev/stdout'), 'a') as f:
        f.write(f"recipe_file={filename}\n")
        f.write(f"recipe_title={clean_title}\n")
        f.write(f"category={fields['category']}\n")


if __name__ == '__main__':
    main()
