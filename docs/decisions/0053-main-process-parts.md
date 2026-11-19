# 0053 - Main-process parts seam (app/parts/)

Date: 2026-11-18. Source: package OVL-MAIN-PARTS (wave 4); finding F-026
(docs/plan/02-findings.md); decisions 0002, 0003, 0041.

## Decision

1. Seam. Electron main-process features live as `app/parts/NN-name.js`
   files. `app/parts.js` (pure: no Electron, readdirSync and require are
   passed in) loads the `*.js` files of `app/parts/` sorted by file name
   (`load`), and `run(parts, hook, ctx, ...args)` calls each part's hook
   in that order inside try / catch: a throwing part is logged through
   `ctx.log` and skipped, the others still run. A part that fails to load
   is logged and left out; a missing directory is no parts.
2. Hooks (`Parts.HOOKS`), each run once from one place in app/main.js:
   `early` (before the mode branch that ends in `app.whenReady()`),
   `ready` (in start(), after the item-check handler is built and before
   the `overlay started` log line, which server/al/diag.py reads),
   `overlayWindow(win)` (end of createWindow), `clientWindow(win, ses)`
   (from the companion window's new `opts.onWindow`), `configChanged`
   (the existing config/local.json watch), `gate(visible)`
   (setOverlayGate), `toggled` (toggle) and `quit` (will-quit).
3. ctx, built once in main.js: app, log, repo, runtimeDir, port,
   readToken, readConfig, env, clientMode, devTools, defaults {toggle,
   eval}, keys {toggle, eval}, getOverlay, getClient, getGate,
   overlayBounds, actions {toggle, restartOverlay, openClient, onEval}.
4. main.js keeps the two windows' creation, the IPC handlers and the one
   clipboard read (the floor scan's ALLOW anchor
   `EvalKey.createEvalHotkey({` is unchanged). A part never creates a
   BrowserWindow, reads the clipboard, starts a timer loop or a process
   (app/test/parts.test.js, tests/test_overlay_smoke.py P4-6).
5. First part: `app/parts/20-hotkeys.js` registers the two global
   shortcuts at `ready` with the same two log sentences ("toggle shortcut
   not available: ", "item check shortcut not available: "). Behaviour is
   unchanged: the same keys, the same order, the same start line.
6. app/client/window.js: `createClient` takes `opts.onWindow(win, ses)`,
   called once per created companion window before its first load, and
   `opts.overlayBounds`; the returned object gains `window()` and `tray()`
   getters.

## Choices the package text left open (ruled)

- Hotkey pick stays in main.js for now (adjudicator ruling, this
  package). The notes moved the `Hotkey.pick` constants into the part, but
  app/test/hotkey.test.js (outside this package's files, owned by
  OVL-KEYS-CLIENT) pins `const toggleKey = Hotkey.pick(` in main.js and
  the accept line needs it green. main.js picks once and passes
  `ctx.keys`; the part only registers. Alternatives: stop as failed;
  edit the test outside the files. Reverses if: OVL-KEYS-CLIENT moves the
  pick into the part with its configChanged re-pick and rewrites the test.
- `globalShortcut.unregisterAll()` stays in will-quit in main.js, after
  the `quit` hook, so the keys are released even if the part fails.
- Hooks get ctx first, then the hook's own arguments.

## Alternatives

- Keep editing app/main.js for every client feature: every later cluster
  (F-027, F-032, F-070, F-073, F-090, F-091, F-129, F-137, TD-04,
  OPEN-10) would collide in one hot file.
- An explicit list file naming the parts: one more file every feature
  edits, the collision moves there.

## Why

File-name order gives a stable, visible load order with no shared list to
edit; one ctx keeps parts off main.js internals; try / catch per part
keeps one broken feature from taking the overlay down.

## Reverses if

A part needs an order that file names cannot give, a packaged build cannot
list the directory, or the floor scan stops covering app/parts.
