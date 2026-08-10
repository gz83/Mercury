"""Load Mercury's pinned Firefox and localization release metadata."""

# Copyright (c) 2026 Alex313031 and gz83.

import json
import re
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPOSITORY_ROOT / "release.json"
PATCH_DIRECTORY = REPOSITORY_ROOT / "patches" / "firefox"
PATCH_MANIFEST_PATH = REPOSITORY_ROOT / "patches" / "manifest.json"
_PATCH_FILENAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\.patch")
_PATCH_ROLE_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_FIREFOX_VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)+")
_FIREFOX_RELEASE_PATTERN = re.compile(r"FIREFOX_[A-Z0-9_]+_RELEASE")
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


def required_string(mapping: dict[str, Any], key: str, location: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location}.{key} must be a non-empty string.")
    return value


def load_config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to read release metadata: {CONFIG_PATH}") from error
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError(f"Unsupported release metadata schema: {CONFIG_PATH}")
    firefox = data.get("firefox")
    localization = data.get("l10n")
    if not isinstance(firefox, dict) or not isinstance(localization, dict):
        raise ValueError(f"Release metadata sections are invalid: {CONFIG_PATH}")
    return data


def _release_metadata() -> tuple[str, str, str, str]:
    config = load_config()
    firefox = config["firefox"]
    localization = config["l10n"]
    return (
        required_string(firefox, "version", "firefox"),
        required_string(firefox, "release", "firefox"),
        required_string(firefox, "commit", "firefox"),
        required_string(localization, "commit", "l10n"),
    )


def load_patch_manifest() -> tuple[tuple[Path, ...], dict[str, tuple[Path, ...]]]:
    try:
        data = json.loads(PATCH_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Unable to read patch manifest: {PATCH_MANIFEST_PATH}"
        ) from error
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError(f"Unsupported patch manifest: {PATCH_MANIFEST_PATH}")
    entries = data.get("patches")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"Patch manifest has no patches: {PATCH_MANIFEST_PATH}")

    files: list[Path] = []
    roles: dict[str, list[Path]] = {}
    seen = set()
    for index, entry in enumerate(entries):
        location = f"patches[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{location} must be an object.")
        filename = required_string(entry, "file", location)
        if _PATCH_FILENAME_PATTERN.fullmatch(filename) is None:
            raise ValueError(f"{location}.file has an invalid format.")
        if filename in seen:
            raise ValueError(f"Patch manifest repeats {filename}.")
        seen.add(filename)
        path = PATCH_DIRECTORY / filename
        if not path.is_file():
            raise ValueError(f"Declared Firefox patch is missing: {path}")
        patch_roles = entry.get("roles")
        if not isinstance(patch_roles, list) or any(
            not isinstance(role, str)
            or _PATCH_ROLE_PATTERN.fullmatch(role) is None
            for role in patch_roles
        ):
            raise ValueError(f"{location}.roles must contain valid role names.")
        if len(patch_roles) != len(set(patch_roles)):
            raise ValueError(f"{location}.roles contains duplicates.")
        files.append(path)
        for role in patch_roles:
            roles.setdefault(role, []).append(path)

    actual = {path.name for path in PATCH_DIRECTORY.glob("*.patch")}
    if actual != seen:
        missing = sorted(seen - actual)
        unlisted = sorted(actual - seen)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unlisted:
            details.append("unlisted: " + ", ".join(unlisted))
        detail = "; ".join(details)
        raise ValueError(f"Patch manifest does not match its directory ({detail}).")
    return tuple(files), {role: tuple(paths) for role, paths in roles.items()}


FIREFOX_VERSION, FIREFOX_RELEASE, FIREFOX_COMMIT, L10N_COMMIT = (
    _release_metadata()
)

if _FIREFOX_VERSION_PATTERN.fullmatch(FIREFOX_VERSION) is None:
    raise ValueError("firefox.version has an invalid format.")
if _FIREFOX_RELEASE_PATTERN.fullmatch(FIREFOX_RELEASE) is None:
    raise ValueError("firefox.release has an invalid format.")
if _COMMIT_PATTERN.fullmatch(FIREFOX_COMMIT) is None:
    raise ValueError("firefox.commit must be a lowercase 40-character Git hash.")
if _COMMIT_PATTERN.fullmatch(L10N_COMMIT) is None:
    raise ValueError("l10n.commit must be a lowercase 40-character Git hash.")

PATCH_FILES, PATCH_ROLES = load_patch_manifest()


def patches_for_role(role: str) -> tuple[Path, ...]:
    patches = PATCH_ROLES.get(role)
    if not patches:
        raise ValueError(f"Patch manifest does not define required role: {role}")
    return patches
