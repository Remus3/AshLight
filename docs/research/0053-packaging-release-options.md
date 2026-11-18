# 0053 - Packaging and release options

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B15 / F
packaging and release options. Scope: how a stranger gets AshLight from the
public repo onto a Windows x64 PC, updates it and removes it; the artifact
to ship; code signing; how a release is cut. Neighbours: 0052 (reference
pattern), 0057 (go-public readiness), 0058 (upstream watchers).
Status: verified

## Sources (accessed 2026-11-17; the load-bearing ones re-fetched 2026-11-18, see Verification)

Web (short keys used in the body):
- EL-DIST: https://www.electronjs.org/docs/latest/tutorial/application-distribution
- EL-SIGN: https://www.electronjs.org/docs/latest/tutorial/code-signing
- EL-TIME: https://www.electronjs.org/docs/latest/tutorial/electron-timelines
- EL-SCHED: https://releases.electronjs.org/schedule
- EL-REL: https://api.github.com/repos/electron/electron/releases/tags/v45.3.3
  and that release's SHASUMS256.txt asset
- EL-UPD: https://www.electronjs.org/docs/latest/tutorial/updates
- EB-OFF: https://www.electron.build/docs/tutorials/offline-air-gapped-builds
- PY-WIN: https://docs.python.org/3/using/windows.html
- PY-DL: https://www.python.org/downloads/windows/
- PY-REL: https://www.python.org/downloads/release/python-31410/
- NODE: https://nodejs.org/en/about/previous-releases
- MS-SS: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- MS-SAC: https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview
- MS-AS: https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart
- MS-PSX: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1
- MS-WGR: https://learn.microsoft.com/en-us/windows/package-manager/package/repository
- WG-INS: https://github.com/microsoft/winget-pkgs/blob/master/doc/manifest/schema/1.12.0/installer.md
- MOTW: https://textslashplain.com/2016/04/04/downloads-and-the-mark-of-the-web/
- CAB: https://cabforum.org/2025/11/17/ballot-csc-31-maximum-validity-reduction
- SPF: https://signpath.org/terms
- GH-REL: https://docs.github.com/en/rest/releases/releases
- GH-RATE: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- GH-ATT: https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds
- GH-IMM: https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases
- GH-VER: https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/verifying-the-integrity-of-a-release
- GH-NOTES: https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
- GH-BILL: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GH-ARCH: https://github.blog/open-source/git/update-on-the-future-stability-of-source-code-archives-and-hashes/
- SC-MAN: https://github.com/ScoopInstaller/Scoop/wiki/App-Manifests
- SC-PER: https://github.com/ScoopInstaller/Scoop/wiki/Persistent-data
- SC-CRIT: https://github.com/ScoopInstaller/Scoop/wiki/Criteria-for-including-apps-in-the-main-bucket
- PEERS: `https://api.github.com/repos/<repo>/releases/latest` for three
  public PoE tools: Kvan7/Exiled-Exchange-2, SnosMe/awakened-poe-trade,
  PathOfBuildingCommunity/PathOfBuilding-PoE2
- MS-STORE: https://blogs.windows.com/windowsdeveloper/2025/09/10/free-developer-registration-for-individual-developers-on-microsoft-store/
- MS-VBS: https://techcommunity.microsoft.com/blog/Windows-ITPro-blog/vbscript-deprecation-timelines-and-next-steps/4148301
- MS-ASP: https://azure.microsoft.com/en-us/pricing/details/artifact-signing/
  (tiers and included signatures only; the page shows no dollar figure,
  the 9.99 USD comes from MS-SS)
  (these three were search summaries in the draft; fetched 2026-11-18)
- KF: https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid
  (accessed 2026-11-18, gap fill; FOLDERID_UserProgramFiles)

Local measurements (this machine, 2026-11-17; scratch copies under
`<sidecar>\Scratch`; the repo and the live client were not touched):
- M1: Authenticode status of the installed Electron 45.3.3 runtime and of
  the embeddable Python files. M8: that Electron package's downloader.
- M2: python-3.14.10-embed-amd64.zip, hash checked against PY-REL, run
  against a `git archive` copy of `server/` (`--check`, then an import of
  every module). M3: the path resolver on that copy (no kit, no `.git`),
  and with a kit default on a drive letter that does not exist.
- M4: on-disk sizes. M5: a payload zip built twice from git blobs at HEAD.
  M6: `npm install --package-lock-only --ignore-scripts` for three
  packaging tools, counting lockfile packages. M7: `git log` subjects,
  `git tag`, `git remote`.

## Summary

- Ship option 2: a portable zip with no installer framework, built by one
  stdlib release tool from the tagged source plus two hash-pinned upstream
  runtimes (embeddable CPython, prebuilt Electron): about 172 MB to
  download, 400 MB on disk, plus a 0.5 MB app-only zip that keeps updates
  tiny. Proven feasible here: the unmodified embeddable CPython 3.14.10
  imports all 70 core modules (M2); the payload is 148 files, 1.33 MB (M5).
  [SUPERSEDED in part by "Fit with 0052 and brief F" points 1, 2 and 6:
  the runtimes, the app zip and the no-framework call stay; the install is
  0052's per-user home with version folders, entered by one pasted line,
  and the full zip is only the offline installer input.]
- Decision 0041's "no packaged .exe" clause does NOT reverse. No release
  channel exists (0 tags, no remote, M7); a framework costs 49 to 276 npm
  packages against 13 today (M6); without a signing identity its stamped
  exe starts every release at zero SmartScreen reputation (MS-SS).
- Today a stranger cannot install reliably: the sidecar default is a fixed
  drive letter (F1), the stated Node floor is wrong (F2), the quick start
  runs the test suite (F3); no uninstall, no update path, no tag, no CI,
  and the version lives in three literals (F4).
- Updates: a quiet daily "new version" note from GitHub's documented
  releases endpoint, only while web data is on; one click applies a
  hash-verified app zip with preflight and rollback; never silent by
  default. [SUPERSEDED by Fit point 4: with web data on, staged by itself
  and switched at the next start after a 24 h hold, one line names it.]
  Releases: only on a `v*` tag, changelog and checksums
  generated, unsigned at first and said plainly. Order: R1 to R8 below.

## Current state

- Prerequisites: Python 3.11+ on PATH (scripts/setup.ps1:40-46, :73-77);
  Node for the client, checked as >= 20 (setup.ps1:135-145); `npm ci`, then
  Electron's own downloader (setup.ps1:230-242); pytest for build.ps1
  (scripts/build.ps1:156-164); Windows PowerShell 5.1 with
  `-ExecutionPolicy Bypass` on every call (README.md:66-73).
- Install flow (README.md:60-73): clone, setup.ps1, build.ps1, run.ps1.
  build.ps1 runs the Python and node tests and writes a stamp; it produces
  no artifact (build.ps1:5-8, :165-204).
- Launch: setup writes a per-user AshLight.lnk to the Start Menu and the
  Desktop, target `app\node_modules\electron\dist\electron.exe` with
  `"<repo>\app" --client` (setup.ps1:186-211; decision 0041 item 8). The
  client starts the core through run.ps1 (app/client/launcher.js:44-57),
  which starts core and supervisor detached through WMI
  (scripts/run.ps1:166-167, :185-186; scripts/al_detach.ps1:5-9).
- Version: `VERSION = "0.1.0"` (server/al/__init__.py:7) feeds the server
  header, /api/health, /api/version and the User-Agent
  (server/al/http.py:122, :234-244; server/al/webfetch.py:73-79). No tag,
  no changelog, no remote (M7); every push is refused unless
  AL_ALLOW_PUSH=1 is set (.githooks/pre-push:10-24).
- State and data: per-host state in `<repo>\ops\runtime` and
  `<repo>\config\local.json` (server/al/paths.py:35-41, :119-121); logs,
  caches, the Electron profile and the optional calc component under the
  sidecar root (paths.py:61-71, :124-155).
- Optional calc component: `setup.ps1 -TcCalc`, archives hash-pinned in
  config/tc_pins.json (decisions 0018, 0027): 390 MB of PoB source, 1.2 MB
  of LuaJIT, and a 276 MB toolchain only when no compiler is installed
  (config/tc_pins.json:11, :33, :47).
- Scheduled tasks: `\AshLight Autostart`, opt-in
  (scripts/autostart.ps1:42-43, :148-157), through a VBScript launcher
  (scripts/autostart_launch.vbs:1-13). `\AshLightOps\LaneLoop` is the
  operator's dev loop (tools/loop_task.py:26), never a user install's.
- Uninstall: no script (F14).
- Release policy: operator order "only on a milestone or an explicit tag,
  never per commit" (AL-NEXT-SESSION.txt:104); packaged .exe deferred
  (docs/decisions/0041-desktop-client.md:88-94; ROADMAP.md:2054); remote
  and CI an open operator row (ROADMAP.md:2059-2061); no `.github/` yet.

## Findings

F1 - A stranger's sidecar lands on a fixed drive letter, or setup fails.
paths.sidecar_root() takes the vendored kit's default whenever the kit file
loads (server/al/paths.py:44-58, :68-70); the kit itself applies it only
when the folder exists (ops/fleet_kit/fleet_lanes.py:1196-1201). M3: with
the default on a missing drive ensure_dirs() raises FileNotFoundError and
setup.ps1:80-82 stops; on a PC that has the drive, a `Sidecars\AL` folder
appears at its root. TEST-CLEAN-CLONE set AL_SIDECAR_ROOT
(ROADMAP.md:1525-1527) and tests/test_sidecar_paths.py:33-41 asserts the
unconditional default, so neither saw it. Without the kit the resolver
already falls back to `<root>\ops\runtime\sidecar` (M3). Why it matters:
the first command a stranger runs fails, or writes outside their folder.

F2 - The stated Node floor is wrong. README.md:62-64 and setup.ps1:5, :141
accept Node 20. The pinned Electron 45.3.3 and its downloader declare
`node >= 22.12.0` (app/package-lock.json:21-23, :39-41, :89-91), and the
downloader is an ES module loaded with require() (M8). Node 20 is
end-of-life since 2026-03-24 (NODE). UNVERIFIED: which Node 20 minors fail in practice
(local Node is 24.15.0). Why it matters: a stranger on Node 20 passes the
check and then fails at "Electron download failed".

F3 - The quick start makes a stranger run the test suite. README.md:67-69
lists build.ps1 as step 2; it needs pytest and runs the whole suite (2316
tests at the last gate, AL-NEXT-SESSION.txt:136-137) through a fleet gate
(build.ps1:165-176). It builds nothing a player needs.

F4 - No single version source, no tags. Three literals
(server/al/__init__.py:7, app/package.json:3, app/package-lock.json:3, :9),
no test that ties them (app/test/about.test.js:22-24 only uses the number
as a fixture), 0 tags in 370 commits at a55fb3b (M7). The User-Agent floor rule
("names AshLight and its version") depends on this number being right.

F5 - State sits inside the program tree: `ops\runtime` (token, consent, run
history, builds) and `config\local.json` (paths.py:35-41, :119-121;
app/main.js:24-28). A new-folder install loses them; an in-place update
must never replace them.

F6 - The launch chain assumes a PATH Python and npm's layout: six lookups
of `python` / `py` (setup.ps1:40-46, build.ps1:23-29, run.ps1:55-61,
stop.ps1:28-34, autostart.ps1:50-56, app/client/launcher.js:13) and three
hard paths to `app\node_modules\electron\dist` (server/al/procs.py:60,
run.ps1:145, setup.ps1:155). A bundle needs each to prefer its own runtime.

F7 - The payload is small and nearly self-contained. server/, web/, app/
without its tests, scripts/, config/, tools/tc_pin.py, the kit's tokens.css
and the license files are 148 files, 1,333,933 bytes; 542,447 bytes
deflated; two builds from git blobs were byte-identical (M5). The one kit
file the running app needs is `ops/fleet_kit/tokens.css`
(server/al/__main__.py:168-169; server/al/http.py:229-230). Without `.git`
the code hot reload turns itself off (server/al/hotreload.py:64-76, M3).

F8 - The embeddable CPython runs the core unmodified.
python-3.14.10-embed-amd64.zip is 12,619,664 bytes, SHA-256
90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159 as
published (PY-REL, M2): 37 files, 24.5 MB extracted, with python.exe,
pythonw.exe and the C runtime DLL, without pip or Tcl/Tk (PY-WIN).
`python -m server.al --check` returned 0 and all 70 `server.al` modules
imported (M2). Two facts shape the layout: under the shipped
`python314._pth` the current directory is not on sys.path (the run failed
until one line naming the app root was added), and the registry and
PYTHON* variables are ignored (PY-WIN), isolating the bundle from any
installed Python. The classic installer is deprecated since 3.14 and will
not be built for 3.16 or later (PY-WIN); the embeddable package is still
listed for 3.15.2 (PY-DL).

F9 - Electron's prebuilt zip is pin-ready, but its exe is unsigned.
electron-v45.3.3-win32-x64.zip is 158,325,836 bytes, SHA-256
49dd2d3875944f08de03d34595cd30093c588b9edcabb41a0ac481028a3a5a8a in the
release's SHASUMS256.txt and in the API `digest` field (EL-REL); 374.4 MB
extracted, of which electron.exe 250.1 MB and locales 51.2 MB (M4). M1:
electron.exe and five of six DLLs checked are NotSigned; every embeddable
Python exe, DLL and pyd checked is validly signed by the Python Software
Foundation. Electron supports its latest three majors; 45 ends about
2027-04-27, tentative (EL-TIME, EL-SCHED): the pin moves twice a year.
Bundling both changes the notices: THIRD-PARTY.md:3-5 says nothing is
bundled, and CLAUDE.md wants a recorded license check first; the license
files ship inside both runtimes (M2, M4).

F10 - What "unsigned" means for a download. SmartScreen warns on unknown
files that carry the Mark of the Web ("Windows protected your PC", then
Run anyway; enterprise policy can forbid that); an unsigned file rebuilds
reputation from zero with every new version; EV certificates no longer
skip the warning (MS-SS). Windows 11 Smart App Control in enforcement mode
blocks unknown unsigned code whether marked or not (MS-SAC, MS-SS).
Browsers add the mark and Explorer's zip extraction copies it to every
file; curl.exe and Invoke-WebRequest add none; the checks run on shell
launches, not on CreateProcess (MOTW, MS-PSX). Here: run.ps1's WMI starts
are CreateProcess (no prompt); the Start Menu shortcut is a shell launch
of the unsigned electron.exe (a prompt is possible when the file is
marked); a framework-stamped `AshLight.exe` would be a new unknown hash
every release. UNVERIFIED: how either rates the upstream electron.exe.

F11 - Signing costs and who can get it. Azure Artifact Signing starts at
9.99 USD a month (MS-SS; the Basic tier includes 5,000 signatures a month,
MS-ASP) with no hardware token,
but public-trust validation is open to individual developers only in the
United States and Canada, and to organizations in a listed set of
countries (MS-AS). Classic certificates need keys on certified hardware
since June 2023 (EL-SIGN) and last at most 460 days since 2026-03-01
(CAB); prices UNVERIFIED. SignPath Foundation signs open-source projects
free of charge but wants an OSI license for every component (Apache-2.0,
MIT and the PSF license qualify), an already released version, a "Code
signing policy" section with named author / reviewer / approver roles and
a privacy policy on the home page, MFA for the team, artifacts built from
the project's own source, an uninstall path, and it runs its own
reputation review (SPF). R5's uninstall script and R6's CI build feed
that list. The Microsoft Store signs MSIX packages; registration has been
free for individuals since 2025-09-10 in about 200 markets (MS-STORE). GitHub attestations and immutable releases are
free provenance (GH-ATT, GH-IMM, GH-VER); SmartScreen does not read them.

F12 - Installer frameworks cost much and do not solve Python. Lockfile
sizes (M6): 13 packages today (docs/audit/2026-11-17-audit.md:161-164);
@electron/packager 20.3.0: 49; Electron Forge 8.0.1 with the Squirrel and
zip makers: 163; electron-builder 26.18.0: 276 (the last two each pull a
package with an install script). electron-builder also fetches toolsets at
build time (NSIS, winCodeSign, 7-Zip; checksums pinned in the tool) and
its docs describe pre-seeded caches for offline builds (EB-OFF). That page
is the docs of the not yet released v27; it says only that cache layouts
older than 26.15 are not read, so offline builds on a released version are
UNVERIFIED. The hand-off's "not offline" (AL-NEXT-SESSION.txt:30,
ROADMAP.md:2054; decision 0041 item 9) may be outdated in that detail; the
dependency cost stands. Electron's built-in Windows updater is built on
Squirrel.Windows and its helper module checks at startup, then every ten
minutes (EL-UPD),
against decision 0013 while web data is off. No framework ships the
Python core; each needs F8's runtime as an extra resource. Peers (PEERS):
both Electron PoE overlays publish an electron-builder setup exe (104 to
109 MB), a portable exe and updater metadata; Path of Building PoE2 a
setup exe and a 383 MB Portable.zip - a form PoE players already know.

F13 - Package managers are thin manifests on a stable artifact. Scoop: a
JSON manifest (url, hash, shortcuts, persist, checkver, autoupdate) that
can live in the project's own repository as a bucket; `persist` keeps
named files and folders across updates and uninstalls (SC-MAN, SC-PER);
the main bucket takes only non-GUI tools, with about 500 stars and 150
forks as its popularity example (SC-CRIT), so AshLight never fits it and
its own bucket is the route. winget: a zip needs a nested installer, and
the `portable` kind maps commands to exe files (WG-INS); a submission must
install and uninstall cleanly for both admins and non-admins, run
non-interactively, come from the publisher's own release location and
pass several antivirus engines (MS-WGR). A .cmd entry
point is a poor fit, and replace-on-upgrade would drop in-folder state.

F14 - Nothing uninstalls. stop.ps1 stops the processes
(scripts/stop.ps1:77, :106) and `autostart.ps1 -Disable` removes the task
(autostart.ps1:182-183), but nothing removes the two shortcuts
(setup.ps1:200-204), `ops\runtime`, `config\local.json`, the sidecar
(logs, caches, the Electron profile at `Cache\overlay-profile`,
app/main.js:105-109) or up to 668 MB of optional calc archives plus their
extracted trees (config/tc_pins.json:11, :33, :47). Nothing is written
into game folders, by design (decisions 0031, 0033, 0034).

F15 - Update options weighed; the building blocks sit in the wrong place.
- Blocks: a rate-limit-aware GET of `releases/latest` with the truthful
  User-Agent (tools/tc_drift.py:114-152); downloads checked by size and
  SHA-256 with safe extraction (tools/tc_pin.py:239, :258, :299, :339,
  :384); a code preflight (`--check`, server/al/__main__.py:38-66); stop /
  run convergence (decision 0010); the web-data gate
  (server/al/webfetch.py:92-96). But the drift check runs from the dev
  loop tick (decision 0025 item 1): an update check must live in the core.
  The endpoint is documented and allows 60 unauthenticated requests an
  hour per IP (GH-REL, GH-RATE).
- Notice only: zero clicks to know, four or five acts to update by hand.
- Notice plus one click: one act per update, with preflight and rollback;
  the click is the player's consent to new code on their PC.
- Automatic when idle: zero acts, but one bad or hijacked release reaches
  every install within a day, unsigned. Opt-in at most, later.
  [SUPERSEDED by Fit point 4: default on with web data, held 24 h,
  self-test and rollback.]
- While web data is off there is no check at all (decision 0013, read
  literally); the release page is the fallback and the README says so.

F16 - Release mechanics. Commit subjects at the draft commit a55fb3b (370
commits): 150 are merge commits, 85 of them with a `merge: <ROW-ID> ...`
subject and 39 with git's default "Merge branch"; of the 220 non-merge
commits, 160 (73 percent) follow `type(scope): text`, with 64 feat, 22 fix
and 41 docs; the scope is usually the ROADMAP row id (M7, recounted in
verification). GitHub's generated notes list merged pull
requests only (GH-NOTES); this repo merges locally, so they would be
empty. Done ROADMAP rows are pruned at /done (ROADMAP.md:3-5): a changelog
must read them from git history. Standard runners are free for public
repositories (GH-BILL). GitHub's "Source code" archives are not promised
byte-stable; uploaded assets are the stable route (GH-ARCH). Immutable
releases lock tag and assets and add a release attestation (GH-IMM); one
PoE peer already publishes them (PEERS). Zip bytes repeat when entries
are sorted, times fixed and bytes read from git blobs (M5). UNVERIFIED:
deflate output across Python / zlib builds; store the small zip
uncompressed, or pin the builder's Python.

F17 - Options compared (impact, effort, risk).
- 1 Source zip plus bootstrap, user installs Python and Node: impact L
  (two installers, PATH and version traps); effort S (R1 only); risk M
  (support load). Stays as the developer path.
- 2 Portable zip, pinned runtimes inside, no framework (the manual route
  Electron documents, EL-DIST): impact H (download, extract, double-click;
  works offline); effort M; risk M (a 172 MB asset, a possible SmartScreen
  prompt, pin upkeep). A net-install variant (0.5 MB zip, runtimes fetched
  and hash-checked on first run) falls out of the same tool.
- 3 Installer frameworks, all needing option 2's Python work first:
  @electron/packager (49 packages) gives a branded exe, worth it only
  with a signing identity; Forge with Squirrel (163) a per-user installer
  and an updater that conflicts with decision 0013; electron-builder with
  NSIS (276) is the peers' choice, effort L, risk H; MSIX must be signed,
  free through the Store, and needs a per-user data root.
- 4 Package managers: scoop is effort S on top of 2; winget only on top of
  a signed exe or installer (F13).

## Recommendations

R1 - Make the source install work for a stranger.
- Action: the sidecar default follows the kit's own rule (kit folder
  exists, else inside the tree); Node floor 22.12 in setup.ps1 and README;
  quick start = setup.ps1 then run.ps1, build.ps1 moves to CONTRIBUTING.
- Impact: H, off the operator's machine the first command fails (F1-F3).
  Effort: S. Risk: low; the operator's machine keeps its sidecar.
- ToS check: no floor rule touched; the fallback path is inside AshLight's
  own folder, never a game folder ("never modify any game file").
- Depends on: nothing. Files likely touched: server/al/paths.py and its
  test, scripts/setup.ps1, README.md, CONTRIBUTING.md.
- Acceptance test: a pytest points the kit default at a missing drive and
  expects sidecar_root() inside the tree and ensure_dirs() to pass;
  TEST-CLEAN-CLONE re-run as a stranger (AL_SIDECAR_ROOT unset, the kit
  folder absent); no build.ps1 in the README quick start.
- ZERO-CLICK: no new step; the same two script calls, no prompt.

R2 - One version, enforced.
- Action: server/al/__init__.py VERSION stays the source; a test fails
  when app/package.json or the lockfile differ; `tools/release.py bump`
  edits all three; a tag must equal `v` + VERSION.
- Impact: M (truthful User-Agent, update comparison, artifact names).
  Effort: S. Risk: low. Depends on: nothing. Files likely touched:
  tests/test_version.py, tools/release.py, app/package.json and its lock.
- ToS check: keeps the floor rule "truthful User-Agent naming AshLight and
  its version" true by construction.
- Acceptance test: the test fails on a deliberate mismatch; `release.py
  bump --check` is a no-op at HEAD.
- ZERO-CLICK: one command inside the release step; nothing for the player.

R3 - Release layout with pinned runtimes and one resolver each.
- Action: `config/runtime_pins.json` (embeddable CPython 3.14.x, Electron
  zip: url, sha256, size, license), fetched with the tc_pin code into
  `runtime\python` and `runtime\electron`; one PowerShell helper and
  launcher.js prefer the bundled `python(w).exe`, `paths.electron_exe()`
  the bundled electron.exe; the `._pth` gains one line for the app root;
  state stays inside the folder (portable). [SUPERSEDED by Fit points 1
  and 2: runtimes in `<home>\runtime\<name>-<ver>\`, state in
  `<home>\data\`.]
- Impact: H. Effort: M. Risk: M - six lookups and three paths move (F6);
  covered by the run / stop / procs tests plus one release-layout test.
  Keep passing the app folder to electron.exe (never `resources\app`), so
  `app.isPackaged` stays false and the devTools gate at app/main.js:30
  behaves as today.
- ToS check: the runtimes are public web data from python.org and GitHub
  release assets, no GGG endpoint, truthful User-Agent, no cookie; fetched
  by setup or the release build, never by the running core (decision 0018
  item 6).
- Depends on: R1. Files likely touched: config/runtime_pins.json,
  tools/tc_pin.py, server/al/paths.py, server/al/procs.py, scripts/*.ps1
  (one shared helper), app/client/launcher.js, THIRD-PARTY.md, a decision
  holding the license check (F9).
- Acceptance test: in a scratch copy with no Python or Node on PATH,
  `runtime\python\python.exe -m server.al --check` returns 0 and `run.ps1
  -NoBrowser` on a spare port answers /api/health; a wrong pin hash
  refuses with exit 2, as tc_pin does.
- ZERO-CLICK: fetched inside setup or the release build; nothing to install.

R4 - One release tool: tools/release.py (called by `build.ps1 -Package`).
- Action: from a tag, write `AshLight-<ver>-win-x64.zip` (portable),
  `AshLight-<ver>-app.zip` (payload only), `SHA256SUMS.txt` and
  `release.json` (version, runtime pins, per-file sha256), with sorted
  entries, the tag's commit time and bytes read from git blobs; refuse a
  dirty tree or a tag / VERSION mismatch.
- Impact: H. Effort: M. Risk: low to M (zip determinism across Python
  builds, F16).
- ToS check: artifact names and contents carry no GGG trademark or art,
  and the README with the disclaimer ships inside (floor: branding,
  disclaimer); the game-data snapshot and the calc component are never
  bundled (decisions 0009, 0018).
- Depends on: R2, R3. Files likely touched: tools/release.py,
  scripts/build.ps1, an allow-list in config/, tests/test_release_tool.py.
- Acceptance test: two builds of one tag give identical SHA256SUMS; the
  app zip holds only allow-listed paths (no tests, no docs; from ops only
  tokens.css and the kit license files); the portable zip starts on a
  clean Windows VM with no Python or Node.
- ZERO-CLICK: one command; none at all once R6 runs it.

R5 - First run and uninstall for the release layout.
- Action: `AshLight.cmd` at the zip root runs setup (config copy,
  shortcuts; no npm, no pytest) then run.ps1. `scripts\uninstall.ps1`
  stops the processes, removes the autostart task and the two shortcuts
  when they point into this folder, and only with `-PurgeData` sends
  config and state to the Recycle Bin and deletes caches and logs; it
  prints what is left (the folder itself). [SUPERSEDED by Fit points 5
  and 6: no `AshLight.cmd`; install.ps1 installs; uninstall.ps1 at the home
  root, also behind Apps & features, takes `-Purge` and keeps only
  `data\`.]
- Impact: H. Effort: M. Risk: M - a delete script; every path comes from
  the resolver, anything outside the install and its sidecar is refused.
- ToS check: never touches a game folder, Client.txt or files the player
  saved elsewhere (floor: never modify any game file); stops only pids
  proven ours (server/al/procs.py), never the game process.
- Depends on: R3. Files likely touched: AshLight.cmd,
  scripts/uninstall.ps1, scripts/setup.ps1, README.md,
  tests/test_uninstall.py (dry run with tripwires, like test_autostart).
- Acceptance test: `-DryRun` lists exactly the task, two links and the
  data paths; a real run in a scratch install leaves no process, task or
  link; without `-PurgeData` config and state survive; a link that points
  at another install is left alone.
- ZERO-CLICK: install is extract plus one double-click; uninstall is one
  command; data removal needs the switch (consent, not a floor rule).
  [SUPERSEDED by Fit point 6: one pasted line; uninstall is one click in
  Apps & features.]

R6 - Tag-triggered CI release with a generated changelog.
- Action: a GitHub Actions workflow on `v*` tags: tests, tools/release.py,
  tools/changelog.py (feat -> Added, fix -> Fixed, scope mapped to the
  ROADMAP row title read from the tag range's ROADMAP diff), a provenance
  attestation, a draft release, the assets, then publish as immutable;
  actions pinned by commit; the kit's identity guard stays required.
- Impact: H. Effort: M. Risk: M - the first CI in the tree; needs the
  remote.
- ToS check: releases are free (floor: no commercial revenue); release
  text uses the game's name only descriptively and carries the
  disclaimer; no GGG art in release images.
- Depends on: R4; operator acts: the remote, immutable releases on
  (ROADMAP.md:2059-2061). Files likely touched: tools/changelog.py,
  .github/workflows/release.yml, CHANGELOG.md, tests/test_changelog.py.
- Acceptance test: a release-candidate tag in a test repository yields a
  release whose assets match SHA256SUMS; `gh attestation verify` and `gh
  release verify-asset` pass; the notes list every feat / fix subject in
  range; a plain commit triggers nothing.
- ZERO-CLICK: pushing the tag is the only act; the rest needs none.

R7 - In-app update notice from the core.
- Action: server/al/updates.py: at most one GET per 24 h of
  `releases/latest` for the project's repository (rate-limit headers
  honoured as tools/tc_drift.py:118-133 does; If-None-Match / ETag as the
  price book sends it, server/al/ninja.py:176-178; tc_drift sends no
  ETag), only while `web_data` is
  on; a newer tag adds one Checks row and a Settings line linking the
  release page; the repository name is one constant, empty = feature off.
- Impact: M. Effort: S to M. Risk: low.
- ToS check: public web data from a documented GitHub endpoint, not GGG
  and not the trade site; truthful User-Agent, no cookie; inside the one
  web-data opt-in (decision 0013); a network timer is not a clipboard or
  screen watcher. Settled-decision note: decision 0018 item 6 states the
  running core "fetches nothing from GitHub"; R7 changes that fact (under
  0013's opt-in, not 0018's setup opt-in), so its decision note amends
  0018 item 6's wording. Nothing in 0018 reverses.
- Depends on: R2 and the public repository. Files likely touched:
  server/al/updates.py, server/al/core.py, web/status.js, README.md (the
  privacy text names the daily GitHub request), tests/test_updates.py.
- Acceptance test: with web_data off the injected transport is never
  called; with it on, one call per 24 h, a 304 costs no parse, a 403 with
  a reset time is honoured; the note text passes the design voice tests.
- ZERO-CLICK: the note appears by itself; no toast, no prompt.

R8 - One-click update with verification and rollback.
- Action: "Update now" on that Settings line starts a detached updater:
  fetch release.json, SHA256SUMS and the app zip (runtimes only when a
  pin changed), verify size and SHA-256, stage, run the staged tree's
  `--check`, stop through scripts/stop.ps1 (its stop.request keeps the
  keepalive supervisor from restarting the core mid-swap, decision 0005),
  back up the replaced files, swap by manifest (never
  `config\local.json` or `ops\runtime`), start, wait for /api/health; on
  failure restore and say so in Checks. Keep one previous version.
  [SUPERSEDED by Fit point 2: stage into `<home>\app\<ver>\`, switch the
  marker, roll back by switching back; no in-place swap, no backup copy.]
- Impact: M. Effort: M to L. Risk: M to H - a self-modifying install;
  held by the preflight, the backup and the health gate.
- ToS check: writes only inside AshLight's own folder and restarts only
  its own processes; never changes the Client.txt consent, never turns
  web data on; no game file or process contact.
- Depends on: R4, R6, R7. Files likely touched: scripts/update.ps1 or
  server/al/updater.py, server/al/http.py (one token-guarded POST), web/,
  tests/test_updater.py.
- Acceptance test: a scratch install of version A updates to B from a
  local test server; a corrupted asset is refused with nothing changed; a
  B that fails `--check` or health rolls back to A; state files are
  byte-identical before and after.
- ZERO-CLICK: one click per update, kept for consent (new code on the
  player's PC), not by the ToS floor; "install when the game is idle"
  (decision 0029) is a later opt-in decision. [SUPERSEDED by Fit point 4:
  zero clicks with web data on, a Settings switch restores the click.]

R9 - Signing track: unsigned first, said plainly; revisit with an identity.
- Action: a README "Windows may warn" section (what the prompt is; how to
  verify the download with SHA256SUMS, the attestation and verify-asset);
  the operator checks Artifact Signing eligibility and applies to SignPath
  after the first public release; with an identity, add @electron/packager
  for a signed `AshLight.exe` and reopen 0041 item 9.
- Impact: M, later. Effort: S now. Risk: low.
- ToS check: the publisher name on a certificate or listing must not
  suggest GGG affiliation (floor: never present as endorsed by GGG).
- Depends on: R4 (a zip to test); operator acts (identity, payment).
  Files likely touched: README.md, SECURITY.md, docs/decisions/.
- Acceptance test: the section exists; a clean Windows 11 VM run records
  what SmartScreen and Smart App Control do with the portable zip (settles
  F10's UNVERIFIED line).
- ZERO-CLICK: nothing for the player; the VM check is scripted.

R10 - Pin watch and a launcher without VBScript.
- Action: a dev-loop watch for Electron patch releases in the pinned
  major, its end-of-life date and CPython patch releases (TC-DRIFT's
  shape; details in 0058). Replace scripts/autostart_launch.vbs:1-13 with
  a pythonw entry point: Windows is retiring VBScript (a feature on demand
  since 24H2, off by default around 2027, then removed; MS-VBS).
- Impact: M (security patches reach players). Effort: S each. Risk: low.
- ToS check: dev-tool reads of GitHub's documented API with the truthful
  User-Agent; autostart stays opt-in (decision 0011), no game contact.
- Depends on: R3. Files likely touched: tools/, scripts/autostart.ps1,
  tests/test_autostart.py.
- Acceptance test: a fixture release newer than the pin produces one loop
  line; the registered task action runs no wscript.
- ZERO-CLICK: the watch runs on the loop tick; a pin move is a gated commit.

R11 - Scoop manifest written by the release tool; winget deferred.
- Action: release.py writes `bucket/ashlight.json` (url, hash, shortcuts,
  persist for config and state, checkver and autoupdate on GitHub
  releases); the README shows the two scoop commands. winget waits for a
  signed exe or installer (F13).
- Impact: L to M. Effort: S. Risk: low. Depends on: R6. Files likely
  touched: tools/release.py, bucket/ashlight.json, README.md.
- ToS check: the manifest text is descriptive, carries no GGG mark and
  links the disclaimer; free (floor: branding, no revenue).
- Acceptance test: in a clean VM `scoop install` from the bucket starts
  the client, `scoop update` keeps config and state, `scoop uninstall`
  removes the shortcuts.
- ZERO-CLICK: `scoop update` is the user's one command; the manifest
  refreshes itself at each release.

Sequence for the waves: R1 and R2 together first; R3, then R4; R5 and R7
in parallel once R3 and R2 are in; R6 as soon as R4 is in and the remote
exists; R8 after R6 and R7; R9 and R10 any time after R4; R11 after R6.

Decisions this path needs (one decision note, before R3's code):
[Items 1, 2, 4 and 7 SUPERSEDED in part by "Fit with 0052 and brief F":
1 = app zip, offline full zip and install.ps1, no framework; 2 = home
`%LOCALAPPDATA%\Programs\AshLight`, state in `data\`; 4 = automatic staged
apply with a 24 h hold under web data; 7 = `-Purge`.]
1. Artifact form: portable zip plus app zip, no installer framework.
   Decision 0041 item 9 stands; restate its trigger as "a public release
   exists AND the operator holds a signing identity" (F10 to F12).
2. State in the release layout: inside the install folder (recommended;
   works today, M3) or `%LOCALAPPDATA%\AshLight` (an MSIX / Store or
   winget route would need it).
3. Runtime pins: the CPython line, the rule for moving pins, the license
   check for redistributing Electron and CPython (F9).
4. Update policy: notice only under web data; one click to apply;
   automatic apply never, or opt-in later.
5. The project's public repository name in tracked files: a hygiene-rule
   exception (see 0057).
6. Versioning: SemVer 0.y.z, tag `vX.Y.Z` equals VERSION; first public tag.
7. Uninstall consent: data kept unless `-PurgeData`. 8. Signing: none at
   first; identity and budget later (operator).
9. Decision 0018 item 6 wording: the core may make one documented GitHub
   releases read a day under web_data (R7); an amendment, not a reversal.

## Fit with 0052 and brief F

Added 2026-11-18 (gap fill). Brief F asks for deployment like the
reference app: one-step install, an update path, a clean uninstall (0052
line 4 and the plan brief). 0052 maps that app to a per-user home with
`app\<version>\`, a marker, data outside the code, an Apps & features entry
and staged updates (0052 P4, P6, M8 to M12, R1, R4 to R6). This note's
first draft chose an extract-and-run folder instead. Plan 05 takes ONE
design; the six points below pick it. Every pick keeps F8 / F9 / R3's
pinned runtimes (embeddable CPython and the prebuilt Electron zip, by hash)
and F12 / decision 0041 item 9's no-framework finding: 0052's installer is
itself a PowerShell bootstrap plus stdlib code, no framework (0052 R4).

1. Home: 0052 wins. One per-user home `%LOCALAPPDATA%\Programs\AshLight`
   (Windows' per-user Programs known folder, FOLDERID_UserProgramFiles,
   default path `%LOCALAPPDATA%\Programs`, KF), with `-InstallDir` for the
   operator (0052 Q1); all player state in `<home>\data\` (today's
   `ops\runtime` and `config\local.json`, 0052 M9), logs / cache / temp in
   sibling folders, never inside a version folder. Why, against brief F: an
   update must not carry state across, and a clean uninstall must be able
   to keep exactly one folder; an extracted folder lives wherever the
   browser put it (often Downloads or a synced Desktop), so neither is
   reliable. It also settles this note's open question on state location
   (closed below). Note: 0052 itself names two homes, `%LOCALAPPDATA%\Programs\AshLight`
   (P4, Q1) and `%LOCALAPPDATA%\AshLight` as R1's fallback; this pick is the
   first, and plan 05 should state it once. ToS check: "never modify any
   game file": the home is AshLight's own; the resolver refuses a home in a
   Steam library or game folder (0052 R1). Superseded: R3 "state stays
   inside the folder (portable)"; decision 2 below.
2. Code layout: 0052 wins. `<home>\app\<version>\` plus the marker
   `install.json` {version, previous, ...}; the runtimes sit in
   `<home>\runtime\` in one folder per pin (for example
   `runtime\electron-45.3.3\`), so a pin move also builds beside. Update =
   stage beside, self-test, atomic marker switch; rollback = switch back;
   one previous version kept (0052 P6, M23, M25). Why, against brief F: the
   old version is never modified, so a failed update cannot leave a
   half-copied tree, and rollback needs no backup copy; an in-place swap
   on Windows also fights files held open by the running electron.exe and
   python DLLs. The extra disk cost is one app payload, about 1.3 MB (F7).
   R8's checks (size and SHA-256, staged `--check`, stop through stop.ps1,
   /api/health gate, report in Checks) all stay. ToS check: writes only
   inside the home, restarts only pids proven ours (server/al/procs.py),
   no game file or process contact. Superseded: R8 "back up the replaced
   files, swap by manifest".
3. Apps & features entry: yes (0052 M12, R4, R5). One per-user uninstall
   key whose version is rewritten and read back at each switch, uninstall
   string = the home-root uninstall.ps1. Why, against brief F: a clean
   uninstall that a player can find is where Windows lists apps; winget
   also matches installed packages through these entries and knows
   per-user ("user" scope) installers (WG-INS). Caveat kept from 0052 Q6:
   Microsoft documents only the machine-wide key; the per-user key works in
   the reference app on Windows 10 and 11 (UNVERIFIED in Microsoft docs).
   ToS check: one per-user registry key, no game file, no admin. This note
   had no entry; nothing to supersede beyond point 6.
4. Update consent: 0052 wins, with a hold. With web data on, the core
   checks once a day (R7), then downloads, verifies and stages by itself
   and switches at the next client start; one Checks / Settings line names
   the new version; "Update now" switches at once; a Settings switch
   "Install updates automatically" (default on) turns the apply step back
   into the click. Hold: a release is applied only when its
   `published_at` is at least 24 h old. Why, against brief F and the tree's
   rules: CLAUDE.md "Minimal interaction" orders that in play the app
   updates itself with no clicks; brief F wants an update path, which
   0052 R6 delivers with zero acts. This note's objection (one bad or
   hijacked release reaches every install within a day, F15) is met by the
   self-test plus automatic rollback (0052 R6), immutable releases (tag
   and assets cannot be changed after publication) and the hold: during it
   the operator can still unmark a bad release as "latest", which GitHub
   allows on an immutable release (GH-IMM, re-read 2026-11-18), so
   `releases/latest` stops offering it. Note: the reference app itself
   ships auto mode off by default (0052 P6); the CLAUDE.md order outranks
   that. With web data off: no check, no download; the Settings tab shows
   the version and a releases link (decision 0013). ToS check: GitHub's
   documented releases endpoint and asset hosts only, truthful User-Agent,
   no cookie, inside the web_data opt-in (decision 0013); a daily network
   timer is not a clipboard or screen watcher; downloads run at
   below-normal priority ("must not cost game FPS"). Superseded: Summary
   "one click applies ... never silent by default"; F15's "Opt-in at most,
   later"; R8 ZERO-CLICK; decision 4; the Rejected bullet on silent updates
   (amended there).
5. Uninstall: 0052's switch name. `uninstall.ps1` at the home root (also
   the Apps & features uninstall string), `-Purge` and `-DryRun`. Without
   `-Purge` only `<home>\data\` survives (Client.txt consent, run history,
   builds, price watch, local.json) plus any filter or `.build` file the
   player saved elsewhere, which the last lines name; code, runtimes,
   cache (including the Electron profile and the optional calc archives),
   logs, temp, marker, shortcuts, the uninstall key and the opt-in
   autostart task go. `-Purge` sends `data\` to the Recycle Bin (FLEET item
   9) and removes the home. Exit 1 with one line while anything remains.
   Why, against brief F: one name across 0052 and 0053 (the reference app
   uses `--purge`), and "clean" means nothing of AshLight's but the
   player's own data is left, which this note's in-folder layout could not
   promise. ToS check: never touches a game folder or Client.txt ("never
   modify any game file"); stops only pids proven ours. Superseded: R5's
   `-PurgeData` and "prints what is left (the folder itself)"; decision 7.
6. First install: one pasted line wins as the primary route, the verified
   local zip as the documented second. The line runs the release's
   `install.ps1` from the `/releases/latest/download/` URL (0052 P3, R4);
   it fetches SHA256SUMS, the app zip and the hash-pinned runtimes,
   verifies every hash, self-tests, then writes marker, shortcuts and the
   uninstall key, and opens the app. The second route: download
   `install.ps1`, the app zip and SHA256SUMS (or the full
   `AshLight-<ver>-win-x64.zip`, kept from R4 as the offline input), check
   them with `gh release verify-asset` or the attestation, run
   `install.ps1 -Zip <file>`. Why, against brief F: brief F names a
   one-step install; it is also the only route that avoids a SmartScreen
   prompt for the unsigned electron.exe, because PowerShell downloads
   carry no Mark of the Web while a browser download plus Explorer
   extraction marks every file (F10). The cost this note raised (unreviewed
   remote code) is limited to the small bootstrap script on an immutable
   release, which verifies everything else; reviewers have route two.
   ToS check: install-time downloads of AshLight's own runtime from GitHub
   and python.org with a truthful User-Agent, no GGG host, no cookie; the
   player pastes into their own PowerShell, nothing is sent to the game.
   Superseded: R5 "`AshLight.cmd` at the zip root" and "install is extract
   plus one double-click"; Summary "download, extract, double-click"; the
   Cut-or-merge bullet "drop the idea of a separate installer"; the
   Rejected bullet on a one-line web command; decision 1's "portable zip"
   (the zip stays as an installer input, not a run-in-place folder).

Kept unchanged: F1 to F4 and R1 / R2 (the source install and one version
are needed under either design), R3's pins and resolver work (pointed at
`<home>\runtime\` instead of the folder), R4's release tool (it also
emits `install.ps1`), R6, R7, R9, R10. R11 (scoop) needs a re-check
against the home layout (open question below).

## Cut or merge

- Cut build.ps1 from the stranger's quick start (F3); it stays the
  developer gate and gains `-Package` (R4).
- Merge the six Python lookups and three Electron paths into one helper
  and one resolver function (F6, R3).
- Cut npm from the end-user path: the pinned fetcher downloads the same
  Electron zip npm would; Node stays a developer dependency (`npm test`).
- Merge first run into setup plus run behind one `AshLight.cmd` (R5), and
  drop the idea of a separate installer: extract-and-run plus an
  uninstall script covers install, repair (extract again) and removal.
  [SUPERSEDED by Fit point 6: 0052's install.ps1 is the installer; a
  re-run repairs.]

## Rejected

- Silent automatic updates by default: new code without the player's act,
  and one hijacked release reaches every install within a day (consent
  and supply chain, not a floor rule); opt-in at most. [Amended by Fit
  point 4: still rejected is an update with no notice at all; automatic
  staged apply with a named line, a 24 h hold and rollback is chosen.]
- Any install, update or uninstall step that writes into a game folder
  (placing the loot filter or `.build` file "for convenience"): floor
  "never modify any game file"; decisions 0031, 0033, 0034.
- Checking whether the game runs before an update or uninstall: decision
  0029 rules out process-presence checks, and the updater needs none.
- An update check through any GGG host, or bundling the game-data
  snapshot, PoB source or LuaJIT: floor (documented endpoints only) and
  decisions 0009, 0018, 0027.
- Paid or donation-gated downloads, supporter builds, ads on the release
  page (floor: no commercial revenue from GGG intellectual property); GGG
  art, logos or the game's name in the artifact, shortcut, publisher or
  store listing name (floor: trademarks and branding).
- A self-signed certificate with instructions to trust it (the same
  SmartScreen result as unsigned, MS-SS), or telling users to switch
  SmartScreen or Smart App Control off: unsafe advice.
- Machine-wide installs that need admin (HKLM, services, Program Files):
  against the per-user, no-admin design (decisions 0011, 0041 item 8).
- A one-line "download and run" web command in the README: it runs
  unreviewed remote code; the documented flow is download, verify, run.
  [SUPERSEDED by Fit point 6: the pasted line is the primary route (brief
  F, no Mark of the Web); download, verify, `-Zip` is the second.]
- electron-updater or update-electron-app as shipped: they poll on their
  own schedule regardless of the web-data opt-in (EL-UPD against decision
  0013) and need a packaged app.

## Open questions

- How do SmartScreen and Smart App Control treat the unmodified upstream
  electron.exe? UNVERIFIED; needs R9's clean Windows 11 VM run. A
  SmartScreen prompt is avoidable with the net-install variant (no marked
  binaries); a Smart App Control block is not: then no unsigned Electron
  build runs on those PCs, under any option, until the exe is signed.
- Operator: eligible for Artifact Signing as an individual (United States
  or Canada only, MS-AS), and is 9.99 USD a month acceptable? May the
  project's GitHub owner and repository name appear in tracked files
  (adjudicator if the hygiene rule is read strictly)?
- CLOSED 2026-11-18 by Fit point 1: state lives in
  `%LOCALAPPDATA%\Programs\AshLight\data\`, outside the version folders.
- R11 (scoop) against the home layout: scoop installs into its own folder
  and replaces it on update; it needs either an installer script that
  calls `install.ps1 -Zip` or `persist` for `data\` plus the AL_HOME
  override (0052 R1). Not tested; plan 05 picks one or drops R11.
- Fit point 4's 24 h hold and default-on switch are this note's call
  under the CLAUDE.md minimal-interaction order; the operator may rule
  click-only (0052 Q4 asks the same question).
- Which CPython line to pin: 3.14 (this machine's gates run on it; M2
  used 3.14.10) or 3.13? The full suite has not run on the embeddable
  build. Windows on ARM (arm64 zips exist, EL-REL, PY-DL) can wait.
- Does deflate output differ between the CI's Python and a contributor's
  (F16)? R4's acceptance test settles it; the fallback is a stored zip.

## Verification

Independent verifier, 2026-11-18. Draft commit a55fb3b.

Checked:
- Code claims: about 60 path:line citations opened (setup / build / run / stop /
  autostart scripts, al_detach.ps1, autostart_launch.vbs, pre-push,
  launcher.js, main.js, about.test.js, paths.py, procs.py, http.py,
  webfetch.py, __main__.py, hotreload.py, tc_drift.py, tc_pin.py,
  loop_task.py, the kit's fleet_lanes.py, test_sidecar_paths.py,
  tc_pins.json, package.json and its lock, THIRD-PARTY.md, the audit,
  decisions 0005 / 0018 / 0025 / 0041, ROADMAP and hand-off lines). All
  but 2 held as written; 2 corrected (pre-push refuses unless AL_ALLOW_PUSH=1;
  tc_drift sends no ETag, the ETag pattern now cites ninja.py).
- Measurements re-run: the embeddable CPython 3.14.10 zip re-hashed
  (matches PY-REL), re-extracted (37 files) and run against a fresh `git
  archive` of server/ at HEAD: 70 modules imported, 0 failed, `--check`
  rc 0 (M2 confirmed). Authenticode re-read: electron.exe and ffmpeg.dll
  NotSigned, python.exe / pythonw.exe / python314.dll valid PSF (M1).
  Lockfile counts re-read: 13 / 49 / 163 / 276, electron-winstaller is the
  install-script package in the last two (M6). Electron zip size and
  SHA-256 match SHASUMS256.txt and the API digest (EL-REL). Peer assets
  re-read from the saved release JSON (PEERS). Git counts recounted (M7).
- Web: 19 sources re-fetched 2026-11-18 (PY-REL, PY-WIN, NODE, EL-SCHED,
  EL-UPD, EB-OFF, MS-SS, MS-AS, MS-SAC, MS-WGR, CAB, SPF, SC-CRIT, GH-RATE,
  GH-NOTES, GH-IMM, MS-VBS, MS-STORE, MS-ASP); all support the claims after
  the corrections below.
- ToS floor: all 11 recommendations re-tested against every floor rule;
  none needs the floor bent (no game process, input, game-file write,
  watcher, trade or undocumented endpoint, cookie, GGG branding or
  revenue). Rejected list unchanged.
- Settled decisions: 0041 item 9 stays (its reverse condition, a release
  channel, is not met); 0013 respected by R7; 0018 item 6 wording needs an
  amendment for R7 (added to R7 and as decision 9); 0005 now named in R8.
- Brief: every point covered.

Corrected:
- F16 commit stats: the draft's "85 are merges" counted only `merge:`
  subjects; there are 150 merge commits; non-merge conventional share is
  160 of 220 (73 percent), feat 64 (not 65). F4 commit count 356 -> 370.
- F12: the offline-cache page documents the unreleased v27; offline builds
  on a released electron-builder are now UNVERIFIED; Electron updater
  wording tightened.
- F13: the scoop main bucket is non-GUI only; winget wants clean install
  and uninstall for admins and non-admins.
- F11: SignPath conditions listed exactly (OSI license, policy page, MFA,
  roles, uninstall); Artifact Signing price source split (9.99 USD from
  MS-SS, 5,000 signatures from MS-ASP); Store date added.
- F8: classic installer "not built for 3.16 or later" stated as the
  source says it. F2: Node 20 end-of-life date added.
- R3: keep `app.isPackaged` false. R7: ETag citation and the 0018 note.
  R8: stop through stop.ps1 so the supervisor does not restart the core.

Still UNVERIFIED: how SmartScreen and Smart App Control rate the upstream
electron.exe (F10); which Node 20 minors fail (F2); classic code-signing
certificate prices (F11); offline builds on a released electron-builder
(F12); deflate determinism across Python builds (F16); M3 and M5 (sidecar
resolver on a missing drive, payload byte counts) were not re-run, though
the resolver logic was read and matches (paths.py:61-71, the kit's
fleet_lanes.py:1196-1201).

Gap fill, 2026-11-18 (completeness critic: 0053 never tested against 0052
or brief F):
- Added the section "Fit with 0052 and brief F" (six points: home, code
  layout, Apps & features entry, update consent, uninstall switch, first
  install), each with a pick, the reason against brief F and a ToS check;
  every losing text is marked in place with [SUPERSEDED ...] (Summary
  bullets 1 and 4, F15, R3, R5 twice, R8 twice, the decisions list, Cut or
  merge, two Rejected bullets); the open question on state location is
  closed; two new open questions (R11 scoop fit, operator ruling on the
  update default).
- Read for it: 0052 Summary, "Reference pattern" P1 to P8, "Mapping onto
  AshLight's rules" M1 to M37, R1, R4, R5, R6, Rejected and Q1 to Q6;
  CLAUDE.md "Minimal interaction" (the "updates itself with no clicks"
  order behind point 4). Found and recorded: 0052 names two homes (P4 / Q1
  vs R1's fallback); point 1 picks P4's.
- Web, re-fetched 2026-11-18 into the scratch folder: KF (the per-user
  Programs folder's default path is `%LOCALAPPDATA%\Programs`); WG-INS
  (installer Scope "user" / "machine" and AppsAndFeaturesEntries exist);
  GH-IMM (tag and assets locked after publication; title, notes, the
  pre-release and "latest" marks stay editable, which point 4's hold
  relies on). Still UNVERIFIED: a Microsoft page documenting the per-user
  uninstall key (0052 Q6).
- Kept: F8 / F9 / R3 pinned runtimes and the F12 no-framework call
  (0052's installer is a PowerShell bootstrap plus stdlib code). No
  settled decision reverses; 0013 and 0041 item 9 stand.
