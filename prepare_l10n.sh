#!/bin/bash

set -euo pipefail

MERCURY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
L10N_REVISION="6795ea14a5bd5ed79a930e6759823c7236476ae4"
FIREFOX_BASE_COMMIT="0c39e9282688363f5028d0541c17784f7fa5117c"
DEFAULT_MOZ_SRC_DIR="$HOME/firefox"
case "${OSTYPE:-}" in
	msys*|cygwin*) DEFAULT_MOZ_SRC_DIR="/c/mozilla-source/firefox" ;;
esac
MOZ_SRC_DIR="${MOZ_SRC_DIR:-$DEFAULT_MOZ_SRC_DIR}"

usage() {
	cat <<'EOF'
Usage: ./prepare_l10n.sh SOURCE_REPOSITORY OUTPUT_DIRECTORY

Create an isolated Firefox 153 localization checkout that covers every locale
supported by the pinned Firefox release. Reviewed Mercury translations are
applied where available; other locales receive explicitly identified machine
drafts only for Mercury-owned messages. SOURCE_REPOSITORY is never modified, and
OUTPUT_DIRECTORY must not already exist. Run setup.sh first and set MOZ_SRC_DIR
if the prepared Firefox checkout is not at its platform default location.
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

for required_command in cmp git grep python3; do
	if ! command -v "${required_command}" >/dev/null 2>&1; then
		printf 'Required command is unavailable: %s\n' "${required_command}" >&2
		exit 1
	fi
done

SOURCE_REPOSITORY="$1"
OUTPUT_DIRECTORY="$2"

if ! git -C "${SOURCE_REPOSITORY}" rev-parse --git-dir >/dev/null 2>&1; then
	printf 'Localization Git repository not found: %s\n' "${SOURCE_REPOSITORY}" >&2
	exit 1
fi

if [ "$(git -C "${MOZ_SRC_DIR}" rev-parse --is-inside-work-tree 2>/dev/null || true)" != "true" ]; then
	printf 'Prepared Firefox Git checkout not found: %s\n' "${MOZ_SRC_DIR}" >&2
	exit 1
fi

CURRENT_FIREFOX_COMMIT="$(git -C "${MOZ_SRC_DIR}" rev-parse HEAD)"
if [ "${CURRENT_FIREFOX_COMMIT}" != "${FIREFOX_BASE_COMMIT}" ]; then
	printf 'Expected Firefox commit %s, found %s.\n' \
		"${FIREFOX_BASE_COMMIT}" "${CURRENT_FIREFOX_COMMIT}" >&2
	exit 1
fi

for required_patch in \
	030-mercury-app-branding.patch \
	080-mercury-localization.patch \
	120-debian-package-identity.patch \
	140-mercury-langpack-identity.patch; do
	patch_path="${MERCURY_DIR}/patches/firefox-153/${required_patch}"
	if ! git -C "${MOZ_SRC_DIR}" apply --reverse --check "${patch_path}" 2>/dev/null; then
		printf '%s is not applied to %s; run setup.sh first.\n' \
			"${required_patch}" "${MOZ_SRC_DIR}" >&2
		exit 1
	fi
done

if ! cmp -s "${MERCURY_DIR}/browser/branding/mercury/configure.sh" \
	"${MOZ_SRC_DIR}/browser/branding/mercury/configure.sh"; then
	printf 'Mercury branding overlay is missing or stale in %s; run setup.sh first.\n' \
		"${MOZ_SRC_DIR}" >&2
	exit 1
fi
if [ ! -f "${MOZ_SRC_DIR}/mozconfig" ] || \
	! grep -Eq '^[[:space:]]*ac_add_options[[:space:]]+--with-branding=browser/branding/mercury([[:space:]]|$)' \
		"${MOZ_SRC_DIR}/mozconfig"; then
	printf 'The configured checkout does not select Mercury branding: %s/mozconfig\n' \
		"${MOZ_SRC_DIR}" >&2
	exit 1
fi

CHANGESETS_FILE="${MOZ_SRC_DIR}/browser/locales/l10n-changesets.json"
LOCALE_MANAGER="${MERCURY_DIR}/l10n/locale_manager.py"
TRANSLATIONS_FILE="${MERCURY_DIR}/l10n/translations.json"

if [ ! -f "${CHANGESETS_FILE}" ]; then
	printf 'Firefox localization changesets are missing: %s\n' "${CHANGESETS_FILE}" >&2
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

python3 "${LOCALE_MANAGER}" apply-translations \
	--changesets "${CHANGESETS_FILE}" \
	--workspace "${OUTPUT_DIRECTORY}" \
	--reference-root "${MOZ_SRC_DIR}/browser/locales/en-US" \
	--translations "${TRANSLATIONS_FILE}" \
	--firefox-commit "${FIREFOX_BASE_COMMIT}"

printf '\nMercury localization workspace is ready.\n'
printf 'export L10NBASEDIR=%q\n' "$(cd "${OUTPUT_DIRECTORY}" && pwd)"
