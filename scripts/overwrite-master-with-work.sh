#!/usr/bin/env bash
set -euo pipefail

SOURCE_BRANCH="${1:-work}"
TARGET_BRANCH="${2:-master}"

current_branch="$(git rev-parse --abbrev-ref HEAD)"

cleanup() {
  git checkout "$current_branch" >/dev/null 2>&1 || true
}
trap cleanup EXIT

git rev-parse --verify "$SOURCE_BRANCH" >/dev/null
git rev-parse --verify "$TARGET_BRANCH" >/dev/null

echo "Overwriting $TARGET_BRANCH with exact content/history tip of $SOURCE_BRANCH"

git checkout "$TARGET_BRANCH" >/dev/null
# hard reset target pointer to source pointer
git reset --hard "$SOURCE_BRANCH" >/dev/null

echo "Done. $TARGET_BRANCH now points to: $(git rev-parse --short "$TARGET_BRANCH")"
echo "If this is a remote branch, push with: git push --force-with-lease origin $TARGET_BRANCH"
