#!/usr/bin/env python3

"""Validate and prepare Firefox localization data for Mercury releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import zipfile
import zlib
from pathlib import Path


EXPECTED_L10N_REVISION = "6795ea14a5bd5ed79a930e6759823c7236476ae4"
EXPECTED_FIREFOX_COMMIT = "0c39e9282688363f5028d0541c17784f7fa5117c"
MARKER_NAME = ".mercury-l10n.json"
MARKER_SCHEMA_VERSION = 6
LANGPACK_EID_HOST = "mercury.alex313031.github.io"
SAFE_LOCALE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")

PRODUCT_ALIASES = {
    "ar": ("فَيَرفُكس",),
    "fa": ("فایرفاکس",),
    "kn": ("ಫೈರ್‌ಫಾಕ್ಸಿಗೆ", "ಫೈರ್ಫಾಕ್ಸ್‍", "ಫೈರ್‌ಫಾಕ್ಸ್", "ಫೈರ್ಫಾಕ್ಸ್"),
    "my": ("မီးမြေခွေး",),
    "ne-NP": ("फायरफक्स",),
    "sat": ("ᱯᱷᱟᱭᱨᱚᱯᱷᱠᱥ", "ᱯᱷᱟᱭᱨᱚ ᱯᱷᱠᱥ"),
    "si": ("ෆයර්ෆොක්ස්", "ෆයර්ෆොක්ස්", "ෆයර්ගෆොක්ස්"),
    "skr": ("فائر فاکس",),
    "ta": ("பயர்பாக்சால்", "பயர்பாக்ஸுக்கு", "ஃபயர்பாக்ஸ்", "பயர்பாக்ஸ்"),
}

PLATFORM_PREFIXES = {
    "linux": "linux",
    "macos": "macos",
    "windows": "win",
}

FTL_MESSAGES = {
    (
        "browser/browser/aboutDialog.ftl",
        "browser/aboutDialog.ftl",
    ): ("community-2",),
    (
        "browser/browser/linuxDesktopEntry.ftl",
        "browser/linuxDesktopEntry.ftl",
    ): ("desktop-action-open-temp-profile",),
}

PROPERTIES_MESSAGES = {
    (
        "browser/chrome/overrides/appstrings.properties",
        "chrome/overrides/appstrings.properties",
    ): (
        "fileNotFound",
        "unknownProtocolFound",
        "connectionFailure",
        "redirectLoop",
        "clientSocketMisconfiguration",
        "netOffline",
        "deniedPortAccess",
        "proxyResolveFailure",
        "proxyConnectFailure",
        "sslv3Used",
        "blockedByCORP",
        "networkProtocolError",
    ),
}

SORTED_PRODUCT_ALIASES = {
    locale: tuple(sorted(aliases, key=len, reverse=True))
    for locale, aliases in PRODUCT_ALIASES.items()
}

MACHINE_REPLACEMENTS = (
    ("ZXQ000ZXQ", "{ -brand-short-name }"),
    (
        "ZXQ001ZXQ",
        '<label data-l10n-name="community-mozillaLink">Mozilla</label>',
    ),
    ("ZXQ003ZXQ", "Mercury"),
    ("ZXQ004ZXQ", "%S"),
    ("ZXQ005ZXQ", "SSLv3"),
)

BRANDED_MANIFEST_FIELDS = (
    ("name", "Mercury Language: "),
    ("description", "Mercury Language Pack for "),
)

FTL_KEYS = frozenset(key for keys in FTL_MESSAGES.values() for key in keys)
PROPERTY_KEYS = frozenset(key for keys in PROPERTIES_MESSAGES.values() for key in keys)


def load_changesets(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8") as stream:
        changesets = json.load(stream)
    if (
        not isinstance(changesets, dict)
        or not changesets
        or any(
            not isinstance(locale, str)
            or SAFE_LOCALE.fullmatch(locale) is None
            or not isinstance(entry, dict)
            or not isinstance(entry.get("revision"), str)
            or not isinstance(entry.get("platforms"), list)
            or not all(
                isinstance(platform, str) for platform in entry["platforms"]
            )
            for locale, entry in changesets.items()
        )
    ):
        raise ValueError(f"Invalid localization changesets file: {path}")
    revisions = {entry.get("revision") for entry in changesets.values()}
    if revisions != {EXPECTED_L10N_REVISION}:
        raise ValueError(
            "Firefox localization revisions do not match Mercury's pinned "
            f"revision: {sorted(str(revision) for revision in revisions)}"
        )
    return changesets


def locales_for_platform(changesets: dict[str, dict], platform: str) -> list[str]:
    if platform == "all":
        return sorted(changesets)
    prefix = PLATFORM_PREFIXES[platform]
    return sorted(
        locale
        for locale, entry in changesets.items()
        if any(
            platform_name.startswith(prefix)
            for platform_name in entry.get("platforms", [])
        )
    )


def load_translations(path: Path) -> dict[str, dict]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(catalog, dict)
        or catalog.get("schemaVersion") != 2
        or catalog.get("sourceLocale") != "en-US"
    ):
        raise ValueError(f"Unsupported translation catalog: {path}")
    locales = catalog.get("locales")
    if not isinstance(locales, dict):
        raise ValueError(f"Translation catalog locale map is invalid: {path}")
    for locale, entry in locales.items():
        if (
            not isinstance(locale, str)
            or SAFE_LOCALE.fullmatch(locale) is None
            or not isinstance(entry, dict)
            or entry.get("status") not in {"reviewed", "machine-draft"}
            or not isinstance(entry.get("target"), str)
            or SAFE_LOCALE.fullmatch(entry["target"]) is None
            or not isinstance(entry.get("messages"), dict)
            or not entry["messages"]
            or any(
                not isinstance(key, str)
                or not key
                or not isinstance(value, str)
                or not value.strip()
                for key, value in entry["messages"].items()
            )
        ):
            raise ValueError(f"Translation catalog entry is invalid: {locale}")
        if entry["status"] == "reviewed" and entry["target"] != locale:
            raise ValueError(
                f"Reviewed translation target does not match its locale: {locale}"
            )
    return locales


def translation_metadata(
    translations: dict[str, dict], locales: list[str]
) -> tuple[list[str], list[str], dict[str, str]]:
    reviewed = sorted(
        locale for locale in locales if translations[locale]["status"] == "reviewed"
    )
    drafts = sorted(set(locales) - set(reviewed))
    targets = {locale: translations[locale]["target"] for locale in drafts}
    return reviewed, drafts, targets


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_records(records) -> str:
    digest = hashlib.sha256()
    for name, content in records:
        encoded_name = name.encode("utf-8")
        if isinstance(content, str):
            content = content.encode("utf-8")
        digest.update(len(encoded_name).to_bytes(8, "big"))
        digest.update(encoded_name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def find_ftl_message(lines: list[str], key: str) -> tuple[int, int] | None:
    pattern = re.compile(rf"^{re.escape(key)}\s*=")
    matches = [index for index, line in enumerate(lines) if pattern.match(line)]
    if len(matches) > 1:
        raise ValueError(f"Duplicate Fluent message: {key}")
    if not matches:
        return None
    start = matches[0]
    end = start + 1
    while end < len(lines) and lines[end].startswith((" ", "\t")):
        end += 1
    return start, end


def property_continues(line: str) -> bool:
    content = line.rstrip("\r\n")
    trailing_backslashes = len(content) - len(content.rstrip("\\"))
    return trailing_backslashes % 2 == 1


def find_property(lines: list[str], key: str) -> tuple[int, int] | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*[:=]")
    matches = [index for index, line in enumerate(lines) if pattern.match(line)]
    if len(matches) > 1:
        raise ValueError(f"Duplicate properties message: {key}")
    if not matches:
        return None
    start = matches[0]
    end = start + 1
    while end < len(lines) and property_continues(lines[end - 1]):
        end += 1
    return start, end


def extract_message(
    lines: list[str], path: Path, key: str, finder
) -> list[str]:
    span = finder(lines, key)
    if span is None:
        raise ValueError(f"Reference message {key} is missing from {path}")
    start, end = span
    message = lines[start:end]
    if any("firefox" in line.casefold() for line in message):
        raise ValueError(f"Reference message {key} still contains Firefox: {path}")
    return message


def replace_message(
    lines: list[str], key: str, replacement: list[str], finder
) -> None:
    span = finder(lines, key)
    if span is None:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.extend(replacement)
    else:
        start, end = span
        lines[start:end] = replacement


def replace_product_name(locale: str, message: list[str]) -> list[str]:
    rendered = []
    for line in message:
        line = re.sub("firefox", "Mercury", line, flags=re.IGNORECASE)
        for alias in SORTED_PRODUCT_ALIASES.get(locale, ()):
            line = line.replace(alias, "Mercury")
        rendered.append(line)
    return rendered


def render_machine_message(value: str) -> str:
    for marker, replacement in MACHINE_REPLACEMENTS:
        value = value.replace(marker, replacement)
    if "ZXQ" in value:
        raise ValueError("A machine-translation placeholder was not resolved")
    return value


def render_community_message(value: str, original: list[str]) -> str:
    if "ZXQ002ZXQ" in value:
        original_text = "".join(original)
        match = re.search(
            r'<label data-l10n-name="community-creditsLink">(.*?)</label>',
            original_text,
        )
        if match is None:
            raise ValueError("The native community link text could not be recovered")
        community = (
            '<label data-l10n-name="community-creditsLink">'
            f"{match.group(1)}</label>"
        )
        value = value.replace("ZXQ002ZXQ", community)
    value = render_machine_message(value)
    mozilla_overlays = value.count('data-l10n-name="community-mozillaLink"')
    credits_overlays = value.count('data-l10n-name="community-creditsLink"')
    if mozilla_overlays == 0 or mozilla_overlays != credits_overlays:
        raise ValueError("The community overlays are missing or unbalanced")
    if not re.search(
        r"\{\s*-brand-short-name(?:\s*\([^{}]*\))?\s*\}", value
    ) or "Alex313031" not in value:
        raise ValueError("The Mercury About-dialog attribution is incomplete")
    original_text = "".join(original)
    brand_gender_selector = r"-brand-short-name\.gender\s*->"
    if re.search(brand_gender_selector, original_text) and not re.search(
        brand_gender_selector, value
    ):
        raise ValueError("The native brand-gender selector was not preserved")
    original_brand_calls = set(
        re.findall(r"-brand-short-name\s*(\([^{}]*\))", original_text)
    )
    rendered_brand_calls = set(
        re.findall(r"-brand-short-name\s*(\([^{}]*\))", value)
    )
    if not original_brand_calls <= rendered_brand_calls:
        raise ValueError("The native inflected brand-term call was not preserved")
    brand_pattern = (
        r"\{\s*-brand-short-name(?:\s*\([^{}]*\))?\s*\}"
        r"([^\s<,.;:!?]*)"
    )
    original_suffixes = {
        suffix
        for suffix in re.findall(brand_pattern, original_text)
        if any(character.isalpha() for character in suffix)
    }
    rendered_suffixes = {
        suffix
        for suffix in re.findall(brand_pattern, value)
        if any(character.isalpha() for character in suffix)
    }
    if not original_suffixes <= rendered_suffixes:
        raise ValueError("The native inflected brand-term suffix was not preserved")
    return value


def format_ftl_message(key: str, value: str) -> list[str]:
    value_lines = value.splitlines()
    if not value_lines or not value_lines[0].strip():
        raise ValueError(f"Machine draft for {key} has an empty first line")
    lines = [f"{key} = {value_lines[0]}\n"]
    lines.extend(f"    {line}\n" for line in value_lines[1:])
    return lines


def validate_message(
    lines: list[str], path: Path, key: str, finder, locale: str, reference: list[str]
) -> None:
    span = finder(lines, key)
    if span is None:
        raise ValueError(f"Prepared message {key} is missing from {path}")
    start, end = span
    message = lines[start:end]
    if any("firefox" in line.casefold() for line in message):
        raise ValueError(f"Prepared message {key} still contains Firefox: {path}")
    for alias in PRODUCT_ALIASES.get(locale, ()):
        if any(alias in line for line in message):
            raise ValueError(
                f"Prepared message {key} still contains a localized Firefox "
                f"name: {path}"
            )
    if finder is find_property:
        expected_placeholders = "".join(reference).count("%S")
        actual_placeholders = "".join(message).count("%S")
        if actual_placeholders != expected_placeholders:
            raise ValueError(
                f"Prepared message {key} has {actual_placeholders} %S markers; "
                f"expected {expected_placeholders}: {path}"
            )


def reference_messages(reference_root: Path):
    messages = []
    for resources, finder in (
        (FTL_MESSAGES, find_ftl_message),
        (PROPERTIES_MESSAGES, find_property),
    ):
        for (workspace_path, reference_path), keys in resources.items():
            source = reference_root / reference_path
            lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
            for key in keys:
                messages.append(
                    (
                        workspace_path,
                        key,
                        extract_message(lines, source, key, finder),
                        finder,
                    )
                )
    return messages


def reference_messages_sha256(messages) -> str:
    return sha256_records(
        (f"{path}\0{key}", "".join(message))
        for path, key, message, _finder in messages
    )


def controlled_resources_sha256(workspace: Path, locales: list[str]) -> str:
    relative_paths = sorted(
        {
            workspace_path
            for workspace_path, _reference_path in (
                *FTL_MESSAGES.keys(),
                *PROPERTIES_MESSAGES.keys(),
            )
        }
    )
    def records():
        for locale in sorted(locales):
            for relative_path in relative_paths:
                path = workspace / locale / relative_path
                if not path.is_file():
                    raise ValueError(
                        f"Controlled localization resource is missing: {path}"
                    )
                yield f"{locale}/{relative_path}", path.read_bytes()

    return sha256_records(records())


def validate_fluent_resources(
    workspace: Path, reference_root: Path, locales: list[str]
) -> None:
    firefox_root = reference_root.parents[2]
    fluent_dependency = firefox_root / "third_party/python/fluent.syntax"
    if not fluent_dependency.is_dir():
        raise ValueError(
            f"Firefox's vendored Fluent parser is missing: {fluent_dependency}"
        )
    sys.path.insert(0, str(fluent_dependency))
    try:
        from fluent.syntax import FluentParser, ast as fluent_ast
    except ImportError as error:
        raise ValueError("Unable to load Firefox's vendored Fluent parser") from error

    parser = FluentParser()
    relative_paths = sorted(path for path, _reference in FTL_MESSAGES)
    for locale in locales:
        for relative_path in relative_paths:
            path = workspace / locale / relative_path
            resource = parser.parse(path.read_text(encoding="utf-8"))
            if any(isinstance(entry, fluent_ast.Junk) for entry in resource.body):
                raise ValueError(f"Prepared Fluent resource is invalid: {path}")


def command_list(args: argparse.Namespace) -> int:
    changesets = load_changesets(args.changesets)
    locales = locales_for_platform(changesets, args.platform)
    if args.include_en_us:
        locales.insert(0, "en-US")
    print("\n".join(locales))
    return 0


def command_apply_translations(args: argparse.Namespace) -> int:
    if args.firefox_commit != EXPECTED_FIREFOX_COMMIT:
        raise ValueError(
            "Prepared Firefox checkout does not match Mercury's pinned commit: "
            f"{args.firefox_commit}"
        )
    changesets = load_changesets(args.changesets)
    supported_locales = locales_for_platform(changesets, "all")
    translations = load_translations(args.translations)
    if set(translations) != set(supported_locales):
        raise ValueError("Translation catalog does not exactly cover Firefox locales")
    reviewed_locales, draft_locales, draft_targets = translation_metadata(
        translations, supported_locales
    )

    missing_directories = [
        locale for locale in supported_locales if not (args.workspace / locale).is_dir()
    ]
    if missing_directories:
        raise ValueError(
            "Pinned localization checkout is missing supported locales: "
            + ", ".join(missing_directories)
        )

    messages = reference_messages(args.reference_root)

    for locale in supported_locales:
        entry = translations[locale]
        catalog_messages = entry["messages"]

        property_lines = {}
        expected_keys = set(FTL_KEYS)
        for (relative_path, _reference_path), keys in PROPERTIES_MESSAGES.items():
            target = args.workspace / locale / relative_path
            if not target.is_file():
                raise ValueError(f"Localization resource is missing: {target}")
            lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
            property_lines[relative_path] = lines
            if entry["status"] == "reviewed":
                expected_keys.update(keys)
            else:
                expected_keys.update(
                    key for key in keys if find_property(lines, key) is None
                )
        catalog_keys = set(catalog_messages)
        if not expected_keys <= catalog_keys <= expected_keys | PROPERTY_KEYS:
            raise ValueError(
                f"Translation catalog key set does not match locale {locale}"
            )

        for (relative_path, _reference_path), keys in FTL_MESSAGES.items():
            target = args.workspace / locale / relative_path
            if not target.is_file():
                raise ValueError(f"Localization resource is missing: {target}")
            lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
            for key in keys:
                span = find_ftl_message(lines, key)
                original = lines[slice(*span)] if span is not None else []
                value = catalog_messages[key]
                if key == "community-2":
                    value = render_community_message(value, original)
                else:
                    value = render_machine_message(value)
                replace_message(
                    lines, key, format_ftl_message(key, value), find_ftl_message
                )
            target.write_text("".join(lines), encoding="utf-8")

        for (relative_path, _reference_path), keys in PROPERTIES_MESSAGES.items():
            target = args.workspace / locale / relative_path
            lines = property_lines[relative_path]
            for key in keys:
                span = find_property(lines, key)
                if key in catalog_messages:
                    value = render_machine_message(catalog_messages[key])
                    replacement = [f"{key} = {value}\n"]
                else:
                    replacement = replace_product_name(locale, lines[slice(*span)])
                replace_message(lines, key, replacement, find_property)
            target.write_text("".join(lines), encoding="utf-8")

    validate_fluent_resources(
        args.workspace, args.reference_root, supported_locales
    )

    for locale in supported_locales:
        resource_lines = {}
        for relative_path, key, reference, finder in messages:
            path = args.workspace / locale / relative_path
            if relative_path not in resource_lines:
                resource_lines[relative_path] = path.read_text(
                    encoding="utf-8"
                ).splitlines(keepends=True)
            lines = resource_lines[relative_path]
            validate_message(
                lines,
                path,
                key,
                finder,
                locale,
                reference,
            )

    marker = {
        "schemaVersion": MARKER_SCHEMA_VERSION,
        "firefoxCommit": args.firefox_commit,
        "l10nRevision": EXPECTED_L10N_REVISION,
        "translationsSha256": sha256_file(args.translations),
        "generatorSha256": sha256_file(Path(__file__).resolve()),
        "referenceMessagesSha256": reference_messages_sha256(messages),
        "controlledResourcesSha256": controlled_resources_sha256(
            args.workspace, supported_locales
        ),
        "supportedLocales": supported_locales,
        "reviewedLocales": reviewed_locales,
        "machineDraftLocales": draft_locales,
        "machineDraftTargets": draft_targets,
        "controlledMessages": [
            {"path": path, "key": key}
            for path, key, _replacement, _finder in messages
        ],
    }
    marker_path = args.workspace / MARKER_NAME
    marker_path.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Prepared {len(supported_locales)} external locales: "
        f"{len(reviewed_locales)} reviewed, {len(draft_locales)} "
        "using explicitly identified machine drafts."
    )
    return 0


def command_target_platform(args: argparse.Namespace) -> int:
    environment = json.loads(args.environment.read_text(encoding="utf-8"))
    if not isinstance(environment, dict) or not isinstance(
        environment.get("substs"), dict
    ):
        raise ValueError(f"Invalid Firefox build environment: {args.environment}")
    toolkit = environment["substs"].get("MOZ_WIDGET_TOOLKIT")
    platforms = {
        "cocoa": "macos",
        "gtk": "linux",
        "windows": "windows",
    }
    try:
        print(platforms[toolkit])
    except KeyError as error:
        raise ValueError(
            f"Unsupported or unconfigured Firefox widget toolkit: {toolkit!r}"
        ) from error
    return 0


def load_marker(
    workspace: Path,
    translations: Path,
    reference_root: Path,
    expected_locales: list[str],
) -> dict:
    marker_path = workspace / MARKER_NAME
    if not marker_path.is_file():
        raise ValueError(
            f"Mercury localization marker is missing: {marker_path}. "
            "Run prepare_l10n.sh first."
        )
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if not isinstance(marker, dict):
        raise ValueError(f"Localization marker is not an object: {marker_path}")
    if marker.get("schemaVersion") != MARKER_SCHEMA_VERSION:
        raise ValueError(f"Unsupported Mercury localization marker: {marker_path}")
    if marker.get("l10nRevision") != EXPECTED_L10N_REVISION:
        raise ValueError(f"Localization marker uses the wrong revision: {marker_path}")
    if marker.get("firefoxCommit") != EXPECTED_FIREFOX_COMMIT:
        raise ValueError(
            f"Localization marker uses the wrong Firefox commit: {marker_path}"
        )
    expected_digest = sha256_file(translations)
    if marker.get("translationsSha256") != expected_digest:
        raise ValueError(
            "Localization marker was prepared from a different translation "
            f"catalog: {marker_path}"
        )
    expected_generator = sha256_file(Path(__file__).resolve())
    if marker.get("generatorSha256") != expected_generator:
        raise ValueError(
            f"Localization marker was prepared by a different generator: {marker_path}"
        )
    messages = reference_messages(reference_root)
    expected_reference = reference_messages_sha256(messages)
    if marker.get("referenceMessagesSha256") != expected_reference:
        raise ValueError(
            "Localization marker was prepared from different patched en-US "
            f"messages: {marker_path}"
        )
    translations_by_locale = load_translations(translations)
    if set(translations_by_locale) != set(expected_locales):
        raise ValueError("Translation catalog does not cover the Firefox locale set")
    expected_reviewed, expected_drafts, expected_draft_targets = (
        translation_metadata(translations_by_locale, expected_locales)
    )

    supported = marker.get("supportedLocales")
    reviewed = marker.get("reviewedLocales")
    drafts = marker.get("machineDraftLocales")
    draft_targets = marker.get("machineDraftTargets")
    if not all(isinstance(locales, list) for locales in (supported, reviewed, drafts)):
        raise ValueError(f"Localization marker has invalid locale lists: {marker_path}")
    if any(
        not isinstance(locale, str) or SAFE_LOCALE.fullmatch(locale) is None
        for locales in (supported, reviewed, drafts)
        for locale in locales
    ) or any(
        len(locales) != len(set(locales))
        for locales in (supported, reviewed, drafts)
    ):
        raise ValueError(f"Localization marker has unsafe locale lists: {marker_path}")
    if supported != expected_locales:
        raise ValueError("Localization marker does not cover the Firefox locale set")
    if set(reviewed) & set(drafts) or set(reviewed) | set(drafts) != set(
        supported
    ):
        raise ValueError(
            f"Localization marker has an invalid locale partition: {marker_path}"
        )
    if not isinstance(draft_targets, dict) or set(draft_targets) != set(drafts):
        raise ValueError(
            f"Localization marker has invalid machine-draft targets: {marker_path}"
        )
    if any(
        not isinstance(target, str) or SAFE_LOCALE.fullmatch(target) is None
        for target in draft_targets.values()
    ):
        raise ValueError(
            f"Localization marker has invalid machine-draft targets: {marker_path}"
        )
    if (
        reviewed != expected_reviewed
        or drafts != expected_drafts
        or draft_targets != expected_draft_targets
    ):
        raise ValueError(
            "Localization marker review metadata does not match the translation "
            f"catalog: {marker_path}"
        )
    expected_controlled_messages = [
        {"path": path, "key": key}
        for path, key, _replacement, _finder in messages
    ]
    if marker.get("controlledMessages") != expected_controlled_messages:
        raise ValueError(
            "Localization marker controlled-message metadata is invalid: "
            f"{marker_path}"
        )
    expected_resources = controlled_resources_sha256(workspace, expected_locales)
    if marker.get("controlledResourcesSha256") != expected_resources:
        raise ValueError(
            f"Controlled localization resources have changed: {marker_path}"
        )
    return marker


def language_pack_manifest(path: Path) -> tuple[dict, list[str]]:
    try:
        with path.open("rb") as stream:
            if stream.read(4) != b"PK\x03\x04":
                raise ValueError("missing ZIP local-file signature")
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                raise ValueError(
                    f"Language pack has a corrupt member {corrupt_member!r}: {path}"
                )
            manifest = json.loads(archive.read("manifest.json"))
    except (
        KeyError,
        NotImplementedError,
        RuntimeError,
        UnicodeDecodeError,
        ValueError,
        zipfile.BadZipFile,
        zlib.error,
    ) as error:
        raise ValueError(f"Invalid language pack: {path}: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError(f"Language-pack manifest is not an object: {path}")
    return manifest, members


def validate_language_pack(path: Path, locale: str) -> str | None:
    try:
        manifest, members = language_pack_manifest(path)
    except ValueError as error:
        return str(error)
    browser_settings = manifest.get("browser_specific_settings", {})
    if not isinstance(browser_settings, dict):
        return "language-pack browser_specific_settings is invalid"
    gecko = browser_settings.get("gecko", {})
    if not gecko:
        applications = manifest.get("applications", {})
        if not isinstance(applications, dict):
            return "language-pack applications metadata is invalid"
        gecko = applications.get("gecko", {})
    if not isinstance(gecko, dict):
        return "language-pack Gecko metadata is invalid"
    extension_id = gecko.get("id")
    expected_id = f"langpack-{locale}@{LANGPACK_EID_HOST}"
    if extension_id != expected_id:
        return f"language-pack ID {extension_id!r} (expected {expected_id!r})"
    if manifest.get("langpack_id") != locale:
        return (
            f"language-pack locale {manifest.get('langpack_id')!r} "
            f"(expected {locale!r})"
        )
    languages = manifest.get("languages")
    if not isinstance(languages, dict) or set(languages) != {locale}:
        actual_languages = (
            sorted(str(key) for key in languages)
            if isinstance(languages, dict)
            else languages
        )
        return (
            f"language-pack languages {actual_languages!r} "
            f"(expected [{locale!r}])"
        )
    if not isinstance(languages[locale], dict):
        return f"language-pack language metadata is invalid for {locale!r}"
    if manifest.get("manifest_version") != 2:
        return "language-pack manifest_version is not 2"
    for field, prefix in BRANDED_MANIFEST_FIELDS:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"language-pack {field} is invalid"
        if not value.startswith(prefix):
            return f"language-pack {field} does not identify Mercury"
        if "firefox" in value.casefold():
            return f"language-pack {field} still identifies Firefox"
    chrome_resources = languages[locale].get("chrome_resources")
    if not isinstance(chrome_resources, dict) or not chrome_resources:
        return f"language-pack chrome resources are invalid for {locale!r}"
    sources = manifest.get("sources")
    if not isinstance(sources, dict) or sources.get("browser") != {
        "base_path": "browser/"
    }:
        return "language-pack browser source mapping is invalid"
    if not any(name.startswith("browser/") and not name.endswith("/") for name in members):
        return "language pack contains no browser localization resources"
    return None


def validate_tar_archive(path: Path) -> str | None:
    try:
        with tarfile.open(path, mode="r:*") as archive:
            if not archive.getmembers():
                return "archive is empty"
    except (EOFError, OSError, tarfile.TarError) as error:
        return f"invalid tar archive: {error}"
    return None


def validate_tar_xz(path: Path) -> str | None:
    try:
        with path.open("rb") as stream:
            if stream.read(6) != b"\xfd7zXZ\x00":
                return "missing XZ stream signature"
    except OSError as error:
        return f"unable to read XZ archive: {error}"
    return validate_tar_archive(path)


def validate_uncompressed_tar(path: Path) -> str | None:
    try:
        with path.open("rb") as stream:
            signature = stream.read(6)
    except OSError as error:
        return f"unable to read tar archive: {error}"
    if signature.startswith((b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00")):
        return "archive is compressed instead of an uncompressed TAR"
    return validate_tar_archive(path)


def validate_zip_archive(path: Path) -> str | None:
    try:
        with path.open("rb") as stream:
            if stream.read(4) != b"PK\x03\x04":
                return "missing ZIP local-file signature"
        with zipfile.ZipFile(path) as archive:
            if not archive.infolist():
                return "archive is empty"
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                return f"corrupt ZIP member {corrupt_member!r}"
    except (
        NotImplementedError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        zlib.error,
    ) as error:
        return f"invalid ZIP archive: {error}"
    return None


def validate_pe_executable(path: Path) -> str | None:
    try:
        with path.open("rb") as stream:
            dos_header = stream.read(64)
            if len(dos_header) != 64 or dos_header[:2] != b"MZ":
                return "missing DOS executable header"
            pe_offset = int.from_bytes(dos_header[60:64], "little")
            if pe_offset < 64 or pe_offset > path.stat().st_size - 4:
                return "invalid PE header offset"
            stream.seek(pe_offset)
            if stream.read(4) != b"PE\0\0":
                return "missing PE executable signature"
    except OSError as error:
        return f"unable to read executable: {error}"
    return None


def validate_dmg(path: Path) -> str | None:
    try:
        if path.stat().st_size < 512:
            return "DMG is smaller than its UDIF trailer"
        with path.open("rb") as stream:
            stream.seek(-512, 2)
            if stream.read(4) != b"koly":
                return "missing UDIF koly trailer"
    except OSError as error:
        return f"unable to read DMG: {error}"
    return None


ARTIFACT_VALIDATORS = {
    "target.tar.xz": validate_tar_xz,
    "target.tar": validate_uncompressed_tar,
    "target.zip": validate_zip_archive,
    "target.installer.exe": validate_pe_executable,
    "target.dmg": validate_dmg,
}

REQUIRED_PACKAGES = {
    "linux": (("target.tar.xz",),),
    "windows": (("target.zip",), ("target.installer.exe",)),
    "macos": (("target.tar", "target.dmg"),),
}


def validate_locale_artifacts(
    locale_dir: Path, locale: str, platform: str
) -> list[str]:
    problems = []
    langpack = locale_dir / "target.langpack.xpi"
    if not langpack.is_file() or langpack.stat().st_size == 0:
        problems.append("language pack target.langpack.xpi")
    else:
        problem = validate_language_pack(langpack, locale)
        if problem is not None:
            problems.append(problem)

    for alternatives in REQUIRED_PACKAGES[platform]:
        failures = []
        valid = False
        for name in alternatives:
            path = locale_dir / name
            if not path.is_file() or path.stat().st_size == 0:
                failures.append(f"{name}: missing or empty")
                continue
            problem = ARTIFACT_VALIDATORS[name](path)
            if problem is None:
                valid = True
                break
            failures.append(f"{name}: {problem}")
        if not valid:
            problems.append("platform artifact " + "; ".join(failures))
    return problems


def command_manifest(args: argparse.Namespace) -> int:
    changesets = load_changesets(args.changesets)
    locales = locales_for_platform(changesets, args.platform)
    marker = load_marker(
        args.workspace,
        args.translations,
        args.reference_root,
        locales_for_platform(changesets, "all"),
    )
    reviewed = set(marker.get("reviewedLocales", []))
    draft_targets = marker["machineDraftTargets"]

    rows = []
    incomplete = []
    for locale in locales:
        if args.overall == "planned":
            status = "planned"
        else:
            locale_dir = args.destination / locale
            problems = validate_locale_artifacts(locale_dir, locale, args.platform)
            status = "produced" if not problems else "incomplete"
            if problems:
                incomplete.append(f"{locale} ({'; '.join(problems)})")
        translation = (
            "reviewed"
            if locale in reviewed
            else f"machine-draft/{draft_targets[locale]}"
        )
        rows.append(f"{locale}\t{args.platform}\t{translation}\t{status}")

    effective_overall = (
        "incomplete" if args.overall == "success" and incomplete else args.overall
    )
    content = [
        f"# overall={effective_overall}",
        f"# l10n_revision={EXPECTED_L10N_REVISION}",
        f"# translations_sha256={marker['translationsSha256']}",
        "locale\tplatform\tmercury_messages\tstatus",
        *rows,
    ]
    args.output.write_text("\n".join(content) + "\n", encoding="utf-8")
    if args.overall == "success" and incomplete:
        raise ValueError(
            "Firefox reported success but produced incomplete artifacts for: "
            + ", ".join(incomplete)
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--changesets", type=Path, required=True)
    list_parser.add_argument(
        "--platform", choices=["all", *PLATFORM_PREFIXES], required=True
    )
    list_parser.add_argument("--include-en-us", action="store_true")
    list_parser.set_defaults(handler=command_list)

    translation_parser = subparsers.add_parser("apply-translations")
    translation_parser.add_argument("--changesets", type=Path, required=True)
    translation_parser.add_argument("--workspace", type=Path, required=True)
    translation_parser.add_argument("--reference-root", type=Path, required=True)
    translation_parser.add_argument("--translations", type=Path, required=True)
    translation_parser.add_argument("--firefox-commit", required=True)
    translation_parser.set_defaults(handler=command_apply_translations)

    target_parser = subparsers.add_parser("target-platform")
    target_parser.add_argument("--environment", type=Path, required=True)
    target_parser.set_defaults(handler=command_target_platform)

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("--changesets", type=Path, required=True)
    manifest_parser.add_argument("--workspace", type=Path, required=True)
    manifest_parser.add_argument("--translations", type=Path, required=True)
    manifest_parser.add_argument("--reference-root", type=Path, required=True)
    manifest_parser.add_argument("--destination", type=Path, required=True)
    manifest_parser.add_argument("--output", type=Path, required=True)
    manifest_parser.add_argument(
        "--platform", choices=list(PLATFORM_PREFIXES), required=True
    )
    manifest_parser.add_argument(
        "--overall", choices=["planned", "success", "failed"], required=True
    )
    manifest_parser.set_defaults(handler=command_manifest)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
