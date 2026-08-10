# Mercury localized releases

Run the commands in this document from the Mercury repository root unless a
different directory is stated. Examples use a POSIX shell. On native Windows,
invoke Mercury scripts with `py -3` and set environment variables with
PowerShell's `$env:NAME = 'value'` syntax.

`release.json` is the authoritative machine-readable source for these pins.
Mercury 153.0.3 pins its localization baseline separately from the Firefox
source baseline:

- Firefox: tag `FIREFOX_153_0_3_RELEASE`, commit
  `0c39e9282688363f5028d0541c17784f7fa5117c`.
- Firefox l10n: commit `6795ea14a5bd5ed79a930e6759823c7236476ae4`.
- Firefox release set: 103 external locale identifiers plus the in-tree
  `en-US` locale.
- Per-platform release set: 102 external locales plus `en-US`.

Firefox uses `ja` on Linux and Windows and `ja-JP-mac` on macOS. All other
external locales are common to the three desktop platforms. Mercury derives
these sets directly from the pinned
`browser/locales/l10n-changesets.json`; repository directory names are not a
release allowlist.

## Mercury-owned messages

General translations remain exactly as maintained by Mozilla. Mercury modifies
only product-owned attribution, hard-coded browser names in active network
errors, and the temporary-profile desktop action.

All external-locale Mercury messages and their review states are stored in
`l10n/translations.json`. The `zh-CN` and `zh-TW` entries are `reviewed`;
`en-US` remains maintained in the Firefox source patches. The other 101
entries are `machine-draft`. They are usable for testing and release coverage,
but they are deliberately not presented as reviewed native translations. Any
publication of draft artifacts must include the generated localization
manifest with its review state and exact translation target; a machine draft
must never be represented as a human-reviewed translation.

Preparation preserves Mozilla's native network-error translation whenever the
message exists, changing only a hard-coded Firefox product name. The machine
draft is used for the About attribution, the new temporary-profile action, 112
individual network-error messages that are absent from Firefox's own locale
data, and explicit locale-specific corrections where an inflected Firefox name
cannot be safely replaced mechanically. This gives every locale all 14
controlled messages without discarding existing Pontoon translations.

About-dialog drafts preserve any Fluent brand-term arguments, grammatical
suffixes, and gender selectors present in the native Mozilla message. This is
required for locales such as Finnish, which requests the genitive brand form,
Telugu and Albanian, which attach a suffix, and Czech, which selects the
sentence from the brand gender. Preparation rejects a draft that drops any of
these contracts.

The frozen draft snapshot was generated on 2026-08-09. Its `target` field
records the exact machine-translation target. Some locales unsupported by the
translation engine use an explicitly recorded related-language target; for
example, `an` currently uses `es`. The release manifest reports values such as
`machine-draft/de` or `machine-draft/es`, so these approximations cannot be
mistaken for reviewed translations.

The Terms of Use and Privacy labels continue to describe their Mozilla
destination URLs. They must not be rebranded until Mercury has its own legal
pages. Some upstream locale trees retain the obsolete `unknownSocketType`
property, but Firefox 153 no longer packages or references it.

## Prepare the source and localization workspace

Apply Mercury's Firefox patches first. The patched `en-US` resources define
the controlled message and placeholder contract:

```bash
export MOZ_SRC_DIR=/path/to/firefox
./setup.py --linux
```

Then create an isolated localization workspace:

```bash
./prepare_l10n.py /path/to/firefox-l10n /tmp/mercury-l10n
export L10NBASEDIR=/tmp/mercury-l10n
```

The source localization repository is never modified and the destination must
not already exist. A normal clone, Git worktree, or bare repository can be used
as the source. Preparation verifies both pinned commits, confirms that every
patch carrying the `l10n-reference` role has supplied the patched `en-US`
reference messages, checks the Mercury branding overlay and active `mozconfig`,
merges the unified translation catalog, and writes `.mercury-l10n.json` into
the workspace. That marker records all supported locales, review states,
machine-translation targets, and SHA-256 digests for
`l10n/translations.json`, the localization generator, patched `en-US`
reference messages, and every generated controlled resource. It is required
by the batch repackaging script. Changing the catalog, generator, reference
patches, or prepared resources invalidates existing workspaces; prepare a fresh
one so content cannot silently drift between preparation and packaging.
Repackaging also derives the expected reviewed/draft partition and translation
targets directly from the catalog, so editing marker metadata alone cannot
promote a draft to reviewed.

Preparation parses every generated controlled FTL resource with Firefox's
vendored Fluent parser. Invalid selectors, placeables, or continuation syntax
therefore fail during preparation rather than during a later package build.

The prepared workspace contains all 103 external Firefox release locales:

- 2 locales with reviewed native Mercury messages;
- 101 locales with frozen, explicitly identified machine drafts;
- all other translated resources unchanged from Mozilla.

On native Windows, the equivalent preparation is:

```powershell
$env:MOZ_SRC_DIR = 'C:\path\to\firefox'
py -3 setup.py --win
py -3 prepare_l10n.py 'C:\path\to\firefox-l10n' `
  "$env:TEMP\mercury-l10n"
$env:L10NBASEDIR = "$env:TEMP\mercury-l10n"
```

## Build the en-US base

Build and package one `en-US` base for each platform and CPU variant:

```bash
./build.py
./package.py
```

Every SSE3, SSE4.1, AVX, AVX2, and ARM64 variant contains different native
binaries. Repackage each variant from its own object directory. A localized
package never changes its variant's compiled native code.

## Repackage every supported locale

Use the platform batch wrapper rather than maintaining a locale list by hand:

```bash
./repackage_locales.py --platform linux
```

Use `windows` or `macos` for the corresponding configured target. The
`--platform` value must describe the target binaries, not necessarily the
build host. For example, a Linux-to-Windows cross-build uses
`--platform windows`.

By default, output is written to `/tmp/mercury-localized-<platform>` on POSIX
systems and the corresponding system temporary directory on Windows. Use
`--dest DIRECTORY` to override it. For a real repackage, the destination may be
absent or an existing empty directory; a non-empty destination is rejected.

For example, a native Windows repackage can be started from PowerShell with:

```powershell
py -3 repackage_locales.py --platform windows `
  --dest "$env:TEMP\mercury-localized-windows"
```

The wrapper:

1. validates the Firefox revision, every `localized-repackage` patch, branding
   overlay, active Mercury `mozconfig`, l10n marker revisions,
   and translation catalog, generator, reference-message, and prepared-resource
   SHA-256 digests;
2. selects the 102 locales allowed for that platform;
3. sets `MERCURY_L10N_REPACK=1` so PGO is not rerun and the base binaries are
   not clobbered;
4. invokes the selected Firefox release's `mach repackage-single-locales`;
5. restores the object directory to `en-US`, including after failure;
6. writes `localization-manifest.tsv` with each locale's review state, exact
   machine target, catalog SHA-256, and produced/incomplete status. If Firefox
   returns success without the complete artifact set, the manifest records
   `overall=incomplete` and the wrapper fails.

Inspect the exact locale set without building:

```bash
./repackage_locales.py --platform linux --dry-run
./repackage_locales.py --platform windows --dry-run
./repackage_locales.py --platform macos --dry-run
```

Dry-run mode still validates the pinned Firefox checkout, applied localization
patches, branding overlay, active mozconfig, translation catalog, and prepared
`L10NBASEDIR`. It does not create platform packages.

The resulting per-locale directories must contain `target.langpack.xpi` and
the platform artifacts produced by Firefox's upload workflow: Linux requires
`target.tar.xz`, Windows requires both `target.zip` and
`target.installer.exe`, and macOS requires either `target.tar` or `target.dmg`.
The wrapper verifies the XPI ZIP structure, CRCs, Mercury extension ID,
Mercury-branded manifest name and description, `langpack_id`, exact `languages`
entry, browser resource mapping, and packaged browser resources. It also opens
TAR/TAR.XZ and ZIP outputs, checks ZIP CRCs, validates the Windows DOS and PE
structural signatures, and checks the DMG UDIF trailer. The PE check confirms
that the file has a plausible executable structure; it does **not** verify an
Authenticode signature or signer identity. Release signing must verify those
separately. An unrelated, empty, malformed, corrupt, wrong-locale, or
Firefox-identified artifact cannot make a locale successful. On macOS, a local
invocation produces a TAR because Firefox 153 intentionally skips the slow
local DMG step. Produce release DMGs through macOS release/signing automation
or a fully configured cross-packaging environment; never rename a TAR to DMG.

## Language packs

The batch repackage creates a Mercury-identified XPI for every selected
external locale. `mercury-langpack-identity.patch` gives its manifest
a `Mercury Language:` name and `Mercury Language Pack` description and assigns
IDs in this form:

```text
langpack-<locale>@mercury.alex313031.github.io
```

The same ID is used by runtime fallback detection. The source patch also keeps
the crash-reporter lookup and MSIX repackaging paths consistent with that ID,
but current Mercury mozconfigs disable the crash reporter and the primary
release workflow does not produce MSIX packages. Those two changes preserve
compatibility rather than describe currently published artifacts. The ID does
not collide with official Firefox language packs. Mercury does not use Firefox
AMO language-pack discovery or Firefox background-update coordination, so XPIs
must be published and updated with Mercury releases.

An XPI contains no CPU-specific native code. One XPI for a given Mercury
version can therefore be shared by SSE3, SSE4.1, AVX, and AVX2 builds, but it
must still be tested on every target operating system. If an `en-US` XPI is
also wanted for switching a localized installation back to English, build it
after the wrapper has restored the base configuration:

```bash
cd "$MOZ_SRC_DIR"
./mach build langpack-en-US
```

## Debian language-pack packages

An external locale XPI can be wrapped with Firefox's native Debian language
pack repackager after the `debian-repackage` patch is applied:

```bash
MERCURY_ROOT="$PWD"
VERSION="$(python3 -c \
  'from release_config import FIREFOX_VERSION; print(FIREFOX_VERSION)')"
cd "$MOZ_SRC_DIR"
./mach repackage deb-l10n \
  --input-xpi-file /path/to/locale.langpack.xpi \
  --input-tar-file "/path/to/mercury-${VERSION}.en-US.linux-x86_64.tar.xz" \
  --output /path/to/mercury-browser-l10n-LOCALE.deb \
  --version "$VERSION" \
  --build-number 1 \
  --templates "$MERCURY_ROOT/packaging/debian-langpack" \
  --product mercury \
  --package-name mercury-browser \
  --install-path usr/lib/mercury \
  --extensions-dir mercury/distribution/extensions
```

The XPI manifest supplies the lower-case package suffix. The resulting package
is `mercury-browser-l10n-<locale>` and depends on the exact matching
`mercury-browser` Debian version.

`L10NBASEDIR` is required when running `make_deb.py`. Before Firefox's localized
desktop generator is invoked, the wrapper verifies the pinned Firefox commit,
every `debian-repackage` patch, marker schema, catalog and generator digests,
review metadata, reference messages, and every controlled resource.
Reviewed locales use their native temporary-profile action label; other
locales use the frozen machine draft recorded for that locale.

## Optional multi-locale package

A single package containing all platform locales can be produced, but it is
much larger than separate localized packages. This POSIX example requires
Bash for `mapfile` and process substitution:

```bash
MERCURY_ROOT="$PWD"
mapfile -t locales < <(
  python3 "$MERCURY_ROOT/l10n/locale_manager.py" list \
    --changesets "$MOZ_SRC_DIR/browser/locales/l10n-changesets.json" \
    --platform linux
)
cd "$MOZ_SRC_DIR"
./mach package-multi-locale --locales "${locales[@]}"
```

The PowerShell equivalent is:

```powershell
$mercuryRoot = (Get-Location).Path
$locales = py -3 "$mercuryRoot\l10n\locale_manager.py" list `
  --changesets "$env:MOZ_SRC_DIR\browser\locales\l10n-changesets.json" `
  --platform windows
Set-Location $env:MOZ_SRC_DIR
py -3 mach package-multi-locale --locales $locales
```

Change the platform argument for the configured target. Separate localized
artifacts plus shared XPIs remain the recommended release model.

For the order in which PGO bases, localized variants, Debian packages,
portable packages, and platform release artifacts are assembled and validated,
see [Releasing Mercury](RELEASING.md).

## Adding a reviewed translation

To promote a machine-draft locale to reviewed native Mercury text, edit only
its entry in `l10n/translations.json`:

1. change `status` from `machine-draft` to `reviewed`;
2. set `target` to the locale itself;
3. provide all 14 Mercury-owned messages, including network messages that
   already exist upstream;
4. preserve Fluent variables, brand-term arguments, suffixes and selectors,
   overlay names, property placeholders, and legal destination names;
5. rerun `prepare_l10n.py` into a new empty workspace.

Preparation rejects incomplete locale coverage, an unknown review state,
mismatched catalog keys, missing controlled messages, broken `%S`
placeholders, unresolved machine-translation markers, or controlled messages
that still contain a known Firefox product name.

## Upgrading Firefox

Upgrade the Firefox and localization commits in `release.json` together with
the revisions in `browser/locales/l10n-changesets.json`. Then update
`l10n/translations.json` and the documentation's audit records. Re-audit the
Mercury-owned key set, verify platform membership, prepare a fresh workspace,
and test installation, locale switching, restart, About dialog, network
errors, desktop actions, and language-pack IDs for every release format.
