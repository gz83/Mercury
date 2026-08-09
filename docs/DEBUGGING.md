# Debugging Mercury <img src="assets/bug.svg" width="28">

## Command-line options

Mercury supports Firefox's current command-line interface. Common options are:

| Option | Purpose |
| --- | --- |
| `--new-instance` | Start a separate instance instead of forwarding to a running browser |
| `-P NAME` | Start with the named profile |
| `--profile PATH` | Start with the profile stored at `PATH` |
| `--ProfileManager` | Open the profile manager |
| `--kiosk URL` | Open a URL in kiosk mode |
| `--devtools` | Open the browser with Developer Tools |
| `--purgecaches` | Invalidate Gecko startup and JavaScript caches |
| `--safe-mode` | Start in troubleshooting mode with extensions and themes disabled |
| `--version` | Print the Mercury version |
| `--MOZ_LOG=MODULES` | Enable Gecko logging for the selected modules |

When running from the Firefox source checkout, pass application arguments after
`--`:

```bash
./mach run -- --new-instance --profile /tmp/mercury-profile
```

Use `about:config` to inspect or temporarily change preferences. Mercury's
audited product defaults and their owners are documented in
[PREFERENCES.md](PREFERENCES.md).

## Resources

- [Gecko logging](https://firefox-source-docs.mozilla.org/xpcom/logging.html)
- [Command-line options](https://firefox-source-docs.mozilla.org/browser/CommandLineParameters.html)
- [Browser Console](https://firefox-source-docs.mozilla.org/devtools-user/browser_console/index.html)
- [Browser Toolbox](https://firefox-source-docs.mozilla.org/devtools-user/browser_toolbox/index.html)
- [DevTools](https://firefox-source-docs.mozilla.org/devtools-user/index.html)
- [`about:debugging`](https://firefox-source-docs.mozilla.org/devtools-user/about_colon_debugging/index.html)
- [Debugging Firefox with GDB](https://firefox-source-docs.mozilla.org/contributing/debugging/debugging_firefox_with_gdb.html)
