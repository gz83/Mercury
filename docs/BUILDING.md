# Building Mercury <img src="assets/build_light.svg#gh-dark-mode-only"> <img src="assets/build_dark.svg#gh-light-mode-only">

Mercury is built from a Firefox Git checkout plus the overlays and versioned
patches in this repository. The scripts default to `$HOME/firefox` on Linux and
macOS, and `/c/mozilla-source/firefox` on Windows. Set `MOZ_SRC_DIR` when the
checkout is elsewhere.

## Prerequisites

Install Git and Python 3, then let Firefox bootstrap the platform toolchain:

```bash
./bootstrap.sh --linux
```

Use `--mac` or `--win` on the corresponding platform. `bootstrap.sh` runs
Firefox's `mach bootstrap`, so a separately maintained system-package list is
not required. See [Firefox Git setup](GIT_SETUP.md) for checkout and revision
management.

Debian packaging additionally requires `dpkg-dev` and `debhelper`. `lintian`
and `desktop-file-utils` are recommended for package validation.

## Prepare the source

`setup.sh` verifies the Firefox 153.0.3 base, copies Mercury-owned overlays,
and applies every patch in `patches/firefox-153/` in order:

```bash
./setup.sh
```

Run `./setup.sh --help` to select another platform or CPU-specific mozconfig.
Use `version.sh` to restore the stable base or `tot.sh` to move the Firefox
checkout to its development tip. Both commands discard changes in the Firefox
checkout, but do not modify the Mercury repository.

Before building or running an x86 release, verify that the machine supports
the selected instruction-set profile:

```bash
./check_simd.py
```

The default `avx` profile matches `mozconfigs/mozconfig` and
`mozconfigs/mozconfig-win`. Use `sse3`, `sse4`, or `avx2` for the corresponding
release variant. The current macOS x64 configs also use the AVX2 baseline, so
run `./check_simd.py --profile avx2` before building or installing that target.
Each profile checks only the explicitly enabled ISA features;
the AVX and AVX2 variants do not implicitly require AES, FMA, F16C, or the
broader `x86-64-v3` feature set. Run
`./check_simd.py --list-profiles` to display every profile and its requirements.
The check applies to the target machine, so do not use the cross-compilation
host's result as a substitute. ARM64 releases do not use an x86 profile.

| Release profile | Required ISA | C/C++ tuning | FP contraction |
| --- | --- | --- | --- |
| SSE3 | SSE3 | Generic | Off |
| SSE4 | SSE3, SSSE3, SSE4.1 | Core 2 | Off |
| AVX | SSE3, AVX | Sandy Bridge | Off |
| AVX2 | SSE3, AVX, AVX2 | Skylake | Off |

The tuning options influence instruction scheduling without raising the
minimum ISA. C/C++ and Rust receive the same explicit ISA baseline. These
profiles are derived from Thorium's profile-oriented build configuration, but
omit Chromium-specific profiles and linker policy that Mercury does not ship.

## Build and package

Build Mercury after preparing the source:

```bash
./build.sh
```

On Linux, create the application archive and then repackage it with Firefox's
Debian tooling:

```bash
./package.sh
./make_deb.sh
```

`make_deb.sh` also accepts an explicit `.tar.xz`, `.tar.bz2`, or `.tar.gz`
archive. It reads the packaged Mercury ELF header to select `amd64`, `i386`, or
`arm64`, including for cross-built archives. `DEB_ARCH` can assert an expected
target, but a value that disagrees with the archive is rejected.

To create a portable package, wrap an existing native package instead of
changing Firefox's platform packager:

```bash
./make_portable.sh /path/to/mercury-linux.tar.xz
./make_portable.sh /path/to/mercury-windows.zip
```

Linux TAR inputs produce a `.portable.tar.xz`; Windows ZIP inputs produce a
`.portable.zip`. Both retain Firefox's `mercury/` application directory and add
a launcher beside it. The launcher creates `USER_DATA/` beside the application
and passes that directory through Firefox's supported `--profile` option. It
resolves paths relative to itself, so the package works when invoked from a
different working directory. Additional browser arguments are forwarded.
Portable packaging is not used for DMG, installer, or Debian outputs.

Windows builds produce the full installer. Mercury does not enable
`MOZ_STUB_INSTALLER`, because its CPU-specific releases do not provide the
single signed payload required by Firefox's stub installer.

The Linux-to-Windows cross configs use Firefox 153's MinGW target. They
intentionally disable WebRTC, geckodriver, the notification server, the
default-browser agent, and update agent because those components are not
supported by Firefox's MinGW configuration. Mercury disables the application
updater on every platform, so its conditional Zucchini option is not present
and must not be passed separately. The cross configs retain MinGW compatibility
flags and deterministic WIDL timestamp, while leaving compiler locations to
Firefox configure so local and bootstrapped toolchains both remain usable.

Use a native Windows Clang/clang-cl build for the primary, full-featured
Windows release. MinGW is the maintained Firefox route when the build host must
be Linux, but its output is a reduced-function compatibility variant; enabling
WebRTC or the other disabled components requires upstream MinGW porting work,
not merely removing the corresponding `--disable-*` options.

For localized installers, archives, and language packs, follow the reproducible
workflow in [LOCALIZATION.md](LOCALIZATION.md). Do not add `--with-l10n-base`
to a mozconfig; Firefox's repack commands consume `L10NBASEDIR` at execution
time.

For general platform requirements and troubleshooting, refer to the
[Firefox build documentation](https://firefox-source-docs.mozilla.org/setup/).
