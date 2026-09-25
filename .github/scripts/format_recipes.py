#!/usr/bin/env python3
"""CLI behind scripts/format-recipes.sh."""

import argparse
import sys
from pathlib import Path

from recipe_style import normalize_markdown


def recipe_files(paths):
    for value in paths:
        path = Path(value)
        if path.is_dir():
            yield from sorted(path.rglob("*.md"))
        elif path.suffix == ".md":
            yield path
        else:
            raise ValueError(f"not a recipe Markdown file: {path}")


def main():
    parser = argparse.ArgumentParser(description="Apply the Mason Recipes style formatter.")
    parser.add_argument("--check", action="store_true", help="report unformatted files without changing them")
    parser.add_argument("paths", nargs="*", default=["docs/recipes"])
    args = parser.parse_args()
    changed = []
    for path in recipe_files(args.paths):
        before = path.read_text(encoding="utf-8")
        after = normalize_markdown(before)
        if before != after:
            changed.append(path)
            if not args.check:
                path.write_text(after, encoding="utf-8")
    if changed and args.check:
        print("Recipe style check failed:", *changed, sep="\n", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
