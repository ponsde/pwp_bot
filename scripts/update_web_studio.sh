#!/usr/bin/env bash
# Sync web-studio/ from upstream Ferry-200/OpenViking:new-frontend.
#
# Strategy: sparse-checkout the upstream web-studio/ into a temp clone,
# then rsync over our copy. Our overlay files (listed in OVERLAY_FILES)
# are preserved automatically because rsync only overwrites files that
# exist in both sides; new overlay-only paths never collide.
# After syncing, check `git diff` for conflicts in overlay paths.
set -euo pipefail

UPSTREAM_URL="https://github.com/Ferry-200/OpenViking.git"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-new-frontend}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
TARGET="$REPO_ROOT/web-studio"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Files WE modified or own — review these manually after sync.
OVERLAY_FILES=(
  "src/routes/sessions/route.tsx"
)

echo "[1/4] Cloning upstream sparsely..."
git clone --filter=blob:none --no-checkout --depth=1 --branch "$UPSTREAM_BRANCH" \
  "$UPSTREAM_URL" "$TMP/up"
(
  cd "$TMP/up"
  git sparse-checkout init --cone
  git sparse-checkout set web-studio
  git checkout "$UPSTREAM_BRANCH"
)

UPSTREAM_COMMIT="$(git -C "$TMP/up" rev-parse --short HEAD)"
echo "[2/4] Upstream commit: $UPSTREAM_COMMIT"

echo "[3/4] Syncing files..."
mkdir -p "$TARGET"
rsync -a --delete \
  --exclude='node_modules/' \
  --exclude='dist/' \
  --exclude='.upstream-commit' \
  --exclude='LICENSE.upstream' \
  "$TMP/up/web-studio/" "$TARGET/"

cp "$TMP/up/LICENSE" "$TARGET/LICENSE.upstream"
echo "$UPSTREAM_COMMIT" > "$TARGET/.upstream-commit"

echo "[4/4] Checking overlay files for changes..."
cd "$REPO_ROOT"
for f in "${OVERLAY_FILES[@]}"; do
  path="web-studio/$f"
  if git status --porcelain -- "$path" 2>/dev/null | grep -q .; then
    echo "  CONFLICT: $path was overwritten — reapply our changes"
  fi
done

echo ""
echo "Done. Review 'git diff web-studio' and re-apply overlay as needed."
