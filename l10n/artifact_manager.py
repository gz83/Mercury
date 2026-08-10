#!/usr/bin/env python3

# Copyright (c) 2026 Alex313031 and gz83.

"""Validate, name, and inventory localized Mercury release artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tarfile
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import Optional

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from l10n.locale_manager import (
    load_changesets,
    load_marker,
    locales_for_platform,
    sha256_file,
)


VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)+")
ARTIFACT_TAG_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
LANGPACK_EID_HOST = "mercury.alex313031.github.io"
BRANDED_MANIFEST_FIELDS = (
    ("name", "Mercury Language: "),
    ("description", "Mercury Language Pack for "),
)
FileIdentity = tuple[int, int, int, int]
ArtifactDigest = tuple[str, FileIdentity]


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


def validate_language_pack(path: Path, locale: str) -> Optional[str]:
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
    if not any(
        name.startswith("browser/") and not name.endswith("/") for name in members
    ):
        return "language pack contains no browser localization resources"
    return None


def validate_tar_archive(path: Path) -> Optional[str]:
    try:
        with tarfile.open(path, mode="r:*") as archive:
            if not archive.getmembers():
                return "archive is empty"
    except (EOFError, OSError, tarfile.TarError) as error:
        return f"invalid tar archive: {error}"
    return None


def validate_tar_xz(path: Path) -> Optional[str]:
    try:
        with path.open("rb") as stream:
            if stream.read(6) != b"\xfd7zXZ\x00":
                return "missing XZ stream signature"
    except OSError as error:
        return f"unable to read XZ archive: {error}"
    return validate_tar_archive(path)


def validate_uncompressed_tar(path: Path) -> Optional[str]:
    try:
        with path.open("rb") as stream:
            signature = stream.read(6)
    except OSError as error:
        return f"unable to read tar archive: {error}"
    if signature.startswith((b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00")):
        return "archive is compressed instead of an uncompressed TAR"
    return validate_tar_archive(path)


def validate_zip_archive(path: Path) -> Optional[str]:
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


def validate_pe_executable(path: Path) -> Optional[str]:
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


def validate_dmg(path: Path) -> Optional[str]:
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


def version_argument(value: str) -> str:
    if VERSION_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(f"invalid release version: {value}")
    return value


def artifact_tag_argument(value: str) -> str:
    if ARTIFACT_TAG_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(f"invalid artifact tag: {value}")
    return value


def published_name(native_name: str, locale: str, version: str, tag: str) -> str:
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(f"Invalid release version: {version}")
    if ARTIFACT_TAG_PATTERN.fullmatch(tag) is None:
        raise ValueError(f"Invalid artifact tag: {tag}")
    if native_name == "target.langpack.xpi":
        return f"mercury-{version}.{locale}.langpack.xpi"
    return (
        f"mercury-{version}.{locale}.{tag}."
        f"{native_name.removeprefix('target.')}"
    )


def artifact_path(
    directory: Path, native_name: str, locale: str, version: str, tag: str
) -> Path:
    published = directory / published_name(native_name, locale, version, tag)
    native = directory / native_name
    if published.is_symlink() or native.is_symlink():
        raise ValueError(
            f"Localized artifacts must not be symbolic links: {native}, {published}"
        )
    if published.exists() and native.exists():
        raise ValueError(
            f"Both native and published artifacts exist: {native}, {published}"
        )
    return published if published.is_file() else native


def validated_artifacts(
    destination: Path,
    locale: str,
    platform: str,
    version: str,
    tag: str,
    artifact_kind: str,
) -> tuple[list[str], list[tuple[str, Path]]]:
    directory = destination / locale
    if directory.is_symlink():
        return [f"locale directory is a symbolic link: {directory}"], []
    problems = []
    artifacts = []

    native_name = "target.langpack.xpi"
    langpack = artifact_path(directory, native_name, locale, version, tag)
    if not langpack.is_file() or langpack.stat().st_size == 0:
        problems.append(f"{native_name}: missing or empty")
    else:
        problem = validate_language_pack(langpack, locale)
        if problem is None:
            artifacts.append((native_name, langpack))
        else:
            problems.append(problem)

    if artifact_kind == "langpack":
        return problems, artifacts

    for alternatives in REQUIRED_PACKAGES[platform]:
        failures = []
        selected = None
        for native_name in alternatives:
            path = artifact_path(directory, native_name, locale, version, tag)
            if not path.is_file() or path.stat().st_size == 0:
                failures.append(f"{native_name}: missing or empty")
                continue
            problem = ARTIFACT_VALIDATORS[native_name](path)
            if problem is None:
                selected = (native_name, path)
                break
            failures.append(f"{native_name}: {problem}")
        if selected is None:
            problems.append("platform artifact " + "; ".join(failures))
        else:
            artifacts.append(selected)
    return problems, artifacts


def selected_locales(
    args: argparse.Namespace, changesets: dict[str, dict]
) -> list[str]:
    supported = locales_for_platform(changesets, args.platform)
    requested = set(args.locales)
    if len(requested) != len(args.locales):
        raise ValueError("The locale list contains duplicates.")
    unknown = sorted(requested - set(supported))
    if unknown:
        raise ValueError(
            f"Locales are not supported on {args.platform}: {', '.join(unknown)}"
        )
    return [locale for locale in supported if locale in requested]


def atomic_write_text(path: Path, content: str) -> None:
    mode = (
        path.stat().st_mode & 0o777
        if path.is_file() and not path.is_symlink()
        else 0o644
    )
    descriptor, staging_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    staging = Path(staging_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        staging.chmod(mode)
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)


def file_identity(path: Path) -> FileIdentity:
    metadata = path.stat()
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def write_checksums(
    destination: Path,
    known_digests: Optional[dict[Path, ArtifactDigest]] = None,
) -> None:
    rows = []
    linked_directories = [
        path for path in destination.iterdir() if path.is_symlink()
    ]
    if linked_directories:
        raise ValueError(
            f"Refusing to checksum symbolic link: {linked_directories[0]}"
        )
    candidates = sorted(destination.glob("*/*"))
    unsafe = [
        path
        for path in candidates
        if path.name.startswith("mercury-")
        and (path.is_symlink() or path.parent.is_symlink())
    ]
    if unsafe:
        raise ValueError(f"Refusing to checksum symbolic link: {unsafe[0]}")
    paths = [
        path
        for path in candidates
        if path.is_file() and path.name.startswith("mercury-")
    ]
    digests = known_digests or {}
    for index, path in enumerate(paths, 1):
        relative = path.relative_to(destination).as_posix()
        print(
            f"[checksum {index}/{len(paths)}] {relative}",
            file=sys.stderr,
            flush=True,
        )
        known_digest = digests.get(path)
        if known_digest is None:
            digest = sha256_file(path)
        else:
            digest, identity = known_digest
            if file_identity(path) != identity:
                raise ValueError(
                    f"Artifact changed after validation: {path}"
                )
        rows.append(f"{digest}  {relative}")
    atomic_write_text(
        destination / "SHA256SUMS", "\n".join(rows) + ("\n" if rows else "")
    )


def publish_artifacts(
    artifacts: list[tuple[str, Path]], locale: str, version: str, tag: str
) -> list[tuple[str, Path]]:
    published_artifacts = []
    for native_name, path in artifacts:
        published = path.parent / published_name(
            native_name, locale, version, tag
        )
        if path != published:
            if published.exists():
                raise ValueError(
                    f"Both native and published artifacts exist: {path}, {published}"
                )
            path.replace(published)
        published_artifacts.append((native_name, published))
    return published_artifacts


def command_resume(args: argparse.Namespace) -> int:
    changesets = load_changesets(args.changesets)
    locales = selected_locales(args, changesets)
    for index, locale in enumerate(locales, 1):
        print(
            f"[validate {index}/{len(locales)}] {locale}",
            file=sys.stderr,
            flush=True,
        )
        problems, artifacts = validated_artifacts(
            args.destination,
            locale,
            args.platform,
            args.version,
            args.artifact_tag,
            args.artifact_kind,
        )
        if problems:
            print(
                f"[incomplete] {locale}: {'; '.join(problems)}",
                file=sys.stderr,
                flush=True,
            )
            continue
        publish_artifacts(
            artifacts, locale, args.version, args.artifact_tag
        )
        print(locale)
        print(f"[complete] {locale}", file=sys.stderr, flush=True)
    return 0


def resumed_locales(args: argparse.Namespace, locales: list[str]) -> set[str]:
    resumed = set(args.resumed_locales)
    if len(resumed) != len(args.resumed_locales):
        raise ValueError("The resumed locale list contains duplicates.")
    unknown_resumed = sorted(resumed - set(locales))
    if unknown_resumed:
        raise ValueError(
            "Resumed locales were not selected: " + ", ".join(unknown_resumed)
        )
    return resumed


def inventory_artifacts(
    args: argparse.Namespace,
    locales: list[str],
    marker: dict,
    resumed: set[str],
    *,
    publish: bool,
) -> tuple[list[str], list[str], dict[Path, ArtifactDigest]]:
    reviewed = set(marker["reviewedLocales"])
    rows = []
    incomplete = []
    digests = {}

    for index, locale in enumerate(locales, 1):
        artifacts = []
        if args.overall == "planned":
            status = "planned"
        else:
            print(
                f"[manifest {index}/{len(locales)}] {locale}",
                file=sys.stderr,
                flush=True,
            )
            problems, artifacts = validated_artifacts(
                args.destination,
                locale,
                args.platform,
                args.version,
                args.artifact_tag,
                args.artifact_kind,
            )
            if problems:
                status = "incomplete"
                incomplete.append(f"{locale} ({'; '.join(problems)})")
            else:
                if publish:
                    artifacts = publish_artifacts(
                        artifacts, locale, args.version, args.artifact_tag
                    )
                status = "resumed" if locale in resumed else "produced"
        translation = (
            "reviewed"
            if locale in reviewed
            else f"machine-draft/{marker['machineDraftTargets'][locale]}"
        )
        paths = [path for _native_name, path in artifacts]
        artifact_digests = []
        for path in paths:
            identity = file_identity(path)
            digest = sha256_file(path)
            if file_identity(path) != identity:
                raise ValueError(f"Artifact changed while hashing: {path}")
            digests[path] = (digest, identity)
            artifact_digests.append(digest)
        rows.append(
            "\t".join(
                (
                    locale,
                    args.platform,
                    translation,
                    status,
                    ",".join(path.name for path in paths),
                    ",".join(artifact_digests),
                )
            )
        )
    return rows, incomplete, digests


def write_manifest(
    args: argparse.Namespace, marker: dict, rows: list[str], incomplete: list[str]
) -> None:
    effective_overall = (
        "incomplete" if args.overall == "success" and incomplete else args.overall
    )
    content = [
        f"# overall={effective_overall}",
        f"# l10n_revision={marker['l10nRevision']}",
        f"# translations_sha256={marker['translationsSha256']}",
        f"# mercury_version={args.version}",
        f"# artifact_tag={args.artifact_tag}",
        f"# artifact_kind={args.artifact_kind}",
        "locale\tplatform\tmercury_messages\tstatus\tartifacts\tsha256",
        *rows,
    ]
    atomic_write_text(args.output, "\n".join(content) + "\n")
    if args.overall == "success" and incomplete:
        raise ValueError(
            "Firefox reported success but produced incomplete artifacts for: "
            + ", ".join(incomplete)
        )


def command_manifest(args: argparse.Namespace) -> int:
    changesets = load_changesets(args.changesets)
    locales = selected_locales(args, changesets)
    resumed = resumed_locales(args, locales)
    marker = load_marker(
        args.workspace,
        args.translations,
        args.reference_root,
        locales_for_platform(changesets, "all"),
    )
    rows, incomplete, _digests = inventory_artifacts(
        args, locales, marker, resumed, publish=False
    )
    write_manifest(args, marker, rows, incomplete)
    return 0


def command_publish(args: argparse.Namespace) -> int:
    changesets = load_changesets(args.changesets)
    locales = selected_locales(args, changesets)
    resumed = resumed_locales(args, locales)
    marker = load_marker(
        args.workspace,
        args.translations,
        args.reference_root,
        locales_for_platform(changesets, "all"),
    )
    rows, incomplete, digests = inventory_artifacts(
        args, locales, marker, resumed, publish=True
    )
    write_checksums(args.destination, digests)
    write_manifest(args, marker, rows, incomplete)
    return 0


def add_artifact_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--changesets", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--platform", choices=["linux", "windows", "macos"], required=True
    )
    parser.add_argument("--version", type=version_argument, required=True)
    parser.add_argument(
        "--artifact-tag", type=artifact_tag_argument, required=True
    )
    parser.add_argument(
        "--artifact-kind", choices=["full", "langpack"], required=True
    )
    parser.add_argument("--locales", nargs="+", required=True)


def add_inventory_arguments(parser: argparse.ArgumentParser) -> None:
    add_artifact_arguments(parser)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--translations", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    resume = subparsers.add_parser("resume")
    add_artifact_arguments(resume)
    resume.set_defaults(handler=command_resume)

    manifest = subparsers.add_parser("manifest")
    add_inventory_arguments(manifest)
    manifest.set_defaults(
        handler=command_manifest, overall="planned", resumed_locales=[]
    )

    publish = subparsers.add_parser("publish")
    add_inventory_arguments(publish)
    publish.add_argument("--resumed-locales", nargs="*", default=[])
    publish.add_argument(
        "--overall", choices=["success", "failed"], required=True
    )
    publish.set_defaults(handler=command_publish)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
