#!/bin/bash

# Copyright (c) 2024 Alex313031.

set -euo pipefail

FIREFOX_REPOSITORY="https://github.com/mozilla-firefox/firefox.git"
FIREFOX_REVISION="${FIREFOX_REVISION:-FIREFOX_153_0_3_RELEASE}"

display_help() {
	cat <<'EOF'
Clone Firefox with Git and bootstrap a Mercury build environment.

Usage: ./bootstrap.sh [--linux|--mac|--win]

Environment variables:
  MOZ_SRC_DIR       Firefox checkout directory (default: $HOME/firefox,
                    or /c/mozilla-source/firefox on Windows)
  FIREFOX_REVISION  Git tag, branch, or commit to check out
                    (default: FIREFOX_153_0_3_RELEASE)
EOF
}

platform=""
case "${1:-}" in
	--linux|--mac|--win) platform="${1#--}" ;;
	--help|-h) display_help; exit 0 ;;
	"") ;;
	*) display_help >&2; exit 2 ;;
esac

if [[ -z "$platform" ]]; then
	case "${OSTYPE:-}" in
		msys*|cygwin*) platform="win" ;;
		darwin*) platform="mac" ;;
		*) platform="linux" ;;
	esac
fi

if [[ -z "${MOZ_SRC_DIR:-}" ]]; then
	if [[ "$platform" == "win" ]]; then
		MOZ_SRC_DIR="/c/mozilla-source/firefox"
	else
		MOZ_SRC_DIR="$HOME/firefox"
	fi
fi
export MOZ_SRC_DIR

command -v git >/dev/null 2>&1 || {
	echo "git is required. Install Git and run this script again." >&2
	exit 1
}
command -v python3 >/dev/null 2>&1 || {
	echo "python3 is required. Install Python 3 and run this script again." >&2
	exit 1
}

if [[ -e "$MOZ_SRC_DIR" ]]; then
	if [[ "$(git -C "$MOZ_SRC_DIR" rev-parse --is-inside-work-tree 2>/dev/null || true)" != "true" ]]; then
		echo "MOZ_SRC_DIR exists but is not a Git working tree: $MOZ_SRC_DIR" >&2
		exit 1
	fi
else
	mkdir -p "$(dirname "$MOZ_SRC_DIR")"
	git clone "$FIREFOX_REPOSITORY" "$MOZ_SRC_DIR"
fi

cd "$MOZ_SRC_DIR"

origin_url="$(git remote get-url origin 2>/dev/null || true)"
case "$origin_url" in
	https://github.com/mozilla-firefox/firefox|https://github.com/mozilla-firefox/firefox.git|git@github.com:mozilla-firefox/firefox.git) ;;
	*)
		echo "Refusing to modify a checkout with an unexpected origin: $origin_url" >&2
		exit 1
		;;
esac

git fetch --tags origin
git checkout --detach "$FIREFOX_REVISION"
./mach bootstrap --application-choice browser

printf '\nFirefox is ready at %s (revision %s).\n' "$MOZ_SRC_DIR" "$FIREFOX_REVISION"
printf 'Return to the Mercury repository and run ./setup.sh.\n'
