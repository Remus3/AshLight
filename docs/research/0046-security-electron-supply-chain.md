# 0046 - Electron hardening and supply chain

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B9
hardening: Electron and supply chain. Scope: every Electron window and
session in `app/`, the 45.x line and an upgrade policy, the npm tree, the
hash pins of the optional calc component, the Python and Node floors,
and provenance for an unsigned, no-revenue release. The local HTTP
surface is research 0045; packaging choices are 0053.
Status: draft

## Sources (all accessed 2026-11-17)

- S1: https://releases.electronjs.org/releases.json
- S2: https://releases.electronjs.org/schedule.json (future dates tentative)
- S3: https://api.github.com/repos/electron/electron/releases?per_page=60
- S4: https://www.electronjs.org/docs/latest/tutorial/electron-timelines
- S5: https://www.electronjs.org/docs/latest/tutorial/security
- S6: https://www.electronjs.org/docs/latest/tutorial/fuses
- S7: https://www.electronjs.org/docs/latest/tutorial/asar-integrity
- S8: https://www.electronjs.org/docs/latest/api/session and
  https://www.electronjs.org/docs/latest/api/web-contents
- S9: https://registry.npmjs.org/-/package/electron/dist-tags and
  https://registry.npmjs.org/electron/45-x-y
- S10: https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions/all/releases
  and the same path with `extended` (Chrome channel versions)
- S11: https://raw.githubusercontent.com/libuv/libuv/v1.x/src/win/process.c
- S12: https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference
- S13: https://docs.github.com/en/code-security/dependabot/dependabot-auto-triage-rules/about-dependabot-auto-triage-rules
- S14: https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives
- S15: https://docs.github.com/en/actions/concepts/security/artifact-attestations
  and https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds
- S16: https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases
- S17: https://devguide.python.org/versions/
- S18: https://www.python.org/downloads/windows/
- S19: https://endoflife.date/api/nodejs.json
- S20: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- S21: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- S22: https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview
- S23: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
- S24: https://signpath.org/terms
- S25: https://osv.dev/vulnerability/GHSA-4x49-vf9v-38px

Local, read-only, 2026-11-17 (Node 24.15.0, npm 11.12.1, Python 3.14.4):
- L1: `npm audit --json` in `app/`: 0 vulnerabilities, 13 packages.
- L2: `npm audit signatures`: 13 registry signatures and 6 provenance
  attestations verified.
- L3: scratch copy of manifest and lockfile: `npm ci --ignore-scripts`
  adds 13 packages in 0.6 s, exit 0; an `.npmrc` with that setting works
  with `--prefix app`; `npm test` still runs.
- L4: the cached electron-v45.3.3-win32-x64.zip (158,325,836 bytes)
  hashes to the electron package's checksums.json entry.
- L5: installed electron.exe: 250,093,056 bytes, SHA-256
  cf7ff337d82f32a437d315721ef361f53a8473905a655a0c650967a66ccd0724, no
  Authenticode signature (empty PE security directory), no zone mark.
- L6: `npm sbom --sbom-format cyclonedx --package-lock-only`: 13
  components with hashes, no network.
- L7: pinned PoB checkout: 1,897 files, 430.2 MB; runnable Lua (src,
  runtime/lua) 1,073 files, 37.5 MB, hashed in 0.07 s; runtime holds 26
  DLLs (16 unsigned) and 2 unsigned EXEs.

## Summary

No critical or high finding: of the 20 Electron checklist items [S5] the
shell meets 13, 2 do not apply (no webview), 2 are partial (15, 17) and 3
are open (16 staying current, 18 file:// pages, 19 fuses). The pin 45.3.3
(2026-11-14) is on the newest stable major, one non-security patch behind
45.3.4 (2026-11-17); the line ends 2027-04-27 and 46.0.0 is due
2027-01-05, both tentative. The real risk is lag: 11 releases in 27 days
and nothing watches them (F1, R1). The Electron binary is hash-chained
from the lockfile (re-verified here), but environment overrides can cut
the chain and the unsigned exe is never checked (F2, R4). npm: 13
packages, 0 advisories; install scripts are allowed though none is
needed, and the Node floor (20) is below the installer's 22.12 (F3, F4,
R2, R3). Calc pins are strict at fetch, trusting at use (F11, F12, R7).
No AshLight binary exists, so SmartScreen has nothing to flag; free
provenance is ready for the day of publishing (F15, R10).

## Current state

Windows and sessions: 3 windows, 2 sessions; no webview, view, worker or
utility process (tests/test_overlay_smoke.py:88-97); webSecurity and the
insecure-content, experimental and Blink flags are never set (defaults).
- Overlay (app/main.js:217-241): preload, contextIsolation true,
  nodeIntegration false, sandbox true, devTools only with AL_DEV=1
  (main.js:32, :239); default session; a file page (main.js:260); every
  navigation prevented (:245), every popup denied (:246).
- Companion (app/client/window.js:151-170): the same flags, its own
  partition `persist:client` (window.js:29, :162); the loopback core or
  the local starting page (window.js:122, :197); navigation, redirects
  and popups routed by link.js routeFor (window.js:172-177).
- Icon render window, build time only (scripts/brand_render.js:35-39):
  offscreen, JavaScript off, sandbox on, a data: page of tracked SVGs.
- Permissions: the default session denies every request and check
  (main.js:334-336); the client partition grants only
  clipboard-sanitized-write to the core's origin (window.js:36, :61-66)
  and saves downloads under a sanitised name (window.js:69-80).

Preload and IPC: 3 channels, no ipcMain.handle.
- The overlay page gets a frozen {token, port, credit, reportGate(bool)}
  (app/preload.js:16-21); the companion page one function,
  restartOverlay() (app/client/preload.js:8-10).
- `al:config` (sync) answers a sender frame whose file URL ends in
  /overlay/index.html (main.js:338-343); `al:gate` only the overlay's
  webContents, forced to a boolean (:344-347); `al:restart-overlay` only
  the companion's main frame on the core (:350-352; window.js:243-247).

Page policy, links, switches:
- Overlay CSP (meta): nothing by default, own scripts and styles,
  connections to http://127.0.0.1 on any port (app/overlay/index.html:5);
  the starting page allows no connection (app/client/starting.html:5).
- Only http(s) URLs with a host and no credentials reach
  shell.openExternal (app/client/link.js:43-47; window.js:106-115).
- main.js:110-126: hardware acceleration off, `in-process-gpu`,
  `enable-features=NetworkServiceInProcess2`. Single-instance lock; a
  second start acts only on `--client` (:139-146). No protocol handler,
  auto-updater or crash upload. Stock binary: 9 fuses at defaults [S6].

npm (app/package.json:12-14; app/package-lock.json): one direct
dependency, electron 45.3.3 exact, under devDependencies; 13 packages
(12 transitive, 1 optional), each with a sha512 and a registry.npmjs.org
URL, none flagged hasInstallScript. Electron 45's package has no
postinstall: its install.js, called explicitly
(scripts/setup.ps1:238-242), fetches the binary and checks it against a
checksums.json inside the package. setup runs `npm ci --no-audit` (:232)
or, with no lockfile, an unpinned `npm install` (:233-235).

Calc pins (config/tc_pins.json; decisions 0018, 0027). Fetch: host
allow-list per hop, size cap, SHA-256 while streaming, quarantine on
mismatch (tools/tc_pin.py:258-286, :299-334); a cached archive is fully
re-hashed (:304-310). Extract: path guard, no symlinks, temp dir then
rename, a marker with the archive hash and a tree digest (:339-351,
:384-410). Use: the toolchain tree is re-hashed before each build
(:458-476); luajit.exe is hashed after the build and before every exec
(server/al/exepin.py:86-97; server/al/theorycraft/bridge.py:90, :155);
one PoB data file is hash-checked at each read
(server/al/tradestats.py:169-185).

Floors and release state: Python >= 3.11 (setup.ps1:75-76), Node >= 20
(setup.ps1:141-144; README.md:63-64; scripts/run.ps1:203). No remote
(.githooks/pre-push:22-24), no `.github` directory, no CI; lanes may run
npm but not gh (tools/al_lane.py:54-58).

## Findings

F1 (medium). Version lag is the one recurring Electron risk and nothing
tracks it.
- 45.3.4 holds one fix (a leak of right-clicked elements) on the same
  Chromium 156.0.8078.100 and Node 24.22.3 as the pin: nothing
  security-relevant is missing today [S1, S3].
- 11 stable releases in 27 days; 9 of the 10 after 45.0.0 moved Chromium
  or Node, backported upstream fixes or distrusted a certificate
  authority [S3]. Chromium 156 is Chrome's Extended Stable milestone,
  whose .108 build began rolling out on 2026-11-17; Chrome Stable is 158
  [S10].
- The latest three majors are supported [S4]: 45 until 2027-04-27, 44
  until 2027-03-02, 43 until 2027-01-05; 46.0.0 is planned for
  2027-01-05 and 47.0.0 for 2027-03-02, all tentative [S2]. No stable
  major newer than 45 exists.
- Only PoB releases are watched (tools/tc_drift.py:1-10); the lane bump
  prompt has no waiting period (tools/loop_inbox.py:128-129). A bump is
  also unsafe to apply (reasoned, not run here): setup.ps1:228-245 runs
  npm ci without checking that the client is stopped, and npm ci starts
  by deleting node_modules while electron.exe is in use.
- Why: the player runs a browser engine beside the game for hours; an
  engine months behind is how Electron apps become exploitable.

F2 (medium). The Electron binary chain is strong, with an environment
hole and no check at the end.
- Verified: lockfile sha512 (package-lock.json:77) -> npm package -> its
  checksums.json -> zip SHA-256; the cached zip matches [L4].
- The package's install.js takes overrides from the caller's
  environment, which setup.ps1:240 passes through: a remote-checksum
  switch (and its `npm_config_` twin) skips the packaged checksums, and
  the mirror variables move the download host. Set together they replace
  both the binary and the checksum it is checked against, silently.
- Nothing compares the installed exe with a tracked value; the shortcut
  starts whatever sits at that path (setup.ps1:198-204); the exe has no
  Authenticode signature [L5], so Windows shows no publisher either.

F3 (medium). npm installs run with lifecycle scripts allowed and no
waiting period.
- setup.ps1:232, :235; lanes: tools/al_lane.py:56-58,
  tools/loop_inbox.py:128-129. No package has an install script today
  and `npm ci --ignore-scripts` gives the same tree [L3]. With no
  lockfile, setup.ps1:233-235 installs unpinned versions, not a refusal.
- The lockfile holds debug 4.4.3 (package-lock.json:56-59), the clean
  release after 4.4.2 carried malware for some hours on 2025-09-08
  [S25]: a bump on that day with scripts allowed is the scenario.
- 6 of 13 packages carry a provenance attestation; electron itself has
  only a registry signature [L2, S9].
- electron sits under devDependencies although it is the runtime:
  `npm audit --omit=dev` is empty (docs/audit/2026-11-17-audit.md:161-164)
  and GitHub's default preset for public repositories auto-dismisses
  some low-impact alerts on npm development dependencies [S13].

F4 (medium). The Node floor is wrong. setup.ps1:141-144 accepts 20.0 and
README.md:63-64 and run.ps1:203 say 20, but the pinned electron package
and its two installer packages declare >= 22.12.0
(package-lock.json:21-23, :39-41, :89-91): install.js loads ESM-only
packages with require. Node 20 reached end of life on 2026-04-30; 22
ends 2027-04-30, 24 on 2028-04-30 [S19]. A user on Node 20 passes the
check and then runs a download step outside its supported range (the
failure itself was not reproduced: no Node 20 on this machine).

F5 (low). The client launcher runs bare program names with the repo as
working directory (app/client/launcher.js:13, :28, :49, :63). For a bare
name libuv looks in the child's working directory before PATH [S11], and
app/test/client.test.js:136 pins the bare name. The Python side closed
this class as audit S5 (server/al/exepin.py:1-14), with a Python-only
test. A writer to the repo already owns the app: the gap is the rule.

F6 (low). Two sender checks are looser than they read.
- `al:config`, the one channel that returns the token, accepts any file
  URL ending in /overlay/index.html and never checks that the sender is
  the overlay window (main.js:339-342). Unreachable today.
- The client partition's permission check compares `requestingOrigin`
  with a string that has no trailing slash (window.js:65-66); Electron's
  own example parses that value as a URL [S8]. Whether it ever matches
  is UNVERIFIED; if not, it fails closed (Copy still passes through the
  request handler, window.js:61-64).
- Both handlers, the download hook and isCompanion are tested only by
  source-text matches (app/test/client.test.js:173-185).

F7 (low). The guards are per window by convention, not structural. There
is no `app.enableSandbox()`, no `web-contents-created` default deny and
no will-attach-webview or will-frame-navigate handler: subframe
navigation rests on the page CSP alone [S8]. WebGL stays on although GPU
code runs in the main process (main.js:120). The static guard
(tests/test_overlay_smoke.py:88-92) bans 12 patterns but not a false
webSecurity, contextIsolation or sandbox, a true nodeIntegration,
allowRunningInsecureContent, enableBlinkFeatures, or the switches
no-sandbox, disable-web-security, ignore-certificate-errors and
remote-debugging-port. The next window added inherits nothing.

F8 (low). Debug entry points are open while unpackaged, and the client
inherits the caller's whole environment.
- Fuses are bits in the binary, set at package time before signing
  [S6]. The app runs the stock binary, so ELECTRON_RUN_AS_NODE,
  NODE_OPTIONS, the inspect switches and remote-debugging-port are all
  honoured.
- scripts/al_detach.ps1:23-26 copies every variable of the caller into
  the client (run.ps1:205-207). The tests scrub ELECTRON_RUN_AS_NODE
  (tests/test_overlay_smoke.py:184; tools/make_icons.py:185); run.ps1
  does not, so a start from another Electron-based tool's terminal can
  come up as plain Node and exit at once.
- Once packaged (for 0053): runAsNode, nodeOptions and nodeCliInspect
  off; onlyLoadAppFromAsar and embeddedAsarIntegrityValidation on
  (Windows since Electron 30 [S7]); grantFileProtocolExtraPrivileges off
  after R11; the other three fuses stay at their defaults.

F9 (low). External links and downloads are wider than the dashboard
needs. window.js:111 passes the raw string, not the parsed URL; any
http(s) host is allowed, with no rate limit and no focus condition, so a
page-initiated navigation can raise the browser over the game.
window.js:69-80 saves any download from any URL, with any extension.

F10 (low, accepted). Two process boundaries are traded away:
main.js:120 and :126 run GPU and network code in the main process
(decision 0002: 245 -> 180 MB). That is sound only while both windows
load nothing but local content, and no egress filter enforces it.

F11 (medium). The calc component is verified at fetch and trusted at
use.
- The marker's tree digest (tc_pin.py:405-408) is never compared again
  for PoB or LuaJIT. run_setup skips on a marker match (:571-574) and
  then builds LuaJIT from the source tree as found (:508-509); only the
  toolchain is re-hashed (:467-468). The three markers on this machine
  predate the digest: none carries tree_sha256.
- The bridge checks luajit.exe (bridge.py:90, :155) and the presence of
  one PoB file (:93). bridge.py:143 puts PoB's runtime folder (26 DLLs,
  16 unsigned [L7]) on LUA_CPATH and
  server/al/theorycraft/bridge.lua:218 tries a native require first. By
  static inspection the load fails today only because lua-utf8.dll
  imports lua51.dll, which a static luajit.exe lacks; a lua51.dll on
  PATH would let it load. So "one hashed exe covers everything that
  runs" (tc_pin.py:421-423) is not enforced.
- Closing it is cheap: the Lua that can run hashes in 0.07 s [L7].

F12 (medium). Two pins hash bytes GitHub does not promise, and two
upstreams have no watcher. GitHub guarantees the file contents of a
commit archive, not the compressed bytes, with six months' notice before
a compression change [S14]; config/tc_pins.json:10 and :32 pin the zip
bytes. A change makes `setup.ps1 -TcCalc` refuse for every new user
(fail closed, tc_pin.py:328-331). Decision 0018's own "Reverses if"
names this case; the toolchain pin is a release asset and unaffected.
LuaJIT (rolling, no releases) and the toolchain have no watcher; only
PoB has one (decision 0025).

F13 (medium). The Python floor is supported on paper, not on Windows.
3.11 gets source-only security fixes until 2027-10 and 3.12 until
2028-10; 3.13 entered security status in 2026-10; 3.14 and 3.15 are in
bugfix status [S17]. Last Windows installers: 3.11.9 (2024-04-02),
3.12.10 (2025-04-08), 3.13.17 (2026-10-21) [S18]: a Windows user on 3.11
runs a build 31 months old. Exposed stdlib parts: http.server on
loopback, json, urllib and ssl with web data on, zipfile in the calc
setup. pytest is installed unpinned by hand (README.md:62-63); the dev
machine runs Python 3.14.4 while 3.14.10 is current [S18].

F14 (medium at publish). Nothing is wired for the day the remote exists:
no CI, no Dependabot config, no gh for lanes (tools/al_lane.py:54-58).
The kit's identity guard fails every bot-authored pull request by design
(ops/fleet_kit/fleet_identity_guard.yml:11-13), so Dependabot pull
requests can only be re-applied locally (FLEET item 17).

F15 (medium at publish). What "unsigned" means here.
- No AshLight-built binary exists (decision 0041 point 9). SmartScreen
  judges downloaded files [S20]; electron.exe is fetched by Node and has
  no zone mark [L5], so no prompt is expected on the clone-and-setup
  path. Scripts run because README.md:67-72 passes the Bypass execution
  policy; the default on Windows clients is Restricted [S23].
- Smart App Control on Windows 11 blocks unknown unsigned code whether
  or not it was downloaded [S20, S22]. The locally built luajit.exe has
  a unique hash and no signature, and an Electron build a few hours old
  has little reputation. UNVERIFIED: no such machine was available.
- A packaged unsigned exe would show the "unrecognized app" warning for
  every new version: without a signature, reputation is per file hash
  [S20]. Costs: Azure Artifact Signing about USD 9.99 a month
  (individuals only in the USA and Canada), OV USD 150-300 a year, EV
  USD 400 or more with no SmartScreen gain since 2024, Store MSIX free,
  SignPath Foundation free for qualifying open source with manual
  approval of every release [S21, S24].

## Recommendations

R1. ELECTRON-WATCH and a written upgrade policy.
- Action: a daily loop-tick read of two small public JSON files (npm
  dist-tags, 3.4 KB; release schedule, 9 KB) [S9, S2] and a decision:
  (a) Line: the newest stable major. (b) Patch and minor: weekly,
  to the newest release at least 3 days old; within 24 h when
  `npm audit` reports an advisory on a pinned package. (c) Major: adopt
  N+1 between 14 and 42 days after its .0.0 (46: 2027-01-19 to
  2027-02-16), one major at a time [S5]. (d) Never past end of life: a
  Checks note and a ROADMAP row from 30 days before. (e) Gates per bump:
  R2's npm checks, R4's hash record, `npm test`, the static guards, and
  the live overlay smoke only in the decision 0029 idle state; a major
  also re-measures the decision 0002 budgets. (f) Apply: lanes bump in
  their own worktree, which warms the sidecar caches; the main checkout
  re-installs offline at the next run.ps1 while the client is not live;
  setup.ps1 refuses the npm step while the client runs.
- Impact H (the only exposure that grows by itself); Effort M. Risk: a
  bad upstream release (waiting period, gates); a feature switch renamed
  at a major (the smoke test's process count catches it).
- ToS check: touches "public web data" and the truthful User-Agent rule:
  two documented public npm / Electron endpoints, no GGG or trade
  endpoint, sent by the dev loop with the AshLight User-Agent, never by
  the shipped app (decision 0013 untouched). The smoke waits for
  log-staleness idle, never a process check, and sends no input.
- Depends on: R2, R4. Files: tools/al_loop.py, a new watcher tool,
  scripts/setup.ps1, scripts/run.ps1, a new decision, tests.
- Acceptance test: a fixture whose line head is 4 days old yields one
  bump item, at 2 days none; a schedule fixture inside the 30-day window
  yields the note; setup with a live client exits before npm runs.
- ZERO-CLICK: unattended for the operator; other users get one Checks
  note naming setup.ps1 (a silent fetch at start would break the
  network-off-by-default rule).

R2. Lock npm down.
- Action: a tracked `app/.npmrc` (ignore-scripts, engine-strict and
  save-exact on); setup.ps1 uses `npm ci --ignore-scripts` and refuses
  without a lockfile; the lane bump prompt gains `--ignore-scripts` and
  the 3-day rule; electron moves to `dependencies`; the bump gate adds
  `npm audit signatures`.
- Impact M; Effort S. Risk: a later package that needs its install
  script (none today); a packager (0053) wants electron as a dev entry.
- ToS check: no floor rule touched; setup-time installs only.
- Depends on: none. Files: app/.npmrc, app/package.json,
  app/package-lock.json, scripts/setup.ps1, tools/loop_inbox.py, tests.
- Acceptance test: asserts the .npmrc keys, no npm call in setup.ps1
  without --ignore-scripts, no lockfile-less branch, no hasInstallScript
  in the lockfile, and `npm audit --omit=dev` covering 13 packages.
- ZERO-CLICK: no change for the user.

R3. Runtime floors: fix Node now, set a Python policy.
- Action: raise the Node floor to 22.12.0 (setup.ps1:141, README.md:63,
  run.ps1:203) and test it against the electron `engines` value in the
  lockfile. Keep Python at 3.11 until its end of life in 2027-10, then
  follow the oldest branch in security status; setup prints one advisory
  line, never a refusal, when the interpreter's branch gets no Windows
  installers (below 3.14 today). Add a `requirements-dev.txt` with
  pytest pinned by hash; CI runs the floor and the newest branch.
- Impact M (a broken first install; unpatched interpreters); Effort S.
  Risk: the advisory line must not read as an error.
- ToS check: no floor rule touched (setup messages and dev tooling).
- Depends on: none. Files: scripts/setup.ps1, scripts/run.ps1,
  README.md, requirements-dev.txt, tests.
- Acceptance test: the test fails when a bump raises `engines` above the
  constant; setup under Node 20 names the floor and skips the overlay;
  under Python 3.11 it prints the line and exits 0.
- ZERO-CLICK: nothing to click; each message names its fix.

R4. Close the Electron chain at both ends.
- Action: setup.ps1 clears the install override variables (the
  remote-checksum pair, the mirror family, ELECTRON_OVERRIDE_DIST_PATH,
  force_no_cache) before npm and install.js run; a tracked
  `config/electron_pin.json` holds the version, the zip SHA-256 and the
  electron.exe SHA-256 and size per architecture; setup verifies the exe
  after install; run.ps1 re-verifies only when its size or mtime changed.
- Impact M; Effort S. Risk: arm64 needs its own entry (ship both, or
  warn and continue on an unknown architecture).
- ToS check: no floor rule touched; it hashes AshLight's own runtime
  file, never a game file.
- Depends on: none (R1 rewrites the file on each bump). Files:
  scripts/setup.ps1, scripts/run.ps1, config/electron_pin.json, a test.
- Acceptance test: with `electron_use_remote_checksums=1` set, setup
  still verifies against the packaged checksums; a one-byte change in a
  copy of the exe fails the check; the pin version equals package.json.
- ZERO-CLICK: runs inside setup and run.

R5. One hardening pass over the shell: guards, senders, launcher.
- Action: (a) new `app/guards.js`, called before any window:
  `app.enableSandbox()`; a `web-contents-created` default that denies
  navigation, popups and webview attach unless the creator registered a
  policy; `webgl: false`; quit when an inspect switch,
  remote-debugging-port or NODE_OPTIONS is present without AL_DEV=1.
  (b) run.ps1 drops ELECTRON_RUN_AS_NODE and NODE_OPTIONS from the
  client's environment. (c) `al:config` answers only the overlay's main
  frame at the exact page URL; the client check handler uses
  Link.isCoreUrl; `al:restart-overlay` at most once per 2 s. (d) The
  launcher resolves powershell.exe under
  %SystemRoot%\System32\WindowsPowerShell\v1.0 and Python from absolute
  PATH entries. (e) The static ban list gains the F7 names and bare
  spawn names in `app/`.
- Impact M (the next window inherits the rules); Effort M. Risk: the
  companion's same-origin reload must stay allowed.
- ToS check: touches the overlay rule (separate click-through window, no
  FPS cost): no new process, timer or window, so the budgets hold; no
  input is sent; the launcher still starts only the repo's own scripts.
- Depends on: none. Files: app/guards.js, app/main.js,
  app/client/window.js, app/client/launcher.js, scripts/run.ps1,
  app/test/, tests/test_overlay_smoke.py, tests/test_audit_exe_path.py.
- Acceptance test: with fake webContents an unregistered one has
  navigation, popups and webview attach refused; both origin spellings
  are granted and a foreign file URL ending in /overlay/index.html gets
  an empty reply; the fake spawn receives absolute paths; the live smoke
  still shows 2 processes under 215 MB.
- ZERO-CLICK: nothing for the player.

R6. An egress lock on both sessions.
- Action: `webRequest.onBeforeRequest` on the default session and the
  client partition cancels every request that is not an app file page,
  the loopback core on the configured port, or devtools with AL_DEV=1;
  the icon render page gets a no-network CSP.
- Impact M: F10's assumption and "the overlay may not fetch" (decisions
  0015 to 0017) become a property of the process; Effort S. Risk: blob
  and data URLs must pass; one callback per request.
- ToS check: enforces "the trade site is never called by the app" and
  the web-data-off rule inside Electron; reads nothing from the game.
- Depends on: R5. Files: app/guards.js, app/client/window.js,
  scripts/brand_render.js, tests.
- Acceptance test: a unit test of the allow function over 20 URLs; the
  opt-in smoke with an external image logs one cancelled request.
- ZERO-CLICK: nothing for the player.

R7. Verify the calc component at use, and pin contents, not bytes.
- Action: (a) tc_pins.json gains a content digest per component (the
  existing tree_digest) and, for PoB, a digest of the 1,073 Lua files
  that can run; (b) the bridge compares the Lua digest before each start
  and says "calc component changed, re-run setup" on a mismatch; (c)
  run_setup re-hashes the LuaJIT source before a build, as it does the
  toolchain; (d) on an archive hash mismatch the download is accepted
  only when its extracted tree digest equals the pin, under a size cap,
  and the log says so; (e) bridge.lua removes the C loaders, bridge.py
  stops setting LUA_CPATH, and `tc_drift.py apply` writes the digests.
- Impact M; Effort M. Risk: start time (0.07 s measured); (d) amends
  decision 0018 in the direction its own "Reverses if" points.
- ToS check: no floor rule touched; the component only ever gets pasted
  build text and hotkey-read item text.
- Depends on: none. Files: config/tc_pins.json, tools/tc_pin.py,
  tools/tc_drift.py, server/al/theorycraft/bridge.py and bridge.lua,
  their tests, amendments to decisions 0018 and 0022.
- Acceptance test: editing one Lua file in the checkout makes
  Bridge.from_component raise BridgeUnavailable; a re-zipped archive
  with identical contents installs; a native require fails inside the
  bridge; the 17 stored GUI outputs still match.
- ZERO-CLICK: automatic; the one manual act stays the -TcCalc opt-in.

R8. Narrow external links and downloads.
- Action: open a link only while the companion window has focus, at most
  1 per second and 5 per minute, https only, passing the parsed href,
  with hosts from one tracked list shared with web/tc.js:49; accept
  downloads only from the core origin with an extension on a short list
  (.build, .filter, .json, .txt); log each refusal.
- Impact L to M (no browser window over the game); Effort S. Risk: a
  new link host must join the list; a test enumerates what `web/` emits.
- ToS check: keeps "the app only builds a trade-search URL the user
  opens in their own browser" (decision 0017): the click stays the
  player's and the app fetches nothing.
- Depends on: none. Files: app/client/link.js, app/client/window.js,
  web/tc.js, a shared host list, tests.
- Acceptance test: routeFor denies without focus, on the sixth link in a
  minute and for http; a download named x.exe is cancelled.
- ZERO-CLICK: the link click is the player's own act; no new prompt.

R9. Go-public wiring for FLEET item 17.
- Action: prepare, not enable: `.github/dependabot.yml` (npm in /app
  weekly, cooldown 3 days and 14 for majors, limit 2; github-actions
  weekly with exclude-paths for the kit's identity-guard copy) [S12]; a
  CI workflow (pytest and node tests, actions pinned by full commit SHA,
  read-only token); a lane tool that re-applies each open Dependabot
  bump locally through the R1 gates, pushes the operator's commit and
  closes the pull request. With the remote: alerts and security updates
  on.
- Impact M at publish; Effort M. Risk: gh needs a token (one operator
  grant); a red identity check on every bot pull request is expected.
- ToS check: no floor rule touched; GitHub only; no AI or bot trailer.
- Depends on: the remote (operator act, ROADMAP.md:2059-2061), R2.
  Files: .github/ (dependabot.yml, ci.yml, a byte copy of the kit's
  identity guard), new tools/dependabot_reapply.py, tools/al_lane.py.
- Acceptance test: a lint test of the YAML keys; a dry run on a recorded
  pull-request fixture yields one local commit with the operator
  identity and one close comment.
- ZERO-CLICK: the lane does it; the operator's part is the single grant.

R10. Free release provenance, and a plain account of "unsigned".
- Action: at each tag the CI builds one source archive with
  `git archive`, writes SHA256SUMS and an SBOM (the npm CycloneDX output
  [L6] merged by a stdlib tool with the Electron zip checksum and the
  three calc pins), attests both with `actions/attest` and publishes
  them on an immutable release [S15, S16]. The README gains "verify your
  download" (`gh attestation verify`) and "what Windows will show" (no
  installer, why Bypass is used, what Smart App Control may do). One
  tester run on Windows 11 with Smart App Control on covers setup, the
  client and -TcCalc and is recorded in this note.
- Impact M at publish (the only provenance an unsigned project can give:
  SLSA Build Level 2 [S15]); Effort S to M. Risk: an attestation proves
  where a file was built, not that it is safe [S15].
- ToS check: no floor rule touched; no revenue; no game data in the
  archive (decision 0009); the README keeps the non-affiliation line.
- Depends on: R9; a Windows 11 tester. Files: a release workflow, new
  tools/sbom.py and its test, README.md, this note.
- Acceptance test: tools/sbom.py lists 13 npm components, 1 Electron
  binary and 3 calc pins, each with a hash; a release dry run on a fork
  verifies with gh; the README section names each prompt.
- ZERO-CLICK: runs on the tag push; the tester run is a one-time act.

R11. Move the two local pages off file://.
- Action: serve the overlay and starting pages through one
  `protocol.handle` scheme (fixed file list, header CSP naming the exact
  core port); the core accepts that origin instead of `null` and
  `file://` (server/al/http.py:64-67; with research 0045).
- Impact L to M (checklist item 18; no null-origin allowance); Effort M.
  Risk: the transparent overlay must still paint (re-run the
  UX-REAL-OVERLAY check).
- ToS check: touches the overlay rule: it stays a separate click-through
  window and the decision 0002 budgets are re-measured.
- Depends on: R5. Files: app/main.js, app/preload.js, the two pages,
  server/al/http.py, tests.
- Acceptance test: the feed request carries the new scheme's origin; a
  request with Origin null gets 403; the smoke budgets hold.
- ZERO-CLICK: nothing for the player.

## Cut or merge

- Cut the lockfile-less install branch (setup.ps1:233-235): refuse
  instead (in R2). Cut plain-http external links (in R8).
- Merge the two static Electron guards
  (tests/test_overlay_smoke.py:70-110, app/test/audit_electron.test.js)
  into one contract test with a single ban list, and the Python and
  JavaScript "no bare program name" rules into one test (in R5).
- Merge TC-DRIFT, GGG-DOCS-WATCH and ELECTRON-WATCH onto one daily
  watcher frame (state file, 24 h gate, User-Agent); with research 0058.

## Rejected

- Flipping fuses on the stock binary now: every `npm ci` undoes it, it
  changes the hash R4 pins, and with no signature nothing stops the bits
  being flipped back [S6]. R5 covers the same ground in code.
- Merging Dependabot pull requests on GitHub: against FLEET item 17.
- An in-app updater or a version check by the running app: a network
  call outside the web-data opt-in (decision 0013). The dev loop watches.
- A process-list check for the game before the live smoke, or running
  the smoke during play: decision 0029 forbids the first; the
  log-staleness idle state gates both.
- Paying for signing out of donations or ads tied to GGG-derived
  features: the floor bars revenue from GGG intellectual property.
- Vendoring Electron, PoB or LuaJIT, or a hash pin for the locally built
  luajit.exe: decisions 0009 and 0018 (never vendored; no hash exists
  before a local build).
- Packaging now: decision 0041 point 9 stands; its "Reverses if" (a
  release channel) is not met while no remote exists. Left to 0053.
- On merit: an EV or self-signed certificate (no SmartScreen gain
  [S20, S21]); `--no-sandbox` to save RAM (it removes the renderer
  sandbox); staying one major behind (older lines sit on Chromium
  milestones with no upstream channel left [S10]).

## Open questions

- Does `requestingOrigin` carry a trailing slash in Electron 45 (F6)?
  One logged client run while the game is idle settles it; R5 is right
  either way. No operator needed.
- Smart App Control against the unsigned stock electron.exe and the
  locally built luajit.exe (F15): needs a Windows 11 machine with it on.
  Operator or a tester.
- Signing, only if 0053 chooses a packaged exe: is the operator an
  individual in the USA or Canada (Azure Artifact Signing), and is about
  USD 120 a year acceptable with no revenue? Operator decision.
- Should ELECTRON-WATCH read while HALT is set, as the GGG docs watch
  does (decision 0044)? Adjudicator; assumed here: read yes, bump no.
- Do the 46.x builds keep the two in-process switches? Known on
  2027-01-05 at the earliest; the smoke test's process count tells.
