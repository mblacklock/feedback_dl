#!/usr/bin/env bash
# release.sh — Merge the main branch into prod, push to origin, and return to main.
#
# Usage:
#   bash release.sh

set -euo pipefail

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Error: You have uncommitted changes. Please commit or stash them before releasing." >&2
    exit 1
fi

# Store the current branch name (typically main)
CURRENT_BRANCH=$(git branch --show-current)

echo "==> Switching to prod branch..."
git switch prod

echo "==> Merging $CURRENT_BRANCH into prod..."
git merge "$CURRENT_BRANCH"

echo "==> Pushing prod to remote origin..."
git push origin prod

echo "==> Deploying documentation to GitHub Pages..."
./.venv/Scripts/mkdocs gh-deploy

echo "==> Returning to $CURRENT_BRANCH branch..."
git switch "$CURRENT_BRANCH"

echo ""
echo "✓ Merge complete and pushed to origin/prod!"
