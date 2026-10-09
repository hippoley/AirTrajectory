#!/usr/bin/env bash
# Launch the genuine open-source Pascal 2D/3D building editor in isolation.
# Pinned upstream tree: https://github.com/pascalorg/editor (MIT).
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="7fc874faec800e18f8be2dab78e7dc2ff2327bd7"
DEST="${PASCAL_NATIVE_DIR:-${BASE}/.upstream/pascal-editor}"
if ! command -v git >/dev/null; then echo "git required" >&2; exit 2; fi
if ! command -v bun >/dev/null; then echo "bun 1.3.14 required (https://bun.sh)" >&2; exit 2; fi
if [[ ! -d "${DEST}/.git" ]]; then
  mkdir -p "$(dirname "${DEST}")"
  git clone https://github.com/pascalorg/editor.git "${DEST}"
fi
cd "${DEST}"
git fetch --depth=1 origin "${VERSION}"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing to overwrite local changes in ${DEST}" >&2; exit 3
fi
git checkout --detach "${VERSION}"
test "$(git rev-parse HEAD)" = "${VERSION}"
test -f LICENSE
bun install --frozen-lockfile
bunx turbo run build --filter="editor^..."
echo "Starting authentic Pascal editor from pinned commit ${VERSION}"
echo "Building editing + 2D/3D are powered by upstream Pascal; AirTrajectory canonical topology conversion is NOT yet connected."
cd apps/editor
exec bun run dev
