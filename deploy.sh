#!/usr/bin/env bash
# deploy.sh — Run this on PythonAnywhere to deploy the latest version.
#
# Usage (from the project root):
#   bash deploy.sh

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$PROJECT_DIR/.venv"
PYTHON="$VENV/bin/python"
DJANGO_SETTINGS="core.settings.prod"
# PythonAnywhere reloads the app when this file is touched
WSGI_FILE="/var/www/mblacklock_pythonanywhere_com_wsgi.py"
# ──────────────────────────────────────────────────────────────────────────────

echo "==> Pulling latest code"
git pull

echo "==> Installing / updating dependencies"
"$PYTHON" -m pip install -q -r "$PROJECT_DIR/requirements/base.txt" --no-cache-dir

echo "==> Running database migrations"
"$PYTHON" "$PROJECT_DIR/manage.py" migrate --settings="$DJANGO_SETTINGS"

echo "==> Collecting static files"
"$PYTHON" "$PROJECT_DIR/manage.py" collectstatic --noinput --settings="$DJANGO_SETTINGS"

echo "==> Building MkDocs documentation"
"$PYTHON" -m mkdocs build --config-file "$PROJECT_DIR/mkdocs.yml"

echo "==> Reloading web app"
touch "$WSGI_FILE"

echo ""
echo "✓ Deploy complete — https://mblacklock.pythonanywhere.com"
