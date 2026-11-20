# 0061 - Electron shell guards

Date: 2026-11-19. Source: package OVL-SHELL-GUARDS (wave 9); finding F-110
(docs/plan/02-findings.md); decisions 0002, 0041, 0053.

## Decision

1. One part, inherited by every window. `app/parts/10-guards.js` (parts
   seam, decision 0053; first in file-name order) does at the `early`
   hook, before any window exists:
   - quits (app.exit(1), then the process exit) when the start carries an
     inspect switch (`--inspect`, `--inspect-*`, `--debug`), a
     remote-debugging port or pipe (in the `--`, `-` or `/` spelling
     Chromium reads on Windows, or as Chromium already parsed it), or a
     non-empty NODE_OPTIONS; `AL_DEV=1` (the devTools switch of the
     AUDIT-ELECTRON finding S6) allows them for development;
   - `app.enableSandbox()`: every renderer is sandboxed, whatever its
     webPreferences say;
   - `app.commandLine.appendSwitch("disable-webgl")`: WebGL is off for
     every page, so neither BrowserWindow option block needs `webgl:
     false`;
   - `app.on("web-contents-created")` attaches default-deny handlers to
     every new webContents: `will-navigate`, `will-redirect`,
     `will-attach-webview` and `setWindowOpenHandler`. They read a
     registry at event time; a webContents its creator did not register
     gets nothing (navigation, redirect, popup and webview all refused).
2. Registration. The `overlayWindow` hook registers the overlay with the
   deny-all policy; the `clientWindow` hook registers the companion with
   its own route rule (`Link.routeFor(url, port, false) === "stay"`, never
   a popup), so its loads and same-origin reloads on the local core keep
   working. The windows' own handlers stay: app/client/window.js still
   hands http(s) links to the default browser, and app/main.js keeps
   `setWindowOpenHandler(() => ({ action: "deny" }))`.
3. Exact IPC senders (app/main.js, IPC block of start()). `al:config` (the
   per-start token) answers only when `e.senderFrame` is the overlay
   window's main frame and its URL is exactly the overlay page
   (`url.pathToFileURL` of app/overlay/index.html, compared in either
   spelling: percent-encoded or plain, forward or back slashes, any
   drive-letter case; no fragment). Any other sender, including a file
   URL elsewhere that also ends in /overlay/index.html, gets `{}`.
   `al:gate` keeps its overlay-only sender check; `al:restart-overlay`
   keeps the companion main-frame check (`client.isCompanion`).
4. Restart throttle. The overlay is rebuilt at most once per 2 s
   (`Guards.throttle(2000)` at the top of `restartOverlay()`); a second
   ask within 2 s is logged and dropped.
5. The pure rules live in `app/guards.js` (isDebugStart,
   frameIsOverlayPage, throttle, createRegistry, attachDefaults), tested
   with fakes in app/test/guards.test.js. The static guard of
   tests/test_overlay_smoke.py (P4-6) bans the debugging switch names
   anywhere in app/ except app/guards.js, and the bare spawn names except
   app/client/launcher.js.

## Choices the package text left open (ruled)

- The restart throttle sits in `restartOverlay()`, so it covers the tray
  and the parts too, not only the IPC message. app/test/client_controls.
  test.js (outside this package's files) pins the IPC handler body as
  `if (client && client.isCompanion(e)) { restartOverlay(); }`; a gate
  inside the handler would break that pin. Alternatives: stop as failed
  for a test edit; wrap ipcMain. A second rebuild within 2 s has no use
  from any caller. Reverses if: a caller needs two rebuilds within 2 s.
- The debug quit also covers `--debug` / `--debug-brk` and Chromium's
  `-name` / `/name` switch spellings, and reads app.commandLine.hasSwitch
  for the remote-debugging names: the stricter reading.
- WebGL is off by switch, not by webPreferences (the notes' preferred
  path): no edit of either window's option block.

## Alternatives

- Per-window rules as today: each window repeats its own navigation,
  popup and sandbox settings, and a new window or a webContents made by a
  library has none until someone remembers to add them.
- A preload or session-level filter only: it does not cover webview
  attach or popups, and a new session would start bare.

## Why

Default deny at web-contents-created means the next window or page
inherits the hardening; the registry keeps the companion's working
routes without a second rule set. Checking the exact frame and page URL
stops a foreign file page from reading the token. A debugging switch or
NODE_OPTIONS on a shortcut would expose the main process or the pages to
any local program; development keeps them with AL_DEV=1.

## Reverses if

A needed feature must navigate or open a window, the guards cost the
overlay budget (decision 0002), or Electron removes an API they rely on.

## Amendment 2026-11-19 (OVL-EGRESS-LOCK, plan unit F-111)

Both Electron sessions, the overlay's default session and the
companion's persist:client partition, cancel every request that is not
an app page (a file: URL under the app folder), the loopback core
(http://127.0.0.1 on the configured port, no user name or password),
blob: or data:, or, with AL_DEV=1 only, devtools:. Any other scheme,
host or port is cancelled, the trade site and poe.ninja included, so
"the trade site is never called by the app" and "nothing hits the
network while web data is off" are properties of the process, not of
each page's code. The rule is app/egress.js (pure: allow and the
onBeforeRequest filter); app/parts/15-egress.js puts it on both sessions
at ready, and on a window's own session at overlayWindow and
clientWindow, because those windows may start loading before ready
runs; a session is locked once. Each refused origin (scheme and host,
never a path or query) is logged once, at most 64 per start. Links that
leave go through shell.openExternal, which is not a session request,
and the main process's own Node http calls to the core are not session
requests either, so neither is affected. One callback per request, no
timer. The icon render page of scripts/brand_render.js (a data: page,
javascript already off) gets the CSP "default-src 'none'; style-src
'unsafe-inline'; img-src data:".

Ruled here: the window hooks lock as well as ready (alternative: ready
only, as the package text says; a window loading before ready would
then go unfiltered for its first requests). Loopback is 127.0.0.1 only,
never localhost (the core binds 127.0.0.1; a name could resolve
elsewhere). The opt-in live smoke check of an external image on the
overlay test page was not added: tests/test_overlay_smoke.py is outside
this package's files; the unit test covers the cancel path.

Reverses if: a page needs a request outside these origins (then it is
added to allow with its reason), Electron drops webRequest
onBeforeRequest, or the per-request callback costs the overlay budget
(decision 0002).
