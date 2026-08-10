#!/usr/bin/env python3

"""Create and validate a complete Mercury localization workspace."""

# Copyright (c) 2026 Alex313031 and gz83.

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from bootstrap import default_source_directory, native_path, run, target_platform
from release_config import (
    FIREFOX_COMMIT,
    FIREFOX_VERSION,
    L10N_COMMIT,
    patches_for_role,
)


REFERENCE_PATCHES = patches_for_role("l10n-reference")
BRANDING_OPTION = re.compile(
    r"^[ \t]*ac_add_options[ \t]+"
    r"--with-branding=browser/branding/mercury(?:[ \t]|$)",
    re.MULTILINE,
)

HELP = f"""Usage: ./prepare_l10n.py SOURCE_REPOSITORY OUTPUT_DIRECTORY

Create an isolated Firefox {FIREFOX_VERSION} localization checkout that covers
every locale supported by the pinned Firefox release. Reviewed Mercury translations are
applied where available; other locales receive explicitly identified machine
drafts only for Mercury-owned messages. SOURCE_REPOSITORY is never modified, and
OUTPUT_DIRECTORY must not already exist. Run setup.py first and set MOZ_SRC_DIR
if the prepared Firefox checkout is not at its platform default location.
"""


def command_output(
    command: List[str], *, stderr: Optional[int] = None
) -> Optional[str]:
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=stderr,
        universal_newlines=True,
    )
    if result.returncode:
        return None
    return result.stdout.strip()


def command_succeeds(command: List[str]) -> bool:
    return (
        subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def required_output(command: List[str]) -> str:
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command)
    return result.stdout.strip()


def files_equal(first: Path, second: Path) -> bool:
    return (
        first.is_file()
        and second.is_file()
        and first.read_bytes() == second.read_bytes()
    )


def prepare(source_value: str, output_value: str) -> None:
    mercury_directory = Path(__file__).resolve().parent
    source_repository = native_path(source_value)
    output_directory = native_path(output_value)
    source_value = str(source_repository)
    output_value = str(output_directory)
    firefox_value = os.environ.get("MOZ_SRC_DIR") or default_source_directory(
        target_platform([])
    )
    firefox_directory = native_path(firefox_value)

    if shutil.which("git") is None:
        raise ValueError("Required command is unavailable: git")
    if not command_succeeds(
        ["git", "-C", source_value, "rev-parse", "--git-dir"]
    ):
        raise ValueError(f"Localization Git repository not found: {source_value}")
    if command_output(
        [
            "git",
            "-C",
            str(firefox_directory),
            "rev-parse",
            "--is-inside-work-tree",
        ],
        stderr=subprocess.DEVNULL,
    ) != "true":
        raise ValueError(
            f"Prepared Firefox Git checkout not found: {firefox_value}"
        )

    current_commit = required_output(
        ["git", "-C", str(firefox_directory), "rev-parse", "HEAD"]
    )
    if current_commit != FIREFOX_COMMIT:
        raise ValueError(
            f"Expected Firefox commit {FIREFOX_COMMIT}, "
            f"found {current_commit}."
        )

    for patch in REFERENCE_PATCHES:
        if not command_succeeds(
            [
                "git",
                "-C",
                str(firefox_directory),
                "apply",
                "--reverse",
                "--check",
                str(patch),
            ]
        ):
            raise ValueError(
                f"{patch.name} is not applied to {firefox_value}; "
                "run setup.py first."
            )

    expected_branding = (
        mercury_directory / "browser/branding/mercury/configure.sh"
    )
    actual_branding = firefox_directory / "browser/branding/mercury/configure.sh"
    if not files_equal(expected_branding, actual_branding):
        raise ValueError(
            "Mercury branding overlay is missing or stale in "
            f"{firefox_value}; run setup.py first."
        )

    mozconfig = firefox_directory / "mozconfig"
    if not mozconfig.is_file() or BRANDING_OPTION.search(
        mozconfig.read_text(encoding="utf-8")
    ) is None:
        raise ValueError(
            "The configured checkout does not select Mercury branding: "
            f"{firefox_value}/mozconfig"
        )

    changesets = firefox_directory / "browser/locales/l10n-changesets.json"
    locale_manager = mercury_directory / "l10n/locale_manager.py"
    translations = mercury_directory / "l10n/translations.json"
    if not changesets.is_file():
        raise ValueError(
            f"Firefox localization changesets are missing: {changesets}"
        )
    if output_directory.exists():
        raise ValueError(
            "Output path already exists; choose a new empty path: "
            f"{output_value}"
        )
    if not command_succeeds(
        [
            "git",
            "-C",
            source_value,
            "cat-file",
            "-e",
            f"{L10N_COMMIT}^{{commit}}",
        ]
    ):
        raise ValueError(
            f"Required localization revision is unavailable: {L10N_COMMIT}"
        )

    run(["git", "clone", "--no-checkout", source_value, output_value])
    run(
        ["git", "checkout", "--detach", L10N_COMMIT],
        cwd=output_directory,
    )
    run(
        [
            sys.executable,
            str(locale_manager),
            "apply-translations",
            "--changesets",
            str(changesets),
            "--workspace",
            str(output_directory),
            "--reference-root",
            str(firefox_directory / "browser/locales/en-US"),
            "--firefox-root",
            str(firefox_directory),
            "--translations",
            str(translations),
            "--firefox-commit",
            FIREFOX_COMMIT,
        ]
    )

    prepared_directory = output_directory.resolve().as_posix()
    print("\nMercury localization workspace is ready.")
    print(f"export L10NBASEDIR={shlex.quote(prepared_directory)}")


def main() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] in {"--help", "-h"}:
        print(HELP, end="")
        return 0
    if len(arguments) != 2:
        print(HELP, end="", file=sys.stderr)
        return 2
    try:
        prepare(arguments[0], arguments[1])
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
