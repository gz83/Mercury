#!/usr/bin/env python3

"""Run Mercury from the configured Firefox build directory."""

# Copyright (c) 2026 Alex313031 and gz83.

import subprocess
import sys

from bootstrap import mach_command, run
from firefox_build import configured_checkout


HELP = """Run Mercury in development mode.

Usage: ./run.py

Environment variables:
  MOZ_SRC_DIR  Firefox checkout prepared by setup.py
"""


def run_mercury() -> None:
    source_directory = configured_checkout()
    print("Running Mercury in development mode...", flush=True)
    run(mach_command(["run"]), cwd=source_directory)


def main() -> int:
    arguments = sys.argv[1:]
    if arguments in (["-h"], ["--help"]):
        print(HELP, end="")
        return 0
    if arguments:
        argument = arguments[0] or "<empty>"
        print(f"Unknown option: {argument}", file=sys.stderr)
        print(HELP, end="", file=sys.stderr)
        return 2

    try:
        run_mercury()
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
