# Debugging Mercury <img src="assets/bug.svg" width="28">

## Build and run a debug configuration

Run these commands from the Mercury repository root. Linux and native Windows
have dedicated debug configurations:

```bash
# Linux
./setup.py --debug
./build.py
./run.py
```

On Windows, use `py -3 setup.py --win-debug`, `py -3 build.py`, and
`py -3 run.py`. The debug configs enable Firefox assertions and retain the AVX
baseline used by Mercury's default release. Use a release profile instead when
the behavior being investigated depends on release optimization or packaging.

`run.py` deliberately accepts no browser arguments. It invokes `mach run`,
which uses a temporary profile when neither `--profile` nor `-P` is supplied.
This prevents development runs from modifying a daily-use profile.

For debugger controls, temporary preferences, or browser arguments, work from
the prepared Firefox checkout and invoke `mach` directly:

```bash
cd "$MOZ_SRC_DIR"
./mach run --debug
./mach run --setpref network.http.http3.enable=false
./mach run -- --new-instance --profile /tmp/mercury-debug-profile
```

Options before the standalone `--` belong to `mach run`; options after it are
passed to Mercury. `--debug` starts the platform's default debugger. Use
`./mach run --help` to inspect other mach options, including `--debugger`,
`--debugger-args`, `--setpref`, and `--temp-profile`. On native Windows, the
equivalent direct form is `py -3 mach run` from the Firefox checkout.

## Command-line options

Mercury inherits the command-line interface of the Firefox release pinned in
`release.json`. Common browser options are:

| Option | Purpose |
| --- | --- |
| `--new-instance` | Start a separate instance instead of forwarding to a running browser |
| `-P NAME` | Start with the named profile |
| `--profile PATH` | Start with the profile stored at `PATH` |
| `--ProfileManager` | Open the profile manager |
| `--kiosk URL` | Open a URL in kiosk mode |
| `--devtools` | Open page Developer Tools on initial load |
| `--jsconsole` | Open the Browser Console |
| `--jsdebugger` | Open the Browser Toolbox |
| `--wait-for-jsdebugger` | Wait during startup for the Browser Toolbox debugger to connect |
| `--purgecaches` | Invalidate Gecko startup and JavaScript caches |
| `--safe-mode` | Start in troubleshooting mode with extensions and themes disabled |
| `-v`, `--version` | Print the Mercury version |
| `--full-version` | Print the version, build ID, and platform build ID |
| `--headless` | Run without a GUI on supported desktop platforms |
| `--console` | Start a debugging console on Windows |
| `--MOZ_LOG=MODULES` | Override the `MOZ_LOG` environment variable |
| `--MOZ_LOG_FILE=FILE` | Write Gecko logs to a file instead of standard output |

These are browser arguments, so place them after the mach separator when
running from the source checkout:

```bash
./mach run -- --new-instance --profile /tmp/mercury-profile
```

## Gecko logging

Enable one or more Gecko log modules with `MOZ_LOG`. The command-line forms are
convenient for a single run and override environment variables of the same
name:

```bash
./mach run -- --MOZ_LOG=timestamp,nsHttp:5 \
  --MOZ_LOG_FILE=/tmp/mercury-http.log
```

Module names and levels depend on the component being diagnosed. If no
`MOZ_LOG_FILE` is supplied, the log is written to standard output. Avoid
publishing logs without review because URLs, paths, and other user data may be
included.

## Tests and linting

Run Firefox tests against paths in the prepared Firefox checkout. `mach test`
does not rebuild automatically, so rebuild after changing a patch or overlay:

```bash
cd "$MOZ_SRC_DIR"
./mach build
./mach test path/to/test
./mach lint path/to/changed/source
```

Firefox selects the appropriate test harness from the supplied test path. Use
`./mach test --help`, or the selected harness's help, for suite-specific
options.

## Preferences

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
