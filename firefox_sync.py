"""Shared safety checks and commands for destructive Firefox source syncs."""

# Copyright (c) 2026 Alex313031 and gz83.

import os
import shutil
import subprocess
from pathlib import Path

from bootstrap import (
    ALLOWED_ORIGINS,
    default_source_directory,
    git_output,
    mach_command,
    native_path,
    run,
    target_platform,
)


def checkout_configuration() -> tuple[str, Path]:
    source = os.environ.get("MOZ_SRC_DIR") or default_source_directory(
        target_platform([])
    )
    os.environ["MOZ_SRC_DIR"] = source
    return source, native_path(source)


def validate_checkout(
    source_value: str, source_directory: Path, *, suggest_bootstrap: bool
) -> None:
    suggestion = " Run ./bootstrap.py first." if suggest_bootstrap else ""
    if shutil.which("git") is None:
        raise ValueError(
            f"Firefox Git checkout not found at {source_value}.{suggestion}"
        )
    root = git_output(
        [
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(source_directory),
            "rev-parse",
            "--show-toplevel",
        ],
        stderr=subprocess.DEVNULL,
    )
    if not root:
        raise ValueError(
            f"Firefox Git checkout not found at {source_value}.{suggestion}"
        )
    if native_path(root).resolve() != source_directory.resolve():
        raise ValueError(
            "MOZ_SRC_DIR must point to the Firefox Git work-tree root: "
            f"{root}"
        )

    origin_url = git_output(
        [
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(source_directory),
            "remote",
            "get-url",
            "origin",
        ],
        stderr=subprocess.DEVNULL,
    )
    if origin_url not in ALLOWED_ORIGINS:
        raise ValueError(
            "Refusing to clean a checkout with an unexpected origin: "
            f"{origin_url}"
        )


def sync_checkout(
    default_revision: str,
    *,
    remote_branch: bool,
    expected_commit: str = "",
) -> None:
    source_value, source_directory = checkout_configuration()
    revision = os.environ.get("FIREFOX_REVISION") or default_revision
    os.environ["FIREFOX_REVISION"] = revision
    validate_checkout(source_value, source_directory, suggest_bootstrap=True)

    print(f"Syncing Firefox to {revision}...")
    git = ["git", "-c", "core.fsmonitor=false"]
    if remote_branch:
        branch_ref = f"refs/heads/{revision}"
        valid_branch = subprocess.run(
            ["git", "check-ref-format", branch_ref],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if not valid_branch:
            raise ValueError(f"Invalid remote branch name: {revision}")
        remote_ref = f"refs/remotes/origin/{revision}"
        run(
            [*git, "fetch", "--tags", "origin", f"+{branch_ref}:{remote_ref}"],
            cwd=source_directory,
        )
        revision_target = remote_ref
    else:
        run([*git, "fetch", "--tags", "origin"], cwd=source_directory)
        revision_target = revision

    checkout_target = git_output(
        [
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(source_directory),
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{revision_target}^{{commit}}",
        ],
        stderr=subprocess.DEVNULL,
    )
    if not checkout_target:
        target_kind = "remote branch" if remote_branch else "revision"
        raise ValueError(f"Firefox {target_kind} is unavailable: {revision}")
    if (
        expected_commit
        and revision == default_revision
        and checkout_target != expected_commit
    ):
        raise ValueError(
            f"Firefox release {default_revision} resolves to {checkout_target}; "
            f"expected {expected_commit}."
        )

    run([*git, "reset", "--hard"], cwd=source_directory)
    run([*git, "clean", "-fd"], cwd=source_directory)
    run(
        [*git, "checkout", "--detach", checkout_target],
        cwd=source_directory,
    )
    run(mach_command(["clobber"]), cwd=source_directory)
    run(
        mach_command(["bootstrap", "--application-choice", "browser"]),
        cwd=source_directory,
    )

    if remote_branch:
        print(f"\nDone. Firefox is at {revision} ({checkout_target}).")
        print(
            "Migrate the Mercury patches and update release.json before "
            "running ./setup.py."
        )
    elif not expected_commit or checkout_target == expected_commit:
        print("\nDone. Return to the Mercury repository and run ./setup.py.")
    else:
        print(f"\nDone. Firefox is at {revision} ({checkout_target}).")
        print(
            "This revision differs from Mercury's pinned release. Update "
            "release.json and migrate the patches before running ./setup.py."
        )
