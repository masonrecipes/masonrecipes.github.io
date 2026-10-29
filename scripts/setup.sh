#!/usr/bin/env bash
# Create the local virtual environment and install the site's dependencies.
# Safe to rerun. Usage: scripts/setup.sh
set -euo pipefail

repo=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
venv="$repo/venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found. Install Python 3 (https://www.python.org/downloads/) and run this again." >&2
  exit 1
fi

if ! "$venv/bin/python" -m pip --version >/dev/null 2>&1; then
  echo "Creating virtual environment in $venv"
  python3 -m venv --clear "$venv" || {
    echo "error: could not create the virtual environment (on Debian/Ubuntu, install python3-venv)." >&2
    exit 1
  }
fi

"$venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$repo/requirements.txt"

cat <<MSG

Setup complete. To preview the site:

  cd "$repo"
  source venv/bin/activate
  zensical serve

Then open http://localhost:8000.
MSG
