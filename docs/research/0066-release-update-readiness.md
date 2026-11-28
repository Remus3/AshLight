# 0066 - Release and self-update readiness (RES-46-RELEASE-READY)

Date: 2026-11-28. Number: 0066 was free in docs/research/ (decision 0066
is a different series), so this note takes it.

Question: what can go wrong with the first public release 0.2.0 and with
the self-update path that 0.2.0 ships, what does the code do today in
each case, and which rows close the gaps before (or right after) the
first tag?

Scope: offline code reading only. No web request was made; every
"GitHub does X" claim below is either read from our own code or left as
an open question for the web dive (section 4). Severity ranks: P1 =
fix before the 0.2.0 tag (a player can be stranded or a bad release
cannot be stopped), P2 = fix before the first update 0.2.0 -> 0.2.1 is
published, P3 = hardening.

Verdict: the download, verify and stage half is careful (two hash
sources, size caps, exact-host redirects, nothing written before
verification, atomic laid-out folders). The weak points are all
AFTER staging: the 24 h hold has no way to act on a pulled release, the
rollback lives inside the code it rolls back, the confirm window is one
60 s try, and the release build is not pinned to CI's Python, so a
pushed tag can end without a release. Twenty-two findings, five P1.

## Sources (all read 2026-11-28, local files only)

- docs/research/README.md (index; 0052 and 0053 are the earlier
  deployment and packaging notes)
- docs/decisions/0063-installed-runtimes.md,
  0064-release-artifact.md, 0065-update-policy.md,
  0066-uninstall-consent.md (title only), 0068-electron-npm-supply-chain.md
  (title only), 0073-versioning-release-trigger.md
- server/al/install/update.py, switch.py, apply_staged.py, rollback.py,
  confirm.py, selftest.py, payload.py, cli.py
- server/al/updates.py, server/al/core.py (tick_update, tick_trigger,
  update_now, _ask_apply), server/al/pinfetch.py, server/al/jsonfile.py
- app/client/launcher.js (applyStaged, relaunch, startConfirm,
  startCore, takeApplyRequest, applyNow), app/client/window.js
  (applyRequested), app/test/launcher.test.js
- tools/rel_publish.py, tools/rel_stage.py (round-trip step),
  tools/rel_build.py (ship list), config/ship_list.json,
  config/public_repo.json, config/electron_pin.json
- .github/workflows/release.yml, scripts/install.ps1
- Test files present: tests/test_updater.py, test_updates.py,
  test_update_switch.py, test_update_checks.py, test_install_*.py,
  test_release_*.py (names checked, not every case read)

## 1. Failure modes of 0.2.0 and the self-update path

Each item: what the code does (file:line), safe or not, the gap and a
fix. IDs F1 to F16.

### Download

F1 (P3) Interrupted download.
Today: the three release assets are read into memory
(server/al/install/update.py:672-673, `_download` at 622-640); a socket
error or a short body raises and nothing is written; the runtime zip of
a changed pin streams to `.<name>.download` beside the target and is
removed in `finally` (server/al/pinfetch.py:316-345). The per-read
timeout is 60 s (pinfetch.py:33), no total deadline.
Safe: yes, nothing half-made survives. Gap: no resume, and an automatic
run that fails waits RETRY_S = 24 h (server/al/updates.py:77, 503-505)
before it is tried again; a ~100 MB Electron download on a flaky link
can fail every day. Fix: keep the `.download` file between runs and
resume with a Range request when its prefix still hashes to the
recorded partial digest; or retry the automatic start after 1 h, 4 h,
then daily while the failure stage is `download`.

F2 (P3) Disk full.
Today: no free-space check before the runtime download or the extract.
A write error inside `payload.extract` removes the `.partial` folder
(server/al/install/payload.py:504-516); pinfetch removes its temp files
(pinfetch.py:342-345); the report write is wrapped
(update.py:759-762). A staged-file write failure leaves a laid-out
`app/<version>` folder with no staged document; it is removed only by
the next confirm's cleanup (server/al/install/switch.py:535-562).
Safe: yes. Gap: the report reason is a bare OSError class name, not
"not enough free space", and peak use with a runtime change is about
old runtime + new zip + new tree (several hundred MB). Fix: before the
download step, `shutil.disk_usage(home)` against zip size + runtime pin
size x 3 + 64 MB; refuse with the fixed reason "not enough free disk
space (N MB needed)"; remove an orphan `app/<version>` whose staged file
is missing at the start of each update run.

F3 (P2) AV or indexer lock on freshly written files.
Today: the folder renames that finish an extract use plain `os.replace`
with no retry: payload.py:513 (app folder), pinfetch.py:341 (runtime),
selftest.py:294 (failed folder aside). Only jsonfile writes retry on
PermissionError (server/al/jsonfile.py:134-142). Windows Defender
routinely holds a handle on a just-written .exe / .dll / .pyd for a
second or two, and a directory rename fails while any file inside is
open.
Safe: no data loss, but the update fails at `extract` and the automatic
path waits 24 h; an install.ps1 first run can fail the same way.
Fix: route the three renames through one helper with the
jsonfile.REPLACE_DELAYS back-off (or a 10 s bounded retry); add a test
that injects two PermissionErrors and expects success.

F4 (P3) Automatic run downloads and self-tests without re-checking
game_idle.
Today: the core starts `update --yes` only while game_idle is true
(server/al/core.py:1446-1447, updates.py:489-508), but the installer's
`main` always passes `clicked=True` (update.py:849-851), so the gate in
`_release_gate` (update.py:784-793) and the self-test gate never wait.
The player can start the game during the download, and the self-test's
demo core plus a possible Electron unzip then run while playing
(below-normal priority, update.py:794).
Safe: ToS floor untouched; FPS budget at risk only on a slow machine.
Gap: decision 0065 amendment says downloads start only on a click or
while game_idle is true, which holds only at the start instant.
Fix: an `--auto` flag for the core's automatic start that passes
`clicked=False` and an `idle` callable reading the running core's
`/api/health` game_idle (selftest already has the shape,
selftest.py:145-171); keep `clicked=True` for the typed line and the
Update now POST.

### Verify

F5 (safe) Size, SHA-256, SHA256SUMS, API digest.
Today: `check_release` refuses a missing asset, a missing or oversize
size and a download URL that is not this tag's GitHub asset
(update.py:544-599); `_download` checks length and the API digest when
present (update.py:622-640); `_verify_release` checks the zip and
release.json against SHA256SUMS.txt and the release.json version and
pins (update.py:643-664). A missing digest is recorded as "absent" or
"partial" in the report (update.py:595-598) and SHA256SUMS alone
decides.
Safe: yes. Note: with no digest field the only anchor for
SHA256SUMS.txt itself is TLS plus GitHub's immutability; the tag
message's `sums-sha256` (tools/rel_publish.py:515-516) is not checked by
the client. Fix (P3): treat "partial" (some assets with a digest, some
without) as a failure, since a mixed answer is not a GitHub shape we
expect; and consider refusing "absent" once the web dive confirms the
digest field is general (section 4 Q2).

F6 (P3) install.ps1 has no second hash source.
Today: install.ps1 checks release.json and the zip against
SHA256SUMS.txt from the same release (scripts/install.ps1:18-22) and
cannot read the API (api.github.com is not in `$AlHosts`,
install.ps1:59-60). Safe enough for a first install (the pasted line is
the trust root anyway). Fix: print the SHA-256 of SHA256SUMS.txt at the
end of the install and in the release notes, so a careful player can
compare; no code path change needed.

### Stage and the 24 h hold

F7 (P1) The hold cannot stop a pulled release.
Today: `apply_after = published_at + 24 h` (update.py:102, 206-208,
483-489); `switch.apply` checks only the local clock against it
(switch.py:414-419) and the MANIFEST (switch.py:357-379). Nothing
re-reads the release answer between staging and the switch. The core's
next daily read would see an older `releases/latest` after a pull
(updates.py:425-437), but that only stops NEW staging
(`newer_version`, updates.py:447-454); an already staged version still
applies when due.
Safe: no. The decision 0065 rationale ("the hold ... bounds the risk")
only works if a withdrawn release is not applied, and today it is.
Fix: a tracked, shipped-with-every-release revocation channel read in
the same daily answer: (a) at apply time, `switch.apply` refuses a
staged version whose tag is newer than the cached `latest` tag in
`<home>/cache/updates/update_check.json` when that answer is younger
than the staged file (the release was pulled after staging), dropping
the staged file with the reason "the release was withdrawn"; and (b)
document the operator's pull procedure: mark the release pre-release
(it then leaves `releases/latest`) instead of deleting it, which works
even with immutable releases (to confirm, section 4 Q1). Add a test:
staged 0.2.1, cache answer now names 0.2.0, apply returns NOT_DUE with
the staged file removed.

F8 (P2) Clock skew decides the hold and can freeze the daily check.
Today: the hold compares the local clock with GitHub's `published_at`
(switch.py:414-419): a PC clock 24 h fast skips the hold, one slow
delays it. `UpdateClient.due` stores an absolute `next_at`
(updates.py:388-392, 414-424); a clock that was far ahead at check time
and is then corrected leaves `next_at` in the future for as long as the
error was, so no check (and no update) for days or months. The retry
hold uses a two-sided test and is safe (updates.py:503-504).
Fix: in `due`, treat `next_at - now > DAY_S + WAIT_MAX_S` (8 days) as
due now; in `apply`, also require `staged_at + 1 h <= now` and, when
the cached answer's HTTP `Date` header is kept, compute the hold on
the server's clock (store `server_now - local_now` at the read and
apply it). Tests with a clock moved back by 30 days.

F9 (P3) Pre-release tags.
Today: GitHub's `releases/latest` route skips pre-releases by itself;
`is_newer` refuses a SemVer pre-release part or the API flag
(updates.py:201-207); `check_release` re-checks and the installer
reports SKIPPED (update.py:559-564, 730-732); release.yml marks `-rc.N`
tags `--prerelease` (.github/workflows/release.yml:115-116).
Safe: yes. An installed `0.2.0-rc.1` sees `0.2.0` as newer and updates
(SemVer precedence, updates.py:189-198), which is intended. Gap: an rc
tester never gets `-rc.2` by update; that is by design (decision 0065
alternatives) but should be in the test-round instructions. No code fix.

F10 (P2) Partial release (assets missing).
Today: release.yml creates a draft, uploads, then publishes
(release.yml:94-120), so `releases/latest` never shows a half-uploaded
release; a hand-made release without assets fails
`check_release` with "the release has no <name>" (update.py:571-574)
and the run waits 24 h. Safe for players. Gap on the operator side: a
failed upload step leaves a draft for the tag, and a re-run of the job
fails at `gh release create` because the draft exists; the tag cannot
be deleted (tools/rel_publish.py:586-588 refuses deletes) so the
recovery path is undocumented. Fix: make the create step idempotent
(`gh release view` first; reuse an existing draft for the same tag),
and write the recovery steps into docs/guide or the release runbook.

### Apply-now, confirm and rollback

F11 (P1) The rollback lives inside the version it must roll back.
Today: `apply-staged` (which also performs the automatic rollback at the
second unconfirmed start, switch.py:454-471) runs only from
`launcher.startCore` of the client that was just started
(app/client/launcher.js:264-278). After a switch the Start Menu
shortcut, the uninstall entry and the logon task all point at the NEW
version (switch.py:474-494 via shell.rewrite). The self-test proves only
the Python core (`--check` and a demo core health answer,
server/al/install/selftest.py:8-20); it never starts the new Electron
main process. A new version whose app/main.js or app/parts/*.js throws
before `startCore` therefore never runs `apply-staged` again: no start
is counted, no rollback happens, and every shortcut start fails. The
only way back is the typed `python -m server.al.install rollback`
line, which needs the private runtime path.
Safe: no; this is the one way 0.2.0 can strand a player with no
zero-click recovery.
Fix (both halves): (a) add an Electron smoke to the self-test: start
`<runtime electron>/electron.exe <new app> --client --selftest` hidden,
which loads every part, opens no window and exits 0 within 30 s (egress
lock stays on; no core needed); fail the stage otherwise. (b) make the
confirm require a client heartbeat too (the client writes
`<data>/client.alive` with its version after the parts load), and have
the KEEPALIVE supervisor (old-code-independent at the switch) or a
stable launcher stub in `<home>` run `apply-staged --if-due` before
starting Electron, so a client that dies early is still counted.

F12 (P1) One 60 s confirm try decides a permanent skip.
Today: after a switch, the first start bumps `start_attempts` to 1
(switch.py:460-471), `startConfirm` spawns `confirm --wait` with the
default 60 s (switch.py:64, confirm.py:28, launcher.js:225-243). If the
new core is not answering with the new version inside 60 s, the next
start rolls back (MAX_ATTEMPTS = 2, switch.py:51, 460-466) and
`record_skip` puts the version in `update_skip.json` for good
(switch.py:157-171, 317); that version is never staged again
(update.py:737-739). A first start after an update is the slowest one:
fresh .py files compiled to bytecode by the private Python, Defender
scanning a new runtime, run.ps1 and the hello proof.
Safe: no for a good release on a slow or busy PC; the player silently
stays on the old version until the next release.
Fix: confirm timeout 180 s and re-armed on each start while
pending (each start runs its own confirm, as today, but the rollback
needs MAX_ATTEMPTS = 3 starts); write the skip with a reason class and
let a version skipped for "no health answer" (not for a failed
self-test or a crash loop) be offered once more after 7 days; keep the
manual skip permanent.

F13 (P2) Apply-now edge cases.
Today: `applyNow` writes stop.request, waits 20 s (launcher.js:320,
376-394), runs `apply-staged` without `--if-due` and relaunches
(launcher.js:400-405). `takeApplyRequest` validates and always removes
the file (launcher.js:324-340), and window.js passes the hello check
(app/client/window.js:298-305). Safe in the main path. Gaps:
(a) when `relaunch` returns 0 after EXIT_SWITCHED (no electron.exe at
the new marker's runtime), `restart` runs the OLD client's run.ps1 from
the old payload root (launcher.js:365-368, 283-285) under a marker that
now names the new version, so client and core versions differ;
(b) `relaunch` passes only `--client` (launcher.js:210), so a logon
(`--client --tray`, scripts/autostart.ps1:85) start that applies a due
update pops the companion window at logon. Fix: (a) when the marker
moved but relaunch failed, run `installer rollback` at once and start
the old version (the switch is unusable); (b) forward the original
`--tray` flag through relaunch.

F14 (P2) Runtime pin change.
Today: a pin whose `<name>-<ver>` folder is not ready is fetched in the
installer process (update.py:299-327, payload.py:617-646) before the
self-test. Two gaps: (a) the self-test runs the new code on the OLD
Python (selftest.py:174-182 uses `paths.python_cmd`, which reads the
marker; the marker is not switched until apply), so a CPython pin move
is never self-tested on its new runtime; (b) the runtime folder name
holds only the version (payload.py:596-601); a re-pin that keeps the
version but changes url/sha256/size makes `ensure_runtime` delete and
replace the folder the RUNNING version uses (pinfetch.py:339-341),
while its electron.exe or python.exe is open (rmtree fails half way;
the running copy may lose files). Fix: (a) give the self-test an
explicit interpreter: the new pin's `<home>/runtime/python-<ver>/
python.exe`; (b) name runtime folders `<name>-<ver>-<sha8>` (marker
and staged doc already carry the folder name, so it is a payload.py
change plus a migration that accepts the old name) and never rmtree a
folder named by the active or previous marker entry.

F15 (P2) First update path never run end to end over the network.
Today: `release.py stage --sandbox` round-trips install N-1, `update
--zip` (local), `apply-staged`, rollback, uninstall
(tools/rel_stage.py:754-804). The network half (`update --yes` against a
real `releases/latest` answer), the core's automatic trigger, Update
now, the client relaunch and the confirm are covered only by unit tests
with injected fetchers and spawners. 0.2.0 is the first version with
update code; whatever 0.2.0's updater does wrong is permanent for
every player who installs it (a broken updater cannot update itself).
Fix: before tagging 0.2.0, publish `0.2.0-rc.1` and `0.2.0-rc.2` as
pre-releases on the real repository and run, on a clean Windows user,
install rc.1 then `installer update --yes --release-cache <answer for
rc.2 written by hand>` with a temporary `allow_prerelease` test-only
switch, the relaunch and the confirm; record the run. Also ship 0.2.0
with a documented escape hatch: "re-run the install line" upgrades in
place (install.ps1:31-32), and say so in the README troubleshooting.

F16 (P3) Update applies only when the core is down.
Today: `apply-staged --if-due` returns BUSY while a core of the home
runs (switch.py:420-423), and the supervisor keeps the core alive while
the window is closed to the tray. A player who never chooses tray Quit
and does not reboot applies only through Update now. Safe. Fix: Checks
"Update" note after 72 h staged-and-due with one line "Restart AshLight
from the tray to finish the update" (the row already exists,
REL-UPDATE-CHECKS).

## 2. Gaps versus decisions 0063, 0064, 0065 and 0073

Each claim of the decision is checked against the code. IDs G1 to G6
(findings 17 to 22).

0063 (installed runtimes)
- Item 1 "exact version and sha256", item 3 "pin checked before any
  request, temp file, nothing in the target on a mismatch, a target
  without AshLight's marker is never removed": holds
  (pinfetch.py:298-346, 312-313).
- G1 (P2) Item 1 pins CPython 3.14.10 for installed copies
  (decisions/0063-installed-runtimes.md:12-16) while CI tests and
  builds on Python 3.11.9 (.github/workflows/release.yml:41-43) and the
  checkout runs the system Python. No suite leg runs on the shipped
  3.14 runtime; the install self-test (`--check` compile and a demo
  health answer) is the only 3.14 check. Fix: a CI job that runs the
  ungated test subset under the pinned embeddable CPython (fetched by
  pinfetch with its hash), or move the pin and CI to one minor version.
- Item 3 "in an update whose release changes a pin": holds, with the
  self-test gap of F14.

0064 (release artifact)
- Item 8 "reproducible" and the CI byte compare: hold inside one Python
  build (release.yml:67-81).
- G2 (P1) Item 3 / Alternatives: "CI builds with the builder's exact
  Python version so its zlib matches". Nothing enforces that the
  operator's local stage uses the same Python and zlib as CI: no
  version check in tools/rel_*.py (searched for python_version,
  sys.version, zlib: no match). If they differ, the deflate bytes
  differ, CI's sums compare fails AFTER the tag is pushed
  (release.yml:73-81), no release is published, and the tag can never
  be deleted (prepush refuses deletes, rel_publish.py:586-588), so the
  version number is burned. Fix: `release.py stage` records
  `sys.version` and `zlib.ZLIB_RUNTIME_VERSION` in stage.json; a new
  publish gate `toolchain` refuses unless they equal the values a
  tracked config/release_toolchain.json holds, and a test asserts that
  file equals release.yml's `python-version`. Alternatively switch the
  ship list to `"compression": "stored"` if the payload fits (it does
  not today: 0064 item 3).
- G3 (P3) Item 3 budget: `max_zip_bytes` 2,000,000
  (config/ship_list.json:8) against a payload "about 1.9 MB" (0064
  item 3). A growing payload refuses the build on release day. Fix: a
  docs_fresh-style test that warns at 90 percent of the budget so it is
  raised in a normal commit, not in the release session.

0065 (update policy)
- Items 1 to 5 (one read per 24 h, gates, webfetch, cache, pre-release
  never newer, view shape): hold (updates.py:384-443, 201-207,
  523-545), with the clock gap of F8.
- Item 6 "size, SHA-256 against SHA256SUMS ... and the API digest":
  holds (F5).
- G4 (P1) Item 6 "applied at the next client start after a 24 h hold":
  the hold exists (update.py:206-208) but has no effect on a pulled
  release (F7). The Why ("the hold, the hash checks and the rollback
  bound the risk", Alternatives) depends on it.
- G5 (P1) Item 6 "the previous version kept and restored by itself
  when the new one fails its self-test": a failed self-test never
  reaches the marker (update.py:478-480), so that clause holds
  trivially; the restore after a failed START is only partly automatic
  (F11: not for a client that dies before startCore; F12: a good
  version can be rolled back and skipped for ever).
- Amendment 2026-11-22 "one Update now click finishes the update":
  holds in the main path (core.py:1452-1488, launcher.js:358-408),
  with the edge cases of F13.
- Item 7 "runtime fetches stay in the installer's own process; the core
  never fetches a runtime": holds (update.py:73-75, core.py:1452-1460
  only spawns).

0073 (versioning and release trigger)
- Items 1 to 5: every listed gate exists (rel_publish.py:446-457), the
  tag is annotated with `sums-sha256` (515-516, 541-543), a failed push
  removes the local tag (548-553), rehearse makes no tag (536-537).
- G6 (P2) Item 3 "a refusal changes nothing" holds before the push, but
  there is no gate between "tag pushed" and "CI published"; a red CI
  run (tests, rebuild, SBOM, attestation) leaves a public tag with no
  release (see G2, F10). Fix: a `ci-dry` gate: before publish, run the
  same workflow on the stage commit through `workflow_dispatch` with a
  `dry_run` input that skips the three release steps (needs a
  release.yml change, so an adjudicator note on decision 0064's
  permission rule; read-only token for the dry run), and require a
  green run for the stage commit.
- Item 2 immutable gate: holds (rel_publish.py:421-436); what immutable
  releases forbid (delete? re-publish as pre-release?) decides F7's
  pull procedure (section 4 Q1).

## 3. Proposed ROADMAP rows (ranked, P1 first)

P1, before the 0.2.0 tag:
- REL-BUILD-TOOLCHAIN-GATE: stage records Python and zlib versions; a
  publish gate refuses a mismatch with a tracked toolchain file equal to
  release.yml's python-version (G2) (ZERO-CLICK: the gate runs inside
  the existing publish and rehearse; nothing new to type)
- REL-UPDATE-WITHDRAW: apply-staged drops a staged version that the
  newer cached releases/latest answer no longer names, and the release
  runbook pulls a bad release by marking it pre-release (F7, G4)
  (ZERO-CLICK: the daily read already refreshes the answer; the launcher
  step already runs apply-staged)
- REL-SELFTEST-CLIENT: the update self-test also starts the new Electron
  main process with --selftest (all parts load, no window, exit 0 in
  30 s) before staging (F11a) (ZERO-CLICK: part of the existing hidden
  staging run)
- REL-CONFIRM-CLIENT: confirm needs the core health answer and a client
  heartbeat; apply-staged runs from outside the new client (supervisor
  or a stable home stub) so an early client crash is still counted and
  rolled back (F11b, G5) (ZERO-CLICK: the next start rolls back by
  itself)
- REL-CONFIRM-PATIENCE: confirm wait 180 s, rollback after 3 unconfirmed
  starts, a "no health answer" skip re-offered once after 7 days (F12)
  (ZERO-CLICK: no player act; slow first starts stop discarding good
  releases)

P2, before 0.2.1 is published:
- REL-UPDATE-E2E-RC: rc.1 to rc.2 network update on a clean Windows
  user (update --yes, trigger, Update now, relaunch, confirm,
  rollback), recorded in docs/ops (F15) (ZERO-CLICK: a scripted
  rehearsal step of release.py stage; the operator only types the
  release phrase)
- REL-REPLACE-RETRY: one retried rename helper for payload.extract,
  pinfetch.ensure_runtime and the self-test's failed-folder move
  (F3) (ZERO-CLICK: transient AV locks no longer fail an update)
- REL-RUNTIME-FOLDER-HASH: runtime folders named with a hash part, never
  removing a folder the active or previous marker names; the self-test
  runs on the new pin's interpreter (F14) (ZERO-CLICK: inside the
  existing update run)
- REL-CLOCK-SKEW: due() treats a next_at more than 8 days ahead as due;
  the hold uses the server Date offset kept at the read (F8)
  (ZERO-CLICK: no player act)
- REL-APPLYNOW-EDGES: roll back at once when the marker moved but the
  relaunch failed; forward --tray through relaunch (F13)
  (ZERO-CLICK: the client handles both by itself)
- REL-CI-RUNTIME-LEG: CI runs the ungated subset under the pinned
  embeddable CPython (G1) (ZERO-CLICK: a CI job, no local act)
- REL-CI-DRY-GATE: a dry run of release.yml on the stage commit is a
  publish gate, so a red CI never strands a pushed tag (G6, F10)
  (ZERO-CLICK: publish reads the run result through gh)
- REL-RELEASE-DRAFT-IDEMPOTENT: release.yml reuses an existing draft
  for the tag on a re-run; runbook for a failed upload (F10)
  (ZERO-CLICK: a re-run of the job finishes the release)

P3, hardening:
- REL-UPDATE-AUTO-IDLE: the core's automatic start passes --auto so the
  installer re-checks game_idle before download and self-test (F4)
  (ZERO-CLICK: unchanged; only the gate gets stricter)
- REL-DOWNLOAD-RESUME: keep and resume the runtime download, retry an
  automatic download failure after 1 h and 4 h before going daily (F1)
  (ZERO-CLICK: retries run by themselves)
- REL-DISK-PRECHECK: free-space check with a fixed reason and orphan
  version folder cleanup at the start of an update run (F2)
  (ZERO-CLICK: the Checks row names the reason; nothing to click)
- REL-DIGEST-PARTIAL: refuse a release answer with digests on some
  assets only (F5) (ZERO-CLICK: no player act)
- REL-ZIP-BUDGET-WARN: a test warns at 90 percent of max_zip_bytes (G3)
  (ZERO-CLICK: caught by the suite in a normal commit)
- REL-APPLY-WAITING-NOTE: Checks note after 72 h staged and due while
  the core never stopped (F16) (ZERO-CLICK: the note shows by itself)
- REL-INSTALL-SUMS-PRINT: install.ps1 prints the SHA-256 of
  SHA256SUMS.txt and the notes carry it (F6) (ZERO-CLICK: printed by the
  install line the player already runs)

## 4. Open questions for the web dive (2026-11-29)

Q1 GitHub immutable releases: once a release is immutable, can its
owner (a) delete the release, (b) flip it back to pre-release or draft,
(c) delete or move the tag? Does `releases/latest` stop naming a
release flipped to pre-release? This decides REL-UPDATE-WITHDRAW's pull
procedure. Also: what does `repos/<repo>/immutable-releases` return
(field names) and does enabling it apply to releases published before
it was turned on?

Q2 Release asset `digest` field: is `digest` ("sha256:<hex>") present on
every asset of `GET /repos/{owner}/{repo}/releases/latest` for assets
uploaded by `gh release upload` from a workflow, since when, and is it
documented in the REST reference (field name, algorithm prefix)? If it
is general, REL-DIGEST-PARTIAL can refuse "absent" too.

Q3 Release asset download hosts: which hosts does
`https://github.com/<o>/<r>/releases/download/<tag>/<name>` redirect to
today (release-assets.githubusercontent.com,
objects.githubusercontent.com, others)? RELEASE_HOSTS
(update.py:117-119), pinfetch.RUNTIME_HOSTS and install.ps1 `$AlHosts`
must list them all; a new host would fail every update closed.

Q4 Electron release cadence: how often does the 45.x line ship patch
releases, when is 46.0.0 due, and is 2027-04-27 still the 45.x end of
life (config/electron_pin.json:4-5)? With decision 0070's weekly patch
policy, every AshLight release that carries an Electron bump makes
each player download about 100 MB; the dive should give the expected
number of runtime downloads per month to judge whether releases should
batch Electron bumps.

Q5 Rate limits for the anonymous `releases/latest` read (60 per hour
per IP) behind shared NAT: does a 403 carry `X-RateLimit-Reset`, and
does GitHub send a `Date` header we can use as the server clock for
REL-CLOCK-SKEW?

Q6 Windows Defender and SmartScreen on an unsigned embeddable CPython
and Electron unpacked under %LOCALAPPDATA%\Programs: known first-run
scan delays or quarantines of python.exe / electron.exe from these
zips (input to the confirm timeout in REL-CONFIRM-PATIENCE and the
retry helper in REL-REPLACE-RETRY).
