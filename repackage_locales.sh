#!/bin/bash

set -euo pipefail

MERCURY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCALE_MANAGER="$MERCURY_DIR/l10n/locale_manager.py"
FIREFOX_BASE_COMMIT="0c39e9282688363f5028d0541c17784f7fa5117c"
DEFAULT_MOZ_SRC_DIR="$HOME/firefox"
case "${OSTYPE:-}" in
	msys*|cygwin*) DEFAULT_MOZ_SRC_DIR="/c/mozilla-source/firefox" ;;
esac
MOZ_SRC_DIR="${MOZ_SRC_DIR:-$DEFAULT_MOZ_SRC_DIR}"

platform=""
destination=""
dry_run=0
verbose=0

display_help() {
	cat <<'EOF'
Repackage an en-US Mercury build into every Firefox-supported locale for one
target platform.

Usage: ./repackage_locales.sh --platform PLATFORM [options]

Options:
  --platform PLATFORM  linux, windows, or macos (required)
  --dest DIRECTORY     Artifact directory (default: /tmp/mercury-localized-PLATFORM)
  --dry-run            Validate and print the locale set without building
  -v, --verbose        Enable verbose Firefox repackaging output
  -h, --help           Show this help

The prepared L10NBASEDIR must come from prepare_l10n.sh. The script selects the
platform-specific Firefox 153 locale set, including `ja` on Linux/Windows and
`ja-JP-mac` on macOS, and restores the object directory to en-US on exit.
EOF
}

while (( $# > 0 )); do
	case "$1" in
		--platform)
			if (( $# < 2 )); then
				echo "$1 requires a value." >&2
				exit 2
			fi
			platform="$2"
			shift 2
			;;
		--dest)
			if (( $# < 2 )); then
				echo "$1 requires a directory." >&2
				exit 2
			fi
			destination="$2"
			shift 2
			;;
		--dry-run)
			dry_run=1
			shift
			;;
		-v|--verbose)
			verbose=1
			shift
			;;
		-h|--help)
			display_help
			exit 0
			;;
		*)
			echo "Unknown option: $1" >&2
			display_help >&2
			exit 2
			;;
	esac
done

case "$platform" in
	linux|windows|macos) ;;
	"") echo "--platform is required." >&2; exit 2 ;;
	*) echo "Unsupported platform: $platform" >&2; exit 2 ;;
esac

for required_command in cmp find git grep mktemp python3; do
	if ! command -v "$required_command" >/dev/null 2>&1; then
		echo "Required command is unavailable: $required_command" >&2
		exit 1
	fi
done

if [[ ! -x "$MOZ_SRC_DIR/mach" ]] || \
	[[ "$(git -C "$MOZ_SRC_DIR" rev-parse --is-inside-work-tree 2>/dev/null || true)" != "true" ]]; then
	echo "Firefox checkout not found at $MOZ_SRC_DIR. Run setup.sh first." >&2
	exit 1
fi
MOZ_SRC_DIR="$(cd "$MOZ_SRC_DIR" && pwd)"
if [[ "$(git -C "$MOZ_SRC_DIR" rev-parse HEAD)" != "$FIREFOX_BASE_COMMIT" ]]; then
	echo "Firefox checkout is not at the pinned Firefox 153.0.3 commit." >&2
	exit 1
fi
for required_patch in \
	030-mercury-app-branding.patch \
	080-mercury-localization.patch \
	120-debian-package-identity.patch \
	140-mercury-langpack-identity.patch; do
	patch_path="$MERCURY_DIR/patches/firefox-153/$required_patch"
	if ! git -C "$MOZ_SRC_DIR" apply --reverse --check "$patch_path" 2>/dev/null; then
		echo "$required_patch is not applied to $MOZ_SRC_DIR; run setup.sh first." >&2
		exit 1
	fi
done
if ! cmp -s "$MERCURY_DIR/browser/branding/mercury/configure.sh" \
	"$MOZ_SRC_DIR/browser/branding/mercury/configure.sh"; then
	echo "Mercury branding overlay is missing or stale in $MOZ_SRC_DIR; run setup.sh first." >&2
	exit 1
fi
if [[ ! -f "$MOZ_SRC_DIR/mozconfig" ]] || \
	! grep -Eq '^[[:space:]]*ac_add_options[[:space:]]+--with-branding=browser/branding/mercury([[:space:]]|$)' \
		"$MOZ_SRC_DIR/mozconfig"; then
	echo "The configured checkout does not select Mercury branding: $MOZ_SRC_DIR/mozconfig" >&2
	exit 1
fi
if [[ -z "${L10NBASEDIR:-}" || ! -d "$L10NBASEDIR" ]]; then
	echo "L10NBASEDIR must point to a workspace created by prepare_l10n.sh." >&2
	exit 1
fi
L10NBASEDIR="$(cd "$L10NBASEDIR" && pwd)"
export L10NBASEDIR

changesets="$MOZ_SRC_DIR/browser/locales/l10n-changesets.json"
mapfile -t locales < <(
	python3 "$LOCALE_MANAGER" list \
		--changesets "$changesets" \
		--platform "$platform"
)
if (( ${#locales[@]} == 0 )); then
	echo "Firefox returned no locales for $platform." >&2
	exit 1
fi

if [[ -z "$destination" ]]; then
	destination="/tmp/mercury-localized-$platform"
elif [[ "$destination" != /* ]]; then
	destination="$PWD/$destination"
fi

if (( dry_run == 1 )); then
	python3 "$LOCALE_MANAGER" manifest \
		--changesets "$changesets" \
		--workspace "$L10NBASEDIR" \
		--translations "$MERCURY_DIR/l10n/translations.json" \
		--reference-root "$MOZ_SRC_DIR/browser/locales/en-US" \
		--destination "$destination" \
		--output /dev/stdout \
		--platform "$platform" \
		--overall planned
	exit 0
fi

environment_file="$(mktemp "${TMPDIR:-/tmp}/mercury-build-environment.XXXXXXXX.json")"
if ! (
	cd "$MOZ_SRC_DIR"
	./mach environment --format json --verbose --output "$environment_file"
); then
	rm -f -- "$environment_file"
	echo "Unable to read the configured Firefox target platform." >&2
	exit 1
fi
configured_platform="$(
	python3 "$LOCALE_MANAGER" target-platform --environment "$environment_file"
)"
rm -f -- "$environment_file"
if [[ "$configured_platform" != "$platform" ]]; then
	echo "Configured Firefox target is $configured_platform, not $platform." >&2
	exit 1
fi

if [[ -e "$destination" && ! -d "$destination" ]]; then
	echo "Artifact destination is not a directory: $destination" >&2
	exit 1
fi
if [[ -d "$destination" ]] && [[ -n "$(find "$destination" -mindepth 1 -print -quit)" ]]; then
	echo "Artifact destination must be empty: $destination" >&2
	exit 1
fi
mkdir -p "$destination"
manifest="$destination/localization-manifest.tsv"

python3 "$LOCALE_MANAGER" manifest \
	--changesets "$changesets" \
	--workspace "$L10NBASEDIR" \
	--translations "$MERCURY_DIR/l10n/translations.json" \
	--reference-root "$MOZ_SRC_DIR/browser/locales/en-US" \
	--destination "$destination" \
	--output "$manifest" \
	--platform "$platform" \
	--overall planned

export MERCURY_L10N_REPACK=1

finish() {
	status=$?
	trap - EXIT
	set +e

	printf '\nRestoring the object directory to en-US...\n'
	(
		cd "$MOZ_SRC_DIR"
		./mach configure --enable-ui-locale=en-US
	)
	restore_status=$?
	if (( restore_status != 0 )); then
		echo "Failed to restore the Firefox object directory to en-US." >&2
		status=1
	fi

	if (( status == 0 )); then
		overall="success"
	else
		overall="failed"
	fi
	python3 "$LOCALE_MANAGER" manifest \
		--changesets "$changesets" \
		--workspace "$L10NBASEDIR" \
		--translations "$MERCURY_DIR/l10n/translations.json" \
		--reference-root "$MOZ_SRC_DIR/browser/locales/en-US" \
		--destination "$destination" \
		--output "$manifest" \
		--platform "$platform" \
		--overall "$overall"
	manifest_status=$?
	if (( manifest_status != 0 )); then
		status=1
	fi

	printf 'Localization manifest: %s\n' "$manifest"
	exit "$status"
}
trap finish EXIT

command=(
	./mach repackage-single-locales
	--locales "${locales[@]}"
	--dest "$destination"
)
if (( verbose == 1 )); then
	command+=(--verbose)
fi

printf 'Repackaging %d Firefox-supported locales for %s...\n' \
	"${#locales[@]}" "$platform"
cd "$MOZ_SRC_DIR"
"${command[@]}"
