#!/usr/bin/env python3

"""Restore Firefox to its current clean Git revision."""

# Copyright (c) 2026 Alex313031 and gz83.

import subprocess
import sys

from bootstrap import mach_command, run
from firefox_sync import checkout_configuration, validate_checkout


HELP = """Restore the Firefox checkout to its current Git revision.

Usage: ./revert.py

Set MOZ_SRC_DIR to choose the Firefox checkout.
WARNING: tracked and untracked changes in the Firefox checkout are removed.
"""


def restore_current_revision() -> None:
    source_value, source_directory = checkout_configuration()
    validate_checkout(source_value, source_directory, suggest_bootstrap=False)

    run(["git", "reset", "--hard", "HEAD"], cwd=source_directory)
    run(["git", "clean", "-fd"], cwd=source_directory)
    run(mach_command(["clobber"]), cwd=source_directory)

    print("\nDone. Return to the Mercury repository and run ./setup.py.")


def main() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] in {"--help", "-h"}:
        print(HELP, end="")
        return 0
    if arguments and arguments[0]:
        print(HELP, end="", file=sys.stderr)
        return 2
    try:
        restore_current_revision()
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
