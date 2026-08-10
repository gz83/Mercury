# Building Mercury <img src="assets/build_light.svg#gh-dark-mode-only"> <img src="assets/build_dark.svg#gh-light-mode-only">

Mercury is built from a Firefox Git checkout plus release-targeted patches and
a small explicit set of product-owned files. The scripts default to
`$HOME/firefox` on Linux and macOS, and `/c/mozilla-source/firefox` on Windows.
Set `MOZ_SRC_DIR` when the checkout is elsewhere.

Run the commands in this document from the Mercury repository root. Examples
use a POSIX shell. In native Windows PowerShell, replace invocations such as
`./setup.py` with `py -3 setup.py` and set environment variables with syntax
such as `$env:MOZ_SRC_DIR = 'C:\mozilla-source\firefox'`.

## Prerequisites

Install Git and Python 3, then let Firefox bootstrap the platform toolchain:

```bash
./bootstrap.py --linux
```

Use `--mac` or `--win` on the corresponding platform. `bootstrap.py` runs
Firefox's `mach bootstrap`, so a separately maintained system-package list is
not required. See [Firefox Git setup](GIT_SETUP.md) for checkout and revision
management.

Debian packaging additionally requires `dpkg-dev` and `debhelper`. `lintian`
and `desktop-file-utils` are recommended for package validation.

## Prepare the source

`setup.py` reads the pinned Firefox release from `release.json`, verifies that
base, applies every patch in the order declared by `patches/manifest.json`,
synchronizes only the explicitly listed Mercury-owned files, and installs the
selected mozconfig:

```bash
./setup.py
```

Select the target explicitly when the default Linux AVX release is not wanted:

| `setup.py` profile | Target | Configuration |
| --- | --- | --- |
| `--linux` | Linux x86-64 | AVX release (default) |
| `--sse3`, `--sse4`, `--avx2` | Linux x86-64 | CPU-specific release |
| `--arm64`, `--raspi` | Linux ARM64 | Cortex-A72 release; the options are aliases |
| `--debug` | Linux x86-64 | AVX debug build |
| `--win` | Native Windows x86-64 | AVX release |
| `--win-sse3`, `--win-sse4`, `--win-avx2` | Native Windows x86-64 | CPU-specific release |
| `--win-debug` | Native Windows x86-64 | AVX debug build |
| `--cross`, `--cross-avx2` | Windows x86-64 from Linux | MinGW AVX or AVX2 release |
| `--mac`, `--mac-arm` | Native macOS | x86-64 AVX2 or Apple Silicon release |
| `--mac-cross`, `--mac-arm-cross` | macOS cross-build | x86-64 AVX2 or Apple Silicon release |

Run `./setup.py --help` for the authoritative list. Use `./setup.py --check`
to validate the checkout, input files, and patch applicability without
modifying the Firefox tree. The setup process never recursively copies the
repository's `app/` or `browser/` directory over Firefox.

The macOS cross configs let Firefox locate its bootstrapped SDK normally. If
configure cannot find the intended extracted SDK, set `MOZ_MACOS_SDK` to its
directory before building.

Use `./version.py` to restore the stable base or `./tot.py` to move the Firefox
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
./build.py
```

Run the development build with `./run.py`. To pass browser command-line
arguments or use debugging tools, follow [Debugging Mercury](DEBUGGING.md) and
invoke `mach run` from the prepared Firefox checkout.

Create the platform's native package after the build:

```bash
./package.py
```

Firefox selects the output for the configured target: a Linux application
archive, a Windows application ZIP and full installer, or a macOS DMG. For a
one-off Linux Debian package, first prepare the pinned localization workspace:

```bash
./prepare_l10n.py /path/to/firefox-l10n /tmp/mercury-l10n
export L10NBASEDIR=/tmp/mercury-l10n
./make_deb.py /path/to/mercury-linux.tar.xz
```

Portable packaging also wraps an existing native package rather than changing
Firefox's platform packager:

```bash
./make_portable.py /path/to/mercury-linux.tar.xz
./make_portable.py /path/to/mercury-windows.zip
```

Both portable formats add a launcher and sibling `USER_DATA/` profile directory.
Native Clang/clang-cl is the primary Windows release configuration; MinGW is a
reduced-function compatibility target. See
[system requirements](SYSTEM_REQUIREMENTS.md) for its feature limitations.

For localization workspace integrity, per-locale artifacts, language packs,
and multi-locale packages, follow [LOCALIZATION.md](LOCALIZATION.md).

For the complete platform/CPU artifact matrix, PGO policy, historical
v129.0.2 artifact mapping, staging, and release validation, follow
[Releasing Mercury](RELEASING.md).

For general platform requirements and troubleshooting, refer to the
[Firefox build documentation](https://firefox-source-docs.mozilla.org/setup/).
