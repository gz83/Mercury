# Releasing Mercury

This guide turns the build and localization workflows into a complete release
matrix. It describes manually assembled release artifacts; the repository's
GitHub Actions rebuild derived branding inputs, but do not currently build,
sign, or publish the full browser matrix.

`release.json` is the authoritative source for the Firefox version, Firefox
commit, and localization commit. Replace a release only after all three inputs,
the patch manifest, branding resources, and translations have been audited
together.

## Release model

Build one `en-US` base for every platform and CPU variant. Localization then
repackages that base without recompiling C++ or Rust, so every localized output
contains the same native code as its base artifact.

Mercury's release mozconfigs have the following PGO policy:

| Target | Profiles | Base build | Localized output |
| --- | --- | --- | --- |
| Linux x86-64 | SSE3, SSE4, AVX, AVX2 | PGO | Reuses the corresponding PGO binaries |
| Native Windows x86-64 | SSE3, SSE4, AVX, AVX2 | PGO | Reuses the corresponding PGO binaries |
| Linux ARM64 | ARMv8-A/Cortex-A72 | LTO, no PGO | Reuses the base binaries |
| macOS x86-64 and ARM64 | AVX2 or Apple M1 | LTO, no PGO | Reuses the base binaries |
| Windows MinGW x86-64 | AVX, AVX2 | LTO, no PGO | Reuses the reduced-function base binaries |

Debug configs are not release inputs. Native Windows builds are the primary
Windows release; MinGW builds disable features that are unavailable in the
selected Firefox MinGW configuration and must be labelled as compatibility
artifacts.

The PGO profiles are collected from the complete `en-US` browser build.
`repackage_locales.py` sets `MERCURY_L10N_REPACK=1` so locale changes neither
rerun PGO nor clobber the compiled base. Running PGO separately for every UI
language would not produce different native code and is not part of the release
process.

## Isolate variants

Use a separate Firefox checkout or worktree for each platform/CPU variant.
Different variants can select the same default object-directory name, and
changing the active mozconfig may clobber a previous build. Set `MOZ_SRC_DIR`
before every Mercury command so the target is unambiguous.

If one checkout must be reused, copy all completed artifacts elsewhere before
running `version.py`; it deliberately discards tracked and untracked content in
the Firefox checkout. Then run `setup.py` again with the next profile and
perform a clean full build. Never reuse binaries from another CPU variant.

The release profiles are:

| Artifact family | `setup.py` profiles |
| --- | --- |
| Linux x86-64 | `--sse3`, `--sse4`, `--linux`, `--avx2` |
| Linux ARM64 | `--arm64` (`--raspi` is an alias) |
| Native Windows x86-64 | `--win-sse3`, `--win-sse4`, `--win`, `--win-avx2` |
| Windows MinGW x86-64 | `--cross`, `--cross-avx2` |
| Native macOS | `--mac`, `--mac-arm` |
| Cross-built macOS | `--mac-cross`, `--mac-arm-cross` |

Use `setup.py --help` as the authoritative profile list. Confirm the x86 target
machine with `check_simd.py`; a cross-build host's result does not establish
target compatibility.

## Prepare localization once

Prepare at least one pinned Firefox checkout before creating the localization
workspace because the patched `en-US` messages are part of its integrity
record:

```bash
export MOZ_SRC_DIR=/path/to/firefox-linux-avx
./setup.py --linux --check
./setup.py --linux
./prepare_l10n.py /path/to/firefox-l10n /tmp/mercury-l10n
export L10NBASEDIR=/tmp/mercury-l10n
```

The source localization repository is not modified. The resulting workspace
can be reused by other checkouts for the same pinned Mercury release, but must
be recreated after changing the Firefox/l10n revisions, localization generator,
translation catalog, or patched reference messages.

On native Windows PowerShell:

```powershell
$env:MOZ_SRC_DIR = 'C:\build\firefox-win-avx'
py -3 setup.py --win --check
py -3 setup.py --win
py -3 prepare_l10n.py 'C:\src\firefox-l10n' `
  "$env:TEMP\mercury-l10n"
$env:L10NBASEDIR = "$env:TEMP\mercury-l10n"
```

## Build the base matrix

For each isolated checkout, select exactly one profile. Run the non-mutating
preflight with that profile before preparing the checkout, then perform a
complete build and native package. This example selects Linux AVX; substitute
the appropriate profile for other variants:

```bash
export MOZ_SRC_DIR=/path/to/firefox-linux-avx
./setup.py --linux --check
./setup.py --linux
./build.py
./package.py
```

`build.py` invokes Firefox's native build, including the two-pass PGO workflow
when the selected mozconfig sets `MOZ_PGO=1`. `package.py` invokes `mach
package` and prints the exact output paths. Copy those outputs to a staging
directory before preparing another variant.

The native base outputs are:

| Target | `package.py` output |
| --- | --- |
| Linux | Firefox-native `.tar.xz` application archive |
| Windows | Application `.zip` and full installer `.exe` |
| macOS | Application `.dmg` in a fully configured packaging environment |

Do not rename a macOS localization TAR to DMG. Release DMGs require the native
packaging path or a fully configured cross-packaging environment, followed by
the applicable signing and notarization process.

### Linux and Debian

Repeat the base commands with `--sse3`, `--sse4`, `--linux`, `--avx2`, and
`--arm64`. Each run produces its own native Linux archive. The current release
format is `.tar.xz`; the legacy Linux ZIP format is not produced by
`package.py`.

Create a Debian package from each exact archive and name the output so its CPU
variant is visible:

```bash
VERSION="$(python3 -c \
  'from release_config import FIREFOX_VERSION; print(FIREFOX_VERSION)')"
./make_deb.py /path/to/mercury-linux-avx.tar.xz \
  -o "/path/to/release/mercury-browser_${VERSION}_AVX.deb"
```

`make_deb.py` requires the prepared `L10NBASEDIR`, reads the packaged ELF
architecture, and rejects a conflicting `DEB_ARCH`. Repeat it for SSE3, SSE4,
AVX2, and ARM64. The CPU label is an artifact filename convention; all variants
use the same Mercury Debian package identity and must not be installed
simultaneously.

### Native Windows

Use a separate native Windows checkout for each primary release profile:

```powershell
$env:MOZ_SRC_DIR = 'C:\build\firefox-win-avx'
py -3 setup.py --win --check
py -3 setup.py --win
py -3 build.py
py -3 package.py
```

Repeat with `--win-sse3`, `--win-sse4`, and `--win-avx2`. Preserve both the ZIP
and full installer generated for every profile. Mercury does not configure a
Windows ARM64 browser build; the checked-in ARM64 7-Zip SFX stub is only an
installer build input.

### macOS

Build the Intel and Apple silicon bases separately:

```bash
export MOZ_SRC_DIR=/path/to/firefox-macos-x64
./setup.py --mac --check
./setup.py --mac
./build.py
./package.py
```

Use `--mac-arm` for Apple silicon. The cross profiles require a compatible
Apple SDK supplied outside the repository. Current native and cross macOS
mozconfigs use LTO but not PGO.

## Repackage localized artifacts

Run the batch wrapper after the corresponding `en-US` base has been built and
packaged:

```bash
export MOZ_SRC_DIR=/path/to/firefox-linux-avx
export L10NBASEDIR=/tmp/mercury-l10n
./repackage_locales.py --platform linux \
  --dest /path/to/release/localized/linux-avx
```

Use `windows` or `macos` for those targets. The platform describes the target
binaries, not the build host. Run the wrapper separately for every CPU variant
whose localized application packages will be published.

The wrapper selects the pinned Firefox platform locale set, verifies Mercury's
translation and patch inputs, restores the object directory to `en-US`, and
writes `localization-manifest.tsv`. It requires the following per-locale
outputs:

| Target | Verified localized outputs |
| --- | --- |
| Linux | `target.tar.xz`, `target.langpack.xpi` |
| Windows | `target.zip`, `target.installer.exe`, `target.langpack.xpi` |
| macOS | `target.tar` or `target.dmg`, `target.langpack.xpi` |

The XPI contains no CPU-specific native code, so one validated XPI for a locale
and Mercury version can be shared by SSE3, SSE4, AVX, and AVX2 artifacts. It
must still be tested on every target operating system, and macOS uses
`ja-JP-mac` where Linux and Windows use `ja`.

Mercury-owned `zh-CN` and `zh-TW` strings are reviewed; other current
Mercury-owned translations are explicitly recorded as machine drafts. Mozilla's
remaining translations are preserved. Publish `localization-manifest.tsv`
beside any draft localization artifacts and never label a machine draft as a
human-reviewed translation.

Separate localized packages plus shared XPIs are the recommended release
model. A single package containing every platform locale is optional; follow
the `package-multi-locale` procedure in [LOCALIZATION.md](LOCALIZATION.md).

## Optional portable packages

Portable packages wrap native package outputs without recompiling Mercury:

```bash
./make_portable.py /path/to/mercury-linux.tar.xz \
  -o /path/to/release/mercury-linux.portable.tar.xz
./make_portable.py /path/to/mercury-windows.zip \
  -o /path/to/release/mercury-windows.portable.zip
```

Portable packaging is supported only for Linux application TARs and Windows
application ZIPs. It is not used for DMG, installer, or Debian artifacts.

## Mapping the v129.0.2 release

The historical [v129.0.2 GitHub release](https://github.com/Alex313031/Mercury/releases/tag/v.129.0.2)
showed 22 assets: 20 uploaded build artifacts plus GitHub's automatically
generated source ZIP and source TAR.GZ. Its uploaded matrix maps to the current
workflow as follows:

| v129.0.2 artifact group | Count | Current producer |
| --- | ---: | --- |
| Linux ARM64/SSE3/SSE4/AVX/AVX2 ZIP | 5 | Replaced by `package.py` native `.tar.xz` outputs |
| Linux ARM64/SSE3/SSE4/AVX/AVX2 DEB | 5 | `make_deb.py` from each matching native archive |
| Windows SSE3/SSE4/AVX/AVX2 ZIP | 4 | Native Windows `package.py` |
| Windows SSE3/SSE4/AVX/AVX2 installer | 4 | Native Windows `package.py` |
| macOS x64/ARM64 DMG | 2 | Native or fully configured cross macOS `package.py` |
| Source ZIP/TAR.GZ | 2 | GitHub automatically generates them from the release tag |

Do not reproduce the old Linux ZIP merely to preserve its filename. Firefox's
current native Linux TAR.XZ output preserves Unix permissions and is the
supported input for Mercury's Debian, portable, and localization workflows.

## Release validation

Before publishing:

1. verify `release.json`, `patches/manifest.json`, and the l10n workspace pins;
2. retain the `en-US` base separately from every localized output;
3. confirm the CPU label matches the selected mozconfig and run
   `check_simd.py` on representative x86 target hardware;
4. require a successful `localization-manifest.tsv` for localized artifacts;
5. install and launch every archive/installer/package family on its target OS;
6. test locale switching, restart, About, network errors, and the temporary
   profile desktop action;
7. sign Windows and macOS binaries with the intended release identities and
   notarize macOS applications where required;
8. validate those signatures independently—the localization wrapper's PE/DMG
   structure checks do not authenticate a signer;
9. generate and publish cryptographic checksums for every uploaded artifact;
10. create the Git tag only from the audited Mercury commit, then let GitHub
    generate its two source archives from that tag.

This repository does not currently automate browser signing, notarization, or
release upload. Treat unsigned local packages as test artifacts, not official
release binaries.
