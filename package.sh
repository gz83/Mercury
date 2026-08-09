#!/bin/bash

# Copyright (c) 2024 Alex313031.

set -euo pipefail

display_help() {
	cat <<'EOF'
Package Mercury with Firefox's native platform packaging workflow.

Usage: ./package.sh

Firefox selects the output for the configured target: an XZ archive on Linux,
a DMG on macOS, or a ZIP and full installer on Windows. `mach package` prints
the exact output path. Set MOZ_MAKE_FLAGS to control make parallelism.
EOF
}

case "${1:-}" in
	-h|--help) display_help; exit 0 ;;
	"") ;;
	*) echo "Unknown option: $1" >&2; display_help >&2; exit 2 ;;
esac

# Firefox source directory
DEFAULT_MOZ_SRC_DIR="$HOME/firefox"
case "${OSTYPE:-}" in
	msys*|cygwin*) DEFAULT_MOZ_SRC_DIR="/c/mozilla-source/firefox" ;;
esac
MOZ_SRC_DIR="${MOZ_SRC_DIR:-$DEFAULT_MOZ_SRC_DIR}"
export MOZ_SRC_DIR

if [[ ! -x "$MOZ_SRC_DIR/mach" || ! -d "$MOZ_SRC_DIR/.git" ]]; then
	echo "Firefox checkout not found at $MOZ_SRC_DIR. Run ./bootstrap.sh and ./setup.sh first." >&2
	exit 1
fi

printf 'Packaging Mercury with Firefox mach...\n'
cd "$MOZ_SRC_DIR"
./mach package --verbose
