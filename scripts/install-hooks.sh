#!/bin/sh
# scripts/install-hooks.sh - copy the versioned pre-commit hook into .git/hooks
set -e
root=$(git rev-parse --show-toplevel)
hooks=$(git rev-parse --git-path hooks)
cp "$root/scripts/pre-commit" "$hooks/pre-commit"
chmod +x "$hooks/pre-commit"
echo "installed $hooks/pre-commit"
