<img src="../browser/branding/mercury/default256.png" width="144">

# Mercury patch manifest <img src="assets/patches.png" width="32">

## Current patch layout

The patches in the stable `patches/firefox/` path currently apply only to
`FIREFOX_153_0_3_RELEASE` (`0c39e9282688363f5028d0541c17784f7fa5117c`).

Git history preserves earlier patch sets; upgrading Firefox replaces or rebases
the files in this directory instead of introducing another versioned path.
`patches/manifest.json` is the machine-readable source for application order
and feature roles. Every `.patch` file must appear exactly once. Consumers use
the `l10n-reference`, `localized-repackage`, `debian-repackage`, and
`windows-sfx` roles instead of depending on individual filenames.

Every declared patch is applied by `setup.py` in manifest order, including
patches whose `roles` list is empty. A role is an additional stable interface
for a specialized consumer; it is not an application filter:

| Role | Consumer and requirement |
| --- | --- |
| `l10n-reference` | `prepare_l10n.py` verifies that patches defining the controlled `en-US` reference messages are applied |
| `localized-repackage` | `repackage_locales.py` verifies all patches required for localized archives, installers, and language packs |
| `debian-repackage` | `make_deb.py` verifies the Firefox Debian repackager changes it depends on |
| `windows-sfx` | The Windows SFX rebuild workflow selects the editable 7-Zip resource patch |

| Patch | Purpose |
| --- | --- |
| `mercury-default-preferences.patch` | Audited Mercury preference defaults |
| `mercury-customizable-ui.patch` | Mercury toolbar defaults and UI migrations |
| `mercury-app-branding.patch` | Mercury title for early Windows launcher errors |
| `mercury-distribution-policy.patch` | Package Mercury's `distribution/policies.json` |
| `mercury-build-configuration.patch` | Select Mercury branding and build-time product options |
| `mercury-default-bookmarks.patch` | Mercury's default toolbar bookmarks on the Firefox 153 template |
| `mercury-windows-installer.patch` | Windows installer branding, MSIX color, isolated reset marker, and disabled Mozilla uninstall survey |
| `mercury-localization.patch` | Mercury-specific About dialog and network error wording |
| `mercury-lto-tuning.patch` | Raise Clang's ThinLTO import instruction limit for Mercury performance builds |
| `mercury-devtools-branding.patch` | Use Mercury branding for the local `about:debugging` runtime without replacing remote Firefox and Fenix channel icons |
| `debian-package-identity.patch` | Give Firefox's application and language-pack Debian repackagers Mercury package/install identities and generate localized desktop entries from Mercury branding |
| `mercury-plugin-container-branding.patch` | Use Mercury's company name in the Windows `plugin-container.exe` version resource |
| `mercury-langpack-identity.patch` | Give Mercury language packs product-specific names and IDs, and keep runtime fallback plus optional crash-reporter and MSIX code paths consistent |
| `mercury-user-agent-compatibility.patch` | Keep Mercury's network User-Agent Firefox-compatible without replacing Firefox 153's HTTP handler |
| `mercury-profileserver-software-rendering.patch` | Make PGO profile generation independent of target GPU and driver availability |
| `mercury-windows-sfx-branding.patch` | Brand the Windows 7-Zip self-extractor source and report Mercury's Windows 10 minimum |

The langpack identity patch also updates crash-reporter lookup and MSIX
repackaging code so those optional paths use Mercury's extension ID. Current
Mercury mozconfigs disable the crash reporter, and the primary release workflow
does not produce MSIX packages; these changes preserve compatibility rather
than describe currently published artifacts.

## Firefox source overlays

`setup.py` keeps its source overlays in the explicit `FILE_OVERLAYS` and
`DIRECTORY_OVERLAYS` allowlists. There is no separate overlay manifest. It
never recursively copies the repository's `app/`, `browser/`, or
`other-licenses/` trees over Firefox. `browser/branding/mercury/` is the only
directory-level overlay; every other source overlay is copied as an individual
file. Mercury-owned files remain as overlays only where a patch is not the
appropriate representation:

- `app/mercury.exe.manifest`: selected automatically for `mercury.exe` by the
  Windows build rules.
- `app/module.ver`: eight-line Windows branding resource. It remains an overlay
  because it supplies product-owned version metadata for `mercury.exe`. Its
  copyright and trademark values intentionally use ASCII because Firefox 153's
  resource generator reads `module.ver` as Latin-1.
- `app/distribution/policies.json`: independently maintained product policy.
- `browser/branding/mercury/`: independently maintained Mercury artwork and
  branding resources, rebased on Firefox 153's `unofficial` branding layout.
  Source mapping and manual regeneration notes for derived branding resources
  live under `browser/branding/mercury/source/`.
  Mercury's two-layer Icon Composer source is maintained under
  `browser/branding/mercury/macos/AppIcon.icon`. The manually dispatched
  `.github/workflows/rebuild-macos-assets-car.yml` workflow compiles it with a
  pinned Xcode toolchain, validates the `AppIcon` catalog, and uploads the
  generated `Assets.car` and provenance sidecars without modifying the
  repository. The validated catalog is checked in beside `firefox.icns` and is
  copied and packaged by Firefox 153's native macOS rules. `CFBundleIconName`
  selects its `AppIcon` entry on current macOS releases, while `firefox.icns`
  remains the legacy fallback. Firefox/Nightly `Assets.car` files must never
  be copied into Mercury branding. Standard ten-rendition sources for the
  legacy application, document-association, and DMG volume icons live in
  `browser/branding/mercury/macos/{LegacyAppIcon,DocumentIcon,DiskIcon}.iconset`.
  The manually dispatched
  `.github/workflows/rebuild-macos-legacy-icons.yml` workflow compiles and
  round-trip-validates `firefox.icns`, `document.icns`, and `disk.icns` with
  Apple's `iconutil`, then uploads them and their provenance files as artifacts
  without changing the repository.
- `other-licenses/7zstub/firefox/{7zSD.Win32.sfx,7zSD.ARM64.sfx,setup.ico}`:
  product-branded binary inputs for Firefox's full Windows installer. The two
  SFX executables are checked in because Firefox packaging also consumes
  prebuilt stubs and must work without a separately configured Visual Studio
  toolchain. Their editable resource changes use the `windows-sfx` role; see the
  adjacent `README.mercury` for provenance and rebuild requirements. The
  manually dispatched `.github/workflows/rebuild-windows-sfx.yml` workflow
  performs the pinned Firefox checkout, x86/ARM64 rebuild, validation,
  attestation, and artifact upload without modifying the repository.

## Build configuration inputs

After applying patches and overlays, `setup.py` copies the selected file from
`mozconfigs/` to the Firefox root as `mozconfig` and copies `mozconfigs/ga` as
`ga`. These are product build-configuration inputs, not Firefox source overlays
and not entries in `patches/manifest.json`.

## Release assembly inputs

The following files are consumed after Firefox source preparation and are not
copied into the source tree by the overlay allowlists:

- `packaging/portable/{linux,windows}/`: auditable launchers used by
  `make_portable.py` after Firefox produces its native Linux TAR or Windows ZIP.
  The old root `portable/` directory and its opaque `shc`-generated Linux
  executable were removed.
- `packaging/debian/` and `packaging/debian-langpack/`: Mercury templates for
  Firefox's native `mach repackage deb` and `mach repackage deb-l10n` commands.

## Removed legacy overlays

The obsolete Firefox 129 overlays `app/Makefile.in`, `app/application.ini`, and
`app/splash.rc` were removed. Firefox 153 generates `application.ini` from
`build/application.ini.in` and automatically embeds the executable manifest.

The obsolete Firefox 129 copies of `build/application.ini.in` and
`build/moz.configure/{lto-pgo,toolchain}.configure`, plus the unused
`build/codename.txt`, were removed. Mercury's CPU and optimization flags remain
in the platform mozconfigs; the only retained build-system source change is the
release-targeted ThinLTO tuning patch above.

The Firefox 129 whole-file `toolkit/moz.configure` overlay was also removed.
Its only Mercury-specific delta enabled JPEG XL outside Nightly, which Firefox
153 already does upstream. Language-pack identity changes now live in patch
`mercury-langpack-identity.patch`, without replacing thousands of current
toolkit configuration lines.

The old whole-file overlays under `browser/base`, `browser/components`,
`browser/installer`, `browser/locales`, and the top level of `browser/` were
removed. Product changes to current Firefox files now live in the
release-targeted patches above; only `browser/branding/mercury/` remains as a
browser overlay.

The seven duplicated `devtools/client/themes/images/aboutdebugging-*.svg`
overlays were removed. They replaced every remote Firefox and Fenix channel
icon with the Mercury logo. `mercury-devtools-branding.patch` instead points
only the local `about:debugging` sidebar entry at Mercury's shared branding
resource and leaves upstream remote-runtime icons intact.

The old `ipc/app/module.ver` overlay differed from Firefox only in the Windows
company-name field. `mercury-plugin-container-branding.patch` now carries that
product-specific change while preserving the rest of Firefox 153's
`plugin-container.exe` version resource. Git encodes this one-line change as a
binary patch only because the upstream file is stored with unnormalized CRLF
line endings.

The Firefox 129 `netwerk/protocol/http/nsHttpHandler.cpp` overlay differed from
its upstream baseline by one User-Agent compatibility line.
`mercury-user-agent-compatibility.patch` carries that line on Firefox 153 and
avoids reverting the current HTTP implementation.

The old whole-file profileserver preference overlay was replaced by
`mercury-profileserver-software-rendering.patch`, which carries only Mercury's
still-valid software-rendering preference on the Firefox 153 profileserver
defaults.

The old recursive `other-licenses/` overlay was removed. Mercury does not
replace Firefox's copy of the LZMA SDK or its build projects. Setup now copies
only the two product-branded prebuilt SFX executables and their source icon;
the `resource.rc` changes are applied to Firefox 153 by the patch carrying the
`windows-sfx` role. The prebuilt executables must be regenerated whenever the
pinned Firefox 7zstub source changes.

Mercury does not enable Firefox's Windows stub installer. Releases contain
multiple CPU-specific installers and do not provide the single signed payload
and certificate identity required by the upstream stub download flow.

Mercury's Debian packages use Firefox's `mach repackage deb` and
`mach repackage deb-l10n` implementations. Product-specific templates live in
`packaging/debian/` and `packaging/debian-langpack/`. Firefox's localized
desktop generator supplies the application entry. `make_deb.py` requires
`L10NBASEDIR` and validates the prepared Mercury localization marker and
content before invoking it. The old committed `dist/` root filesystem and its
duplicated icons, compressed documentation, static dependency list, and legacy
MIME registration were removed.

External-locale Mercury translations are maintained in the unified
`l10n/translations.json` catalog. Each entry declares `reviewed` or
`machine-draft` status and the exact translation target. `prepare_l10n.py`
merges this catalog into an isolated checkout of Firefox 153's pinned
localization repository; no locale-specific patch directory or separate locale
allowlist is required. See [`LOCALIZATION.md`](LOCALIZATION.md).
