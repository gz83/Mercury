#!/usr/bin/env python3

"""Build a Mercury Debian package with Firefox's repackage tooling."""

# Copyright (c) 2026 Alex313031 and gz83.

import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import List, Optional, Tuple

from bootstrap import (
    default_source_directory,
    mach_command,
    native_path,
    run,
    target_platform,
)
from prepare_l10n import command_succeeds, required_output
from release_config import FIREFOX_COMMIT, FIREFOX_VERSION, patches_for_role


PACKAGE_NAME = "mercury-browser"
DEBIAN_REPACKAGE_PATCHES = patches_for_role("debian-repackage")
INSTALL_PATH = "usr/lib/mercury"
SUPPORTED_SUFFIXES = (".tar.xz", ".tar.bz2", ".tar.gz")
REQUIRED_COMMANDS = ("dh", "dpkg-buildpackage", "dpkg-deb", "git")
SAFE_ARCHIVE_ROOT = re.compile(r"^[A-Za-z0-9._+-]+$")
ARCHITECTURES = {
    "amd64": ("x86_64", "amd64"),
    "x86_64": ("x86_64", "amd64"),
    "i386": ("x86", "i386"),
    "x86": ("x86", "i386"),
    "arm64": ("aarch64", "arm64"),
    "aarch64": ("aarch64", "arm64"),
}
ELF_MACHINES = {3: "i386", 62: "amd64", 183: "arm64"}

HELP = """Build a Debian package with Firefox's `mach repackage deb` workflow.

Usage: ./make_deb.py [options] [archive]

Archives produced by `./mach package` in .tar.xz, .tar.bz2, or .tar.gz
format are supported. If archive is omitted, the script searches this
repository and $MOZ_SRC_DIR/obj-*/dist/ for exactly one Mercury archive.

Options:
  -o, --output FILE  Write the package to FILE
  -h, --help         Show this help

Environment variables:
  MOZ_SRC_DIR       Firefox checkout prepared by setup.py
  L10NBASEDIR       Workspace created by prepare_l10n.py (required)
  DEB_ARCH          Target architecture: amd64, i386, arm64, x86_64, x86,
                    or aarch64 (default: detected from the archive)
  DEB_BUILD_NUMBER  Debian build number (default: 1)
"""


class HelpRequested(Exception):
    """Raised when command-line help was requested."""


class UsageError(Exception):
    """Raised for an invalid command line."""

    def __init__(self, message: str, *, show_help: bool = False) -> None:
        super().__init__(message)
        self.show_help = show_help


def parse_arguments(arguments: List[str]) -> Tuple[Optional[str], Optional[str]]:
    archive = None
    output = None
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in {"-o", "--output"}:
            if index + 1 >= len(arguments):
                raise UsageError(f"{argument} requires a file path.")
            output = arguments[index + 1]
            index += 2
        elif argument in {"-h", "--help"}:
            raise HelpRequested
        elif argument.startswith("-"):
            raise UsageError(f"Unknown option: {argument}", show_help=True)
        else:
            if archive:
                raise UsageError("Only one archive may be specified.")
            archive = argument
            index += 1
    return archive, output


def validate_firefox_checkout(script_directory: Path, source_value: str) -> Path:
    source_directory = native_path(source_value)
    mach = source_directory / "mach"
    if (
        not mach.is_file()
        or not os.access(str(mach), os.X_OK)
        or not command_succeeds(
            [
                "git",
                "-C",
                str(source_directory),
                "rev-parse",
                "--is-inside-work-tree",
            ]
        )
    ):
        raise ValueError(
            f"Firefox checkout not found at {source_value}. "
            "Run ./bootstrap.py and ./setup.py first."
        )

    source_directory = source_directory.resolve()
    if required_output(
        ["git", "-C", str(source_directory), "rev-parse", "HEAD"]
    ) != FIREFOX_COMMIT:
        raise ValueError(
            f"Firefox checkout is not at the pinned Firefox {FIREFOX_VERSION} commit."
        )

    template_directory = script_directory / "packaging/debian"
    if not (template_directory / "control.in").is_file():
        raise ValueError(f"Debian templates not found at {template_directory}.")

    for patch in DEBIAN_REPACKAGE_PATCHES:
        if not command_succeeds(
            [
                "git",
                "-C",
                str(source_directory),
                "apply",
                "--reverse",
                "--check",
                str(patch),
            ]
        ):
            raise ValueError(
                f"{patch.name} is not applied to {source_directory}; "
                "run setup.py first."
            )
    return source_directory


def validate_l10n_workspace(
    script_directory: Path, source_directory: Path
) -> None:
    workspace_value = os.environ.get("L10NBASEDIR")
    if not workspace_value or not native_path(workspace_value).is_dir():
        raise ValueError(
            "L10NBASEDIR must point to a workspace created by prepare_l10n.py."
        )
    workspace = native_path(workspace_value).resolve()
    os.environ["L10NBASEDIR"] = str(workspace)

    run(
        [
            sys.executable,
            str(script_directory / "l10n/locale_manager.py"),
            "validate-workspace",
            "--changesets",
            str(source_directory / "browser/locales/l10n-changesets.json"),
            "--workspace",
            str(workspace),
            "--translations",
            str(script_directory / "l10n/translations.json"),
            "--reference-root",
            str(source_directory / "browser/locales/en-US"),
        ]
    )


def discover_archives(script_directory: Path, source_directory: Path) -> List[Path]:
    archives = []
    for suffix in SUPPORTED_SUFFIXES:
        archives.extend(script_directory.glob(f"[Mm]ercury*{suffix}"))
    for suffix in SUPPORTED_SUFFIXES:
        archives.extend(source_directory.glob(f"obj-*/dist/[Mm]ercury*{suffix}"))
    return archives


def resolve_archive(
    archive_value: Optional[str], script_directory: Path, source_directory: Path
) -> Path:
    if not archive_value:
        archives = discover_archives(script_directory, source_directory)
        if len(archives) != 1:
            raise ValueError(
                "Expected exactly one Mercury package archive, "
                f"found {len(archives)}.\nPass the desired archive path explicitly."
            )
        archive = archives[0]
    else:
        archive = native_path(archive_value)

    if not archive.is_file():
        raise ValueError(f"Archive not found: {archive}")
    if not str(archive).endswith(SUPPORTED_SUFFIXES):
        raise ValueError(f"Unsupported archive format: {archive}")
    if not archive.is_absolute():
        archive = Path.cwd() / archive
    return archive.parent.resolve() / archive.name


def application_version(content: bytes) -> str:
    in_application = False
    for line in content.decode("utf-8", errors="replace").splitlines():
        if line == "[App]":
            in_application = True
            continue
        if line.startswith("["):
            in_application = False
        if in_application and line.startswith("Version="):
            return line.removeprefix("Version=")
    return ""


def elf_architecture(content: bytes, binary_member: str) -> str:
    if (
        len(content) < 20
        or content[:4] != b"\x7fELF"
        or content[5] not in {1, 2}
    ):
        raise ValueError(
            f"Mercury executable is not a readable ELF file: {binary_member}"
        )
    byte_order = "little" if content[5] == 1 else "big"
    machine = int.from_bytes(content[18:20], byte_order)
    try:
        return ELF_MACHINES[machine]
    except KeyError as error:
        raise ValueError(
            "Unsupported or unreadable Mercury ELF architecture: unknown"
        ) from error


def inspect_archive(archive: Path) -> Tuple[str, str]:
    try:
        with tarfile.open(archive, mode="r|*") as package:
            application_members = []
            binary_members = {}
            for member in package:
                if re.fullmatch(r"[^/]+/application\.ini", member.name):
                    stream = package.extractfile(member)
                    if stream is None:
                        content = b""
                    else:
                        with stream:
                            content = stream.read()
                    application_members.append((member.name, content))

                binary_match = re.fullmatch(r"([^/]+)/mercury", member.name)
                if binary_match:
                    content = None
                    if member.isfile():
                        stream = package.extractfile(member)
                        if stream is not None:
                            with stream:
                                content = stream.read(20)
                    binary_members[binary_match.group(1)] = (member, content)

            if len(application_members) != 1:
                raise ValueError(
                    f"Expected one top-level application.ini in {archive}, "
                    f"found {len(application_members)}."
                )
            application_name, application_content = application_members[0]
            version = application_version(application_content)
            if not version:
                raise ValueError(
                    "Could not read the Mercury version from "
                    f"{application_name}."
                )

            archive_root = application_name.split("/", 1)[0]
            if (
                SAFE_ARCHIVE_ROOT.fullmatch(archive_root) is None
                or archive_root in {".", ".."}
            ):
                raise ValueError(
                    f"Unsafe top-level archive directory: {archive_root}"
                )
            binary_name = f"{archive_root}/mercury"
            binary_result = binary_members.get(archive_root)
            if binary_result is None:
                raise ValueError(
                    f"Mercury executable not found in archive: {binary_name}"
                )
            binary_member, binary_content = binary_result
            if not binary_member.isfile() or binary_content is None:
                raise ValueError(
                    f"Mercury executable is not a readable ELF file: {binary_name}"
                )
            detected_architecture = elf_architecture(binary_content, binary_name)
    except (EOFError, OSError, tarfile.TarError) as error:
        raise ValueError(
            f"Unable to read Mercury archive: {archive}: {error}"
        ) from error
    return version, detected_architecture


def architecture_options(detected_architecture: str) -> Tuple[str, str]:
    requested_architecture = os.environ.get("DEB_ARCH") or detected_architecture
    try:
        mach_architecture, debian_architecture = ARCHITECTURES[
            requested_architecture
        ]
    except KeyError as error:
        raise ValueError(
            f"Unsupported Debian architecture: {requested_architecture}"
        ) from error
    if debian_architecture != detected_architecture:
        raise ValueError(
            f"DEB_ARCH={requested_architecture} does not match the archive "
            f"architecture ({detected_architecture})."
        )
    return mach_architecture, debian_architecture


def build_package(archive_value: Optional[str], output_value: Optional[str]) -> None:
    script_directory = Path(__file__).resolve().parent
    template_directory = script_directory / "packaging/debian"
    source_value = os.environ.get("MOZ_SRC_DIR") or default_source_directory(
        target_platform([])
    )

    for command in REQUIRED_COMMANDS:
        if shutil.which(command) is None:
            raise ValueError(f"Required command not found: {command}")

    source_directory = validate_firefox_checkout(script_directory, source_value)
    validate_l10n_workspace(script_directory, source_directory)
    archive = resolve_archive(archive_value, script_directory, source_directory)
    version, detected_architecture = inspect_archive(archive)
    mach_architecture, debian_architecture = architecture_options(
        detected_architecture
    )

    build_number = os.environ.get("DEB_BUILD_NUMBER") or "1"
    if re.fullmatch(r"[1-9][0-9]*", build_number) is None:
        raise UsageError("DEB_BUILD_NUMBER must be a positive integer.")

    if not output_value:
        output = script_directory / (
            f"{PACKAGE_NAME}_{version}~build{build_number}_{debian_architecture}.deb"
        )
    else:
        output = native_path(output_value)
        if not output.is_absolute():
            output = Path.cwd() / output
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Building {output} with Firefox repackage tooling...")
    run(
        mach_command(
            [
                "repackage",
                "deb",
                "--input",
                str(archive),
                "--output",
                str(output),
                "--arch",
                mach_architecture,
                "--version",
                version,
                "--build-number",
                build_number,
                "--templates",
                str(template_directory),
                "--product",
                "mercury",
                "--release-type",
                "release",
                "--package-name",
                PACKAGE_NAME,
                "--install-path",
                INSTALL_PATH,
            ]
        ),
        cwd=source_directory,
    )

    quoted_output = shlex.quote(str(output))
    print(f"\nPackage created: {output}")
    print(f"Inspect it with: dpkg-deb --info {quoted_output}")
    print(f"Install it with: sudo dpkg -i {quoted_output}")


def main() -> int:
    try:
        archive, output = parse_arguments(sys.argv[1:])
    except HelpRequested:
        print(HELP, end="")
        return 0
    except UsageError as error:
        print(error, file=sys.stderr)
        if error.show_help:
            print(HELP, end="", file=sys.stderr)
        return 2

    try:
        build_package(archive, output)
    except UsageError as error:
        print(error, file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        return error.returncode or 1
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
