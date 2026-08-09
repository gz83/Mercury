# Mercury branding sources

`private-browsing.svg` combines Firefox 153's private-browsing mask geometry
with Mercury's cyan-and-purple vector logo. The logo paths are embedded in the
SVG instead of referencing a neighboring PNG, so browsers, repository previews,
and build tools render the same self-contained artwork. It is the source for
the four checked-in private-browsing PNG resources and `../pbmode.ico`. Render
it on a transparent background at 192 and 384 pixels for the About Private
Browsing artwork. For Windows visual elements, render it at 150 pixels on a
transparent 300-by-300 canvas and at 84 pixels on a transparent 142-by-142
canvas. The source's internal margin gives the visible composition the same
approximate 125- and 70-pixel bounds used by Firefox 153. The ICO contains
16-, 32-, 48-, and 256-pixel renditions; the first three use legacy DIB payloads
and the 256-pixel rendition uses a compressed PNG payload.

The two wordmark SVGs under `content/` contain outlined `Mercury` glyphs rather
than live SVG text. This keeps their rendering identical across operating
systems while preserving Firefox's `context-fill` theme integration. The About
wordmark has no fallback color; the new-tab/private-browsing wordmark retains
Firefox's dark fallback color.

The Windows MSIX document-association icon
`../msix/Assets/Document44x44.png` is rendered from the 256-pixel document
source in `../macos/DocumentIcon.iconset`. It deliberately retains the document
page silhouette instead of reusing the standalone Mercury application logo.

The three macOS ICNS resources have standard ten-rendition sources under
`../macos/`. `LegacyAppIcon.iconset` generates the fallback `firefox.icns`,
`DocumentIcon.iconset` generates `document.icns`, and `DiskIcon.iconset`
generates the mounted-volume `disk.icns`. The last is based on Firefox 153's
`unofficial` DMG drive chassis with its Nightly globe replaced by Mercury's
logo. The macOS legacy-icons workflow compiles all three with Apple's
`iconutil`, round-trips every result, and uploads the verified files as an
artifact. The three ICNS files serve different packaging roles and must not be
substituted for one another.
