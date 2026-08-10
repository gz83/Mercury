#!/usr/bin/env python3

"""Build Mercury in the configured Firefox checkout."""

# Copyright (c) 2026 Alex313031 and gz83.

import subprocess
import sys

from bootstrap import mach_command, run
from firefox_build import configured_checkout


HELP = """Build Mercury with Firefox's native build workflow.

Usage: ./build.py

Set MOZ_MAKE_FLAGS=-jN to control make parallelism.

Environment variables:
  MOZ_SRC_DIR     Firefox checkout prepared by setup.py
  MOZ_MAKE_FLAGS  Flags passed by Firefox to the underlying make process
"""


def build() -> None:
    source_directory = configured_checkout()
    print("Building Mercury...", flush=True)
    run(mach_command(["build", "-v"]), cwd=source_directory)
    print("\nBuild completed.")
    print("Run ./package.py to generate installation packages.")


def main() -> int:
    arguments = sys.argv[1:]
    if arguments in (["-h"], ["--help"]):
        print(HELP, end="")
        return 0
    if arguments:
        print(f"Unknown option: {arguments[0]}", file=sys.stderr)
        print(HELP, end="", file=sys.stderr)
        return 2

    try:
        build()
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
