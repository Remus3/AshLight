# 0041 - Desktop client (DESKTOP-CLIENT): one Electron client owns the window, tray and overlay

Date: 2026-11-17. Operator asks: "an actual launchable desktop client for the
companion, not the dashboard opened as a URL in Chrome", then (same day,
via MAIN) "the overlay must only exist while the AshLight desktop client is
running". Taken by the building agent under CLAUDE.md FLEET item 1; the
overlay gate amendment to decision 0029 was adjudicated separately.

## Decision

1. The existing Electron app (`app/`, Electron 45.3.3 exact pin) is the
   desktop client. Started with `--client` it runs, in ONE process:
   - a normal framed "AshLight" companion window (`app/client/window.js`)
     with the standard Windows title bar (minimize, maximize / restore,
     X): resizable, focusable, in the taskbar, NOT always-on-top, minimum
     560x420, size / position / maximized saved to
     `ops/runtime/client-window.json` (gitignored) and reused only while a
     connected display still shows it;
   - a tray icon (`app/client/tray_menu.js`, operator order 2026-11-17):
     Minimize / Restore AshLight (toggle) / Show in-game overlay (checkbox,
     the same toggle as Alt+Shift+A, reflects the state) / Restart overlay
     / Quit AshLight. Left-click restores the companion;
   - the overlay window, unchanged (transparent, click-through,
     non-focusable, always-on-top; decision 0002 budgets).
2. The overlay exists only while the client runs. A start without
   `--client` exits at once; the only exception is the bounded opt-in
   overlay smoke (`AL_OVERLAY_SMOKE_S`), which measures the overlay alone.
   Because the overlay is a window of the client's own process, a tray
   Quit or a client crash takes it down too: nothing can linger.
   "Restart overlay" (tray, and a `restart-overlay` button in the
   dashboard's overlay position panel, shown only inside the client)
   destroys the overlay window and builds it again; the player's show /
   hide choice carries over and the gate re-seeds.
   `scripts/run.ps1` starts the client (`electron app --client`, detached,
   pid recorded for stop.ps1) instead of a bare overlay, and opens no
   browser when the client is installed (`-Browser` / `-EdgeApp` /
   `-NoOverlay` keep the browser path). `-NoBrowser` (and the logon
   autostart, decision 0011) starts the core and supervisor only, so no
   overlay at logon. The keepalive supervisor never starts Electron.
3. One launch path: the client checks `GET /api/health`; when the core
   does not answer it runs `scripts\run.ps1 -NoBrowser` hidden (which
   converges core + supervisor, decision 0010, and sees this process as the
   live "overlay" component, so it starts no second one), shows a local
   "Starting AshLight" page and loads the dashboard when the core answers
   (30 s, then a plain failure line). Single-instance lock: a second
   `--client` start (shortcut, run.ps1) only shows the running window.
   Started from a shortcut there is no `AL_SIDECAR_ROOT`, so the client
   asks `python -m server.al.paths` (the one resolver) first; its Electron
   profile, and with it the single-instance lock, is then the same one a
   run.ps1 start uses.
4. X closes the companion window to the tray: the window goes (its
   renderer is freed), the tray, overlay and core keep running, and the
   first X of a run shows a tray note ("AshLight keeps running here.
   Right-click this icon to quit."); the tray tooltip says the same.
   Chosen over "X quits" because the overlay is the in-game view and the
   core a background tracker: a player clearing desktop space should not
   lose the HUD mid-map. Tray "Quit AshLight" closes everything: it runs
   `scripts\stop.ps1` (core, supervisor, client and so its overlay).
5. The token never shows in a URL bar: the window has none, the dashboard
   URL carries it in the fragment (`/#token=`, never sent over the wire),
   and `web/app.js` moves it to sessionStorage and strips it at once (the
   same path the browser start used).
6. Navigation: the window may only show `http://127.0.0.1:<port>`.
   `will-navigate`, `will-redirect` and every popup go through
   `app/client/link.js routeFor`: an http(s) link with no credentials goes
   to the user's default browser via `shell.openExternal`; anything else
   (file:, javascript:, custom schemes) is refused. No popup ever opens a
   second window.
7. The window has its own session partition (`persist:client`), so the
   overlay's deny-all session is untouched. It grants exactly one
   permission, `clipboard-sanitized-write`, only to the core's origin (the
   dashboard's Copy buttons on the player's click, decision 0014). Its
   sandboxed preload (`app/client/preload.js`) hands the page ONE action,
   `alClient.restartOverlay()`, a fixed IPC message with no data that main
   honours only from the companion window's main frame on the core; no
   token, Node or fs. Downloads (.build file, loot
   filter, settings export) are saved to the user's Downloads folder under
   a sanitised base name, matching the dashboard's own words.
8. Launchable entry: `scripts/setup.ps1` writes a per-user `AshLight.lnk`
   to the Start Menu (Programs) and the desktop (no admin; `-NoShortcut`
   skips), target the pinned `app\node_modules\electron\dist\electron.exe`
   with `"<repo>\app" --client`. It is rewritten only when target,
   arguments, folder or icon differ (a re-run is a no-op). The icon is
   AshLight's own brand mark (no GGG art, logo or trademark): the tracked
   `app\assets\icon.ico` and the tray PNGs from `app/brand/index.js`
   (BRAND-ICON, docs/design/0005-brand-mark.md; at merge 2026-11-17 this
   replaced the first code-drawn `app/client/icon.js`).
9. No packaged .exe for now. `electron-builder` / `@electron/packager`
   would add a large exact-pinned devDependency tree whose build step
   downloads further binaries (NSIS, winCodeSign, rcedit) at build time, so
   an offline-safe `build.ps1` is not possible without vendoring them; the
   repo also has no release channel yet. The shortcut to the pinned
   Electron plus the repo's `app/` gives the same launch with nothing new
   to pin.

10. The local "Starting AshLight" page (`app/client/starting.css`) keeps
    its own small commented colour block: the core serves the kit's
    `/tokens.css`, and the page exists exactly while the core is not up
    (design review DESKTOP-CLIENT D4, token-block exception). The tray
    note on X fires once per run and only on the player's own close,
    never on a core event (D5).

## Alternatives

- Separate Electron app / process for the client, overlay kept as its own
  process: rejected. Two processes need an IPC or parent-pid watchdog so
  the overlay dies with the client; one process makes that structural.
- Window close = quit everything: rejected as the default; it would stop
  the overlay mid-map when the player only wanted the desktop space back.
  The tray gives both quits.
- Token by request header (session.webRequest) instead of the fragment:
  rejected; `web/app.js` needs the token itself for fetch and EventSource,
  and the fragment path is already reviewed (decision 0002 "API token").
- A preload that hands the token to the dashboard: rejected; a page
  served over HTTP gets one fixed action (restart overlay), nothing to read.
- X quits the client (and its overlay): rejected (point 4); the tray Quit
  is one right-click away and the tooltip and first-close note say so.
- electron-builder portable .exe: deferred (point 9).
- A .vbs launcher that runs run.ps1 then Electron: rejected; nothing shows
  for seconds while PowerShell and Python start. The client opens its
  window at once and starts the core behind it.

## Why

Zero-click: one shortcut opens the whole app; the core, supervisor and
overlay follow by themselves, and a second click only brings the window
forward. Nothing new is fetched or pinned, the ToS floor is untouched (no
game process contact; the client only runs the repo's own scripts and the
path resolver), and the overlay's process and RAM budget stays measured
alone (the companion window is a second renderer only while it is open).

## Reverses if

The overlay needs to run without the client (operator order withdrawn);
a release channel makes a packaged, signed .exe worth its build
dependencies; Electron drops the fragment-in-file-URL / sessionStorage
path the token rides on; or the companion window's renderer pushes the
client past the decision 0002 RAM budget in normal play (then close it
by default to the tray).

## Amendment 2026-11-19 (OVL-LINKS-DOWNLOADS, plan units F-112, F-110, F-099)

Links, downloads and the first-run place of the companion window.
- Decision: a link leaves the companion for the default browser only
  (a) on a navigation or popup while the companion window has focus,
  (b) as https on the default port with no user info, (c) to a host of
  the one tracked list `config/link_hosts.json` or a subdomain of one,
  and (d) at most 1 a second and 5 a minute (a pure limiter in
  `app/client/link.js`, `routeFor(url, port, isPopup, ctx)`; no ctx
  means no link). The browser gets the parsed, normalised href. The list
  holds exactly the hosts the dashboard can emit (web/tc.js link builders
  and tree hosts, the trade search URL of `server/al/trade.py`, any https
  host literal in web/), checked both ways by
  `app/test/link_hosts.test.js`; a missing or broken list refuses every
  link. A download is saved only from the core origin (its page or a
  blob: URL the page made) with a .build, .filter, .json or .txt name;
  anything else is cancelled (`item.cancel()`) and logged. The clipboard
  permission check compares the requesting origin with
  `Link.isCoreUrl`. With no usable saved place, two or more displays and
  a known overlay display (`opts.overlayBounds().displayId`, mapped to
  its work area through Electron's display list only), the companion is
  centred on the largest work area that is not the overlay's; with one
  display, or the overlay's display unknown, it is centred on the primary
  as before; a saved place on a connected display still wins.
- Alternatives: exact host match only - rejected: the tree link already
  accepts subdomains of its hosts (www.pathofexile2.com), so an exact
  list would emit links the window refuses; a per-feature host list in
  each web/ file - rejected: two places to drift; a confirm prompt before
  each link - rejected: the click is the player's own act (zero-click);
  the largest area even when the overlay's display is unknown - rejected:
  with no overlay place the safe default is today's primary.
- Why: a compromised or buggy dashboard page cannot use the companion
  to open arbitrary sites, spam the browser or drop executables into the
  Downloads folder; nothing new is read and nothing is sent to the game
  (the trade link stays a URL the player's browser opens, decision 0017).
- Reverses if: the dashboard needs a host the enumeration test cannot
  see, a subdomain of a listed host is shown to serve untrusted content,
  players hit the rate limit in normal use, or the overlay's display id
  stops matching Electron's display list.

## Amendment 2026-11-19 (OVL-WAKE-COMPANION, plan unit F-167)

- Decision: when the log goes from idle to a fresh line (the overlay
  gate of decision 0029 turns from false to true, seen by the part
  `app/parts/40-wake.js`), a companion that is closed to the tray or
  minimised comes back with `showInactive()`, never `focus()`, `show()`,
  `restore()` or `maximize()` (each of those activates the window on
  Windows), and only when `Link.wakeAction` finds its saved bounds
  (client-window.json) wholly on one display (Electron display bounds,
  with an 8 px allowance for Windows' invisible resize border) that is
  not the overlay's display (`opts.overlayBounds().displayId`). Same
  display, straddling bounds, no saved bounds, an unknown overlay
  display, a shown window or the switch off: it stays as it is. A closed
  window reopens at its saved normal size, not maximised, for that one
  open. The tray checkbox "Open AshLight when the game wakes" is the
  switch, default on, kept in client-prefs.json in the runtime dir (the
  client never writes config/local.json). An overlay-only start has no
  companion and does nothing.
- Alternatives: show on any display - rejected: the game's display must
  never get a window over it; move the window to another display before
  showing - rejected: it would override where the player put it; a
  watcher of the game process or its window - rejected: decision 0029
  allows Client.txt freshness only; restore a maximised window
  maximised - rejected: maximize() activates the window and so steals
  focus from the game; a config/local.json key - rejected: the client
  never writes the player's config.
- Why: the player alt-tabs back to a game that just woke and finds
  AshLight already on the second screen, with no click and no focus
  change in the game; nothing is read beyond the log freshness the
  overlay already uses and nothing is sent to the game.
- Reverses if: showInactive() is seen taking focus from the game in
  play, players find the window coming back unwanted with the switch on
  by default, the 8 px allowance lets a window show on the game's
  display, or decision 0029 changes its idle signal.
