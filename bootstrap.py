#!/usr/bin/env python3

"""Clone Firefox and bootstrap a Mercury build environment."""

# Copyright (c) 2026 Alex313031 and gz83.

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from release_config import FIREFOX_RELEASE


FIREFOX_REPOSITORY = "https://github.com/mozilla-firefox/firefox.git"
DEFAULT_FIREFOX_REVISION = FIREFOX_RELEASE
ALLOWED_ORIGINS = {
    "https://github.com/mozilla-firefox/firefox",
    FIREFOX_REPOSITORY,
    "git@github.com:mozilla-firefox/firefox.git",
}

HELP = f"""Clone Firefox with Git and bootstrap a Mercury build environment.

Usage: ./bootstrap.py [--linux|--mac|--win]

Environment variables:
  MOZ_SRC_DIR       Firefox checkout directory (default: $HOME/firefox,
                    or /c/mozilla-source/firefox on Windows)
  FIREFOX_REVISION  Git tag, branch, or commit to check out
                    (default: {FIREFOX_RELEASE})
"""


class UsageError(Exception):
    """Raised when the command line is not supported."""


def target_platform(arguments: List[str]) -> str:
    if arguments:
        argument = arguments[0]
        if argument in {"--linux", "--mac", "--win"}:
            return argument[2:]
        raise UsageError
    if sys.platform.startswith(("win", "cygwin", "msys")):
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def default_source_directory(platform: str) -> str:
    if platform == "win":
        return "/c/mozilla-source/firefox"
    try:
        return f"{os.environ['HOME']}/firefox"
    except KeyError as error:
        raise ValueError("HOME is not set") from error


def native_path(path: str) -> Path:
    if os.name == "nt":
        match = re.fullmatch(r"/([A-Za-z])(?:/(.*))?", path)
        if match:
            drive, remainder = match.groups()
            path = f"{drive.upper()}:/{remainder or ''}"
    return Path(path)


def run(command: List[str], *, cwd: Optional[Path] = None) -> None:
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command)


def git_output(arguments: List[str], *, stderr=None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=stderr,
        universal_newlines=True,
    )
    if result.returncode:
        return ""
    return result.stdout.strip()


def mach_command(arguments: List[str]) -> List[str]:
    command = ["./mach"] if os.name != "nt" else [sys.executable, "mach"]
    return [*command, *arguments]


def bootstrap(platform: str) -> None:
    source_value = os.environ.get("MOZ_SRC_DIR") or default_source_directory(platform)
    source_directory = native_path(source_value)
    revision = os.environ.get("FIREFOX_REVISION") or DEFAULT_FIREFOX_REVISION
    os.environ["MOZ_SRC_DIR"] = source_value

    if shutil.which("git") is None:
        raise ValueError("git is required. Install Git and run this script again.")

    if source_directory.exists():
        inside_work_tree = git_output(
            ["-C", str(source_directory), "rev-parse", "--is-inside-work-tree"],
            stderr=subprocess.DEVNULL,
        )
        if inside_work_tree != "true":
            raise ValueError(
                "MOZ_SRC_DIR exists but is not a Git working tree: "
                f"{source_value}"
            )
    else:
        source_directory.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", FIREFOX_REPOSITORY, str(source_directory)])

    origin_url = git_output(
        ["-C", str(source_directory), "remote", "get-url", "origin"],
        stderr=subprocess.DEVNULL,
    )
    if origin_url not in ALLOWED_ORIGINS:
        raise ValueError(
            "Refusing to modify a checkout with an unexpected origin: "
            f"{origin_url}"
        )

    run(["git", "fetch", "--tags", "origin"], cwd=source_directory)
    run(["git", "checkout", "--detach", revision], cwd=source_directory)
    run(
        mach_command(["bootstrap", "--application-choice", "browser"]),
        cwd=source_directory,
    )

    print(f"\nFirefox is ready at {source_value} (revision {revision}).")
    print("Return to the Mercury repository and run ./setup.py.")


def main() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] in {"--help", "-h"}:
        print(HELP, end="")
        return 0
    try:
        platform = target_platform(arguments)
        bootstrap(platform)
    except UsageError:
        print(HELP, end="", file=sys.stderr)
        return 2
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
