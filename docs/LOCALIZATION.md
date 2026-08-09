# Mercury localized releases

Mercury 153.0.3 pins its localization baseline separately from the Firefox
source baseline:

- Firefox: tag `FIREFOX_153_0_3_RELEASE`, commit
  `0c39e9282688363f5028d0541c17784f7fa5117c`.
- Firefox l10n: commit `6795ea14a5bd5ed79a930e6759823c7236476ae4`.
- Audited Mercury locales: the in-tree `en-US` locale and the external
  `zh-CN` and `zh-TW` locales listed in `l10n/locales.txt`.

Patch `080-mercury-localization.patch` maintains `en-US`. The `zh-CN` and
`zh-TW` patches change only Mercury-owned product attribution and product names
in network errors; they do not rewrite general translations maintained by
Mozilla. The Terms of Use and Privacy labels in the About dialog continue to
describe their Mozilla destination URLs. They must not be rebranded until
Mercury has its own legal pages. The obsolete `unknownSocketType` key still
contains the Firefox name, but Firefox 153 no longer references it, so Mercury
intentionally does not maintain it.

## Prepare an isolated localization workspace

Do not modify or dirty the l10n repository used as the source mirror. Create an
isolated workspace at the pinned revision and apply the Mercury patches there:

```bash
cd /chromium-source/Mercury
./prepare_l10n.sh /chromium-source/firefox-l10n /tmp/mercury-l10n-153
export L10NBASEDIR=/tmp/mercury-l10n-153
```

The destination must not already exist. The script verifies that the pinned
revision exists. Uncommitted changes in the resulting workspace are expected:
they are the Mercury patches for `zh-CN` and `zh-TW`.

## Recommended workflow: repackage a base build

Select a platform and CPU variant, then build and package the `en-US` base in
the usual way. For example, for Linux AVX:

```bash
export MOZ_SRC_DIR=/chromium-source/firefox
cd /chromium-source/Mercury
./setup.sh
./build.sh
./package.sh
```

Next, disable configuration that applies only to a full PGO compilation and
let Firefox configure and repackage each locale:

```bash
export MERCURY_L10N_REPACK=1
cd "$MOZ_SRC_DIR"
./mach repackage-single-locales \
  --locales zh-CN zh-TW \
  --dest /tmp/mercury-localized
```

For native Linux and Windows release mozconfigs, `MERCURY_L10N_REPACK=1` omits
`MOZ_PGO=1`, allowing `mach` to run the `installers-<locale>` targets. It also
clears `AUTOCLOBBER`, so locale configuration changes do not delete the already
compiled base binaries. This does not reduce the optimization level of those
binaries. Repackaging reuses them, replaces localized resources, and produces
the locale-specific artifacts without rebuilding Gecko for every locale.

Firefox 153's `repackage-single-locales` configures each locale in turn but
does not restore `en-US` when it finishes. The object directory therefore
remains configured for the last locale in sorted order, currently `zh-TW`. If
separate XPIs are also required, run the commands in the next section first.
After all localized artifacts have been generated, restore the base locale:

```bash
cd "$MOZ_SRC_DIR"
./mach configure --enable-ui-locale=en-US
unset MERCURY_L10N_REPACK
```

This restores the `en-US` configuration in repack mode while preserving the
base binaries. `MERCURY_L10N_REPACK` must remain unset before the next full PGO
build. Firefox will then configure from the normal mozconfig and clobber the
object directory if required.

On macOS, a local invocation of this command produces a TAR because Firefox 153
skips the time-consuming local DMG step. Produce release DMGs through the macOS
release/signing automation, or on Linux with a fully configured macOS
cross-packaging toolchain. Do not merely rename the TAR to DMG.

Every platform and CPU variant (SSE3, SSE4.1, AVX, and AVX2) contains different
native binaries. Build one base package for every variant and repackage locales
from that variant's own object directory. Never use one CPU variant's base to
create another variant's installer.

## Publish language packs (XPI)

`repackage-single-locales` generates an XPI for each requested locale. To
regenerate only the language packs, keep `L10NBASEDIR` and
`MERCURY_L10N_REPACK=1` set in the same shell and run:

```bash
cd "$MOZ_SRC_DIR"
./mach build langpack-en-US
./mach build langpack-zh-CN
./mach build langpack-zh-TW
find obj-* -path '*/dist/*' -name '*.langpack.xpi' -print
```

The `en-US` XPI lets a single-locale Chinese installation switch completely
back to English. Patch `140-mercury-langpack-identity.patch` assigns IDs in the
form `langpack-<locale>@mercury.alex313031.github.io`, preventing collisions
with official Firefox language packs and making runtime fallback detection use
the same ID. Mercury also disables the Firefox AMO language-pack list and the
Firefox application/background-update coordination for installed language
packs. Users must install and update these XPIs from the Mercury release page.
MSIX packaging preserves the same Mercury IDs.

An XPI contains no CPU-specific Mercury native code, so one language pack for a
given Mercury version can be shared by its SSE3, SSE4.1, AVX, and AVX2 builds.
Before release, still test installation, locale switching, and restart behavior
on every target operating system.

## Optional workflows

To compile a complete build directly in one locale, temporarily add
`ac_add_options --enable-ui-locale=zh-CN` (or `zh-TW`) to a dedicated mozconfig
and use a separate object directory. This repeats the full compilation and is
not appropriate for the normal release matrix.

A single package containing multiple locale resources can instead be produced
with:

```bash
cd "$MOZ_SRC_DIR"
./mach package-multi-locale --locales zh-CN zh-TW
```

Mercury's normal release is better served by separate localized installers or
archives plus optional XPIs. That gives users an explicit download choice and
does not unconditionally enlarge every CPU variant.

## Upgrading Firefox

Upgrade the Firefox source commit and the locale repository revisions from
`browser/locales/l10n-changesets.json` together. Then update both pinned
commits in this document, update `L10N_REVISION` in `prepare_l10n.sh`, replay
`l10n/patches/`, verify that Fluent variables and HTML overlay names have not
changed, and perform an installation test for every release format.
