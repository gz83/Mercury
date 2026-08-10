#!/usr/bin/env python3

"""Create a Mercury portable package from a native Firefox package."""

# Copyright (c) 2026 Alex313031 and gz83.

import copy
import os
import sys
import tarfile
import time
import zipfile
import zlib
from pathlib import Path
from typing import List, Optional, Tuple

from bootstrap import native_path


HELP = """Create a Mercury portable package from Firefox's native package output.

Usage: ./make_portable.py [options] ARCHIVE

Supported inputs:
  .tar.xz, .tar.bz2, .tar.gz  Linux package produced by `mach package`
  .zip                        Windows package produced by `mach package`

The input must contain one top-level `mercury/` directory. The portable
launcher and its USER_DATA profile directory live beside that directory.

Options:
  -o, --output FILE  Write the portable package to FILE
  -h, --help         Show this help
"""

LINUX_SUFFIXES = (".tar.xz", ".tar.bz2", ".tar.gz")


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
                raise UsageError("Only one package archive may be specified.")
            archive = argument
            index += 1
    if not archive:
        raise UsageError("A package archive is required.", show_help=True)
    return archive, output


def resolve_archive(value: str) -> Path:
    archive = native_path(value)
    if not archive.is_file():
        raise ValueError(f"Archive not found: {value}")
    if not archive.is_absolute():
        archive = Path.cwd() / archive
    return archive.parent.resolve() / archive.name


def archive_options(archive: Path) -> Tuple[str, str, str]:
    name = archive.name
    for suffix in LINUX_SUFFIXES:
        if name.endswith(suffix):
            return "linux", name[: -len(suffix)], ".portable.tar.xz"
    if name.endswith(".zip"):
        return "windows", name[:-4], ".portable.zip"
    raise ValueError(f"Unsupported archive format: {archive}")


def resolve_output(
    value: Optional[str], script_directory: Path, stem: str, suffix: str
) -> Path:
    if not value:
        return script_directory / f"{stem}{suffix}"
    output = native_path(value)
    if not output.is_absolute():
        output = Path.cwd() / output
    return output


def normalized_member(name: str) -> str:
    return name[2:] if name.startswith("./") else name


def validate_member(name: str) -> str:
    name = normalized_member(name)
    if (
        not name
        or name.startswith("/")
        or name.startswith("../")
        or "/../" in name
        or name.endswith("/..")
        or "\\" in name
    ):
        raise ValueError(f"Unsafe archive member: {name}")
    if name != "mercury" and not name.startswith("mercury/"):
        raise ValueError(f"Unexpected top-level archive member: {name}")
    return name


def copy_tar_member(
    source: tarfile.TarFile,
    destination: tarfile.TarFile,
    member: tarfile.TarInfo,
    normalized_name: str,
) -> None:
    copied = copy.copy(member)
    copied.name = normalized_name
    copied.pax_headers = dict(copied.pax_headers)
    copied.pax_headers.pop("path", None)
    stream = source.extractfile(member) if member.isfile() else None
    destination.addfile(copied, stream)


def add_tar_launcher(destination: tarfile.TarFile, launcher: Path) -> None:
    member = destination.gettarinfo(
        str(launcher), arcname="MERCURY_PORTABLE.sh"
    )
    member.mtime = int(time.time())
    with launcher.open("rb") as stream:
        destination.addfile(member, stream)


def create_linux_portable(archive: Path, output: Path, launcher: Path) -> None:
    if not launcher.is_file() or not os.access(str(launcher), os.X_OK):
        raise ValueError(
            f"Linux portable launcher is missing or not executable: {launcher}"
        )
    try:
        with tarfile.open(archive, mode="r:*") as source:
            members = source.getmembers()
            if not members:
                raise ValueError(f"Archive is empty: {archive}")
            normalized = [validate_member(member.name) for member in members]
            executable = [
                member
                for member, name in zip(members, normalized)
                if name == "mercury/mercury"
            ]
            if (
                not executable
                or not executable[-1].isfile()
                or executable[-1].mode & 0o111 == 0
            ):
                raise ValueError(
                    "Linux Mercury executable is missing from the package."
                )

            output.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(output, mode="w:xz") as destination:
                add_tar_launcher(destination, launcher)
                if "mercury" not in normalized and "mercury/" not in normalized:
                    root = tarfile.TarInfo("mercury")
                    root.type = tarfile.DIRTYPE
                    root.mode = 0o755
                    root.mtime = int(time.time())
                    destination.addfile(root)
                for member, name in zip(members, normalized):
                    copy_tar_member(source, destination, member, name)
    except (EOFError, OSError, tarfile.TarError) as error:
        raise ValueError(
            f"Invalid Linux package archive: {archive}: {error}"
        ) from error


def zip_member_is_symlink(member: zipfile.ZipInfo) -> bool:
    unix_mode = (member.external_attr >> 16) & 0o170000
    return member.create_system == 3 and unix_mode == 0o120000


def directory_zip_info(name: str) -> zipfile.ZipInfo:
    timestamp = time.localtime()[:6]
    member = zipfile.ZipInfo(name, timestamp)
    member.create_system = 3
    member.external_attr = (0o40755 << 16) | 0x10
    member.compress_type = zipfile.ZIP_STORED
    return member


def zip_compression(content: bytes) -> int:
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(content) + compressor.flush()
    if len(compressed) < len(content):
        return zipfile.ZIP_DEFLATED
    return zipfile.ZIP_STORED


def add_zip_launcher(destination: zipfile.ZipFile, launcher: Path) -> None:
    content = launcher.read_bytes()
    member = zipfile.ZipInfo("MERCURY.BAT", time.localtime()[:6])
    member.create_system = 3
    member.external_attr = launcher.stat().st_mode << 16
    member.compress_type = zip_compression(content)
    destination.writestr(member, content)


def create_windows_portable(archive: Path, output: Path, launcher: Path) -> None:
    if not launcher.is_file():
        raise ValueError(f"Windows portable launcher is missing: {launcher}")
    try:
        with zipfile.ZipFile(archive) as source:
            members = source.infolist()
            if not members:
                raise ValueError(f"Archive is empty: {archive}")
            corrupt_member = source.testzip()
            if corrupt_member is not None:
                raise ValueError(
                    f"Invalid Windows package archive: {archive}: "
                    f"corrupt member {corrupt_member}"
                )
            normalized = [validate_member(member.filename) for member in members]
            executable = [
                member
                for member, name in zip(members, normalized)
                if name == "mercury/mercury.exe" and not member.is_dir()
            ]
            if not executable or zip_member_is_symlink(executable[-1]):
                raise ValueError(
                    "Windows Mercury executable is missing from the package."
                )
            for member, name in zip(members, normalized):
                if zip_member_is_symlink(member):
                    raise ValueError(f"Unsafe archive member: {name}")

            output.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(
                output, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as destination:
                add_zip_launcher(destination, launcher)
                if "mercury" not in normalized and "mercury/" not in normalized:
                    destination.writestr(directory_zip_info("mercury/"), b"")
                for member, name in zip(members, normalized):
                    copied = copy.copy(member)
                    copied.filename = name
                    content = b"" if member.is_dir() else source.read(member)
                    copied.compress_type = (
                        zipfile.ZIP_STORED
                        if member.is_dir()
                        else zip_compression(content)
                    )
                    destination.writestr(copied, content)
    except (
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        if isinstance(error, ValueError):
            raise
        raise ValueError(
            f"Invalid Windows package archive: {archive}: {error}"
        ) from error


def create_portable(archive_value: str, output_value: Optional[str]) -> None:
    script_directory = Path(__file__).resolve().parent
    archive = resolve_archive(archive_value)
    platform, stem, suffix = archive_options(archive)
    output = resolve_output(output_value, script_directory, stem, suffix)
    if output == archive:
        raise ValueError("Output must not overwrite the input archive.")
    if output.exists():
        raise ValueError(f"Output already exists: {output}")

    if platform == "linux":
        create_linux_portable(
            archive,
            output,
            script_directory / "packaging/portable/linux/MERCURY_PORTABLE.sh",
        )
    else:
        create_windows_portable(
            archive,
            output,
            script_directory / "packaging/portable/windows/MERCURY.BAT",
        )
    print(f"Portable package created: {output}")


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
        create_portable(archive, output)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
