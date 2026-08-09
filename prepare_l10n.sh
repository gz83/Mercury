#!/bin/bash

set -euo pipefail

MERCURY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
L10N_REVISION="6795ea14a5bd5ed79a930e6759823c7236476ae4"

usage() {
	cat <<'EOF'
Usage: ./prepare_l10n.sh SOURCE_REPOSITORY OUTPUT_DIRECTORY

Create an isolated Firefox 153 localization checkout, then apply Mercury's
locale-specific patches. SOURCE_REPOSITORY is never modified, and
OUTPUT_DIRECTORY must not already exist.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
	usage
	exit 0
fi

if [ "$#" -ne 2 ]; then
	usage >&2
	exit 2
fi

SOURCE_REPOSITORY="$1"
OUTPUT_DIRECTORY="$2"

if [ ! -d "${SOURCE_REPOSITORY}/.git" ]; then
	printf 'Localization Git repository not found: %s\n' "${SOURCE_REPOSITORY}" >&2
	exit 1
fi

if [ -e "${OUTPUT_DIRECTORY}" ]; then
	printf 'Output path already exists; choose a new empty path: %s\n' "${OUTPUT_DIRECTORY}" >&2
	exit 1
fi

if ! git -C "${SOURCE_REPOSITORY}" cat-file -e "${L10N_REVISION}^{commit}"; then
	printf 'Required localization revision is unavailable: %s\n' "${L10N_REVISION}" >&2
	exit 1
fi

git clone --no-checkout "${SOURCE_REPOSITORY}" "${OUTPUT_DIRECTORY}"
git -C "${OUTPUT_DIRECTORY}" checkout --detach "${L10N_REVISION}"

LOCALES_FILE="${MERCURY_DIR}/l10n/locales.txt"
PATCH_DIRECTORY="${MERCURY_DIR}/l10n/patches/firefox-153"

for patch_file in "${PATCH_DIRECTORY}"/*.patch; do
	patch_locale="$(basename "${patch_file}" .patch)"
	if ! grep -Fqx "${patch_locale}" "${LOCALES_FILE}"; then
		printf 'Localization patch is not listed in locales.txt: %s\n' "${patch_locale}" >&2
		exit 1
	fi
done

while IFS= read -r locale; do
	if [ -z "${locale}" ]; then
		continue
	fi
	if [ ! -d "${OUTPUT_DIRECTORY}/${locale}" ]; then
		printf 'Locale is missing from the pinned repository: %s\n' "${locale}" >&2
		exit 1
	fi
	patch_file="${PATCH_DIRECTORY}/${locale}.patch"
	if [ ! -f "${patch_file}" ]; then
		printf 'Mercury localization patch is missing: %s\n' "${locale}" >&2
		exit 1
	fi
	git -C "${OUTPUT_DIRECTORY}" apply --check "${patch_file}"
	git -C "${OUTPUT_DIRECTORY}" apply "${patch_file}"
done < "${LOCALES_FILE}"

printf '\nMercury localization workspace is ready.\n'
printf 'export L10NBASEDIR=%q\n' "$(cd "${OUTPUT_DIRECTORY}" && pwd)"
