#!/bin/sh
set -eu

repo=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)

check=false
if [ "${1:-}" = "--check" ]; then
  check=true
  shift
fi

if [ "$#" -eq 0 ]; then
  set -- "$repo/docs/recipes"
fi

if [ "$check" = true ]; then
  exec python3 "$repo/.github/scripts/format_recipes.py" --check "$@"
fi
exec python3 "$repo/.github/scripts/format_recipes.py" "$@"
