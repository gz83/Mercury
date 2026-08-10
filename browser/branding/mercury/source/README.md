# Mercury branding source notes

This directory contains editable design sources for manually maintained Mercury
branding resources. Firefox does not generate the packaged PNG, ICO, or ICNS
files from these sources during a build. The checked-in generated files are the
authoritative build and release inputs.

Bit-for-bit reproduction is not required. When a design source changes, update
all of its derived resources in the same commit, preserve the dimensions and
formats documented below, and visually validate the result on the affected
platforms.

## Private-browsing artwork

`private-browsing.svg` combines the private-browsing mask geometry audited
against Mercury's pinned Firefox 153 baseline with Mercury's cyan-and-purple
vector logo. The Firefox version identifies the source provenance; it is not a
build-time dependency. The logo paths are embedded in the SVG so browsers,
repository previews, and image tools render the same self-contained artwork.

The following checked-in release inputs are maintained from this source:

| Output | Required format and composition |
| --- | --- |
| `../content/about-logo-private.png` | Transparent 192-by-192 PNG |
| `../content/about-logo-private@2x.png` | Transparent 384-by-384 PNG |
| `../PrivateBrowsing_150.png` | Transparent 300-by-300 PNG with nominal 150-pixel artwork and an approximate 125-pixel visible bound |
| `../PrivateBrowsing_70.png` | Transparent 142-by-142 PNG with nominal 84-pixel artwork and an approximate 70-pixel visible bound |
| `../pbmode.ico` | 16-, 32-, 48-, and 256-pixel frames; the first three use legacy DIB payloads and the 256-pixel frame uses PNG |

The choice of renderer and resampling algorithm is left to the maintainer.
Before replacing these files, verify transparency, centering, edge quality, ICO
frame membership, the About Private Browsing view at 1x and 2x scale, and the
Windows private-browsing visual elements.

## Wordmarks

The two wordmark SVGs under `../content/` contain outlined `Mercury` glyphs
rather than live SVG text. This keeps their rendering independent of installed
fonts while preserving Firefox's `context-fill` theme integration.
`about-wordmark.svg` intentionally has no fallback color;
`firefox-wordmark.svg`, used by new-tab and private-browsing surfaces, retains a
dark fallback color. Both files are checked-in build inputs and are edited
directly rather than generated during a build.

## Windows document icon

`../msix/Assets/Document44x44.png` is a manually maintained 44-by-44 rendition
of the 256-pixel source in `../macos/DocumentIcon.iconset`. It deliberately
retains the document-page silhouette instead of reusing the standalone Mercury
application logo. Update and visually inspect it whenever the document icon
design changes.

## macOS icon sources

The editable Icon Composer package, legacy iconsets, generated macOS resources,
manual replacement checks, and build provenance are documented in
[`../macos/README.md`](../macos/README.md).
