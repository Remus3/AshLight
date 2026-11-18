# 0042 - Hot reload of data, web assets, overlay page and core code

Date: 2026-11-17 (drafted as 0041, renumbered to 0042 at merge because
0041 is the desktop client). Row HOT-RELOAD (operator request: make the app
hot-reloadable). Inputs: CLAUDE.md stack and overlay rules, decisions 0002
(stdlib core, overlay budgets), 0005 (keepalive supervisor), 0008 and 0023
(state rebuilt from Client.txt at start), 0010 (process registry), 0040
(Checks card).

## Decision

1. Data files (always on). `server/al/hotreload.py` holds one shared
   stat-only watcher: `Watched(path, loader, name, default, check)` re-reads
   a file only when its (mtime, size) moved, keeps the LAST GOOD value when
   the new bytes fail to parse (`check` / `loader` raise) and sets a
   one-line `error`. Every Watched joins `hotreload.REGISTRY` (a WeakSet);
   the core's 0.5 s loop runs `Core.tick_reload()`, which polls the
   registry (one stat per file) and shows any note on the Checks card as a
   "Live reload" fail row (`diag.check_reload`, present only while a note
   exists). Wired: tracked `server/al/data/zone_notes.json` (zonenotes),
   and the cached snapshots behind `acts.TableCache` (zone levels, now also
   re-published from `tick_sources`; it was read at start only),
   `campaign.FlaskCache` and `basetypes.NamesCache`, which became
   Watched subclasses with unchanged APIs. Public API for in-flight work
   (zone guide, per-character build): `hotreload.register(path, loader,
   name=..., default=dict, check=hotreload.check_json())` then `.get()`.
   config/local.json keeps its own mtime check (core._config). Not moved:
   treedata.TreeCache and tradestats.IndexCache already re-read on change
   (their own error handling, a two-file signature); they can adopt
   Watched later without an API change.
2. Web assets (source checkout only). `Core.tick_reload` scans `web/` with
   `hotreload.TreeWatch` (os.scandir stat, at most once a second, at most
   4000 files). A change bumps `core.reload_web`; every SSE stream sends
   `event: reload` `{"target": "web", "seq": n}` once per bump, and
   `web/app.js` answers with `location.reload()` (the token stays in
   sessionStorage). Static files already go out with `Cache-Control:
   no-store`.
3. Overlay page (source checkout only). `app/hotreload.js` polls the
   overlay page's own files (`app/overlay`, `app/shared`: .html / .js /
   .css, at most 200) with `fs.watchFile` in the Electron MAIN process
   (1 s, persistent false, 300 ms debounce) and calls
   `win.webContents.reload()`. The page itself gets no timer or listener,
   so the overlay render path and its FPS / RAM budgets are untouched.
   `main.js` / `preload.js` edits still need an overlay restart.
4. Core code (source checkout only). The keepalive supervisor polls at
   1 s instead of 5 s and stat-scans `server/**/*.py`. A change settles
   for 1.5 s (a burst of saves is one reload), then a preflight runs in a
   child process: `python -m server.al --check` imports the core and the
   HTTP server and compiles every server .py (no .pyc written). Pass: the
   supervisor writes `<runtime>/restart.request`; the core's loop exits
   cleanly, keeps its token file and writes `token.reuse`; the supervisor
   starts the new code at once (no backoff, not counted against the crash
   cap). The new core keeps the token (mark younger than 120 s, well-formed
   token), so the open dashboard's EventSource and the overlay reconnect on
   their own; state is rebuilt from Client.txt at start (0008, 0023).
   Fail: the running core stays, nothing is written to it, and
   `<runtime>/hotreload.json` carries the one-line error (repo-relative
   file:line, no absolute path), which the core shows on the Checks card;
   nothing is retried until the next edit. A new core that passed the
   preflight but dies before its first heartbeat blocks further starts
   until the next code change (never a crash loop); stop.request still
   wins. A core that ignores restart.request for 20 s is terminated
   (python image only, as before). Supervisor code (keepalive.py) itself
   is not reloaded; run.ps1 restarts it.
5. "Source checkout" = a `.git` entry at the repo root. Override with
   config/local.json `"hot_reload": true | false` or env `AL_HOT_RELOAD`
   (`1` / `0`; env first). The test suite pins `AL_HOT_RELOAD=0`
   (tests/conftest.py) so a real core or supervisor a test starts never
   restarts on an edit made during the suite.

## Alternatives

- OS change notifications (ReadDirectoryChangesW via ctypes, fs.watch):
  rejected; a stat poll on loops that already run is stdlib, bounded and
  identical on every file system (FAT / SMB mtime quirks included).
- Importlib reload of changed modules inside the running core: rejected;
  module-level state, threads and class identity make partial reloads
  wrong in subtle ways, while a full restart is cheap because all state is
  rebuilt from Client.txt and runtime files.
- A fresh token on the reload start: rejected; the open dashboard would
  sit at "reconnecting" until the player reopened it (not zero-click). The
  kept token never leaves the runtime dir and only lives across a restart
  the supervisor itself asked for.
- Hot reload on for every install: rejected for web / code (an edit in an
  installed copy is not expected and a restart drops in-flight work);
  kept on for data files (a snapshot rebuild or data edit is ordinary use).
- The overlay page listening for the SSE "reload" itself: rejected; the
  sandboxed page has no IPC and `will-navigate` is blocked, and keeping
  the poll in the main process keeps the page's render path unchanged.

## Why

The operator asked for a hot-reloadable app; every reload path here is
zero-click, bounded (stat calls on existing ticks), and fails safe: a bad
data file keeps the last good copy, broken code keeps the running core,
and a bad new core never loops.

## Reverses if

- The stat polls show up in the overlay budget test or the core's tick
  cost on the target machine.
- Token reuse across a supervisor-requested restart is ruled a weakening
  of the per-start token (then the dashboard needs a token re-read path).
- A reload restart loses state that Client.txt cannot rebuild (then code
  reload needs a hand-off file or stays manual).
