#!/usr/bin/env python3

"""Restore Firefox and sync it to Mercury's selected stable base."""

# Copyright (c) 2026 Alex313031 and gz83.

import subprocess
import sys

from firefox_sync import sync_checkout
from release_config import FIREFOX_COMMIT, FIREFOX_RELEASE


DEFAULT_FIREFOX_REVISION = FIREFOX_RELEASE

HELP = f"""Restore the Firefox checkout and sync it to Mercury's stable base.

Usage: ./version.py

Set MOZ_SRC_DIR to choose the Firefox checkout and FIREFOX_REVISION to
override the default release tag ({FIREFOX_RELEASE}).

WARNING: tracked and untracked changes in the Firefox checkout are removed.
"""


def main() -> int:
    arguments = sys.argv[1:]
    if arguments in (["--help"], ["-h"]):
        print(HELP, end="")
        return 0
    if arguments:
        argument = arguments[0] or "<empty>"
        print(f"Unknown option: {argument}", file=sys.stderr)
        print(HELP, end="", file=sys.stderr)
        return 2
    try:
        sync_checkout(
            DEFAULT_FIREFOX_REVISION,
            remote_branch=False,
            expected_commit=FIREFOX_COMMIT,
        )
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
