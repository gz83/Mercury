#!/usr/bin/env python3

"""Package Mercury with Firefox's native platform workflow."""

# Copyright (c) 2026 Alex313031 and gz83.

import subprocess
import sys
from typing import List

from bootstrap import mach_command, run
from firefox_build import configured_checkout


HELP = """Package Mercury with Firefox's native platform packaging workflow.

Usage: ./package.py

Firefox selects the output for the configured target: an XZ archive on Linux,
a DMG on macOS, or a ZIP and full installer on Windows. `mach package` prints
the exact output path. Set MOZ_MAKE_FLAGS to control make parallelism.
"""


class UsageError(Exception):
    """Raised when the command line is not supported."""


def parse_arguments(arguments: List[str]) -> None:
    if arguments:
        raise UsageError(f"Unknown option: {arguments[0]}")


def package() -> None:
    source_directory = configured_checkout()
    print("Packaging Mercury with Firefox mach...", flush=True)
    run(mach_command(["package", "--verbose"]), cwd=source_directory)


def main() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] in {"-h", "--help"}:
        print(HELP, end="")
        return 0

    try:
        parse_arguments(arguments)
        package()
    except UsageError as error:
        print(error, file=sys.stderr)
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
