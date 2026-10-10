#!/usr/bin/env bash
# Runs the complete licensed Pascal Editor, including its native build/scene/2D/3D tools.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHA="7fc874faec800e18f8be2dab78e7dc2ff2327bd7"
UPSTREAM="${BASE}/.upstream/pascal-editor"
command -v git >/dev/null || { echo "git is required" >&2; exit 2; }
docker compose version >/dev/null || { echo "Docker Compose v2 is required" >&2; exit 2; }
mkdir -p "$(dirname "$UPSTREAM")"
if [[ ! -d "$UPSTREAM/.git" ]]; then
  git clone --filter=blob:none https://github.com/pascalorg/editor.git "$UPSTREAM"
fi
OVERLAY_SRC="$BASE/integrations/pascal-native-overlay/app/airtrajectory/import/page.tsx"
OVERLAY_DEST="$UPSTREAM/apps/editor/app/airtrajectory/import/page.tsx"
# The only permitted workspace overlay is our own identical import route.
if [[ -f "$OVERLAY_DEST" ]]; then
  cmp -s "$OVERLAY_SRC" "$OVERLAY_DEST" || { echo "Unrecognized modified Pascal import route; refusing overwrite" >&2; exit 3; }
  rm "$OVERLAY_DEST"
fi
if [[ -n "$(git -C "$UPSTREAM" status --porcelain)" ]]; then
  echo "Refusing to reset modified upstream source. Check $UPSTREAM" >&2; exit 3
fi
git -C "$UPSTREAM" fetch origin "$SHA"
git -C "$UPSTREAM" checkout --detach "$SHA"
[[ "$(git -C "$UPSTREAM" rev-parse HEAD)" == "$SHA" ]] || { echo "SHA mismatch" >&2; exit 4; }
grep -q 'MIT License' "$UPSTREAM/LICENSE" || { echo "Upstream license not verified" >&2; exit 4; }
# Stitch the product import page into the full original Pascal app, before Docker builds it.
mkdir -p "$(dirname "$OVERLAY_DEST")"
cp "$OVERLAY_SRC" "$OVERLAY_DEST"
echo "Private residential import is available at http://localhost:${PASCAL_EDITOR_PORT:-3002}/airtrajectory/import"
echo "Building native Pascal Editor at $SHA with persistent SQLite scenes"
echo "Open http://localhost:${PASCAL_EDITOR_PORT:-3002} when healthy"
cd "$BASE"
exec docker compose -f compose.pascal-native.yml up --build --detach --wait
