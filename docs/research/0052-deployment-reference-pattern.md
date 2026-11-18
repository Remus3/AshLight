# 0052 - Deployment reference pattern (install, build, release, update, uninstall)

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B15 / F.
The operator wants AshLight "properly deployable like" another app of theirs
on this machine, called "the reference app" here. This note extracts that
app's whole deployment pattern, maps each element onto AshLight's rules and
ends with the gap to AshLight's five scripts. Packaging alternatives are
research 0053; go-public readiness is 0057; upstream watchers are 0058.
Status: draft

## Sources (all accessed 2026-11-17)

The reference app, read only (file reads and git log / show; nothing was
built, installed, run or changed there). By the brief it is cited by role,
never by name, path or repository:

- REF-README: its public README (install, update, uninstall, troubleshooting).
- REF-BOOT: its one-command PowerShell bootstrap installer.
- REF-ENGINE: its installer command line and about 20 modules (install,
  update, swap, stop, repair, uninstall, launcher, manifest, release, paths).
- REF-TESTS: its 13 deployment test files (about 137 tests by declaration
  count) and its CI workflow.
- REF-PUB: its export / stage / publish tool and Windows Sandbox harness,
  kept beside the app in its parent tree.
- REF-NOTES: its six per-version release notes and its version-bump commits.

Web:

- S1: https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases
- S2: https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/
- S3: https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/
- S4: https://docs.python.org/3/using/windows.html (the 3.15 docs)
- S5: https://www.python.org/downloads/windows/
- S6: https://www.python.org/downloads/release/python-31410/
- S7: https://www.python.org/downloads/latest/pymanager/
- S8: https://www.electronjs.org/docs/latest/tutorial/installation
- S9: https://www.electronjs.org/docs/latest/tutorial/electron-timelines
- S10: https://releases.electronjs.org/schedule
- S11: https://learn.microsoft.com/en-us/windows/win32/msi/uninstall-registry-key
- S12: https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file

Repo: scripts/*.ps1, server/al/, app/, tools/tc_pin.py, tools/tc_drift.py,
the decisions cited below, ROADMAP.md, AL-NEXT-SESSION.txt.

## Summary

- The reference app ships with no packaged executable and no admin rights:
  a zip with a per-file SHA-256 manifest and a checksum file, installed per
  user by one pasted PowerShell line and self-tested before an install
  marker is written. That fits decision 0041 point 9 as it stands.
- Its core idea is the layout: one home with `app\<version>\`, user data
  outside the code and a marker naming the active and previous version.
  Update = build beside, self-test, switch the marker; rollback = switch back.
- AshLight has five scripts for a git checkout: no artifact, marker, update
  path or uninstall. Two defects stop any stranger first: a drive-rooted
  path default (F2) and the whole test suite in the first-time path (F5).
- Of 37 pattern elements: 15 adopt, 16 adapt, 6 not applicable. Seven ranked
  recommendations; R1 to R5 and the local half of R6 need no remote and no
  operator act; publishing and CI (R7) wait for the remote.

## Current state

- setup.ps1: checks Python 3.11+ (scripts/setup.ps1:73-77), creates the
  sidecar folders (:79-82), copies the config example once (:105-115),
  installs the overlay's npm packages only when the lockfile hash changed
  (:147-160, :228-248) and writes two per-user shortcuts (:164-211).
- build.ps1: a test gate, not an artifact builder: the Python suite through
  the suite gate (scripts/build.ps1:165-177), the node tests (:179-192),
  then a build stamp with the version (:194-204).
- run.ps1: converges to one core, one supervisor and one client
  (scripts/run.ps1:132-226); waits up to 15 s for /api/health (:155-176).
- stop.ps1: stop.request, a wait, a forced stop only of a pid proven ours
  (scripts/stop.ps1:77-98), then the process registry (:100-121).
- autostart.ps1: opt-in logon task "AshLight Autostart", limited run level,
  30 s delay (scripts/autostart.ps1:42-44, :148-157).
- Version: `VERSION = "0.1.0"` (server/al/__init__.py:7) and `"version":
  "0.1.0"` (app/package.json:3), served by /api/health and /api/version
  (server/al/http.py:234-245) and sent in the User-Agent
  (server/al/webfetch.py:77). 0 tags, 356 commits, no notes file.
- Paths: one resolver (server/al/paths.py:124-155). State lives in the
  checkout's `ops/runtime` (:35-41), config in `config/local.json`
  (:119-121), the rest under the sidecar root from the fleet kit (:44-71).
- Launch: the shortcut targets the pinned Electron inside the checkout with
  `"<repo>\app" --client` (scripts/setup.ps1:195-204, decision 0041 point 8);
  the client starts the core through run.ps1 (app/client/launcher.js:45-58).
- No remote and no CI: the pre-push hook refuses every push
  (.githooks/pre-push:22-24) with one deliberate override (:11-19). Operator
  order: releases only on a milestone or an explicit tag, never per commit
  (AL-NEXT-SESSION.txt:104).

## Reference pattern (extracted)

P1 Version (REF-ENGINE, REF-NOTES).
- One field in the package manifest is the source (semver; a pre-release
  suffix selects a beta channel), served from the info endpoint.
- A bump is one commit: manifest, lockfile and a new hand-written notes
  file. Six releases shipped between 2026-10-18 and 2026-11-03. Tags exist
  only in the public repository; the publish step creates them.

P2 Build (REF-ENGINE).
- One CLI command, `release --out DIR`: stage the source through a skip
  list, write `MANIFEST.json` (name, version, channel, created, SHA-256 per
  file), zip it with one top-level `<app>-<version>` folder, copy the
  bootstrap and the notes, write `SHA256SUMS.txt`. 4 to 5 assets, no compile
  step, no bundled dependencies; it ends with "not uploaded".

P3 Install (REF-README, REF-BOOT).
- One pasted line pipes the bootstrap from the latest release's download URL
  (the `/releases/latest/download/<asset>` form, S1) into PowerShell; no
  admin rights. It also takes a local zip; a re-run upgrades or repairs.
- Bootstrap order: the runtime (installed when missing through winget or the
  publisher's installer, checked against the publisher's SHA-256 list,
  failing closed when no hash can be got); `SHA256SUMS.txt`, then the zip it
  names, verified; hand-over to the release's own installer; start.
- Before the marker is written a self-test starts that version's server on
  an ephemeral port with scratch data, checks the info endpoint for the
  expected version and runs a 2-file test subset. A failure moves the build
  aside, writes a report and leaves no marker.

P4 What an install creates (REF-ENGINE).
- A home under `%LOCALAPPDATA%\Programs\<app>` (a flag or an environment
  variable moves it; tests pass a scratch home) with nine entries: the
  marker `install.json` {version, path, channel, installedAt, previous},
  `app\<version>\`, a pristine copy of that release, three user-data folders
  outside the code, `backups\`, `reports\` and `cache\`.
- A first-run local config, written once and merged over the shipped
  defaults; launchers at the home root, rewritten on every update because
  they name the version; Desktop and Start-menu shortcuts to them.
- An Apps & features entry in the per-user uninstall key, its version
  rewritten and read back on every switch; a user PATH entry.
- No scheduled task and no service; its one task (auto-update) is created
  by a script the user runs on purpose.

P5 Release process (REF-PUB, REF-TESTS).
- Export: tracked files at a git ref go into a separate public repository
  through an exclude list, strip markers and a deny-term scan.
- Stage (local, uploads nothing): 11 steps, 3 of them app-specific, ending
  in a `stage.json` verdict with the commit and the asset hashes: whole
  suite, export and scan, the exported tree's suite, end-to-end UI, release
  assets, media, README lint, then Windows Sandbox phases: clean install
  from the staged assets, update from the previous published release, stop
  / uninstall / purge, and a no-egress phase with networking disabled. A
  sandbox needs more than 6 GB free.
- Publish: nine refusals before anything changes (the exact typed phrase
  naming the version; a stage report that exists, is PASS, matches the
  version and is under 24 h old; an unmoved release ref; an unmoved public
  head; a clean dry run of the final private merge; a no-reply identity).
  Then one squash commit, a tag `v<version>`, a fast-forward push, the
  release with assets and notes, and a read-back of the head, the tag
  target and every asset digest (S2). A rehearse mode stops before the
  first push.
- Notes are hand-written per version; nothing is generated from commits.
- CI: one Windows-runner workflow with actions pinned by commit: tests, a
  privacy scan, a Windows PowerShell 5.1 parse of every script.

P6 Update, rollback, repair (REF-ENGINE, REF-README).
- Learning: one unauthenticated GET of the release list, ETag-cached, off by
  a setting, skipped when no repository is configured. Since its sixth
  release nothing checks in the background: a click or a command does.
- Applying: download checksum file and zip (4 allowed hosts), verify the
  hash, extract, verify every file against the manifest, zip a backup, stop
  the app only when the target folder is in use and no work is in progress,
  copy the release beside the old version, install dependencies, self-test,
  then switch the marker with an atomic write, rewrite the launchers,
  refresh the uninstall entry and restart when idle.
- User-edited installed code is merged three ways against the pristine
  copy. Auto mode is off by default and applies only in a night window.
- Rollback: a failed self-test leaves the marker on the old version (the
  old folder is never modified) and exits 1 with the failing test names;
  `rollback` switches back by hand; `reinstall` needs a typed phrase.

P7 Uninstall (REF-ENGINE, REF-README).
- From Apps & features or the CLI. It refuses in one case: an optional
  feature that changed the user's other tools is still applied.
- It stops the server and waits for the process itself to exit, removes
  shortcuts, uninstall entry, PATH entry and the optional task, then code,
  launchers and marker. User data stays unless `--purge` (Recycle Bin).
- It never reports success while files remain (one "uninstall incomplete"
  line, exit 1), and its last lines name what stays.

P8 Config, logs, health, tests (REF-ENGINE, REF-TESTS).
- Config: shipped defaults plus one local override file. Logs: an
  append-only server log and a JSON report per install, update, reinstall.
- Health: an info endpoint with the version, a `status` command, a 15 s
  start watch that turns a failed start into one sentence, and a scrubbed
  problem report the user reads in full before choosing where it goes.
- Tests: every effect is injected, so the whole CLI runs against scratch
  homes with fakes (no real install, shortcut, registry write, Recycle Bin,
  network or server). PowerShell is parsed, never run. Real-machine
  behaviour is proven only in the sandbox phases.

## Mapping onto AshLight's rules

Verdicts: ADOPT (as is), ADAPT (how), N/A (why). Rules checked: stdlib core,
Electron exact pin, no CDN at runtime, sidecar folders, decision 0041,
releases only on a milestone or an explicit version tag, decision 0013.

Version and build
- M1 one version field served by the app: ADAPT. `VERSION` stays the
  source; app/package.json and its lockfile must equal it by test.
- M2 bump = one commit with a hand-written notes file: ADOPT.
- M3 tags only at publish: ADOPT. It is the operator's order.
- M4 zip, manifest and checksums from one local command: ADAPT. Stdlib
  only; an allow-list over `git ls-files`; output under `<sidecar>\Build\`.
- M5 dependencies fetched on the target, not bundled: ADAPT. The pinned
  Electron by hash, at install or update time only (no CDN at runtime).

Install
- M6 one pasted line plus a local-zip route: ADAPT. Local zip first.
- M7 prerequisite with a publisher hash, fail closed: ADAPT, for Python.
- M8 per-user home, versioned code folders, marker: ADAPT. An installed
  mode in server/al/paths.py; the sidecar rule keeps governing the checkout.
- M9 user data outside the code: ADAPT. `ops/runtime` and
  `config/local.json` become `<home>\data\` in installed mode.
- M10 launch target that survives an update: ADAPT. Resolved from the
  marker, so decision 0041's one-click shortcut works after a switch.
- M11 Desktop and Start-menu shortcuts: ADOPT. Already there.
- M12 Apps & features entry, version read back: ADOPT.
- M13 user PATH entry: N/A. Players have no everyday command.
- M14 no task or service by default: ADOPT. Decision 0011 says so.
- M15 self-test before the marker: ADAPT. `--check` plus /api/health on a
  scratch runtime, `--no-tail`, a free port in 8961-8979: nothing live.
- M16 re-run repairs or upgrades: ADOPT. The scripts are idempotent today.

Release
- M17 export to a separate repository: N/A. This repo is kept
  publish-ready; the allow-list and the leak sweep do the scrub (0057).
- M18 stage command with a verdict file and sandbox phases: ADAPT.
- M19 publish gates and read-back: ADOPT.
- M20 CI on a Windows runner: ADAPT. After the remote exists, with the
  kit's identity guard as a required check.

Update
- M21 ETag-cached release check, opt-out, repo-gated: ADAPT. Through
  server/al/webfetch.py and only while web data is on (decision 0013).
- M22 host allow-list, SHA-256 and manifest verification: ADOPT.
- M23 backup, build beside, self-test, atomic switch, restart when idle:
  ADAPT. Idle means `game_idle` (decision 0029) or the next client start.
- M24 three-way merge of user-edited code, pristine copy, patch export:
  N/A. Installed code is not edited; a changed file is reported, replaced.
- M25 rollback with one previous version kept: ADOPT.
- M26 auto mode through a scheduled task: N/A. The core's daily loop checks.
- M27 typed-phrase reinstall modes: N/A. A re-run repairs; purge resets.

Uninstall
- M28 stop, verify, remove, keep data unless purge, never claim success
  with files left: ADOPT.
- M29 refuse while changes to other tools remain: N/A. AshLight changes
  nothing outside its home, two shortcuts, one key and one optional task.
- M30 detached cleanup of files in use: ADAPT, for the private runtime.

Config, logs, health, tests
- M31 shipped defaults plus a local override, test overrides by
  environment: ADOPT. Needs the player and dev keys split (F8).
- M32 JSON report per install, update, uninstall: ADOPT.
- M33 `status` command and version in the info endpoint: ADAPT. Add the
  install mode (checkout or installed) and the previous version.
- M34 scrubbed report read before any send: ADOPT. DIAG-SELF does this.
- M35 recovery without a runtime: ADAPT. Stop and uninstall stay PowerShell.
- M36 egress allow-list with tests: ADOPT. webfetch.py is the one path.
- M37 injected effects, scratch homes, parse-only PowerShell: ADOPT.

## Findings

F1. The pattern needs no packaged executable. The reference app reaches
one-line install, an Apps & features entry, update, rollback and uninstall
with a zip, a manifest and scripts (P2 to P7). Decision 0041 point 9
deferred a packaged .exe because packagers download more binaries at build
time (docs/decisions/0041-desktop-client.md:88-94). Matters: the operator's
goal is reachable without reversing 0041.

F2. A stranger's setup fails, or writes to a drive root nobody chose.
Without `AL_SIDECAR_ROOT` the resolver returns the fleet kit's fixed sidecar
default plus "AL" with no existence check (server/al/paths.py:61-71, pinned
by tests/test_sidecar_paths.py:33-41), and setup.ps1 creates folders there
under `$ErrorActionPreference = 'Stop'` (scripts/setup.ps1:35, :79-82). A
probe with a drive letter that does not exist gave DriveNotFoundException
from New-Item and FileNotFoundError (WinError 3) from Python's mkdir; where
the letter exists, a root folder appears on that drive. TEST-CLEAN-CLONE
missed it because it set AL_SIDECAR_ROOT (ROADMAP.md:1525-1527). Matters:
the first run elsewhere stops or leaves files in a surprising place.

F3. State and config sit inside the code folder: `ops/runtime` (token,
consent, weights, run history, window position) and `config/local.json`
resolve under the repo root (server/al/paths.py:35-41, :119-121). Matters:
a versioned code folder cannot be swapped or removed without losing the
player's consent, settings and history.

F4. The version is two unlinked strings with no release record
(server/al/__init__.py:7, app/package.json:3; no test compares them; 0 tags,
no notes). Matters: marker, manifest, update compare, uninstall entry and
the truthful User-Agent all key on one version.

F5. The first-time path makes the player run the test suite: the README
Quick start lists build.ps1 as step two (README.md:60-73); it runs the whole
Python suite (2316 tests at the last gate, AL-NEXT-SESSION.txt:136-137) and
exits 1 without pytest (scripts/build.ps1:155-177). The reference app runs a
2-file self-test. Matters: minutes of CPU and a dev tool before first use.

F6. Node is a prerequisite the running app does not need. Setup needs Node
20+ for the client (scripts/setup.ps1:134-145), yet the app requires only
`electron`, Node built-ins and its own files (a grep of every require call
in app/ outside tests). Installed: 13 packages, 372 MB, 358 MB of it the
Electron folder; the download is one 151.0 MB zip (measured in the sidecar
cache), fetched for the exact version and checked against checksums (S8).
Electron is a devDependency (app/package.json:12-14), so the reference
app's `--omit=dev` flag would install nothing. Matters: a second runtime
install, maybe with an elevation prompt, to download one zip.

F7. No uninstall, no update path, and no record of what an install created.
Today's footprint: 2 shortcuts (scripts/setup.ps1:200-204), the optional
task (scripts/autostart.ps1:42), `config/local.json`
(scripts/setup.ps1:105-110), `ops/runtime`, 6 sidecar folders
(server/al/paths.py:25) and `app/node_modules`; no registry write (the only
registry code reads Steam's keys, server/al/logfile.py:37-48). The README
has no Update or Uninstall section (README.md:60-113). Matters: removal is
five manual steps the player has to guess.

F8. The runtime is tied to the checkout and to the fleet kit. Every start
finds Python by bare name (scripts/setup.ps1:40-46, scripts/run.ps1:55-61,
app/client/launcher.js:13); on Windows a bare `python` can open the Store
or, with the install manager and no runtime, download one by itself (S4).
"Our" Electron is recognised by its folder inside this checkout
(server/al/procs.py:52-60); shortcut and logon task point into the checkout
(scripts/setup.ps1:195-204, scripts/autostart.ps1:45, :80-81); `/tokens.css`
is served from the kit folder (server/al/__main__.py:169); the example
config opens with a dev-loop block (config/local.example.json:3-10).
Matters: after a switch to `app\<new>\` the stop script would miss a
shortcut-started client (only run.ps1 records its pid, scripts/run.ps1:212)
and the shortcut would start the old version. The reference app records its
runtime's full path at install.

F9. A release needs a ship list, not a skip list. The tree tracks 532
files, 5.0 MB; server, web, app without tests, scripts, assets and config
are about 1.5 MB. A skip list would ship 29 ops files and 22 tools files
that players never run, plus the hand-off and the roadmap.

F10. Most building blocks exist: hash check, bounded download with a host
allow-list, zip-member check and extract (tools/tc_pin.py:239, :258, :339,
:384); a GitHub release read with rate-limit handling
(tools/tc_drift.py:118-150); ETag requests (server/al/ninja.py:175-178);
one outbound path with an allow-list and a truthful User-Agent
(server/al/webfetch.py:1-21); a code preflight
(server/al/__main__.py:38-66); the process registry; a per-user task helper
with read-back (tools/loop_task.py:161-196); an idempotent shortcut writer
(scripts/setup.ps1:164-184); a redacted report (server/al/diag.py:11-15).
Matters: effort goes into layout, swap and gates, not plumbing.

F11. The Electron pin sets a floor on release frequency. Electron supports
its latest three majors and ships one about every 8 weeks (S9); Electron 45
went stable on 2026-10-20 and its end of life is listed as 2027-04-27,
tentative (S10). Matters: "only on a milestone" must count "the pinned
Electron leaves support" as one, or installs keep an unsupported engine.

F12. Python for strangers is in transition. The newest Windows builds are
3.15.2 and 3.14.10 (2026-10-25) and 3.13.17 (2026-10-21); the last 3.11
build is 3.11.9 (2024-04-02), the last 3.12 one 3.12.10 (2025-04-08) (S5).
The classic installer is deprecated since 3.14 and ends with 3.16; the
install manager replaces it (S4, S7). Each line has an embeddable zip: 12.0
MB for 3.14.10, SHA-256 on its release page (S6), with the standard
library, python.exe and pythonw.exe, no pip, isolated by a path file (S4).
Matters: "3.11 or newer" means 3.13+ for a new install; the embeddable zip
is the smallest hash-checkable route with no admin prompt. UNVERIFIED: that
the core, supervisor and tools run under its path file.

F13. The publish gates already match the operator's order. The reference
app publishes only on a typed phrase naming the version (P5); AshLight's
order is "only on a milestone or an explicit tag" and the pre-push hook has
the one override (.githooks/pre-push:11-19). GitHub computes a SHA-256
digest per release asset (S2) and can make a release and its tag immutable
(S3). Matters: the gate needs code and the remote, no new policy.

## Recommendations

R1. Installed-mode paths.
- Action: give server/al/paths.py an installed mode (a marker above the
  package, or `AL_HOME`): state, config, logs, cache and temp resolve under
  the install home; the kit default counts only when its folder exists;
  else `%LOCALAPPDATA%\AshLight`.
- Impact: H (F2, F3; every later item stands on it). Effort: M. Risk: path
  regressions across the core, held by the path test.
- ToS check: "never modify any game file": resolver and installer refuse a
  home inside a Steam library or game folder; consent moves with the data
  folder, no new read.
- Depends on: nothing (the plan records a decision and one Sidecar
  sentence). Files: server/al/paths.py, procs.py, __main__.py,
  app/client/launcher.js, tests/test_sidecar_paths.py.
- Acceptance test: with `AL_HOME=<tmp>` every runtime path is inside
  `<tmp>`; with no env and no kit folder none leaves `%LOCALAPPDATA%`; cores
  started from `<tmp>\app\0.1.0` and `<tmp>\app\0.1.1` read the same
  consent file; a home inside a fake game folder is refused.
- ZERO-CLICK: resolved from the marker; nothing to set.

R2. One version, tested, with notes.
- Action: keep `VERSION` as the source, test that app/package.json and the
  lockfile equal it, add a notes file per version and a `tools/release.py
  bump X.Y.Z` that writes all of it in one commit.
- Impact: H (F4). Effort: S. Risk: low.
- ToS check: "truthful User-Agent naming AshLight and its version": the
  header reads `VERSION` (server/al/webfetch.py:77); one source keeps it so.
- Depends on: nothing. Files: server/al/__init__.py, app/package.json,
  app/package-lock.json, tools/release.py, a version test, a notes folder.
- Acceptance test: the test fails when the strings differ; a bump on a
  scratch clone changes exactly four paths; a pre-release sorts below its
  release.
- ZERO-CLICK: nothing for the player; the loop never bumps by itself
  (operator order: only on a milestone or an explicit tag).

R3. Release builder that never uploads.
- Action: `tools/release.py build`: a ship list over `git ls-files` at a
  ref, `MANIFEST.json`, a reproducible `AshLight-<version>.zip` with one top
  folder, the bootstrap, `SHA256SUMS.txt` and the notes, written to
  `<sidecar>\Build\release\<version>\`.
- Impact: H. Effort: M. Risk: shipping a dev or fleet file (F9), held by
  the allow-list, a leak sweep of the staged tree and a deny test.
- ToS check: "no GGG trademarks, art or logos" and decision 0009 (bundle no
  game data): only tracked files can ship; the build fails when anything
  from the sidecar cache is in the staged tree; the disclaimer ships.
- Depends on: R2. Files: tools/release.py, a tracked ship list, a test.
- Acceptance test: two builds of one ref give the same SHA-256; the
  manifest check catches a changed file, a missing file and an unsafe path;
  nothing under ops/loop, tools, tests or docs is listed; zip under 2 MB.
- ZERO-CLICK: one command, no prompt, no upload.

R4. Installer and bootstrap, local zip first.
- Action: an `install.ps1` (Windows PowerShell 5.1) plus a stdlib installer
  package shipped in the release: verify the zip, lay out
  `<home>\app\<version>\`, fetch the hash-pinned Electron zip and Python
  runtime into `<home>\runtime\`, write the first-run config, self-test,
  then the marker, the two shortcuts and the Apps & features entry. A
  re-run repairs or upgrades. The checkout keeps `npm ci`. The README gets
  an Install section and the scripts move to "Build from source".
- Impact: H (F5 to F8). Effort: L. Risk: the embeddable Python layout is
  untested (spike first, F12); the Electron zip route needs a recorded
  decision (Q2).
- ToS check: "truthful User-Agent" and "public web data": downloads go only
  to GitHub's release hosts and python.org, named as the AshLight installer
  with its version, no cookie, no GGG or trade endpoint. "Never modify any
  game file": it writes its home, two shortcuts and one per-user key.
- Depends on: R1, R2, R3. Files: the bootstrap, the installer package, a
  runtime pin file beside config/tc_pins.json, README.md, tests.
- Acceptance test: in a scratch home with fakes a clean install lays out
  marker, code, data and runtime; a tampered zip or a missing hash installs
  nothing; a failed self-test leaves no marker and one report; a re-run
  restores a deleted shipped file; the script parses under PowerShell 5.1;
  the pinned Electron version equals the one in app/package.json.
- ZERO-CLICK: one pasted line, then the app opens; no elevation prompt.

R5. Uninstall that is complete and needs no Python.
- Action: an `uninstall.ps1` at the home root, also behind Apps & features:
  stop through stop.request and the registry, remove the logon task when
  present, the shortcuts, the key, code, runtime, cache, logs and temp;
  keep `data\` unless `-Purge` (Recycle Bin); exit 1 with one line while
  anything remains; `-DryRun` prints the plan.
- Impact: H (F7). Effort: M. Risk: deleting a wrong folder, held by fixed
  child names under a home that carries a valid marker, else a refusal.
- ToS check: "never modify any game file": it touches no game folder, even
  where the player copied an AshLight-made filter or build file there
  (decisions 0031, 0033, 0034); its last lines name those files instead.
  It stops only pids proven ours (server/al/procs.py:10-27).
- Depends on: R1, R4. Files: scripts/uninstall.ps1, README.md, a test.
- Acceptance test: a scratch home ends with only `data\`; `-Purge` leaves
  nothing (recycle injected); a held file gives exit 1 and the one line;
  `-DryRun` changes nothing; PowerShell 5.1 parse.
- ZERO-CLICK: one click in Apps & features; no question by default, since
  nothing outside the home needs a choice.

R6. Update and rollback.
- Action: `update --check`, `update --yes`, `update --zip FILE` and
  `rollback` in the installer package; a daily check in the core's refresh
  loop that publishes an `update` entry in the snapshot; download, verify
  and stage by itself; switch at the next client start or on "Update now".
  The Checks view and its copied report show mode (checkout or installed),
  version, previous version and the last update result; every run writes
  `reports\last-<kind>.json`.
- Impact: H. Effort: L. Risk: a bad release, held by the self-test, the
  automatic rollback and one kept previous version.
- ToS check: decision 0013 ("nothing hits the network while off"): check
  and download sit behind the web-data opt-in; with it off the Settings tab
  shows the installed version and a releases link the player opens in
  their own browser. "Must not cost game FPS": download and extract run at
  below-normal priority, never during a live session unless clicked. The
  report stays redacted and click-only (decisions 0040, 0014).
- Depends on: R1 to R4, and a published release for the network half
  (operator act); the `--zip` half works today. Files: the installer
  package, server/al/core.py, state.py, diag.py, the Settings tab, tests.
- Acceptance test: N to N+2 with a fake release keeps `data\` byte for
  byte; a tampered zip is refused; a failed self-test leaves the marker on
  N with exit 1; rollback restores N and reads back marker and uninstall
  entry; with web data off a fake fetch records 0 calls.
- ZERO-CLICK: with web data on, no click: the next start runs the new
  version and one line names it. With web data off, one click on the
  releases link (decision 0013 requires it).

R7. Stage, publish and CI, with gates.
- Action: `tools/release.py stage` writes a PASS / FAIL `stage.json` (suite
  through the gate, node tests, two identical builds, leak sweep of the
  staged tree, a scratch-home install / update / rollback / uninstall round
  trip, optional sandbox phases); `publish --version V --go "release V"`
  refuses unless the stage is PASS, under 24 h old, for the same commit and
  the tag is free; then tag, push through the hook's override, release,
  read back tag and asset digests; a rehearse mode stops before the push.
  One Windows CI workflow (pytest, node tests, leak sweep, PowerShell 5.1
  parse, the kit's identity guard). A watcher files a release-due row 30
  days before the pinned Electron's end of life (F11; 0058 owns it).
- Impact: M today, H once public (F13). Effort: M. Risk: a release by
  accident, held by the typed phrase and the loop having no path to it.
- ToS check: "no GGG trademarks ... in branding" and "no commercial revenue
  from GGG IP": notes and assets pass the README's brand checks and carry
  the disclaimer; publishing touches no game system; CI keeps web data off.
- Depends on: R3 to R6; operator acts: the remote (ROADMAP.md:2059-2061),
  the `gh` sign-in, the immutable-releases setting (S3). Files:
  tools/release.py, a workflow file, tests with git, gh and clock injected.
- Acceptance test: every gate has a refusal test where nothing changed;
  rehearse makes 0 pushes; a digest mismatch fails the read-back; a planted
  drive path fails CI. Sandbox phases never run while the game runs.
- ZERO-CLICK: one operator phrase per release (the operator's order
  requires it); everything before and after is automatic.

## Cut or merge

- Cut for players, at once: build.ps1 in the README's first-time path (F5).
- Do not port: the three-way merge, the pristine copy, the patch export,
  the typed-phrase reinstall modes, the PATH entry, the auto-update task
  and the separate-repository export (M13, M17, M24, M26, M27, M29).
- Merge autostart.ps1's task code and setup.ps1's shortcut writer into one
  shell-integration module that installer and uninstaller both call
  (decision 0011 stays: off by default), and the fetch, hash and extract
  helpers of tools/tc_pin.py with the installer's into one stdlib module.
- Keep `\AshLightOps\LaneLoop` (tools/loop_task.py:26) out of every
  install: it is the dev loop's task, not the app's.

## Rejected

- A packaged .exe or an installer framework now: against decision 0041
  point 9. Its "Reverses if" (a release channel makes a packaged, signed
  .exe worth its build dependencies) is not met: the pattern delivers the
  channel without one. Options stay with 0053.
- An update check or download while web data is off: against decision 0013.
- Timing an update restart by looking for the game in the process list:
  against decision 0029. `game_idle` from the log is the signal.
- Installing or removing anything in a game folder during install, update
  or uninstall: outside the floor (no game file change); decisions 0031,
  0034. Game data inside the release zip: against decision 0009.
- A Windows service or a machine-wide install: against decisions 0005 and
  0011 (a detached per-user supervisor; logon start is an opt-in task).
- Telemetry, a crash upload or an update ping with an identifier: against
  the README's privacy promise and the floor's no-account rule.

## Open questions

- Q1 (operator or adjudicator): the home on the operator's machine. The
  pattern default is `%LOCALAPPDATA%\Programs\AshLight`; the Sidecar order
  reads as `<sidecar>\Install`. Recommended: the pattern default for
  everyone, with `-InstallDir` for the operator.
- Q2 (adjudicator): Electron for installed copies by pinned zip (no Node on
  the player's machine) or by `npm ci` (Node 20+ needed). Evidence favours
  the zip (F6); it needs one new decision and a Stack sentence.
- Q3 (spike, then 0053): private embeddable Python or the player's own
  Python 3.13+. UNVERIFIED until the core, the supervisor and the calc
  bridge pass a smoke run under the embeddable layout.
- Q4 (operator): switch to a staged update at the next start by default, or
  only on a click. Recommended: by default, with a Settings switch.
- Q5 (operator): whether the operator's live copy becomes an installed
  release, with the checkout on another port for dev.
- Q6 (UNVERIFIED): Microsoft documents only the machine-wide uninstall key
  (S11); the per-user key works for the reference app on Windows 10 and 11
  (REF-PUB sandbox phases). That 45.3.3 is Electron's newest stable build
  (2026-11-14) was seen only through a search summary of the releases page.

## Gap list (AshLight today vs the pattern)

- setup.ps1: sets up a checkout, not an install. No download or
  verification of the app, no marker, no uninstall entry; its folder
  default breaks on other machines (F2); it finds Python by bare name,
  copies dev keys into the player's config and points the shortcut into
  the checkout (F8); it needs Node for one zip (F6).
- build.ps1: produces a stamp, no artifact: no manifest, zip or checksums;
  and it sits in the player's first-time path (F5).
- run.ps1: starts whatever the checkout holds: no marker, no version
  awareness, no install mode; Python by bare name on every start (F8).
- stop.ps1: matches the pattern's stop (waits for the process, kills only
  proven pids). Gap: the client is recognised by the checkout path (F8).
- autostart.ps1: matches "no task by default". Gaps: its task points into
  the checkout (F8) and nothing removes it on uninstall (F7).
- Missing entirely: a version test and notes (R2), a release builder (R3),
  an installer with a marker and a self-test (R4), an uninstaller (R5), an
  update check, an updater, a rollback, install status and reports (R6),
  stage and publish gates, CI and a remote (R7), and Install / Update /
  Uninstall sections in the README (R4 to R6).
- Already at or above the pattern: 127.0.0.1 only with a per-start token,
  one outbound path with an allow-list, a supervisor that restarts a dead
  core, an idempotent start, a redacted report, PowerShell 5.1 parse tests.
