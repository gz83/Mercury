#!/bin/bash

# Copyright (c) 2024 Alex313031.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR/packaging/debian"
LOCALE_MANAGER="$SCRIPT_DIR/l10n/locale_manager.py"
TRANSLATIONS_FILE="$SCRIPT_DIR/l10n/translations.json"
PACKAGE_NAME="mercury-browser"
INSTALL_PATH="usr/lib/mercury"
FIREFOX_BASE_COMMIT="0c39e9282688363f5028d0541c17784f7fa5117c"
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
  L10NBASEDIR       Workspace created by prepare_l10n.sh (required)
  DEB_ARCH          Target architecture: amd64, i386, arm64, x86_64, x86,
                    or aarch64 (default: detected from the archive)
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

for command_name in awk dh dpkg-buildpackage dpkg-deb git python3 readelf tar; do
	command -v "$command_name" >/dev/null 2>&1 || {
		echo "Required command not found: $command_name" >&2
		exit 1
	}
done

if [[ ! -x "$MOZ_SRC_DIR/mach" ]] || \
	[[ "$(git -C "$MOZ_SRC_DIR" rev-parse --is-inside-work-tree 2>/dev/null || true)" != "true" ]]; then
	echo "Firefox checkout not found at $MOZ_SRC_DIR. Run ./bootstrap.sh and ./setup.sh first." >&2
	exit 1
fi
MOZ_SRC_DIR="$(cd "$MOZ_SRC_DIR" && pwd)"
if [[ "$(git -C "$MOZ_SRC_DIR" rev-parse HEAD)" != "$FIREFOX_BASE_COMMIT" ]]; then
	echo "Firefox checkout is not at the pinned Firefox 153.0.3 commit." >&2
	exit 1
fi
if [[ ! -f "$TEMPLATE_DIR/control.in" ]]; then
	echo "Debian templates not found at $TEMPLATE_DIR." >&2
	exit 1
fi
for required_patch in \
	030-mercury-app-branding.patch \
	080-mercury-localization.patch \
	120-debian-package-identity.patch \
	140-mercury-langpack-identity.patch; do
	patch_path="$SCRIPT_DIR/patches/firefox-153/$required_patch"
	if ! git -C "$MOZ_SRC_DIR" apply --reverse --check "$patch_path" 2>/dev/null; then
		echo "$required_patch is not applied to $MOZ_SRC_DIR; run setup.sh first." >&2
		exit 1
	fi
done

if [[ -z "${L10NBASEDIR:-}" || ! -d "$L10NBASEDIR" ]]; then
	echo "L10NBASEDIR must point to a workspace created by prepare_l10n.sh." >&2
	exit 1
fi
L10NBASEDIR="$(cd "$L10NBASEDIR" && pwd)"
export L10NBASEDIR

python3 "$LOCALE_MANAGER" manifest \
	--changesets "$MOZ_SRC_DIR/browser/locales/l10n-changesets.json" \
	--workspace "$L10NBASEDIR" \
	--translations "$TRANSLATIONS_FILE" \
	--reference-root "$MOZ_SRC_DIR/browser/locales/en-US" \
	--destination "${TMPDIR:-/tmp}" \
	--output /dev/null \
	--platform linux \
	--overall planned

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

archive_root="${application_ini_paths[0]%/application.ini}"
if [[ ! "$archive_root" =~ ^[A-Za-z0-9._+-]+$ || "$archive_root" == "." || "$archive_root" == ".." ]]; then
	echo "Unsafe top-level archive directory: $archive_root" >&2
	exit 1
fi
binary_member="$archive_root/mercury"
if ! tar -tf "$archive" | awk -v member="$binary_member" '$0 == member { found = 1 } END { exit !found }'; then
	echo "Mercury executable not found in archive: $binary_member" >&2
	exit 1
fi

inspection_dir="$(mktemp -d "${TMPDIR:-/tmp}/mercury-deb-arch.XXXXXXXX")"
cleanup() {
	rm -rf -- "$inspection_dir"
}
trap cleanup EXIT
tar -xf "$archive" -C "$inspection_dir" "$binary_member"
if ! elf_machine="$(LC_ALL=C readelf -h "$inspection_dir/$binary_member" | awk -F: '/^[[:space:]]*Machine:/ { sub(/^[[:space:]]+/, "", $2); print $2; exit }')"; then
	echo "Mercury executable is not a readable ELF file: $binary_member" >&2
	exit 1
fi
case "$elf_machine" in
	*X86-64*) detected_arch="amd64" ;;
	*80386*) detected_arch="i386" ;;
	AArch64*) detected_arch="arm64" ;;
	*) echo "Unsupported or unreadable Mercury ELF architecture: ${elf_machine:-unknown}" >&2; exit 1 ;;
esac

requested_arch="${DEB_ARCH:-$detected_arch}"
case "$requested_arch" in
	amd64|x86_64) mach_arch="x86_64"; deb_arch="amd64" ;;
	i386|x86) mach_arch="x86"; deb_arch="i386" ;;
	arm64|aarch64) mach_arch="aarch64"; deb_arch="arm64" ;;
	*) echo "Unsupported Debian architecture: $requested_arch" >&2; exit 1 ;;
esac
if [[ "$deb_arch" != "$detected_arch" ]]; then
	echo "DEB_ARCH=$requested_arch does not match the archive architecture ($detected_arch)." >&2
	exit 1
fi

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
