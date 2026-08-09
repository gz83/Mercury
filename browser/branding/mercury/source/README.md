# Mercury branding sources

`private-browsing.svg` combines Firefox 153's private-browsing mask geometry
with Mercury's cyan-and-purple vector logo. The logo paths are embedded in the
SVG instead of referencing a neighboring PNG, so browsers, repository previews,
and build tools render the same self-contained artwork. It is the source for
the four checked-in private-browsing PNG resources. Render it on a transparent
background at 192 and 384 pixels for the About Private Browsing artwork. For Windows visual
elements, render it at 150 pixels on a transparent 300-by-300 canvas and at 84
pixels on a transparent 142-by-142 canvas. The source's internal margin gives
the visible composition the same approximate 125- and 70-pixel bounds used by
Firefox 153.

The two wordmark SVGs under `content/` contain outlined `Mercury` glyphs rather
than live SVG text. This keeps their rendering identical across operating
systems while preserving Firefox's `context-fill` theme integration. The About
wordmark has no fallback color; the new-tab/private-browsing wordmark retains
Firefox's dark fallback color.

`disk.icns` is based on Firefox 153's `unofficial` DMG drive chassis, with its
Nightly globe replaced by Mercury's logo at every embedded resolution. Its ten
editable PNG renditions live in `../macos/DiskIcon.iconset`; the macOS disk-icon
workflow compiles those sources with Apple's `iconutil`, round-trips the result,
and uploads the verified ICNS as an artifact. Do not replace it with
`firefox.icns`: the former identifies the mounted installer volume, while the
latter is the legacy application icon.
