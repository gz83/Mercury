## Firefox Git setup

Mercury uses Mozilla's official Firefox Git repository. For a new checkout,
run `./bootstrap.sh`; it configures the full **Firefox for Desktop** build.
Artifact Mode cannot build Mercury's C++ and Rust changes.

The default checkout directory is `$HOME/firefox` on Linux and macOS, and
`C:\mozilla-source\firefox` on Windows. Override it when necessary:

```bash
export MOZ_SRC_DIR=/path/to/firefox
```

An existing normal checkout or Git worktree can be used. Mercury's setup,
sync, restore, package, Debian, and localized-repackage scripts identify it
through Git rather than assuming that `.git` is a directory; bare repositories
are not valid Firefox build trees.

`bootstrap.sh` checks out `FIREFOX_153_0_3_RELEASE` by default. A different
release tag, branch, or commit can be selected with:

```bash
export FIREFOX_REVISION=FIREFOX_153_0_3_RELEASE
./bootstrap.sh --linux
```

For an existing checkout, `version.sh` syncs the stable base and `tot.sh`
syncs the development tip. Both commands discard changes in the Firefox
checkout, including files copied there by `setup.sh`. Mercury's own repository
is not modified.

After the checkout is ready, return to the Mercury repository and run
`./setup.sh` with the desired platform or optimization flag, then run
`./build.sh`.
