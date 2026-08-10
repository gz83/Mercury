"""Load Mercury's pinned Firefox and localization release metadata."""

# Copyright (c) 2026 Alex313031 and gz83.

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPOSITORY_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPOSITORY_ROOT / "release.json"
PATCH_DIRECTORY = REPOSITORY_ROOT / "patches" / "firefox"
PATCH_MANIFEST_PATH = REPOSITORY_ROOT / "patches" / "manifest.json"


def required_string(mapping: Dict[str, Any], key: str, location: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location}.{key} must be a non-empty string.")
    return value


def load_config() -> Dict[str, Any]:
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


def load_patch_manifest() -> Tuple[Tuple[Path, ...], Dict[str, Tuple[Path, ...]]]:
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

    files: List[Path] = []
    roles: Dict[str, List[Path]] = {}
    seen = set()
    for index, entry in enumerate(entries):
        location = f"patches[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{location} must be an object.")
        filename = required_string(entry, "file", location)
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.patch", filename) is None:
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
            or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", role) is None
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
    return tuple(files), {
        role: tuple(role_files) for role, role_files in roles.items()
    }


CONFIG = load_config()
FIREFOX = CONFIG["firefox"]
LOCALIZATION = CONFIG["l10n"]

FIREFOX_VERSION = required_string(FIREFOX, "version", "firefox")
FIREFOX_RELEASE = required_string(FIREFOX, "release", "firefox")
FIREFOX_COMMIT = required_string(FIREFOX, "commit", "firefox")
L10N_COMMIT = required_string(LOCALIZATION, "commit", "l10n")

if re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", FIREFOX_VERSION) is None:
    raise ValueError("firefox.version has an invalid format.")
if re.fullmatch(r"FIREFOX_[A-Z0-9_]+_RELEASE", FIREFOX_RELEASE) is None:
    raise ValueError("firefox.release has an invalid format.")
if re.fullmatch(r"[0-9a-f]{40}", FIREFOX_COMMIT) is None:
    raise ValueError("firefox.commit must be a lowercase 40-character Git hash.")
if re.fullmatch(r"[0-9a-f]{40}", L10N_COMMIT) is None:
    raise ValueError("l10n.commit must be a lowercase 40-character Git hash.")

if not PATCH_DIRECTORY.is_dir():
    raise ValueError(f"Firefox patch directory is missing: {PATCH_DIRECTORY}")

PATCH_FILES, PATCH_ROLES = load_patch_manifest()


def patches_for_role(role: str) -> Tuple[Path, ...]:
    patches = PATCH_ROLES.get(role)
    if not patches:
        raise ValueError(f"Patch manifest does not define required role: {role}")
    return patches
