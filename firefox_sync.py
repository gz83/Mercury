"""Shared safety checks and commands for destructive Firefox source syncs."""

# Copyright (c) 2026 Alex313031 and gz83.

import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

from bootstrap import (
    ALLOWED_ORIGINS,
    default_source_directory,
    git_output,
    mach_command,
    native_path,
    run,
    target_platform,
)


def checkout_configuration() -> Tuple[str, Path]:
    source = os.environ.get("MOZ_SRC_DIR") or default_source_directory(
        target_platform([])
    )
    os.environ["MOZ_SRC_DIR"] = source
    return source, native_path(source)


def validate_checkout(
    source_value: str, source_directory: Path, *, suggest_bootstrap: bool
) -> None:
    if shutil.which("git") is None or git_output(
        ["-C", str(source_directory), "rev-parse", "--is-inside-work-tree"],
        stderr=subprocess.DEVNULL,
    ) != "true":
        suggestion = " Run ./bootstrap.py first." if suggest_bootstrap else ""
        raise ValueError(
            f"Firefox Git checkout not found at {source_value}.{suggestion}"
        )

    origin_url = git_output(
        ["-C", str(source_directory), "remote", "get-url", "origin"],
        stderr=subprocess.DEVNULL,
    )
    if origin_url not in ALLOWED_ORIGINS:
        raise ValueError(
            "Refusing to clean a checkout with an unexpected origin: "
            f"{origin_url}"
        )


def sync_checkout(default_revision: str, *, remote_branch: bool) -> None:
    source_value, source_directory = checkout_configuration()
    revision = os.environ.get("FIREFOX_REVISION") or default_revision
    os.environ["FIREFOX_REVISION"] = revision
    validate_checkout(source_value, source_directory, suggest_bootstrap=True)

    print(f"Syncing Firefox to {revision}...")
    run(["git", "fetch", "--tags", "origin"], cwd=source_directory)
    run(["git", "reset", "--hard"], cwd=source_directory)
    run(["git", "clean", "-fd"], cwd=source_directory)
    checkout_target = f"origin/{revision}" if remote_branch else revision
    run(
        ["git", "checkout", "--detach", checkout_target],
        cwd=source_directory,
    )
    run(mach_command(["clobber"]), cwd=source_directory)
    run(
        mach_command(["bootstrap", "--application-choice", "browser"]),
        cwd=source_directory,
    )

    print("\nDone. Return to the Mercury repository and run ./setup.py.")
