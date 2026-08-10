#!/usr/bin/env python3

# Copyright (c) 2026 Alex313031 and gz83.

"""Validate, name, and inventory localized Mercury release artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from l10n.locale_manager import (
    ARTIFACT_VALIDATORS,
    REQUIRED_PACKAGES,
    load_changesets,
    load_marker,
    locales_for_platform,
    sha256_file,
    validate_language_pack,
)


def published_name(native_name: str, locale: str, version: str, tag: str) -> str:
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
    unknown = sorted(requested - set(supported))
    if unknown:
        raise ValueError(
            f"Locales are not supported on {args.platform}: {', '.join(unknown)}"
        )
    return [locale for locale in supported if locale in requested]


def command_complete(args: argparse.Namespace) -> int:
    changesets = load_changesets(args.changesets)
    for locale in selected_locales(args, changesets):
        problems, _artifacts = validated_artifacts(
            args.destination,
            locale,
            args.platform,
            args.version,
            args.artifact_tag,
            args.artifact_kind,
        )
        if not problems:
            print(locale)
    return 0


def write_checksums(destination: Path) -> None:
    rows = []
    paths = [
        path
        for path in sorted(destination.glob("*/*"))
        if path.is_file() and path.name.startswith("mercury-")
    ]
    for index, path in enumerate(paths, 1):
        relative = path.relative_to(destination).as_posix()
        print(
            f"[checksum {index}/{len(paths)}] {relative}",
            file=sys.stderr,
            flush=True,
        )
        rows.append(f"{sha256_file(path)}  {relative}")
    (destination / "SHA256SUMS").write_text(
        "\n".join(rows) + ("\n" if rows else ""), encoding="utf-8"
    )


def command_finalize(args: argparse.Namespace) -> int:
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
        for native_name, path in artifacts:
            published = path.parent / published_name(
                native_name, locale, args.version, args.artifact_tag
            )
            if path == published:
                continue
            if published.exists():
                raise ValueError(
                    f"Both native and published artifacts exist: {path}, {published}"
                )
            path.replace(published)
        problems, _artifacts = validated_artifacts(
            args.destination,
            locale,
            args.platform,
            args.version,
            args.artifact_tag,
            args.artifact_kind,
        )
        if problems:
            raise ValueError(
                f"Finalized artifacts failed validation for {locale}: "
                + "; ".join(problems)
            )
        print(locale)
        print(f"[complete] {locale}", file=sys.stderr, flush=True)
    write_checksums(args.destination)
    return 0


def command_manifest(args: argparse.Namespace) -> int:
    changesets = load_changesets(args.changesets)
    locales = selected_locales(args, changesets)
    marker = load_marker(
        args.workspace,
        args.translations,
        args.reference_root,
        locales_for_platform(changesets, "all"),
    )
    reviewed = set(marker["reviewedLocales"])
    resumed = set(args.resumed_locales)
    rows = []
    incomplete = []

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
                status = "resumed" if locale in resumed else "produced"
        translation = (
            "reviewed"
            if locale in reviewed
            else f"machine-draft/{marker['machineDraftTargets'][locale]}"
        )
        paths = [path for _native_name, path in artifacts]
        rows.append(
            "\t".join(
                (
                    locale,
                    args.platform,
                    translation,
                    status,
                    ",".join(path.name for path in paths),
                    ",".join(sha256_file(path) for path in paths),
                )
            )
        )

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
    args.output.write_text("\n".join(content) + "\n", encoding="utf-8")
    if args.overall == "success" and incomplete:
        raise ValueError(
            "Firefox reported success but produced incomplete artifacts for: "
            + ", ".join(incomplete)
        )
    return 0


def add_artifact_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--changesets", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--platform", choices=["linux", "windows", "macos"], required=True
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--artifact-tag", required=True)
    parser.add_argument(
        "--artifact-kind", choices=["full", "langpack"], required=True
    )
    parser.add_argument("--locales", nargs="+", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, handler in (
        ("complete", command_complete),
        ("finalize", command_finalize),
    ):
        command_parser = subparsers.add_parser(name)
        add_artifact_arguments(command_parser)
        command_parser.set_defaults(handler=handler)

    manifest = subparsers.add_parser("manifest")
    add_artifact_arguments(manifest)
    manifest.add_argument("--workspace", type=Path, required=True)
    manifest.add_argument("--translations", type=Path, required=True)
    manifest.add_argument("--reference-root", type=Path, required=True)
    manifest.add_argument("--output", type=Path, required=True)
    manifest.add_argument("--resumed-locales", nargs="*", default=[])
    manifest.add_argument(
        "--overall", choices=["planned", "success", "failed"], required=True
    )
    manifest.set_defaults(handler=command_manifest)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
