#!/usr/bin/env python3

"""Repackage an en-US Mercury build for every supported target locale."""

# Copyright (c) 2026 Alex313031 and gz83.

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from bootstrap import (
    default_source_directory,
    mach_command,
    native_path,
    run,
    target_platform,
)
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
  --dest DIRECTORY     Artifact directory (default: /tmp/mercury-localized-PLATFORM)
  --dry-run            Validate and print the locale set without building
  -v, --verbose        Enable verbose Firefox repackaging output
  -h, --help           Show this help

The prepared L10NBASEDIR must come from prepare_l10n.py. The script selects the
platform-specific Firefox {FIREFOX_VERSION} locale set, including `ja` on
Linux/Windows and `ja-JP-mac` on macOS, and restores the object directory to
en-US on exit.
"""

SUPPORTED_PLATFORMS = {"linux", "windows", "macos"}


class HelpRequested(Exception):
    """Raised when command-line help was requested."""


class UsageError(Exception):
    """Raised for an invalid command line."""

    def __init__(self, message: str, *, show_help: bool = False) -> None:
        super().__init__(message)
        self.show_help = show_help


def parse_arguments(
    arguments: List[str],
) -> Tuple[str, Optional[str], bool, bool]:
    platform = ""
    destination = None
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
        elif argument == "--dest":
            if index + 1 >= len(arguments):
                raise UsageError(f"{argument} requires a directory.")
            destination = arguments[index + 1]
            index += 2
        elif argument == "--dry-run":
            dry_run = True
            index += 1
        elif argument in {"-v", "--verbose"}:
            verbose = True
            index += 1
        elif argument in {"-h", "--help"}:
            raise HelpRequested
        else:
            raise UsageError(f"Unknown option: {argument}", show_help=True)

    if not platform:
        raise UsageError("--platform is required.")
    if platform not in SUPPORTED_PLATFORMS:
        raise UsageError(f"Unsupported platform: {platform}")
    return platform, destination, dry_run, verbose


def process_output(command: List[str]) -> str:
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command)
    return result.stdout.strip()


def optional_process_output(command: List[str]) -> str:
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def manager_command(locale_manager: Path, arguments: List[str]) -> List[str]:
    return [sys.executable, str(locale_manager), *arguments]


def run_manifest(
    locale_manager: Path,
    changesets: Path,
    workspace: Path,
    translations: Path,
    reference_root: Path,
    destination: Path,
    output: Path,
    platform: str,
    overall: str,
) -> None:
    run(
        manager_command(
            locale_manager,
            [
                "manifest",
                "--changesets",
                str(changesets),
                "--workspace",
                str(workspace),
                "--translations",
                str(translations),
                "--reference-root",
                str(reference_root),
                "--destination",
                str(destination),
                "--output",
                str(output),
                "--platform",
                platform,
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


def default_destination(platform: str) -> Path:
    base = Path(tempfile.gettempdir()) if os.name == "nt" else Path("/tmp")
    return base / f"mercury-localized-{platform}"


def resolve_destination(value: Optional[str], platform: str) -> Path:
    if not value:
        return default_destination(platform)
    destination = native_path(value)
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    return destination


def print_dry_run_manifest(
    locale_manager: Path,
    changesets: Path,
    workspace: Path,
    translations: Path,
    reference_root: Path,
    destination: Path,
    platform: str,
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="mercury-localization-manifest.", suffix=".tsv"
    )
    os.close(descriptor)
    output = Path(temporary_name)
    try:
        run_manifest(
            locale_manager,
            changesets,
            workspace,
            translations,
            reference_root,
            destination,
            output,
            platform,
            "planned",
        )
        print(output.read_text(encoding="utf-8"), end="")
    finally:
        output.unlink(missing_ok=True)


def configured_target_platform(
    locale_manager: Path, firefox_directory: Path
) -> str:
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
        return process_output(
            manager_command(
                locale_manager,
                ["target-platform", "--environment", str(environment)],
            )
        )
    finally:
        environment.unlink(missing_ok=True)


def finalize_repackage(
    status: int,
    locale_manager: Path,
    changesets: Path,
    workspace: Path,
    translations: Path,
    reference_root: Path,
    destination: Path,
    manifest: Path,
    platform: str,
    firefox_directory: Path,
) -> int:
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
    try:
        run_manifest(
            locale_manager,
            changesets,
            workspace,
            translations,
            reference_root,
            destination,
            manifest,
            platform,
            overall,
        )
    except (OSError, subprocess.CalledProcessError):
        status = 1

    print(f"Localization manifest: {manifest}")
    return status


def repackage(
    platform: str,
    destination_value: Optional[str],
    dry_run: bool,
    verbose: bool,
) -> int:
    mercury_directory = Path(__file__).resolve().parent
    locale_manager = mercury_directory / "l10n/locale_manager.py"
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
    locales_output = optional_process_output(
        manager_command(
            locale_manager,
            ["list", "--changesets", str(changesets), "--platform", platform],
        )
    )
    locales = locales_output.splitlines() if locales_output else []
    if not locales:
        raise ValueError(f"Firefox returned no locales for {platform}.")

    destination = resolve_destination(destination_value, platform)
    reference_root = firefox_directory / "browser/locales/en-US"
    if dry_run:
        print_dry_run_manifest(
            locale_manager,
            changesets,
            workspace,
            translations,
            reference_root,
            destination,
            platform,
        )
        return 0

    configured_platform = configured_target_platform(
        locale_manager, firefox_directory
    )
    if configured_platform != platform:
        raise ValueError(
            f"Configured Firefox target is {configured_platform}, not {platform}."
        )

    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Artifact destination is not a directory: {destination}")
    if destination.is_dir() and next(destination.iterdir(), None) is not None:
        raise ValueError(f"Artifact destination must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = destination / "localization-manifest.tsv"

    run_manifest(
        locale_manager,
        changesets,
        workspace,
        translations,
        reference_root,
        destination,
        manifest,
        platform,
        "planned",
    )
    os.environ["MERCURY_L10N_REPACK"] = "1"

    command = mach_command(
        ["repackage-single-locales", "--locales", *locales, "--dest", str(destination)]
    )
    if verbose:
        command.append("--verbose")

    print(
        f"Repackaging {len(locales)} Firefox-supported locales for {platform}..."
    )
    status = 0
    try:
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
        locale_manager,
        changesets,
        workspace,
        translations,
        reference_root,
        destination,
        manifest,
        platform,
        firefox_directory,
    )


def main() -> int:
    try:
        platform, destination, dry_run, verbose = parse_arguments(sys.argv[1:])
    except HelpRequested:
        print(HELP, end="")
        return 0
    except UsageError as error:
        print(error, file=sys.stderr)
        if error.show_help:
            print(HELP, end="", file=sys.stderr)
        return 2

    try:
        return repackage(platform, destination, dry_run, verbose)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        return error.returncode or 1
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
