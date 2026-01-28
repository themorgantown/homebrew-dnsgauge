#!/bin/bash
set -e

NEW_REPO_URL="https://github.com/themorgantown/homebrew-dnsgauge.git"

echo "Using new remote: $NEW_REPO_URL"

# 1. Update remote (or add if clean)
# We use 'set-url' to replace origin. If origin doesn't exist, we add it.
if git remote | grep -q "^origin$"; then
    echo "Updating existing 'origin' remote..."
    git remote set-url origin "$NEW_REPO_URL"
else
    echo "Adding 'origin' remote..."
    git remote add origin "$NEW_REPO_URL"
fi

# 2. Stage all recent renames and edits
echo "Staging all changes..."
git add .

# 3. Commit
echo "Committing migration changes..."
git commit -m "chore: migrate to homebrew-dnsgauge repo and rebrand" || echo "No changes to commit, continuing..."

# 4. Push
echo "Pushing to new repository (this may ask for credentials)..."
git push -u origin main

echo "✅ Migration complete! Repository is now at: $NEW_REPO_URL"
