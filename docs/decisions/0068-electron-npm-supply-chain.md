# 0068 - Electron and npm supply chain

Date: 2026-11-19. Source: packages OVL-NPM-LOCK (wave 12, merged in wave
13) and OVL-ELECTRON-SETUP (wave 13), on OVL-ELECTRON-PIN; findings F-037
and F-044 (docs/plan/02-findings.md); research 0046 F2, F3, R1 and R4.
Builds on: decisions 0002 (stack), 0010 (one process registry), 0041
(desktop client), 0063 (installed-copy runtimes; this record covers the
checkout's developer path).

## Decision

1. npm runs only as `npm ci --ignore-scripts --no-audit` from the tracked
   app/package-lock.json (OVL-NPM-LOCK). A missing lockfile refuses; there
   is no `npm install` branch. The tracked app/.npmrc sets
   `ignore-scripts=true`, `engine-strict=true`, `save-exact=true` and a
   `user-agent` naming AshLight and its version (the line is a release
   stamp, moved by `release.py bump`), so npm's own requests name
   AshLight. electron sits under `dependencies` with its exact pin; the
   lockfile carries no install script. A lane's dependency bump passes
   `--ignore-scripts`, runs `npm audit signatures`, and lets a version
   published under 3 days ago wait.
2. The Electron binary arrives only through tools/electron_pin.py
   (OVL-ELECTRON-PIN): the zip URL, size and SHA-256 come from the tracked
   config/electron_pin.json, the request names AshLight, every redirect
   hop is host-checked, and a wrong zip is moved aside and refused before
   anything is unpacked. scripts/setup.ps1 never runs electron's own
   installer script (install.js); after `npm ci` it runs
   `python tools/electron_pin.py setup --app-dir app` (fetch, or reuse the
   cached verified zip; unpack; check electron.exe), then `verify-exe`.
   Exit 2 throws "REFUSED ... run setup again"; exit 1 throws "failed ...
   run setup again".
3. Override variables are cleared before npm. setup.ps1's
   Clear-AlElectronOverrides removes, from its own process only (never the
   player's stored environment): the remote-checksum pair
   (`electron_use_remote_checksums`, `ELECTRON_USE_REMOTE_CHECKSUMS`) and
   its `npm_config_` twin, the mirror family (`ELECTRON_MIRROR`,
   `ELECTRON_NIGHTLY_MIRROR`, `ELECTRON_CUSTOM_DIR`, `_FILENAME`,
   `_VERSION`, each with its lower-case and `npm_config_` spelling),
   `ELECTRON_OVERRIDE_DIST_PATH`, `ELECTRON_INSTALL_PLATFORM` / `_ARCH`,
   `npm_config_platform` / `npm_config_arch`, `electron_config_cache` and
   `force_no_cache` (with their `npm_config_` twins). setup.ps1 no longer
   sets `electron_config_cache` (nothing reads it once install.js is gone).
   AshLight's fetch reads none of these names (a test keeps it so), so
   with `electron_use_remote_checksums=1` in the environment the pin still
   decides.
4. electron.exe is verified against the pin at setup and at run.
   - setup.ps1, after the install, and on the up-to-date fast path before
     the "no-op" line. A fast-path exe that is not the pinned one is never
     kept: setup falls through to the full install (npm ci wipes
     node_modules, the exe is unpacked again from the verified cached zip),
     so a repair needs no click.
   - run.ps1, before the one `Start-AlDetached -FilePath $electron`:
     Test-AlElectronExe runs `tools/electron_pin.py verify-exe --exe
     <path>`. A refusal starts no client; the dashboard opens in the
     browser instead (as when the client is not installed) and run.log
     says "run scripts\setup.ps1 again to restore it".
   - Both count verify-exe as good only with exit 0 AND its `electron.exe
     ok` line: exit 0 with "no client" (no pin for this machine's
     architecture) is not a verified exe, so it is refused too.
   - The full SHA-256 runs only when the exe's size or mtime changed since
     the last good check (sidecar Build\electron-exe-check.json, shared by
     setup and run), so a normal start costs a stat.

## Choices the package text left open (ruled)

- The notes say "python tools/electron_pin.py fetch"; fetch only fills the
  cache, so setup.ps1 calls the tool's `setup` command, which is fetch plus
  the guarded unpack plus the exe check. Same request, same pin.
- A changed exe at the setup fast path: re-install from the verified zip
  (zero-click) rather than stop setup and ask the player to delete
  node_modules. Setup still refuses (throws) if the fresh unpack does not
  match.
- A changed exe at run: no client and a browser fallback, exit 0, rather
  than exit 1 with nothing shown. The player keeps a dashboard and the log
  names the fix.
- Override variables are cleared right before npm (the earliest point
  that matters), not at the top of setup; tc_pin and the Python checks
  before it read none of them.

## Alternatives

- Keep electron's install.js and rely on its packaged checksums.json,
  with the overrides cleared: rejected. Its requests do not name AshLight
  (the User-Agent floor rule, strict reading), it still honours variables
  a future version may add, and nothing checks the exe after install.
- Vendor the Electron zip (or the unpacked dist) in the repository or a
  release: rejected. It is about 150 MB per architecture, breaks the
  go-public blob gate (decision 0079), and decision 0063 keeps AshLight
  artefacts free of third-party runtimes.
- `npm install` with scripts on and a lockfile when present: rejected
  (F-037): a missing lockfile resolved fresh versions and any package
  script ran with the player's rights.
- Verify the exe only at setup: rejected; a run-time swap of electron.exe
  (the shortcut starts whatever sits at that path) would go unseen.
- Hash the exe in full on every run: rejected; about 250 MB read on each
  start, where size and mtime catch any ordinary change.

## Why

Research 0046 F2: the Electron chain was strong but had an environment
hole (the remote-checksum switch and mirror / dist variables could replace
both the binary and the checksum it was checked against, silently) and no
check at the end (nothing compared the installed exe with a tracked
value). F3: npm ran with lifecycle scripts allowed. This closes both ends:
one fetch route under AshLight's own User-Agent and pin, overrides gone
before npm, and an exe check at every setup and every client start, all
with no prompt; each failure line names its fix (run setup again).

## Reverses if

- The operator rules the User-Agent bullet binds only AshLight's own
  requests (ruling A-02): the app/.npmrc user-agent line may then go.
- Electron stops publishing hash-verifiable release zips on GitHub.
- A packager needs electron as a dev entry (devDependencies).
- A signed release channel replaces the pin (then the signature is the
  check).
