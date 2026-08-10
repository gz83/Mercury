#!/usr/bin/env python3

"""Repackage an en-US Mercury build for every supported target locale."""

# Copyright (c) 2026 Alex313031 and gz83.

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from bootstrap import (
    default_source_directory,
    mach_command,
    native_path,
    run,
    target_platform,
)
from l10n.artifact_manager import published_name
from prepare_l10n import (
    BRANDING_OPTION,
    command_succeeds,
    files_equal,
    required_output,
)
from release_config import FIREFOX_COMMIT, FIREFOX_VERSION, patches_for_role


LOCALIZED_REPACKAGE_PATCHES = patches_for_role("localized-repackage")


HELP = f"""Repackage an en-US Mercury build into every Firefox-supported locale for one
target platform.

Usage: ./repackage_locales.py --platform PLATFORM [options]

Options:
  --platform PLATFORM  linux, windows, or macos (required)
  --all-locales        Repackage every locale supported by the target
  --locales LOCALE...  Repackage only the listed locales
  --locales-file FILE  Read locales from FILE (one per line; # comments allowed)
  --package FILE       Local en-US package to repackage (or MERCURY_PACKAGE)
  --dest DIRECTORY     Artifact directory (defaults under the system temp directory)
  --resume             Validate and skip complete artifacts already in --dest
  --langpacks-only     Build and publish only language-pack XPIs
  --dry-run            Validate and print the locale set without building
  -v, --verbose        Enable verbose Firefox repackaging output
  -h, --help           Show this help

The prepared L10NBASEDIR must come from prepare_l10n.py. The script selects the
platform-specific Firefox {FIREFOX_VERSION} locale set, including `ja` on
Linux/Windows and `ja-JP-mac` on macOS, and restores the object directory to
en-US on exit.
"""

SUPPORTED_PLATFORMS = {"linux", "windows", "macos"}

PROFILE_ARTIFACT_TAGS = {
    "mozconfig": ("linux", "linux-x86_64-avx"),
    "mozconfig-sse3": ("linux", "linux-x86_64-sse3"),
    "mozconfig-sse4": ("linux", "linux-x86_64-sse4"),
    "mozconfig-avx2": ("linux", "linux-x86_64-avx2"),
    "mozconfig-arm64": ("linux", "linux-aarch64-arm64"),
    "mozconfig-debug": ("linux", "linux-x86_64-avx-debug"),
    "mozconfig-win": ("windows", "windows-x86_64-avx"),
    "mozconfig-win-sse3": ("windows", "windows-x86_64-sse3"),
    "mozconfig-win-sse4": ("windows", "windows-x86_64-sse4"),
    "mozconfig-win-avx2": ("windows", "windows-x86_64-avx2"),
    "mozconfig-win-debug": ("windows", "windows-x86_64-avx-debug"),
    "mozconfig-win-cross": ("windows", "windows-x86_64-mingw-avx"),
    "mozconfig-win-avx2-cross": (
        "windows",
        "windows-x86_64-mingw-avx2",
    ),
    "mozconfig-macos-x64": ("macos", "macos-x86_64-avx2"),
    "mozconfig-macos-x64-cross": ("macos", "macos-x86_64-avx2"),
    "mozconfig-macos-arm64": ("macos", "macos-arm64"),
    "mozconfig-macos-arm64-cross": ("macos", "macos-arm64"),
}


@dataclass(frozen=True)
class Options:
    platform: str
    package: Optional[str]
    destination: Optional[str]
    locales: tuple[str, ...]
    locales_file: Optional[str]
    all_locales: bool
    resume: bool
    langpacks_only: bool
    dry_run: bool
    verbose: bool


@dataclass(frozen=True)
class ArtifactContext:
    manager: Path
    changesets: Path
    workspace: Path
    translations: Path
    reference_root: Path
    destination: Path
    platform: str
    locales: tuple[str, ...]
    artifact_tag: str
    artifact_kind: str


class HelpRequested(Exception):
    """Raised when command-line help was requested."""


class UsageError(Exception):
    """Raised for an invalid command line."""

    def __init__(self, message: str, *, show_help: bool = False) -> None:
        super().__init__(message)
        self.show_help = show_help


def parse_arguments(arguments: list[str]) -> Options:
    if arguments in (["-h"], ["--help"]):
        raise HelpRequested

    platform = ""
    package = None
    destination = None
    locales = []
    locales_file = None
    all_locales = False
    resume = False
    langpacks_only = False
    dry_run = False
    verbose = False
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--platform":
            if index + 1 >= len(arguments):
                raise UsageError(f"{argument} requires a value.")
            platform = arguments[index + 1]
            index += 2
        elif argument in {"--package", "--dest", "--locales-file"}:
            if index + 1 >= len(arguments):
                raise UsageError(f"{argument} requires a value.")
            if argument == "--package":
                package = arguments[index + 1]
            elif argument == "--dest":
                destination = arguments[index + 1]
            else:
                locales_file = arguments[index + 1]
            index += 2
        elif argument == "--locales":
            index += 1
            start = index
            while index < len(arguments) and not arguments[index].startswith("-"):
                locales.append(arguments[index])
                index += 1
            if index == start:
                raise UsageError("--locales requires at least one locale.")
        elif argument == "--all-locales":
            all_locales = True
            index += 1
        elif argument == "--resume":
            resume = True
            index += 1
        elif argument == "--langpacks-only":
            langpacks_only = True
            index += 1
        elif argument == "--dry-run":
            dry_run = True
            index += 1
        elif argument in {"-v", "--verbose"}:
            verbose = True
            index += 1
        else:
            raise UsageError(f"Unknown option: {argument}", show_help=True)

    if not platform:
        raise UsageError("--platform is required.")
    if platform not in SUPPORTED_PLATFORMS:
        raise UsageError(f"Unsupported platform: {platform}")
    selection_count = int(all_locales) + int(bool(locales)) + int(
        locales_file is not None
    )
    if selection_count != 1:
        raise UsageError(
            "Select exactly one of --all-locales, --locales, or --locales-file."
        )
    return Options(
        platform=platform,
        package=package,
        destination=destination,
        locales=tuple(locales),
        locales_file=locales_file,
        all_locales=all_locales,
        resume=resume,
        langpacks_only=langpacks_only,
        dry_run=dry_run,
        verbose=verbose,
    )


def manager_command(manager: Path, arguments: list[str]) -> list[str]:
    return [sys.executable, str(manager), *arguments]


def artifact_arguments(
    context: ArtifactContext, command: str, locales: tuple[str, ...]
) -> list[str]:
    return [
        command,
        "--changesets",
        str(context.changesets),
        "--destination",
        str(context.destination),
        "--platform",
        context.platform,
        "--version",
        FIREFOX_VERSION,
        "--artifact-tag",
        context.artifact_tag,
        "--artifact-kind",
        context.artifact_kind,
        "--locales",
        *locales,
    ]


def inventory_arguments(
    context: ArtifactContext,
    command: str,
    output: Path,
) -> list[str]:
    return [
        *artifact_arguments(context, command, context.locales),
        "--workspace",
        str(context.workspace),
        "--translations",
        str(context.translations),
        "--reference-root",
        str(context.reference_root),
        "--output",
        str(output),
    ]


def run_manifest(context: ArtifactContext, output: Path) -> None:
    run(
        manager_command(
            context.manager,
            inventory_arguments(context, "manifest", output),
        )
    )


def run_publish(
    context: ArtifactContext,
    output: Path,
    overall: str,
    resumed_locales: tuple[str, ...],
) -> None:
    run(
        manager_command(
            context.manager,
            [
                *inventory_arguments(context, "publish", output),
                "--resumed-locales",
                *resumed_locales,
                "--overall",
                overall,
            ],
        )
    )


def validate_firefox_checkout(
    mercury_directory: Path, firefox_value: str
) -> Path:
    firefox_directory = native_path(firefox_value)
    mach = firefox_directory / "mach"
    if (
        not mach.is_file()
        or not os.access(str(mach), os.X_OK)
        or not command_succeeds(
            [
                "git",
                "-C",
                str(firefox_directory),
                "rev-parse",
                "--is-inside-work-tree",
            ]
        )
    ):
        raise ValueError(
            f"Firefox checkout not found at {firefox_value}. Run setup.py first."
        )

    firefox_directory = firefox_directory.resolve()
    if required_output(
        ["git", "-C", str(firefox_directory), "rev-parse", "HEAD"]
    ) != FIREFOX_COMMIT:
        raise ValueError(
            f"Firefox checkout is not at the pinned Firefox {FIREFOX_VERSION} commit."
        )

    for patch in LOCALIZED_REPACKAGE_PATCHES:
        if not command_succeeds(
            [
                "git",
                "-C",
                str(firefox_directory),
                "apply",
                "--reverse",
                "--check",
                str(patch),
            ]
        ):
            raise ValueError(
                f"{patch.name} is not applied to {firefox_directory}; "
                "run setup.py first."
            )

    expected_branding = (
        mercury_directory / "browser/branding/mercury/configure.sh"
    )
    actual_branding = firefox_directory / "browser/branding/mercury/configure.sh"
    if not files_equal(expected_branding, actual_branding):
        raise ValueError(
            "Mercury branding overlay is missing or stale in "
            f"{firefox_directory}; run setup.py first."
        )

    mozconfig = firefox_directory / "mozconfig"
    if not mozconfig.is_file() or BRANDING_OPTION.search(
        mozconfig.read_text(encoding="utf-8")
    ) is None:
        raise ValueError(
            "The configured checkout does not select Mercury branding: "
            f"{firefox_directory}/mozconfig"
        )
    return firefox_directory


def default_destination(platform: str, langpacks_only: bool = False) -> Path:
    base = Path(tempfile.gettempdir()) if os.name == "nt" else Path("/tmp")
    family = "langpacks" if langpacks_only else "localized"
    return base / f"mercury-{family}-{platform}"


def resolve_destination(
    value: Optional[str], platform: str, langpacks_only: bool = False
) -> Path:
    if not value:
        return default_destination(platform, langpacks_only)
    destination = native_path(value)
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    return destination


def resolve_base_package(value: Optional[str]) -> Path:
    package_value = value or os.environ.get("MERCURY_PACKAGE")
    if not package_value:
        raise ValueError(
            "A local en-US Mercury package is required. Pass --package FILE "
            "or set MERCURY_PACKAGE."
        )
    package = native_path(package_value)
    if not package.is_absolute():
        package = Path.cwd() / package
    package = package.resolve()
    if not package.is_file() or package.stat().st_size == 0:
        raise ValueError(f"Mercury base package is missing or empty: {package}")
    return package


def read_locale_file(value: str) -> list[str]:
    path = native_path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_file():
        raise ValueError(f"Locale list is missing: {path}")
    locales = []
    for line in path.read_text(encoding="utf-8").splitlines():
        locale = line.split("#", 1)[0].strip()
        if locale:
            locales.append(locale)
    if not locales:
        raise ValueError(f"Locale list is empty: {path}")
    return locales


def select_locales(options: Options, supported: list[str]) -> list[str]:
    if options.all_locales:
        return supported
    requested = (
        list(options.locales)
        if options.locales
        else read_locale_file(options.locales_file or "")
    )
    if len(requested) != len(set(requested)):
        raise ValueError("The requested locale list contains duplicates.")
    unknown = sorted(set(requested) - set(supported))
    if unknown:
        raise ValueError(
            f"Locales are not supported on {options.platform}: "
            + ", ".join(unknown)
        )
    requested_set = set(requested)
    return [locale for locale in supported if locale in requested_set]


def configured_artifact_tag(
    mercury_directory: Path, firefox_directory: Path, platform: str
) -> str:
    active = firefox_directory / "mozconfig"
    active_contents = active.read_bytes() if active.is_file() else None
    matches = []
    for filename, (profile_platform, artifact_tag) in PROFILE_ARTIFACT_TAGS.items():
        candidate = mercury_directory / "mozconfigs" / filename
        if (
            active_contents is not None
            and profile_platform == platform
            and candidate.is_file()
            and candidate.read_bytes() == active_contents
        ):
            matches.append(artifact_tag)
    matches = sorted(set(matches))
    if len(matches) != 1:
        raise ValueError(
            "The active Firefox mozconfig does not uniquely match a Mercury "
            f"{platform} release profile. Run setup.py with the intended profile."
        )
    return matches[0]


def resume_artifacts(
    context: ArtifactContext, locales: tuple[str, ...]
) -> str:
    return required_output(
        manager_command(
            context.manager,
            artifact_arguments(context, "resume", locales),
        )
    )


def print_dry_run_manifest(
    context: ArtifactContext,
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="mercury-localization-manifest.", suffix=".tsv"
    )
    os.close(descriptor)
    output = Path(temporary_name)
    try:
        run_manifest(context, output)
        print(output.read_text(encoding="utf-8"), end="")
    finally:
        output.unlink(missing_ok=True)


def configured_build_environment(
    locale_manager: Path, firefox_directory: Path
) -> tuple[str, Path]:
    temporary_directory = os.environ.get("TMPDIR") or tempfile.gettempdir()
    descriptor, environment_name = tempfile.mkstemp(
        prefix="mercury-build-environment.",
        suffix=".json",
        dir=temporary_directory,
    )
    os.close(descriptor)
    environment = Path(environment_name)
    try:
        try:
            run(
                mach_command(
                    [
                        "environment",
                        "--format",
                        "json",
                        "--verbose",
                        "--output",
                        str(environment),
                    ]
                ),
                cwd=firefox_directory,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise ValueError(
                "Unable to read the configured Firefox target platform."
            ) from error
        data = json.loads(environment.read_text(encoding="utf-8"))
        topobjdir = data.get("topobjdir") if isinstance(data, dict) else None
        if not isinstance(topobjdir, str) or not topobjdir:
            raise ValueError(
                "Firefox build environment does not declare topobjdir."
            )
        platform = required_output(
            manager_command(
                locale_manager,
                ["target-platform", "--environment", str(environment)],
            )
        )
        return platform, native_path(topobjdir).resolve()
    finally:
        environment.unlink(missing_ok=True)


def build_language_packs(
    firefox_directory: Path,
    topobjdir: Path,
    destination: Path,
    locales: tuple[str, ...],
    artifact_tag: str,
    verbose: bool,
) -> None:
    source = topobjdir / "dist/target.langpack.xpi"
    os.environ["MOZ_SIMPLE_PACKAGE_NAME"] = "target"
    for index, locale in enumerate(locales, 1):
        print(
            f"[langpack {index}/{len(locales)}] {locale}",
            flush=True,
        )
        source.unlink(missing_ok=True)
        command = mach_command(["build"])
        if verbose:
            command.append("-v")
        command.append(f"langpack-{locale}")
        run(command, cwd=firefox_directory)
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError(
                f"Firefox did not produce the expected language pack: {source}"
            )
        locale_directory = destination / locale
        locale_directory.mkdir(parents=True, exist_ok=True)
        published = locale_directory / published_name(
            "target.langpack.xpi", locale, FIREFOX_VERSION, artifact_tag
        )
        published.unlink(missing_ok=True)
        shutil.copy2(source, locale_directory / "target.langpack.xpi")


def finalize_repackage(
    status: int,
    context: ArtifactContext,
    manifest: Path,
    firefox_directory: Path,
    resumed_locales: tuple[str, ...],
    restore_configuration: bool,
) -> int:
    if restore_configuration:
        print("\nRestoring the object directory to en-US...")
        try:
            run(
                mach_command(["configure", "--enable-ui-locale=en-US"]),
                cwd=firefox_directory,
            )
        except (OSError, subprocess.CalledProcessError):
            print(
                "Failed to restore the Firefox object directory to en-US.",
                file=sys.stderr,
            )
            status = 1

    overall = "success" if status == 0 else "failed"
    print(
        f"Publishing and inventorying {len(context.locales)} locales...",
        flush=True,
    )
    try:
        run_publish(context, manifest, overall, resumed_locales)
    except (OSError, subprocess.CalledProcessError):
        print("Failed to publish localized artifacts.", file=sys.stderr)
        status = 1

    print(f"Localization manifest: {manifest}")
    return status


def repackage(
    options: Options,
) -> int:
    mercury_directory = Path(__file__).resolve().parent
    locale_manager = mercury_directory / "l10n/locale_manager.py"
    artifact_manager = mercury_directory / "l10n/artifact_manager.py"
    translations = mercury_directory / "l10n/translations.json"
    firefox_value = os.environ.get("MOZ_SRC_DIR") or default_source_directory(
        target_platform([])
    )

    if shutil.which("git") is None:
        raise ValueError("Required command is unavailable: git")
    firefox_directory = validate_firefox_checkout(
        mercury_directory, firefox_value
    )

    workspace_value = os.environ.get("L10NBASEDIR")
    if not workspace_value or not native_path(workspace_value).is_dir():
        raise ValueError(
            "L10NBASEDIR must point to a workspace created by prepare_l10n.py."
        )
    workspace = native_path(workspace_value).resolve()
    os.environ["L10NBASEDIR"] = str(workspace)

    changesets = firefox_directory / "browser/locales/l10n-changesets.json"
    locales_output = required_output(
        manager_command(
            locale_manager,
            [
                "list",
                "--changesets",
                str(changesets),
                "--platform",
                options.platform,
            ],
        )
    )
    supported_locales = locales_output.splitlines() if locales_output else []
    if not supported_locales:
        raise ValueError(f"Firefox returned no locales for {options.platform}.")
    locales = tuple(select_locales(options, supported_locales))
    artifact_tag = configured_artifact_tag(
        mercury_directory, firefox_directory, options.platform
    )
    artifact_kind = "langpack" if options.langpacks_only else "full"

    destination = resolve_destination(
        options.destination, options.platform, options.langpacks_only
    )
    reference_root = firefox_directory / "browser/locales/en-US"
    context = ArtifactContext(
        manager=artifact_manager,
        changesets=changesets,
        workspace=workspace,
        translations=translations,
        reference_root=reference_root,
        destination=destination,
        platform=options.platform,
        locales=locales,
        artifact_tag=artifact_tag,
        artifact_kind=artifact_kind,
    )
    if options.dry_run:
        print_dry_run_manifest(context)
        return 0

    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Artifact destination is not a directory: {destination}")
    if (
        not options.resume
        and destination.is_dir()
        and next(destination.iterdir(), None) is not None
    ):
        raise ValueError(f"Artifact destination must be empty: {destination}")

    configured_platform, topobjdir = configured_build_environment(
        locale_manager, firefox_directory
    )
    if configured_platform != options.platform:
        raise ValueError(
            f"Configured Firefox target is {configured_platform}, "
            f"not {options.platform}."
        )

    destination.mkdir(parents=True, exist_ok=True)
    manifest = destination / "localization-manifest.tsv"

    resumed_locales: tuple[str, ...] = ()
    if options.resume:
        print(
            f"Validating {len(locales)} existing locale directories...",
            flush=True,
        )
        completed_output = resume_artifacts(context, locales)
        completed = set(completed_output.splitlines()) if completed_output else set()
        resumed_locales = tuple(
            locale for locale in locales if locale in completed
        )
    pending_locales = tuple(
        locale for locale in locales if locale not in resumed_locales
    )
    base_package = (
        resolve_base_package(options.package)
        if pending_locales and not options.langpacks_only
        else None
    )

    run_manifest(context, manifest)
    os.environ["MERCURY_L10N_REPACK"] = "1"
    if base_package is not None:
        os.environ["MOZ_ARTIFACT_FILE"] = str(base_package)

    print(f"Selected locales: {len(locales)}")
    if resumed_locales:
        print(f"Already complete: {len(resumed_locales)}")
    print(f"Locales to repackage: {len(pending_locales)}")
    status = 0
    if pending_locales:
        try:
            if options.langpacks_only:
                build_language_packs(
                    firefox_directory,
                    topobjdir,
                    destination,
                    pending_locales,
                    artifact_tag,
                    options.verbose,
                )
            else:
                command = mach_command(
                    [
                        "repackage-single-locales",
                        "--locales",
                        *pending_locales,
                        "--dest",
                        str(destination),
                    ]
                )
                if options.verbose:
                    command.append("--verbose")
                run(command, cwd=firefox_directory)
        except subprocess.CalledProcessError as error:
            status = error.returncode or 1
        except OSError as error:
            print(error, file=sys.stderr)
            status = 1
        except KeyboardInterrupt:
            status = 130
    return finalize_repackage(
        status,
        context,
        manifest,
        firefox_directory,
        resumed_locales,
        bool(pending_locales) and not options.langpacks_only,
    )


def main() -> int:
    try:
        options = parse_arguments(sys.argv[1:])
    except HelpRequested:
        print(HELP, end="")
        return 0
    except UsageError as error:
        print(error, file=sys.stderr)
        if error.show_help:
            print(HELP, end="", file=sys.stderr)
        return 2

    try:
        return repackage(options)
    except subprocess.CalledProcessError as error:
        return error.returncode or 1
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
