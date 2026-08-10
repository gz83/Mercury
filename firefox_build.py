"""Shared Firefox checkout checks for Mercury build commands."""

# Copyright (c) 2026 Alex313031 and gz83.

import os
import subprocess
from pathlib import Path

from bootstrap import (
    default_source_directory,
    git_output,
    native_path,
    target_platform,
)


def configured_checkout() -> Path:
    """Return the configured, validated Firefox checkout."""
    source_value = os.environ.get("MOZ_SRC_DIR") or default_source_directory(
        target_platform([])
    )
    os.environ["MOZ_SRC_DIR"] = source_value
    source_directory = native_path(source_value)
    mach = source_directory / "mach"
    executable = mach.is_file() and (
        os.name == "nt" or os.access(str(mach), os.X_OK)
    )
    inside_work_tree = git_output(
        ["-C", str(source_directory), "rev-parse", "--is-inside-work-tree"],
        stderr=subprocess.DEVNULL,
    )
    if not executable or inside_work_tree != "true":
        raise ValueError(
            f"Firefox checkout not found at {source_value}. "
            "Run ./bootstrap.py and ./setup.py first."
        )
    return source_directory
