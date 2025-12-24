#!/usr/bin/env python3
"""
Remove extra blank lines between list items in recipe markdown files.
This script processes all markdown files in docs/recipes/ directory.
"""

import os
import re
from pathlib import Path

def remove_list_spacing(file_path):
    """Remove blank lines between list items in a markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match blank lines between list items (both dash and numbered lists)
    # This matches: list item + blank line(s) + another list item
    # For dash lists: - item\n\n- item
    # For numbered lists: 1. item\n\n2. item
    
    # Remove blank lines between dash list items
    content = re.sub(r'(^- .+)\n\n+(^- )', r'\1\n\2', content, flags=re.MULTILINE)
    
    # Remove blank lines between numbered list items
    # Match pattern like "1. item" followed by blank line(s) and "2. item"
    content = re.sub(r'(^\d+\. .+)\n\n+(^\d+\. )', r'\1\n\2', content, flags=re.MULTILINE)
    
    # Only write if content changed
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    recipes_dir = Path('docs/recipes')
    
    if not recipes_dir.exists():
        print(f"Error: {recipes_dir} directory not found")
        return
    
    # Find all markdown files
    md_files = list(recipes_dir.glob('*.md'))
    
    if not md_files:
        print(f"No markdown files found in {recipes_dir}")
        return
    
    print(f"Processing {len(md_files)} recipe files...")
    modified_count = 0
    
    for file_path in sorted(md_files):
        if remove_list_spacing(file_path):
            modified_count += 1
            print(f"✓ Updated: {file_path.name}")
        else:
            print(f"  Skipped: {file_path.name}")
    
    print(f"\nCompleted! Modified {modified_count} file(s).")

if __name__ == '__main__':
    main()
