#!/usr/bin/env python3

"""Prepare a pinned Firefox checkout for building Mercury."""

# Copyright (c) 2026 Alex313031 and gz83.

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bootstrap import (
    default_source_directory,
    git_output,
    native_path,
    run,
    target_platform,
)
from release_config import (
    FIREFOX_COMMIT,
    FIREFOX_RELEASE,
    FIREFOX_VERSION,
    PATCH_FILES,
)


PROFILE_CONFIGS: Dict[str, Tuple[str, str]] = {
    "--linux": ("Linux AVX", "mozconfig"),
    "--win": ("Windows native AVX", "mozconfig-win"),
    "--cross": ("Windows MinGW AVX", "mozconfig-win-cross"),
    "--cross-avx2": (
        "Windows MinGW AVX2",
        "mozconfig-win-avx2-cross",
    ),
    "--sse3": ("Linux SSE3", "mozconfig-sse3"),
    "--win-sse3": ("Windows native SSE3", "mozconfig-win-sse3"),
    "--sse4": ("Linux SSE4.1", "mozconfig-sse4"),
    "--win-sse4": ("Windows native SSE4.1", "mozconfig-win-sse4"),
    "--avx2": ("Linux AVX2", "mozconfig-avx2"),
    "--win-avx2": ("Windows native AVX2", "mozconfig-win-avx2"),
    "--debug": ("Linux debug AVX", "mozconfig-debug"),
    "--win-debug": ("Windows debug AVX", "mozconfig-win-debug"),
    "--mac": ("macOS x64", "mozconfig-macos-x64"),
    "--mac-arm": ("macOS ARM64", "mozconfig-macos-arm64"),
    "--mac-cross": ("macOS x64 cross", "mozconfig-macos-x64-cross"),
    "--mac-arm-cross": (
        "macOS ARM64 cross",
        "mozconfig-macos-arm64-cross",
    ),
    "--arm64": ("Linux ARM64", "mozconfig-arm64"),
    "--raspi": ("Linux ARM64", "mozconfig-arm64"),
}

FILE_OVERLAYS = (
    ("app/mercury.exe.manifest", "browser/app/mercury.exe.manifest"),
    ("app/module.ver", "browser/app/module.ver"),
    (
        "app/distribution/policies.json",
        "browser/app/distribution/policies.json",
    ),
    (
        "other-licenses/7zstub/firefox/7zSD.Win32.sfx",
        "other-licenses/7zstub/firefox/7zSD.Win32.sfx",
    ),
    (
        "other-licenses/7zstub/firefox/7zSD.ARM64.sfx",
        "other-licenses/7zstub/firefox/7zSD.ARM64.sfx",
    ),
    (
        "other-licenses/7zstub/firefox/setup.ico",
        "other-licenses/7zstub/firefox/setup.ico",
    ),
)

DIRECTORY_OVERLAYS = (
    ("browser/branding/mercury", "browser/branding/mercury"),
)

HELP = f"""Prepare Firefox {FIREFOX_VERSION} for a Mercury build.

Usage: ./setup.py [profile] [--check]

The script applies the release-targeted Firefox patches, synchronizes only
Mercury's explicit product-owned overlays, and installs the selected mozconfig.
It does not recursively overlay the repository's app/ or browser/ directories.

Profiles:
  --linux             Linux AVX (default)
  --sse3              Linux SSE3
  --sse4              Linux SSE4.1
  --avx2              Linux AVX2
  --arm64, --raspi    Linux ARM64
  --debug             Linux debug AVX
  --win               Windows native AVX
  --win-sse3          Windows native SSE3
  --win-sse4          Windows native SSE4.1
  --win-avx2          Windows native AVX2
  --win-debug         Windows debug AVX
  --cross             Windows MinGW AVX
  --cross-avx2        Windows MinGW AVX2
  --mac               macOS x64
  --mac-arm           macOS ARM64
  --mac-cross         macOS x64 cross-compile
  --mac-arm-cross     macOS ARM64 cross-compile

Options:
  --check             Validate the checkout and inputs without modifying it
  -h, --help          Show this help

Environment variables:
  MOZ_SRC_DIR         Firefox checkout directory
"""


class HelpRequested(Exception):
    """Raised when command-line help was requested."""


class UsageError(Exception):
    """Raised for an invalid command line."""


@dataclass(frozen=True)
class SetupOptions:
    profile: str
    label: str
    mozconfig: str
    check_only: bool


def parse_arguments(arguments: List[str]) -> SetupOptions:
    selected: Optional[str] = None
    check_only = False
    for argument in arguments:
        if argument in {"-h", "--help"}:
            raise HelpRequested
        if argument == "--check":
            if check_only:
                raise UsageError("--check may be specified only once.")
            check_only = True
            continue
        if argument not in PROFILE_CONFIGS:
            raise UsageError(f"Unknown option: {argument}")
        if selected is not None:
            raise UsageError("Only one build profile may be selected.")
        selected = argument

    profile = selected or "--linux"
    label, mozconfig = PROFILE_CONFIGS[profile]
    return SetupOptions(profile, label, mozconfig, check_only)


def git_command(source_directory: Path, arguments: List[str]) -> List[str]:
    return [
        "git",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(source_directory),
        *arguments,
    ]


def command_succeeds(command: List[str]) -> bool:
    try:
        return (
            subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        return False


def resolve_firefox_checkout() -> Tuple[str, Path]:
    source_value = os.environ.get("MOZ_SRC_DIR") or default_source_directory(
        target_platform([])
    )
    os.environ["MOZ_SRC_DIR"] = source_value
    source_directory = native_path(source_value)

    inside_work_tree = git_output(
        [
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(source_directory),
            "rev-parse",
            "--is-inside-work-tree",
        ],
        stderr=subprocess.DEVNULL,
    )
    if inside_work_tree != "true":
        raise ValueError(
            f"Firefox Git checkout not found at {source_value}. "
            "Run ./bootstrap.py first."
        )

    current_commit = git_output(
        [
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(source_directory),
            "rev-parse",
            "HEAD",
        ],
        stderr=subprocess.DEVNULL,
    )
    if current_commit != FIREFOX_COMMIT:
        raise ValueError(
            f"Expected {FIREFOX_RELEASE} ({FIREFOX_COMMIT}), "
            f"found {current_commit or 'an unreadable revision'}."
        )
    return source_value, source_directory.resolve()


def required_inputs(
    mercury_directory: Path, options: SetupOptions
) -> Tuple[List[Path], Path]:
    patches = list(PATCH_FILES)

    for source_name, _ in FILE_OVERLAYS:
        source = mercury_directory / source_name
        if not source.is_file():
            raise ValueError(f"Required Mercury overlay is missing: {source}")
    for source_name, _ in DIRECTORY_OVERLAYS:
        source = mercury_directory / source_name
        if not source.is_dir():
            raise ValueError(f"Required Mercury overlay is missing: {source}")

    api_key = mercury_directory / "mozconfigs/ga"
    if not api_key.is_file():
        raise ValueError(f"API key file is missing: {api_key}")
    mozconfig = mercury_directory / "mozconfigs" / options.mozconfig
    if not mozconfig.is_file():
        raise ValueError(f"Mozconfig is missing: {mozconfig}")
    return patches, mozconfig


def patch_status(
    source_directory: Path, patch: Path
) -> str:
    if command_succeeds(
        git_command(source_directory, ["apply", "--check", str(patch)])
    ):
        return "pending"
    if command_succeeds(
        git_command(
            source_directory,
            ["apply", "--reverse", "--check", str(patch)],
        )
    ):
        return "applied"
    return "conflict"


def inspect_patches(
    source_directory: Path, patches: List[Path]
) -> List[Tuple[Path, str]]:
    statuses = [
        (patch, patch_status(source_directory, patch)) for patch in patches
    ]
    conflicts = [patch.name for patch, status in statuses if status == "conflict"]
    if conflicts:
        names = ", ".join(conflicts)
        raise ValueError(
            f"Firefox patches do not apply cleanly: {names}. Reset the "
            f"checkout to {FIREFOX_RELEASE} and rerun ./setup.py."
        )
    return statuses


def apply_patches(
    source_directory: Path, statuses: List[Tuple[Path, str]]
) -> None:
    for patch, status in statuses:
        if status == "applied":
            print(f"Patch already applied: {patch.name}")
            continue
        print(f"Applying patch: {patch.name}")
        run(
            git_command(source_directory, ["apply", str(patch)]),
            cwd=source_directory,
        )


def copy_file(source: Path, destination: Path, description: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(f"{description}: {destination}")


def replace_overlay_directory(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.setup-",
            dir=destination.parent,
        )
    )
    shutil.rmtree(staging)
    try:
        shutil.copytree(
            source,
            staging,
            copy_function=shutil.copy2,
            symlinks=True,
        )
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.is_dir():
            shutil.rmtree(destination)
        staging.replace(destination)
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)
    print(f"Synchronized overlay: {destination}")


def install_overlays(
    mercury_directory: Path, source_directory: Path
) -> None:
    for source_name, destination_name in FILE_OVERLAYS:
        copy_file(
            mercury_directory / source_name,
            source_directory / destination_name,
            "Installed overlay",
        )
    for source_name, destination_name in DIRECTORY_OVERLAYS:
        replace_overlay_directory(
            mercury_directory / source_name,
            source_directory / destination_name,
        )


def install_build_configuration(
    mercury_directory: Path,
    source_directory: Path,
    mozconfig: Path,
) -> None:
    copy_file(
        mercury_directory / "mozconfigs/ga",
        source_directory / "ga",
        "Installed API key file",
    )
    copy_file(
        mozconfig,
        source_directory / "mozconfig",
        "Selected mozconfig",
    )


def prepare(options: SetupOptions) -> None:
    mercury_directory = Path(__file__).resolve().parent
    source_value, source_directory = resolve_firefox_checkout()
    patches, mozconfig = required_inputs(mercury_directory, options)
    statuses = inspect_patches(source_directory, patches)

    if options.check_only:
        pending = sum(status == "pending" for _, status in statuses)
        applied = len(statuses) - pending
        print(f"Firefox checkout: {source_value}")
        print(f"Firefox revision: {FIREFOX_RELEASE} ({FIREFOX_COMMIT})")
        print(f"Patches: {pending} pending, {applied} already applied")
        print("Overlays: 6 explicit files and browser/branding/mercury/")
        print(f"Build profile: {options.label} ({mozconfig.name})")
        print("Validation completed without modifying the checkout.")
        return

    print(f"Preparing {source_value} for Mercury ({options.label})...")
    apply_patches(source_directory, statuses)
    install_overlays(mercury_directory, source_directory)
    install_build_configuration(
        mercury_directory,
        source_directory,
        mozconfig,
    )
    print("\nMercury source preparation completed.")
    print("Run ./build.py to build the selected profile.")


def main() -> int:
    try:
        options = parse_arguments(sys.argv[1:])
    except HelpRequested:
        print(HELP, end="")
        return 0
    except UsageError as error:
        print(error, file=sys.stderr)
        print(HELP, end="", file=sys.stderr)
        return 2

    try:
        prepare(options)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
