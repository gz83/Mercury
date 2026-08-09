#!/bin/bash

# Copyright (c) 2024 Alex313031.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINUX_LAUNCHER="$SCRIPT_DIR/packaging/portable/linux/MERCURY_PORTABLE.sh"
WINDOWS_LAUNCHER="$SCRIPT_DIR/packaging/portable/windows/MERCURY.BAT"

archive=""
output=""

display_help() {
	cat <<'EOF'
Create a Mercury portable package from Firefox's native package output.

Usage: ./make_portable.sh [options] ARCHIVE

Supported inputs:
  .tar.xz, .tar.bz2, .tar.gz  Linux package produced by `mach package`
  .zip                        Windows package produced by `mach package`

The input must contain one top-level `mercury/` directory. The portable
launcher and its USER_DATA profile directory live beside that directory.

Options:
  -o, --output FILE  Write the portable package to FILE
  -h, --help         Show this help
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
				echo "Only one package archive may be specified." >&2
				exit 2
			fi
			archive="$1"
			shift
			;;
	esac
done

if [[ -z "$archive" ]]; then
	echo "A package archive is required." >&2
	display_help >&2
	exit 2
fi
if [[ ! -f "$archive" ]]; then
	echo "Archive not found: $archive" >&2
	exit 1
fi

archive="$(cd "$(dirname "$archive")" && pwd)/$(basename "$archive")"
archive_name="$(basename "$archive")"
case "$archive_name" in
	*.tar.xz)
		platform="linux"
		archive_stem="${archive_name%.tar.xz}"
		output_suffix=".portable.tar.xz"
		;;
	*.tar.bz2)
		platform="linux"
		archive_stem="${archive_name%.tar.bz2}"
		output_suffix=".portable.tar.xz"
		;;
	*.tar.gz)
		platform="linux"
		archive_stem="${archive_name%.tar.gz}"
		output_suffix=".portable.tar.xz"
		;;
	*.zip)
		platform="windows"
		archive_stem="${archive_name%.zip}"
		output_suffix=".portable.zip"
		;;
	*)
		echo "Unsupported archive format: $archive" >&2
		exit 1
		;;
esac

if [[ -z "$output" ]]; then
	output="$SCRIPT_DIR/$archive_stem$output_suffix"
elif [[ "$output" != /* ]]; then
	output="$PWD/$output"
fi
if [[ "$output" == "$archive" ]]; then
	echo "Output must not overwrite the input archive." >&2
	exit 1
fi
if [[ -e "$output" ]]; then
	echo "Output already exists: $output" >&2
	exit 1
fi

case "$platform" in
	linux)
		for command_name in tar xz; do
			command -v "$command_name" >/dev/null 2>&1 || {
				echo "Required command not found: $command_name" >&2
				exit 1
			}
		done
		[[ -x "$LINUX_LAUNCHER" ]] || {
			echo "Linux portable launcher is missing or not executable: $LINUX_LAUNCHER" >&2
			exit 1
		}
		tar -tf "$archive" >/dev/null
		mapfile -t archive_members < <(tar -tf "$archive")
		;;
	windows)
		for command_name in unzip zip; do
			command -v "$command_name" >/dev/null 2>&1 || {
				echo "Required command not found: $command_name" >&2
				exit 1
			}
		done
		[[ -f "$WINDOWS_LAUNCHER" ]] || {
			echo "Windows portable launcher is missing: $WINDOWS_LAUNCHER" >&2
			exit 1
		}
		unzip -tq "$archive" >/dev/null
		mapfile -t archive_members < <(unzip -Z1 "$archive")
		;;
esac

if (( ${#archive_members[@]} == 0 )); then
	echo "Archive is empty: $archive" >&2
	exit 1
fi
for member in "${archive_members[@]}"; do
	member="${member#./}"
	case "$member" in
		""|/*|../*|*/../*|*/..|*\\*)
			echo "Unsafe archive member: $member" >&2
			exit 1
			;;
	esac
	if [[ "$member" != "mercury" && "$member" != mercury/* ]]; then
		echo "Unexpected top-level archive member: $member" >&2
		exit 1
	fi
done

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/mercury-portable.XXXXXXXX")"
cleanup() {
	rm -rf -- "$work_dir"
}
trap cleanup EXIT

case "$platform" in
	linux)
		tar -xf "$archive" -C "$work_dir"
		if [[ ! -x "$work_dir/mercury/mercury" ]]; then
			echo "Linux Mercury executable is missing from the package." >&2
			exit 1
		fi
		cp "$LINUX_LAUNCHER" "$work_dir/MERCURY_PORTABLE.sh"
		mkdir -p "$(dirname "$output")"
		tar -cJf "$output" -C "$work_dir" MERCURY_PORTABLE.sh mercury
		;;
	windows)
		unzip -q "$archive" -d "$work_dir"
		if [[ ! -f "$work_dir/mercury/mercury.exe" ]]; then
			echo "Windows Mercury executable is missing from the package." >&2
			exit 1
		fi
		cp "$WINDOWS_LAUNCHER" "$work_dir/MERCURY.BAT"
		mkdir -p "$(dirname "$output")"
		(
			cd "$work_dir"
			zip -qr "$output" MERCURY.BAT mercury
		)
		;;
esac

printf 'Portable package created: %s\n' "$output"
