#!/bin/bash

# Copyright (c) 2024 Alex313031.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR/packaging/debian"
PACKAGE_NAME="mercury-browser"
INSTALL_PATH="usr/lib/mercury"
DEFAULT_MOZ_SRC_DIR="$HOME/firefox"
case "${OSTYPE:-}" in
	msys*|cygwin*) DEFAULT_MOZ_SRC_DIR="/c/mozilla-source/firefox" ;;
esac
MOZ_SRC_DIR="${MOZ_SRC_DIR:-$DEFAULT_MOZ_SRC_DIR}"

archive=""
output=""

display_help() {
	cat <<'EOF'
Build a Debian package with Firefox's `mach repackage deb` workflow.

Usage: ./make_deb.sh [options] [archive]

Archives produced by `./mach package` in .tar.xz, .tar.bz2, or .tar.gz
format are supported. If archive is omitted, the script searches this
repository and $MOZ_SRC_DIR/obj-*/dist/ for exactly one Mercury archive.

Options:
  -o, --output FILE  Write the package to FILE
  -h, --help         Show this help

Environment variables:
  MOZ_SRC_DIR       Firefox checkout prepared by setup.sh
  DEB_ARCH          Target architecture: amd64, i386, arm64, x86_64, x86,
                    or aarch64 (default: the build host architecture)
  DEB_BUILD_NUMBER  Debian build number (default: 1)
EOF
}

while (( $# > 0 )); do
	case "$1" in
		-o|--output)
			if (( $# < 2 )); then
				echo "$1 requires a file path." >&2
				exit 2
			fi
			output="$2"
			shift 2
			;;
		-h|--help)
			display_help
			exit 0
			;;
		-*)
			echo "Unknown option: $1" >&2
			display_help >&2
			exit 2
			;;
		*)
			if [[ -n "$archive" ]]; then
				echo "Only one archive may be specified." >&2
				exit 2
			fi
			archive="$1"
			shift
			;;
	esac
done

for command_name in awk dpkg git tar; do
	command -v "$command_name" >/dev/null 2>&1 || {
		echo "Required command not found: $command_name" >&2
		exit 1
	}
done

if [[ ! -x "$MOZ_SRC_DIR/mach" || ! -d "$MOZ_SRC_DIR/.git" ]]; then
	echo "Firefox checkout not found at $MOZ_SRC_DIR. Run ./bootstrap.sh and ./setup.sh first." >&2
	exit 1
fi
if [[ ! -f "$TEMPLATE_DIR/control.in" ]]; then
	echo "Debian templates not found at $TEMPLATE_DIR." >&2
	exit 1
fi
if ! git -C "$MOZ_SRC_DIR" apply --reverse --check \
	"$SCRIPT_DIR/patches/firefox-153/120-debian-package-identity.patch" 2>/dev/null; then
	echo "The Mercury Debian repackaging patch is not applied. Run ./setup.sh first." >&2
	exit 1
fi

if [[ -z "$archive" ]]; then
	shopt -s nullglob
	archives=(
		"$SCRIPT_DIR"/[Mm]ercury*.tar.xz
		"$SCRIPT_DIR"/[Mm]ercury*.tar.bz2
		"$SCRIPT_DIR"/[Mm]ercury*.tar.gz
		"$MOZ_SRC_DIR"/obj-*/dist/[Mm]ercury*.tar.xz
		"$MOZ_SRC_DIR"/obj-*/dist/[Mm]ercury*.tar.bz2
		"$MOZ_SRC_DIR"/obj-*/dist/[Mm]ercury*.tar.gz
	)
	shopt -u nullglob
	if (( ${#archives[@]} != 1 )); then
		echo "Expected exactly one Mercury package archive, found ${#archives[@]}." >&2
		echo "Pass the desired archive path explicitly." >&2
		exit 1
	fi
	archive="${archives[0]}"
fi

if [[ ! -f "$archive" ]]; then
	echo "Archive not found: $archive" >&2
	exit 1
fi
case "$archive" in
	*.tar.xz|*.tar.bz2|*.tar.gz) ;;
	*) echo "Unsupported archive format: $archive" >&2; exit 1 ;;
esac
archive="$(cd "$(dirname "$archive")" && pwd)/$(basename "$archive")"

mapfile -t application_ini_paths < <(tar -tf "$archive" | awk '/^[^/]+\/application\.ini$/')
if (( ${#application_ini_paths[@]} != 1 )); then
	echo "Expected one top-level application.ini in $archive, found ${#application_ini_paths[@]}." >&2
	exit 1
fi
version="$(tar -xOf "$archive" "${application_ini_paths[0]}" | awk '
	/^\[App\]$/ { in_app = 1; next }
	/^\[/ { in_app = 0 }
	in_app && /^Version=/ { sub(/^Version=/, ""); print; exit }
')"
if [[ -z "$version" ]]; then
	echo "Could not read the Mercury version from ${application_ini_paths[0]}." >&2
	exit 1
fi

requested_arch="${DEB_ARCH:-$(dpkg --print-architecture)}"
case "$requested_arch" in
	amd64|x86_64) mach_arch="x86_64"; deb_arch="amd64" ;;
	i386|x86) mach_arch="x86"; deb_arch="i386" ;;
	arm64|aarch64) mach_arch="aarch64"; deb_arch="arm64" ;;
	*) echo "Unsupported Debian architecture: $requested_arch" >&2; exit 1 ;;
esac

build_number="${DEB_BUILD_NUMBER:-1}"
if [[ ! "$build_number" =~ ^[1-9][0-9]*$ ]]; then
	echo "DEB_BUILD_NUMBER must be a positive integer." >&2
	exit 2
fi

if [[ -z "$output" ]]; then
	output="$SCRIPT_DIR/${PACKAGE_NAME}_${version}~build${build_number}_${deb_arch}.deb"
elif [[ "$output" != /* ]]; then
	output="$PWD/$output"
fi
mkdir -p "$(dirname "$output")"

printf 'Building %s with Firefox repackage tooling...\n' "$output"
(
	cd "$MOZ_SRC_DIR"
	./mach repackage deb \
		--input "$archive" \
		--output "$output" \
		--arch "$mach_arch" \
		--version "$version" \
		--build-number "$build_number" \
		--templates "$TEMPLATE_DIR" \
		--product mercury \
		--release-type release \
		--package-name "$PACKAGE_NAME" \
		--install-path "$INSTALL_PATH"
)

printf '\nPackage created: %s\n' "$output"
printf 'Inspect it with: dpkg-deb --info %q\n' "$output"
printf 'Install it with: sudo dpkg -i %q\n' "$output"
