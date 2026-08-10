# Mercury preference migration for Firefox 153

This audit is tied to Firefox tag `FIREFOX_153_0_3_RELEASE`, commit
`0c39e9282688363f5028d0541c17784f7fa5117c`. The source delta was extracted
from Mercury's `app/profile/firefox.js` against Firefox 129.0.2; it contains
136 changed preference keys (including the conditional change for
`devtools.command-button-experimental-prefs.enabled`).

The complete set of retained defaults is the final block added by
`patches/firefox/mercury-default-preferences.patch`. The old complete
copy of `firefox.js` must not be restored: doing so would replace nearly 400
lines of Firefox 153 defaults and features with Firefox 129 code.

## Ownership and validity

The patch deliberately keeps product overrides together at the end of
`browser/app/profile/firefox.js`, while the owning implementation remains:

| Owner in Firefox 153 | Preferences covered |
| --- | --- |
| `browser/app/profile/firefox.js` | Browser UI, startup, session restore, update, discovery, Normandy, telemetry sender switches, FxA promotion, Sync-registration, and DevTools defaults |
| `modules/libpref/init/StaticPrefList.yaml` | DNT/GPC, rendering, JXL, EME, CSS masonry, media/image caches, DNS cache, TLS cache, initial paint, and GTK overlay-scrollbar preferences |
| `modules/libpref/init/all.js` | User-agent compatibility and HTTP/WebSocket/buffer/prefetch defaults |
| `browser/extensions/newtab/lib/ActivityStream.sys.mjs`, `browser/extensions/newtab/lib/SectionsManager.sys.mjs` | New Tab sites, rows, stories, sponsored content, and New Tab telemetry; `DefaultPrefs.init()` explicitly preserves an application default already registered by `firefox.js` |
| `toolkit/mozapps/extensions/internal/AddonRepository.sys.mjs` | Firefox language-pack discovery through `extensions.getAddons.langpacks.url` |
| `toolkit/mozapps/update/BackgroundUpdate.sys.mjs` | Language-pack coordination during application and background updates through `app.update.langpack.enabled` |
| Other runtime pref consumers | `toolkit.telemetry.enabled`, `browser.newtabpage.activity-stream.feeds.system.topstories`, and the generic `services.sync.prefs.sync.*` registrations |

The retained block contains 91 unique keys: 87 directly migrated defaults and
four current replacements or Mercury product controls. Every key has an active
Firefox 153 definition, a runtime consumer, or (for Sync registrations) a
generic branch consumer. The four current additions are:

- `browser.newtabpage.activity-stream.telemetry=false`, replacing the dead Ping
  Centre switch;
- `browser.newtabpage.activity-stream.system.showSponsored=false`, replacing
  removed granular Pocket/Discovery Stream advertising switches;
- `extensions.getAddons.langpacks.url=""`, preventing Firefox language packs
  from being fetched from AMO alongside Mercury language packs; and
- `app.update.langpack.enabled=false`, leaving language-pack update coordination
  to Mercury's release and localization process.

The old `browser.uiCustomization.state` was not copied verbatim. Its intent is
migrated in `patches/firefox/mercury-customizable-ui.patch`, against the
Firefox 153 `CustomizableUI` owner: Home, Developer Tools and Unified Extensions
remain in the navbar; Firefox View, springs, vertical spacer, sidebar and IP
Protection are omitted from Mercury's default placements. The obsolete v18
Firefox View insertion, v21 spacer insertion, and Proton home-button removal
migrations are disabled. This avoids freezing new profiles to a serialized v19
toolbar state and retains Firefox 153's v24 state format and later migrations.

## Keys intentionally not copied verbatim

This table accounts for every remaining Firefox 129-era delta.

| Preference(s) | Firefox 153 result |
| --- | --- |
| `browser.uiCustomization.state` | Replaced by the owner-level `mercury-customizable-ui.patch`; the stale serialized v19 state is not copied. |
| `browser.attribution.enabled`, `browser.shell.defaultBrowserAgent.thanksURL`, `browser.theme.colorway-migration` | Removed with no current consumer or replacement pref. |
| `browser.shopping.experience2023.active`, `browser.shopping.experience2023.autoOpen.userEnabled`, `browser.shopping.experience2023.survey.enabled` | The 2023 Review Checker implementation and these switches were removed. |
| `extensions.pocket.api`, `extensions.pocket.bffApi`, `extensions.pocket.bffRecentSaves`, `extensions.pocket.enabled`, `extensions.pocket.oAuthConsumerKey`, `extensions.pocket.oAuthConsumerKeyBff`, `extensions.pocket.showHome`, `extensions.pocket.site` | The old Pocket extension integration was removed. Current Stories and sponsored-content controls are migrated through active Activity Stream prefs. |
| `browser.pocket.enabled`, `browser.tabs.firefox-view`, `browser.search.serpEventTelemetry.enabled`, `browser.urlbar.searchEngagementTelemetry.enabled` | These exact keys had no functional consumer even in the Firefox 129 baseline (prefix matches and tests are not consumers); they are not carried forward. SERP categorization uses the retained `browser.search.serpEventTelemetryCategorization.enabled`. |
| `browser.ping-centre.telemetry` | Dead key; replaced by active `browser.newtabpage.activity-stream.telemetry`. |
| `browser.newtabpage.activity-stream.discoverystream.merino-provider.enabled`, `browser.newtabpage.activity-stream.discoverystream.onboardingExperience.dismissed`, `browser.newtabpage.activity-stream.discoverystream.personalization.enabled`, `browser.newtabpage.activity-stream.discoverystream.saveToPocketCard.enabled`, `browser.newtabpage.activity-stream.discoverystream.sendToPocket.enabled`, `browser.newtabpage.activity-stream.discoverystream.spocTopsitesPlacement.enabled`, `browser.newtabpage.activity-stream.discoverystream.spocs.personalized` | Removed granular Discovery Stream keys. The active master Stories/Discovery Stream and sponsored switches are disabled instead. |
| `browser.newtabpage.activity-stream.feeds.snippets`, `browser.newtabpage.activity-stream.section.highlights.includePocket`, `browser.urlbar.suggest.pocket`, `browser.topsites.contile.sov.enabled` | Removed legacy New Tab/Pocket keys. Their surviving parent features are disabled by current prefs. |
| `services.sync.prefs.sync.browser.newtabpage.activity-stream.section.highlights.includePocket`, `services.sync.prefs.sync.browser.offline-apps.notify` | The corresponding target preferences were removed, so retaining their Sync registrations would have no effect. |
| `security.app_menu.recordEventTelemetry`, `security.certerrors.recordEventTelemetry`, `security.protectionspopup.recordEventTelemetry`, `toolkit.telemetry.pioneer-new-studies-available` | Removed telemetry switches with no Firefox 153 consumer. Current surviving granular telemetry switches remain disabled. |
| `image.avif.enabled`, `layout.css.has-selector.enabled` | AVIF and CSS `:has()` are shipped capabilities in Firefox 153 and no longer have these feature gates. |
| `media.autoplay.block-webaudio` | Removed; Web Audio autoplay is handled by the current unified autoplay implementation, with no direct replacement pref. |
| `network.predictor.enabled`, `network.predictor.enable-prefetch` | Removed predictor switches. `network.dns.disablePrefetch`, `network.prefetch-next`, and speculative parallel connections remain active and are retained. |
| `browser.urlbar.trimHttps` | Firefox 153 Release already defaults to `false`; no Mercury override is needed. |
| `dom.enable_web_task_scheduling`, `general.smoothScroll`, `mousewheel.with_control.action`, `mousewheel.with_meta.action` | Firefox 153 already has Mercury's effective values. On non-macOS, Control+wheel already uses action 3 from `all.js`; Meta+wheel remains action 1. |
| `gfx.canvas.accelerated.cache-items` | Firefox 153 increased the default to 8192, above Mercury's old 4096 tuning; copying it would be a regression. |
| `network.dns.max_high_priority_threads` | Firefox 153 increased the default to 40, above Mercury's old value 8; copying it would be a regression. |

## Effectiveness caveats

- `xpinstall.signatures.required=false` and
  `extensions.langpacks.signatures.required=false` are effective only when the
  build does not set `MOZ_REQUIRE_SIGNING`. Mercury's mozconfigs explicitly
  clear it. Enabling unsigned add-ons weakens add-on authenticity protection.
- `extensions.getAddons.langpacks.url=""` prevents Firefox language packs from
  AMO from replacing or duplicating Mercury's product-specific language packs.
  `app.update.langpack.enabled=false` disables Firefox's special app-update and
  background-update coordination for installed language packs. Mercury
  language packs must be installed and updated from Mercury release artifacts.
- `layers.acceleration.force-enabled=true` can bypass Firefox GPU/driver
  blocklisting. It may improve acceleration availability, but can reduce
  stability or rendering correctness on unsupported hardware and drivers.
- `image.jxl.enabled=true` requires a build with `MOZ_JXL`; Mercury's mozconfigs
  use `--enable-jxl`.
- `media.eme.enabled=true` makes EME visible and enabled on Linux and can cause
  proprietary DRM components to be downloaded.
- `app.update.auto=false` remains a default/migration value on Windows; after
  migration Firefox stores the actual choice in the update directory. Mercury
  mozconfigs also use `--disable-updater`, so this preference is not a substitute
  for an update mechanism. Users must update through Mercury release artifacts
  or the package manager that supplied Mercury.
- `toolkit.telemetry.enabled` may be locked by Firefox channel/build policy.
  The retained granular sender switches are independently set to `false`.
- `privacy.donottrackheader.enabled` and
  `privacy.globalprivacycontrol.enabled` send preference signals to sites; they
  do not guarantee that a site will honor those signals.
- The high connection limits and enlarged DNS, TLS, media, image, and buffer
  caches are workload-dependent tuning choices. They can retain more memory and
  network resources and must not be treated as universally faster defaults.
- Disabling DNS prefetch, link prefetch, and speculative parallel connections
  reduces speculative networking but can increase navigation latency.
- These are default-branch values. Existing profiles can have user-branch
  values that take precedence, except where Firefox locks a preference.

## Re-audit procedure

For a later Firefox release:

1. Pin the exact upstream tag and commit in `release.json`, and verify that
   `mercury-default-preferences.patch` passes `git apply --check` against that
   checkout. A failing patch must be re-audited rather than forced onto another
   revision.
2. Extract and count the unique preference names in the retained block. Account
   explicitly for additions, removals, renames, and replacements instead of
   assuming the Firefox 153 total of 91 still applies.
3. Search the new upstream tree for each definition and runtime consumer. For
   `services.sync.prefs.sync.*`, also inspect the generic Sync branch consumer;
   absence of a full-string match alone does not make a registration dead.
4. Compare upstream defaults and build-time feature flags, especially updater,
   signing, JXL, telemetry, EME, New Tab, and GPU behavior.
5. Run `python3 setup.py --check`, then test both a fresh profile and an existing
   profile because user-branch and migrated values can override application
   defaults.
