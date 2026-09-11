#!/usr/bin/env bash
# Idempotent dependency refresh for the RDGen Django app.
# Safe to run repeatedly: it only installs what is missing.
set -euo pipefail

# Resolve the repository root (this script lives in .cursor/).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# The base image ships python3 without ensurepip, which `python3 -m venv`
# needs. Install the venv package only when it is actually missing.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

# Create the virtualenv once; reuse it on later runs.
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Apply migrations to the local sqlite database.
.venv/bin/python manage.py migrate --noinput
