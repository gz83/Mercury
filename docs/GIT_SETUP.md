# Firefox Git setup

Mercury is built from Mozilla's official Firefox Git repository. Artifact Mode
cannot build Mercury's C++ and Rust changes, so use a full **Firefox for
Desktop** checkout.

Run the commands below from the Mercury repository root. Examples use a POSIX
shell; on native Windows, invoke Mercury scripts with `py -3`, for example
`py -3 bootstrap.py --win`.

## Create the checkout

`bootstrap.py` clones Firefox when the checkout does not exist, checks out the
release declared by `release.json` as a detached HEAD, and runs Firefox's
`mach bootstrap --application-choice browser`:

```bash
./bootstrap.py --linux
```

Use `--mac` or `--win` on the corresponding host. With no platform option, the
script detects the host. The default checkout is `$HOME/firefox` on Linux and
macOS and `/c/mozilla-source/firefox` (`C:\mozilla-source\firefox`) on Windows.
Override it before running any Mercury command when necessary:

```bash
export MOZ_SRC_DIR=/path/to/firefox
```

In PowerShell, use:

```powershell
$env:MOZ_SRC_DIR = 'C:\path\to\firefox'
py -3 bootstrap.py --win
```

An existing normal checkout or Git worktree is supported. Bare repositories
are not valid build trees. All checkout-management commands require `origin`
to point directly to Mozilla's official Firefox repository using one of the
accepted HTTPS or SSH URLs. A personal fork or mirror configured as `origin`
is deliberately rejected; it may be added under another remote name.

Rerunning `bootstrap.py` for an existing checkout fetches and attempts the
requested checkout, but does not reset tracked changes, remove untracked files,
or clobber build output. Use one of the restore commands below when the checkout
has already been prepared or modified.

## Release pins and detached HEAD

`release.json` is the authoritative source for the Firefox version, release
tag, exact source commit, and localization commit. The localization commit
belongs to the separate l10n repository and does not select the main Firefox
checkout.

`bootstrap.py`, `version.py`, and `tot.py` intentionally check Firefox out on a
detached HEAD; `revert.py` preserves the current checkout state. Do not commit
Mercury changes in the Firefox checkout. Product changes belong in Mercury's
patches or explicit overlays; `setup.py` applies them to the disposable Firefox
build tree.

`FIREFOX_REVISION` can temporarily override the revision selected by
`bootstrap.py` or `version.py`:

```bash
export FIREFOX_REVISION=<git-revision>
./bootstrap.py --linux
```

This override is intended for upstream investigation and porting work.
`setup.py` still requires the exact Firefox commit pinned by `release.json` and
will reject another tag, branch, or commit. Likewise, a checkout moved to the
development tip by `tot.py` cannot use the current patch set until the patches
are migrated and `release.json` is updated.

Before returning to Mercury's pinned stable release, remove any override:

```bash
unset FIREFOX_REVISION
./version.py
```

The PowerShell equivalent is:

```powershell
Remove-Item Env:FIREFOX_REVISION -ErrorAction SilentlyContinue
py -3 version.py
```

## Restore or change the checkout

Choose the command according to the intended revision:

| Command | Revision after completion | Fetch | Source cleanup | `mach clobber` | `mach bootstrap` |
| --- | --- | --- | --- | --- | --- |
| `bootstrap.py` | Pinned release or raw `FIREFOX_REVISION` | Yes | No | No | Yes |
| `revert.py` | Current HEAD | No | Yes | Yes | No |
| `version.py` | Pinned release or raw `FIREFOX_REVISION` | Yes | Yes | Yes | Yes |
| `tot.py` | `origin/main` or `origin/$FIREFOX_REVISION` | Yes | Yes | Yes | Yes |

`revert.py` is the shortest way to discard applied patches and overlays while
remaining on the current revision:

```bash
./revert.py
```

`version.py` fetches tags and restores the stable base. Unless
`FIREFOX_REVISION` is unset, however, it checks out that override instead of
the release tag:

```bash
unset FIREFOX_REVISION
./version.py
```

`tot.py` is for inspecting or beginning a port to an upstream development
branch. Its override is interpreted as a remote branch name and is checked out
as `origin/$FIREFOX_REVISION`; it is not an arbitrary commit expression:

```bash
unset FIREFOX_REVISION
./tot.py
```

> **Warning:** `revert.py`, `version.py`, and `tot.py` run
> `git reset --hard` and `git clean -fd` in the Firefox checkout. They delete
> tracked modifications and untracked, non-ignored files. They also run
> `mach clobber`, which removes the configured object directory. They never
> modify the Mercury repository.

Git-ignored source-tree files are not removed by `git clean -fd`. In
particular, Firefox ignores the root `mozconfig`, so a previously selected
configuration can remain until the next `setup.py` call replaces it. The
restore commands should therefore be followed by `setup.py` before building
Mercury again.

## Prepare Mercury

After creating or restoring the pinned Firefox checkout, apply Mercury's
patches, overlays, and selected build configuration:

```bash
./setup.py --linux
./build.py
```

Choose the platform or CPU profile documented in
[Building Mercury](BUILDING.md). Use `./setup.py --check` first when only
validation is wanted.
