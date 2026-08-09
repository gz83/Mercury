#!/bin/bash

# Copyright (c) 2024 Alex313031.

set -euo pipefail

DEFAULT_MOZ_SRC_DIR="$HOME/firefox"
case "${OSTYPE:-}" in
	msys*|cygwin*) DEFAULT_MOZ_SRC_DIR="/c/mozilla-source/firefox" ;;
esac
MOZ_SRC_DIR="${MOZ_SRC_DIR:-$DEFAULT_MOZ_SRC_DIR}"
FIREFOX_REVISION="${FIREFOX_REVISION:-main}"
export MOZ_SRC_DIR FIREFOX_REVISION

display_help() {
	cat <<'EOF'
Restore the Firefox checkout and sync it to the development tip.

Usage: ./tot.sh

Set MOZ_SRC_DIR to choose the checkout. FIREFOX_REVISION defaults to main.
WARNING: tracked and untracked changes in the Firefox checkout are removed.
EOF
}

case "${1:-}" in
	--help|-h) display_help; exit 0 ;;
	"") ;;
	*) display_help >&2; exit 2 ;;
esac

if [[ "$(git -C "$MOZ_SRC_DIR" rev-parse --is-inside-work-tree 2>/dev/null || true)" != "true" ]]; then
	echo "Firefox Git checkout not found at $MOZ_SRC_DIR. Run ./bootstrap.sh first." >&2
	exit 1
fi

cd "$MOZ_SRC_DIR"
origin_url="$(git remote get-url origin 2>/dev/null || true)"
case "$origin_url" in
	https://github.com/mozilla-firefox/firefox|https://github.com/mozilla-firefox/firefox.git|git@github.com:mozilla-firefox/firefox.git) ;;
	*) echo "Refusing to clean a checkout with an unexpected origin: $origin_url" >&2; exit 1 ;;
esac

printf 'Syncing Firefox to %s...\n' "$FIREFOX_REVISION"
git fetch --tags origin
git reset --hard
git clean -fd
git checkout --detach "origin/$FIREFOX_REVISION"
./mach clobber
./mach bootstrap --application-choice browser

printf '\nDone. Return to the Mercury repository and run ./setup.sh.\n'
