# 05 - Deployment
Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md).
Status: final

Scope: operator ask F. Make AshLight deployable like the reference app:
one-step install, a versioned release artifact, an update path and a clean
uninstall; releases only on a planned milestone or an explicit version
tag, with a generated changelog. Sources: research 0052 and 0053 (primary),
0039, 0042, 0046, 0050, 0058; findings and rulings in
docs/plan/findings.json (finding ids F-.., ruling ids Q-..). The remote,
the first push and the public flip belong to plan 04; this section names
where it waits for them.

## Goal

Done means every statement below is true and tested.

- G1 A stranger on Windows 10 or 11 x64 with no Python and no Node pastes
  one PowerShell line and ends with a running AshLight: no elevation
  prompt, no second step, shortcuts on the Start Menu and Desktop, one
  entry in Apps and features.
- G2 A release is a fixed set of files built by one command from one git
  ref: `AshLight-<ver>-app.zip`, `install.ps1`, `release.json`,
  `SHA256SUMS.txt`, `AshLight-<ver>-notes.md` and an SBOM. Two builds of
  the same ref are byte-identical.
- G3 One version string (`VERSION` in server/al/__init__.py) names the
  app, the artifact, the tag (`v` + VERSION) and the User-Agent; a test
  fails on any mismatch.
- G4 A commit to main never produces a release. A release exists only
  after a `REL-PREP-<n>` milestone row or an explicit version request,
  and only after the operator's phrase `release X.Y.Z`. The loop has no
  code path to a tag.
- G5 The notes of a version are generated from commit subjects and
  ROADMAP row titles, curated once, and written to
  `docs/releases/<ver>.md`, `CHANGELOG.md`, the release asset and the
  release page.
- G6 An installed copy updates itself with web data on: daily check,
  verified download, staged beside the running version, applied at the
  next client start after a 24 h hold, rolled back by itself when the new
  version does not come up. With web data off: zero requests; Settings
  shows the installed version and a releases link the player opens in
  their own browser, and a re-run of the pasted line (or `install.ps1
  -Zip`) upgrades in place.
- G7 `uninstall.ps1` (also the Apps and features button) needs no Python
  and leaves nothing of AshLight but `<home>\data\`; `-Purge` leaves
  nothing. It never reports success while a file remains.
- G8 Nothing in install, update or uninstall reads or writes a game
  folder, looks for the game process, or makes a request while web data
  is off (except the install-time fetch the player started).
- G9 The operator's own live copy is an installed release; the checkout
  runs on a spare port for development.
- G10 Stdlib-only core, Electron exact pin, no CDN at runtime and the
  sidecar rules hold as before; a source checkout keeps working with
  `setup.ps1` then `run.ps1`.

## Design

One design, taken from the "Fit with 0052 and brief F" section of
research 0053 and the rulings. Nothing below relies on a not-adopted item.

1. No packaged .exe and no installer framework (decision 0041 point 9
   stands; not-adopted 0052-X1). The installer is a PowerShell 5.1
   bootstrap plus stdlib Python shipped in the payload (F-050).
2. Home (Q-19, F-049): players install to
   `%LOCALAPPDATA%\Programs\AshLight`; `-InstallDir` moves it; this
   machine uses `<sidecar>\Install`. All player state sits in
   `<home>\data\`, outside the code.
3. Code (F-050): `<home>\app\<version>\` plus the marker
   `<home>\install.json`. A version folder is never modified after its
   self-test. Update = build beside, self-test, switch the marker;
   rollback = switch back (conflict "install shape" resolved for 0052).
4. Runtimes (Q-20, F-047; gated on spike F-038): a private embeddable
   CPython 3.14.x and the unmodified Electron zip, each hash-pinned,
   fetched at install time from their publishers into
   `<home>\runtime\<name>-<ver>\`. Never bundled in any AshLight artifact
   and never fetched by the running core. The checkout keeps `npm ci` and
   the system Python. No Electron fuse is flipped on the unmodified exe
   (research gap "fuses" resolved; guards come from F-110). Pins at plan
   time (research 0053 F8, F9; re-read at DEP-06):
   `python-3.14.10-embed-amd64.zip`, 12,619,664 bytes, SHA-256
   90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159,
   from www.python.org; `electron-v45.3.3-win32-x64.zip`, 158,325,836
   bytes, SHA-256
   49dd2d3875944f08de03d34595cd30093c588b9edcabb41a0ac481028a3a5a8a,
   from the Electron project's GitHub release. Disk after install: about
   400 MB (Electron 374 MB, CPython 25 MB, the app under 2 MB).
5. Conflict settled here: F-048 lists an "offline full zip" with the
   runtimes inside; Q-20 rules "never bundled" and rests the third-party
   rule on that. The ruling wins. No artifact carries Electron or
   CPython. The offline route is `install.ps1 -Zip <app zip> -RuntimeDir
   <folder>` where the folder holds the two publisher zips the player
   downloaded; both are checked against the pins. A bundled full zip
   stays a marked option (see Risks) that needs its own licence decision.
6. Launch under the private Python (F-038, F-047): the embeddable
   runtime ignores the current directory and PYTHON* variables, and
   today every start uses the `-m` form with the checkout as cwd:
   scripts/run.ps1 (`-m server.al.paths`, then the core),
   server/al/keepalive.py core_command and run_preflight (`-m server.al`),
   and app/client/launcher.js (a bare-name `python` / `py` lookup for
   `-m server.al.paths`, then a hidden `scripts\run.ps1 -NoBrowser`).
   Target: a tracked `boot.py` at
   the payload root puts its own folder first on sys.path and runs the
   named module; one command builder (`paths.python_cmd`) and one
   PowerShell helper return `<python> <app>\boot.py <module> ...` in
   installed mode and today's `-m` form in a checkout. This lets version
   N+1 self-test while N runs. The spike confirms it; the fallback is one
   `._pth` line and a self-test through `-c`.
7. Version (F-023): SemVer 0.y.z; `VERSION` is the source;
   app/package.json and its lockfile equal it by test; a pre-release is
   `X.Y.Z-rc.N` and sorts below `X.Y.Z`.
8. Release tool (F-048, F-074, F-101): one stdlib dev tool,
   `tools/release.py`, with `bump`, `notes`, `build`, `stage`, `publish`
   and `prepush-check`. It builds and never uploads assets; the published
   assets are rebuilt, compared and attested by CI on the tag (F-076;
   conflict "who cuts a release" resolved).
9. Update (Q-21, F-055, F-077): one read of the project's
   `releases/latest` per 24 h, only while web data is on and the player
   has seen the opt-in sentence that names the update check and the
   automatic apply. Verified, staged, applied at the next client start
   after a 24 h hold; a Settings switch gives click-only; the previous
   version is kept.
10. Uninstall (F-063): PowerShell only; fixed child names under a home
    with a valid marker; data kept unless `-Purge`; a fixed last sentence
    about files the player may have copied elsewhere; no game folder is
    listed, stat-ed or opened.
11. Signing (Q-22, F-148): none at first. Provenance is SHA256SUMS, an
    SBOM, a build attestation and an immutable release; the README says
    plainly what "unsigned" means.
12. Deferred, not built now: a scoop manifest (F-210, defer), winget, a
    signed packaged exe, Windows on ARM.
13. Runtime fetches in an installed copy happen only in the installer
    package's own process (`boot.py server.al.install ...`): at install,
    at repair, and inside an update whose release changes a pin (that
    update runs under web data, Q-21). The core process itself never
    fetches a runtime (F-047 ToS check; decision 0018 item 6 is amended
    only for the release read, D5).
14. Game data and the optional calc in an installed copy. Game data:
    the client start runs the snapshot tool (`boot.py
    server.al.theorycraft.snapshot`) as its own hidden below-normal
    process when web data is on and the cache is missing or over 24 h
    (F-072 step 2, Q-04 amends decision 0009 item 2); nothing is bundled.
    Calc: `installer calc --opt-in` runs the shipped `tools\tc_pin.py`
    against `<home>\cache` and `<home>\build` and sets `tc_calc` only
    after a verified install (F-132); off by default (decision 0018), the
    decision 0027 toolchain route unchanged.
15. The first-run config an install writes has web data off and no
    Client.txt consent: both stay the player's own clicks on the first
    window (the floor's opt-in with its visible indicator; decision 0013;
    F-069's setup card). A fresh install never inherits dev keys.
16. The release build ships with poe.ninja polling off (F-046 release
    constant in server/al/ninja.py, keyed on `paths.install_mode() ==
    "installed"`) until a decision records poe.ninja's yes (Q-05); the
    trade-search link stays.

## Installed-mode layout

`<home>` is `%LOCALAPPDATA%\Programs\AshLight` for players and
`<sidecar>\Install` on this machine (`-InstallDir`, or `AL_HOME` for
tests).

- `<home>\install.json`: the marker. Fields: `schema` (1), `name`
  ("AshLight"), `version`, `previous`, `channel` (stable or rc),
  `installed_at`, `updated_at`, `python` (runtime folder name),
  `electron` (runtime folder name), `pending_confirm` (bool),
  `start_attempts` (int). Written through the hardened write path of
  F-014 (temp file, fsync, replace, one `.bak`).
- `<home>\uninstall.ps1`: copied from the active version at each switch.
- `<home>\app\<version>\`: the payload, read-only by convention:
  `server\`, `web\`, `app\` (the Electron app without its tests),
  `scripts\`, `config\` (shipped defaults and pins), `tools\tc_pin.py`,
  `ops\fleet_kit\tokens.css`, licence files, `README.md`, `CHANGELOG.md`,
  `MANIFEST.json` (sha256 and size per file), `BUILD` (version, 12-hex
  commit, created; read by F-027) and `boot.py`.
- `<home>\runtime\python-<ver>\` and `<home>\runtime\electron-<ver>\`:
  one folder per pin, so a pin move also builds beside.
- `<home>\data\`: today's `ops\runtime` plus `local.json` (today's
  `config\local.json`): consent, settings, run history, builds, price
  watch, visits, the per-start token and pid files. Private ACL per
  F-011. The only folder an uninstall keeps.
- `<home>\cache\` (Electron profile, web caches, game-data snapshot,
  calc archives, `downloads\` for release and runtime zips),
  `<home>\logs\` (core and supervisor logs, `reports\last-install.json`,
  `last-update.json`), `<home>\temp\`, `<home>\build\` (only when the
  optional calc is installed), `<home>\staged\<version>.json` (a pending
  update: version, published_at, hashes, apply_after).

What moves out of the source checkout in installed mode:

- `ops\runtime` and `config\local.json` -> `<home>\data\`.
- Sidecar `Cache`, `Logs`, `Temp`, `Build` -> `<home>\cache`, `logs`,
  `temp`, `build`. `Worktree`, `Scratch` and `ClaudeHistory` do not exist
  in an install.
- `app\node_modules\electron\dist` -> `<home>\runtime\electron-<ver>\`
  (procs.py's proven-ours folder; amends decision 0010).
- PATH `python` / `py` -> `<home>\runtime\python-<ver>\python(w).exe`.
- Shortcut target and the opt-in logon task action -> the active
  version's paths, rewritten and read back at every switch (amends
  decision 0041 point 8).
- Dev-only keys (`hot_reload`, `tc_drift_live_unattended`, loop keys) are
  not written into a player's `local.json`; code hot reload is off
  without `.git` (server/al/hotreload.py dev_enabled), data-file hot
  reload stays.
- Not shipped at all: `tests\`, `docs\` (except what is named above),
  `tools\` except `tc_pin.py`, `ops\` except `tokens.css` and the kit
  licence, `.claude\`, `.githooks\`, the hand-off, ROADMAP.md, CLAUDE.md.

Mode detection (F-049): `paths.install_mode()` is "installed" when
`AL_HOME` is set or `install.json` lies two levels above the payload
root; else "checkout". In a checkout nothing changes. The resolver
refuses a home whose path text has a `steamapps` component or a
`Path of Exile 2` component: by path shape only, with no registry read,
no library file and no folder listing (floor audit on F-049).

How an update swaps versions:

1. Download to `<home>\cache\downloads\`, verify size and SHA-256 (see
   Release procedure for the checks), extract to
   `<home>\app\<new>.partial\`, check every file against `MANIFEST.json`,
   rename to `<home>\app\<new>\`. Runtimes are fetched only when a pin
   changed.
2. Self-test of `<new>`: `boot.py server.al --check`, then a demo core
   (F-034 demo mode, shipped synthetic fixture log, scratch runtime under
   `<home>\temp\`, web data off) on the first free port of 8970-8979;
   `/api/health` must answer with `version == <new>` within 15 s. Like
   the download and extract, the self-test runs hidden at below-normal
   priority and starts only while `game_idle` is true or on a click
   ("must not cost game FPS"; decision 0029 signal, never a process
   check). Any failure moves the folder to `<home>\temp\failed-<new>\`,
   writes the report and leaves the marker alone.
3. Write `<home>\staged\<new>.json` with `apply_after = published_at +
   24 h`. One Settings and Checks line names the staged version.
4. Apply: at the next client start the launcher runs `apply-staged
   --if-due` before it starts the core (a no-op must cost under 300 ms).
   When due, and never while a core of this home runs: switch the marker
   (`previous` = old, `pending_confirm` = true, `start_attempts` = 0),
   rewrite the shortcuts, the uninstall entry, `uninstall.ps1` and the
   logon task action, read each back, then relaunch from the marker.
   "Update now" does the same after a stop through stop.request.
5. Confirm: the first `/api/health` answer from the new version clears
   `pending_confirm`. Then folders that are neither `version` nor
   `previous` (and runtimes neither needs) are deleted.

Rollback:

- Automatic: the launcher adds 1 to `start_attempts` before each start
  while `pending_confirm` is true; at the second start without a confirm
  it switches the marker back, rewrites and reads back the shell
  entries, records the bad version in `<home>\data\update_skip.json`
  (never offered again; a newer release is) and adds one Checks line.
- By hand: `installer rollback` (README), same switch.
- A failed self-test never reaches the marker, so it needs no rollback.

Repair: a re-run of `install.ps1`, or `installer repair`, checks the
active version against `MANIFEST.json`; a changed or missing file is
reported and the version is re-extracted from the cached zip (installed
code is not edited; no merge, 0052 M24).

## Release procedure

When: only (a) a planned milestone, which is a `REL-PREP-<n>` row filed
by plan 07 at the end of a wave, or (b) an explicit request for a version
(a security fix, an Electron pin move). Never per commit. Proposed
ladder: 0.2.0-rc.N for the installed-copy dogfood before any remote
(built with `build --ref`, no tag, never pushed); 0.2.0 = first public
release after the flip; 0.y.0 per finished wave; 0.y.z for fixes; 1.0.0
on the operator's word.

Who triggers what:

1. The REL-PREP lane (unattended; it never tags or pushes): `release.py
   bump X.Y.Z` (one commit: server/al/__init__.py, app/package.json,
   app/package-lock.json, docs/releases/X.Y.Z.md with a STUB mark, plus
   each line marked `al-version-stamp`, today README.md's install line
   once DEP-14 adds it); `release.py notes X.Y.Z --write`; it curates the notes,
   regenerates CHANGELOG.md and commits; `release.py stage`; it then sets
   the REL-PREP row to `BLOCKED: operator phrase "release X.Y.Z" (stage
   PASS)` so the tick skips it and the next /done carries it into the
   operator batch (the lane never edits the hand-off).
2. The operator types `release X.Y.Z` in an interactive session (a MAIN
   ORDER carrying the same phrase counts, FLEET item 6, and is likewise
   acted on only in an interactive session). No
   other input exists. A lane, a loop tick and an inbox responder cannot
   publish: `publish` refuses when a headless marker is set (the kit
   progress-owner variable or a lane lock), and a static test finds no
   `release.py publish` and no `git tag` in tools/al_loop.py,
   tools/al_lane.py and tools/loop_prompts.py.
3. The session runs `release.py publish --version X.Y.Z --go "release
   X.Y.Z"`. Refusals, each tested, each leaving nothing changed: the
   phrase differs; no stage report, FAIL, another version, another
   commit, or older than 24 h; the tree is dirty or HEAD is not the stage
   commit; the notes file still has its STUB mark or CHANGELOG.md is
   stale; the tag exists locally or on the remote; `origin/main` is not
   HEAD; no remote; the committer is not the operator identity; the
   repository's immutable-releases setting is not confirmed (read through
   `gh`, else the dated `immutable_confirmed` value the operator act
   records in config/release.json).
4. Then: an annotated tag `vX.Y.Z` on the stage commit whose message
   carries `sums-sha256: <hex of the staged SHA256SUMS.txt>`; one push of
   that one ref (`git push origin refs/tags/vX.Y.Z`, never `--tags`,
   `--all` or `--mirror`) through fleet_gitlock and the guarded pre-push
   hook (F-016 allows `refs/tags/v*`; `release.py prepush-check` in the
   hook refuses a `v*` tag without a matching PASS stage report). Main
   itself is pushed under plan 04's push policy; publish never pushes a
   branch.
5. CI (`.github/workflows/release.yml`, trigger: `v*` tags only; actions
   pinned by 40-hex commit; Windows runner; Python pinned to the
   builder's exact version): checkout with full history; pytest and the
   node tests; `release.py build --tag vX.Y.Z`; compare the hash of its
   SHA256SUMS.txt with the tag's `sums-sha256` line and fail on a
   difference; `tools/sbom.py`; attest the assets and the SBOM (build
   provenance); create a draft release with the notes file as body;
   upload the assets; publish it (immutable; `--prerelease` for an
   `-rc.` tag so `releases/latest` skips it). The kit's identity guard
   (fleet_identity_guard.yml, installed with the remote by plan 04) is a
   required check. CI keeps web data off, merges no pull request and
   pushes no commit.
6. Read-back by the session, bounded polling to a deadline: the release
   is published and immutable, the tag targets the stage commit, every
   asset digest equals the staged one, `gh attestation verify` passes on
   the app zip. Result in `<sidecar>\Build\release\X.Y.Z\publish.json`
   and one hand-off line. `publish --rehearse` runs every gate and makes
   0 pushes and no tag.

What `release.py build` writes, to `<sidecar>\Build\release\<ver>\`:

- `AshLight-<ver>-app.zip`: one top folder `AshLight-<ver>\`; entries
  from the ship list over `git ls-files` at the ref (allow-list in
  config/ship_list.json), bytes from git blobs, sorted, every time field
  = the ref's commit time; `MANIFEST.json` and `BUILD` generated inside.
  Budget: under 2 MB (0053 F7 measured 542,447 bytes deflated for 148
  files). If deflate differs between two Python builds the zip is stored
  uncompressed (0053 F16).
- `install.ps1`: the bootstrap with the version stamped in; every
  request it makes sends `AshLight/<ver> (installer)` as User-Agent.
- `release.json`: name, version, channel, commit, created, bootstrap
  protocol (1), the runtime pins (url, sha256, size, licence) and the
  asset list (name, size, sha256).
- `AshLight-<ver>-notes.md`: a copy of docs/releases/<ver>.md.
- `AshLight-<ver>.sbom.json`: from tools/sbom.py (13 npm components, the
  Electron binary, CPython, the 3 calc pins, each with a hash; F-148).
- `SHA256SUMS.txt`: one `<sha256>  <name>` line per file above, sorted.

Reproducible means: every `created` field (release.json, `BUILD`, the
SBOM timestamp) is the ref's commit time, the SBOM serial number is a
uuid5 of the commit id, and nothing reads the clock, the host name or a
random source; otherwise CI's rebuild could never match the staged
SHA256SUMS.

It refuses a dirty tree, a tag and VERSION mismatch, a final version
without a tag (2026-11-18, adjudicator LE-53: only for `build --tag`;
`stage` builds with `--ref`, the artifacts carry no tag, the tag binds
the staged sums at publish, and CI's `--tag` rebuild must match byte for
byte), anything from the sidecar cache in the staged tree, and a
leak-sweep hit in the staged tree. No game data, PoB source, LuaJIT,
Electron or CPython is in any artifact (decisions 0009, 0018; Q-20).

`release.py stage` (F-074) writes `stage.json` {version, commit, verdict,
steps, assets, sums_sha256, created, sandbox}: (1) clean tree and version
checks; (2) the Python suite through the suite gate; (3) node tests; (4)
two builds, identical; (5) leak sweep and deny test on the staged tree;
(6) a scratch-home round trip with the real runtimes taken from the
sidecar cache: install, update from the previous version (a synthetic
N-1 for the first release), rollback, uninstall, purge; its shell
effects (shortcuts, the uninstall key, the logon task) go to a scratch
root, so the operator's real Start Menu, Desktop, registry and task
entries are never written or removed, and its demo cores run hidden on
8970-8979 with web data off; (7) Windows
Sandbox phases (networking and clipboard off, assets in a read-only
mapped folder), only with the operator's `--sandbox` flag. The tool never
looks for the game: no process list, no window query, no Client.txt
access (floor audit on F-074; static test).

Checksums and what a client trusts: the bootstrap and the updater compute
SHA-256 of every download and compare it with SHA256SUMS.txt from the
same immutable release; the updater also compares it with the asset
`digest` field of the releases API answer, which arrives from another
host. The Sigstore attestation is for people and CI (`gh attestation
verify`, README): the Python standard library cannot verify it, so the
installed updater does not claim to (this narrows F-077's wording; see
Decisions D5 and Risks).

## Changelog generation

One generator: `tools/release.py notes` (F-101; tools/changelog.py is
not built).

Inputs:

- First-parent commit subjects in `<previous tag>..<ref>` (the whole
  history for the first release). Two shapes count: `merge: <ROW-ID>
  ...` and `type(scope): text`, where scope is usually the row id.
- ROADMAP row titles. Done rows are pruned at /done, so titles are read
  from git history: the ROADMAP.md diff of each commit in the range plus
  ROADMAP.md at both ends give id -> kind and title.
- The hand-written lead paragraph in docs/releases/<ver>.md, kept on
  every regeneration (text between two marker comments).

Rules:

- One line per row id, not per commit: `- <title in player words>
  (<ROW-ID>)`. Commits without a row id produce a line only for types
  feat, fix, perf and security.
- Groups: Added (feat), Changed (perf, refactor, `(data)` rows), Fixed
  (fix), Security (type security or deps, Electron pin rows). docs,
  test, chore, ops, release and plain merges are left out and counted in
  one closing line: "Also: N internal changes."
- This plan's package ids start with `DEP-` and mean deployment; the
  Security group therefore keys on the commit type and the row kind,
  never on an id prefix (0058 R9 proposed the prefix).
- `.githooks/commit-msg` gains a subject check with the type list the
  history already uses plus the new ones (feat, fix, perf, refactor,
  data, docs, test, chore, ops, security, deps, merge, release, audit,
  design, verify, revert, done); git's own generated `Merge branch ...`
  subjects (worktree syncs) pass and count as plain merges; any other
  subject without a type is refused. The check runs after the kit's
  identity strip and the leak sweep already in that hook.
- Only subjects are read, never bodies or trailers, so no attribution
  line can reach a notes file (FLEET item 17).
- Every notes file ends with the not-affiliated sentence; no GGG art, no
  link to a paid page.

Format (ASCII, LF):

    ## [0.2.0] - 2026-12-01
    <lead paragraph, 1 to 3 sentences, hand-written>
    ### Added
    - <title> (<ROW-ID>)
    ### Changed
    ### Fixed
    ### Security
    Also: N internal changes.

Where it is written:

- `docs/releases/<ver>.md` (tracked): stub from `bump`, draft from
  `notes --write`, curated by the REL-PREP lane.
- `CHANGELOG.md` (tracked, shipped): every docs/releases file, newest
  first; `notes --changelog` regenerates it and a test fails when it
  differs from that concatenation.
- The release asset `AshLight-<ver>-notes.md` and the release page body.
- In the app (F-055): a fold with the newest 3 versions, read from the
  shipped CHANGELOG.md and, for a newer version, from the cached release
  answer.

## Uninstall

Entry points: Apps and features (the per-user uninstall key; the command
is Windows PowerShell 5.1 with `-NoProfile -ExecutionPolicy Bypass -File
"<home>\uninstall.ps1"`), or the same file by hand. Switches: `-Purge`,
`-Yes`, `-DryRun`, `-Quiet`. A source checkout uses
`scripts\uninstall.ps1 -Checkout` (below).

Asked first: nothing by default (F-063: one click, no question; the data
is kept). `-Purge` is the consent to remove data; run by hand without
`-Yes` it asks once for the typed word PURGE. `-DryRun` prints the plan
and changes nothing.

Steps, in order. Every removal is conditional on "it is ours":

1. Validate: `install.json` beside the script, name "AshLight", schema
   known; the home passes the path-shape guard. Else exit 2, nothing
   touched. The script then re-runs itself from a copy in the user's temp
   folder so the home can be removed.
2. Stop: write `<home>\data\stop.request`; wait up to 10 s; then end
   only processes proven ours: a pid from our pid files whose creation
   time matches, or an image whose full path lies under
   `<home>\runtime\` (the rule of decision 0010). Wait for each to exit.
3. Logon task: remove `AshLight Autostart` only when its action path
   lies under this home.
4. Shortcuts: remove the Start Menu and Desktop `AshLight` links only
   when their target lies under this home.
5. Uninstall key: remove the per-user `Uninstall\AshLight` key only when
   its InstallLocation is this home.
6. Delete, by fixed name only: `app\`, `runtime\`, `cache\`, `logs\`,
   `temp\`, `build\`, `staged\`, `install.json`, `install.json.bak`, and
   inside `data\` the per-run files (token, pid files, stop.request,
   heartbeat, locks). Method: a direct delete; all of it is replaceable.
7. Without `-Purge`: `<home>\data\` stays (consent, settings, run
   history, builds, price watch, visits, local.json) and
   `uninstall.ps1` is removed. With `-Purge`: `data\` goes to the
   Recycle Bin (FLEET item 9), then the empty home is removed.
8. Last lines, byte-identical for a given home whether or not any
   AshLight file sits in a game folder: what stays (`<home>\data` or
   nothing) and one fixed sentence: AshLight hands out the files
   `ashlight.filter` and its `.build` file as downloads; if you copied
   them into the game's filter or planner folder they are still there.
   The script never looks (floor audit on F-063).
9. Exit 0 only when nothing but the kept data remains; else exit 1 with
   one line, "uninstall incomplete: <n> items remain", and a report file
   in the user's temp folder.

Never touched: any game folder, Client.txt, files the player saved
elsewhere, another AshLight install or checkout, the dev loop task
`\AshLightOps\LaneLoop`, any process not proven ours.

Checkout mode (`scripts\uninstall.ps1 -Checkout`, for a source install
and for this machine's checkout): stops the checkout's processes, removes
the logon task and the links only when they point into this checkout,
and prints what stays. With `-Purge` it sends `ops\runtime` and
`config\local.json` to the Recycle Bin and deletes the sidecar's `Cache`,
`Logs` and `Build`, and in `Temp` only AshLight's own run files. It
never removes `Worktree`, `Scratch`, `ClaudeHistory`, `Install` (an
installed copy has its own uninstall) or the agent temp folders under
`Temp` (headless runs and live sessions use them), never touches
another tree's sidecar, and names the loop task with its own remove
command (`tools/loop_task.py remove`).

## Work packages

Hotspots named per package: state.py, web/app.js, README.md,
ROADMAP.md, CLAUDE.md; serial files across packages: server/al/paths.py
(DEP-02, DEP-05, DEP-06), scripts/setup.ps1 and scripts/autostart.ps1
(DEP-02, DEP-07, DEP-06), tools/release.py (DEP-03, DEP-04, DEP-08,
DEP-12). Every package gets a ROADMAP row from plan 07 (one ROADMAP.md
edit, done by the plan, not by the package). Every acceptance test runs
on named test files, scratch homes and spare ports: never the live
client on 8960, the live Client.txt or a visible window.

### DEP-01 Spike: AshLight under the private runtimes
- Goal: prove the runtime design before any code rests on it.
- Files: the new docs/ops/runtime-spike-record.md (amended 2026-11-18,
  close-out LE-164: this final file is not edited by a package); work
  under `<sidecar>\Scratch\dep-spike\`.
- Acceptance: with the hash-checked embeddable CPython 3.14.10 zip and a
  `git archive` copy of the tree, no Python or Node on PATH and
  `AL_SIDECAR_ROOT` at scratch: a demo core answers `/api/health` on a
  port in 8970-8979; the supervisor restarts it once; the calc bridge
  answers one calc on the reference build when the calc is installed;
  with pytest placed by the system pip `--target <scratch>\site` and
  named in the scratch `._pth`, tests/test_sidecar_paths.py,
  tests/test_keepalive.py, tests/test_procs.py, tests/test_jsonfile.py
  and tests/test_http_security.py pass; the boot shim and the `._pth`
  variant are both tried and one is recorded; the unpacked Electron zip
  reports its version without Node. The record lists every re-spawn
  site that needed a change.
- ZERO-CLICK: dev only; hidden, fixture log, spare port.
- Size: S. Depends on: F-034 (demo mode). Findings: F-038.
- Parallel with: DEP-02, DEP-03, DEP-04, DEP-05. Hotspots: none.

### DEP-02 The source install works for a stranger
- Goal: `setup.ps1` then `run.ps1` works off this machine.
- Files: server/al/paths.py, tests/test_sidecar_paths.py,
  scripts/setup.ps1, scripts/run.ps1, README.md, CONTRIBUTING.md,
  requirements-dev.txt.
- Acceptance: with the kit default pointed at a missing drive,
  `sidecar_root()` lies inside the tree and `ensure_dirs()` passes; Node
  floor 22.12.0 in setup.ps1, run.ps1 and README, tested against the
  Electron `engines` field (`>= 22.12.0` in the pinned package today);
  no build.ps1 in the README quick start (it moves to CONTRIBUTING.md);
  the TEST-CLEAN-CLONE run repeated with `AL_SIDECAR_ROOT` unset: a fresh
  `git clone` of HEAD in `<sidecar>\Scratch\clean-clone`, `setup.ps1
  -NoShortcut`, then `run.ps1 -NoOverlay -NoBrowser -Port 8961`, answers
  `/api/health`, and every path it created lies in the clone or the AL
  sidecar.
- ZERO-CLICK: the same two script calls, no prompt.
- Size: S. Depends on: none. Findings: F-019.
- Parallel with: DEP-01, DEP-03, DEP-04. Not with DEP-05 (paths.py) or
  DEP-07 (setup.ps1). Hotspots: README.md.

### DEP-03 One version, enforced
- Goal: one source of the version and a one-commit bump.
- Files: tests/test_version.py, tools/release.py (new, `bump`),
  app/package.json, app/package-lock.json, docs/releases/ (new).
- Acceptance: the test fails on a planted mismatch; `bump` on a scratch
  clone changes exactly the 4 paths of Release procedure step 1 plus
  each tracked file holding an `al-version-stamp` marker line (none
  until DEP-14 adds README.md's install line), and the test fails when a
  stamped line differs from VERSION; `bump --check` is a no-op at HEAD;
  `0.2.0-rc.1` sorts below `0.2.0`; a tag must equal `v` + VERSION.
- ZERO-CLICK: nothing for the player; the loop never bumps by itself.
- Size: S. Depends on: none. Findings: F-023.
- Parallel with: DEP-01, DEP-02, DEP-05. Hotspots: none.

### DEP-04 Notes and changelog generator
- Goal: the Changelog generation section, built.
- Files: tools/release.py (`notes`), .githooks/commit-msg,
  tools/commit_subject.py (new, called by the hook), CHANGELOG.md (new),
  docs/releases/0.1.0.md, tests/test_release_notes.py.
- Acceptance: a fixture history of 3 merges gives 3 grouped lines; a
  subject without a type is refused by the hook; a row with id prefix
  `DEP-` and type feat lands under Added, not Security; CHANGELOG.md
  equals the concatenation; two runs give the same bytes; the lead
  paragraph survives a regeneration; the hook passes every subject
  shape in the last 400 commits of main except untyped ones listed in a
  fixture, and passes git's `Merge branch ...` subjects.
- ZERO-CLICK: prepared unattended by the REL-PREP lane.
- Size: S. Depends on: DEP-03, F-024 (row id lint). Findings: F-101.
- Parallel with: DEP-05, DEP-06, DEP-07. Not with DEP-08
  (tools/release.py). Hotspots: none.

### DEP-05 Installed-mode paths
- Goal: one resolver that serves a checkout and an install home.
- Files: server/al/paths.py, server/al/ports.py (`AL_DEV_PORT = 8961`,
  `SELFTEST_PORTS = (8970, 8979)`), server/al/procs.py,
  server/al/__main__.py, app/client/launcher.js,
  tests/test_sidecar_paths.py, tests/test_install_paths.py, CLAUDE.md
  (one Sidecar sentence, Q-19).
- Acceptance: with `AL_HOME=<tmp>` every runtime path is inside `<tmp>`;
  with no variable and no kit folder none leaves the per-user local
  application data folder; cores from `<tmp>\app\0.1.0` and
  `<tmp>\app\0.1.1` read the same consent file; a home with a
  `steamapps` or game-directory component is refused while winreg and
  every listing or stat outside the home are patched to fail; with the
  home under the AL sidecar tests/test_sidecar_paths.py is green; both
  port constants lie in 8960-8979; `/api/health` and `/api/version`
  carry `mode` and `previous`.
- ZERO-CLICK: resolved from the marker; nothing to set.
- Size: M. Depends on: DEP-02, F-014 (write path). Findings: F-049.
- Parallel with: DEP-03, DEP-04, DEP-07. Not with DEP-02, DEP-06
  (paths.py, procs.py, launcher.js). Hotspots: CLAUDE.md.

### DEP-06 Pinned runtimes, one resolver each, one command builder
- Goal: the launch chain prefers the private runtimes; no npm and no
  PATH Python on the player path.
- Files: config/runtime_pins.json (new: the CPython entry; the Electron
  entry is read from config/electron_pin.json of F-044, one source),
  tools/tc_pin.py (shared fetch, hash, extract code), server/al/paths.py
  (`python_exe`, `electron_exe`, `python_cmd`), server/al/keepalive.py,
  server/al/procs.py, scripts/al_env.ps1 (new shared helper) used by
  run.ps1, stop.ps1, setup.ps1, build.ps1, autostart.ps1,
  app/client/launcher.js, boot.py (new, payload root), THIRD-PARTY.md,
  CLAUDE.md (one Stack sentence, Q-20), tests/test_runtime_layout.py.
- Acceptance: in a scratch layout with no Python or Node on PATH,
  `<python> boot.py server.al --check` returns 0 and `run.ps1 -NoBrowser`
  on a spare port answers `/api/health`; a wrong pin hash refuses with
  exit 2; no script holds its own `python` / `py` lookup (static test:
  one helper); the pinned Electron version equals app/package.json; the
  app folder is passed to electron.exe (never `resources\app`), so
  `app.isPackaged` stays false; the launcher drops
  `ELECTRON_RUN_AS_NODE` and `NODE_OPTIONS`.
- ZERO-CLICK: fetched inside setup or install; nothing to install.
- Size: M. Depends on: DEP-01 (pass), DEP-02, DEP-05, DEP-07 (setup.ps1
  and autostart.ps1 serial), F-044. Findings: F-047.
- Parallel with: DEP-04. Not with DEP-07 (setup.ps1, autostart.ps1).
  Hotspots: CLAUDE.md.

### DEP-07 Shell integration helper and a launcher without VBScript
- Goal: one place that writes and removes shortcuts, the uninstall
  entry and the logon task; no wscript.
- Files: scripts/al_shell.ps1 (new; setup.ps1 and autostart.ps1 use it),
  server/al/autostart_entry.py (new pythonw entry point),
  scripts/autostart_launch.vbs (removed, after a consumer check),
  scripts/autostart.ps1, scripts/setup.ps1, tests/test_autostart.py,
  tests/test_shell_integration.py.
- Acceptance: effects injected, nothing real is written in tests; the
  registered task action runs no wscript; a shortcut or task that points
  elsewhere is left alone; every write is read back; PowerShell 5.1
  ParseFile passes.
- ZERO-CLICK: unchanged; autostart stays opt-in (decision 0011).
- Size: S. Depends on: DEP-02 (setup.ps1 serial). Findings: F-170, 0052
  cut-or-merge.
- Parallel with: DEP-03, DEP-04, DEP-05. Not with DEP-02 or DEP-06
  (setup.ps1, autostart.ps1). Hotspots: none.

### DEP-08 Release build tool
- Goal: `release.py build` (also `build.ps1 -Package`) as specified in
  Release procedure; never uploads.
- Files: tools/release.py (`build`), config/ship_list.json (new),
  scripts/build.ps1, tools/sbom.py (new), tests/test_release_tool.py,
  tests/test_sbom.py.
- Acceptance: two builds of one ref give identical SHA256SUMS.txt; the
  manifest check catches a changed file, a missing file and an unsafe
  path; nothing under ops/loop, tests or docs and no tool but tc_pin.py
  is listed; the zip is under 2 MB; a dirty tree, a version mismatch, a
  cache file or a leak-sweep hit refuses; the SBOM lists 13 npm
  components, the Electron binary, CPython and 3 calc pins with hashes;
  the build makes 0 network calls; with the clock, host name and random
  source patched to differ, a second build still gives the same
  SHA256SUMS; a build whose staged server/al/ninja.py has the F-046
  release switch on while no decision records poe.ninja's yes refuses.
- ZERO-CLICK: one command, no prompt, no upload.
- Size: M. Depends on: DEP-03, DEP-04 (tools/release.py serial), DEP-06,
  F-027 (BUILD file reader), F-046 (release constant). Findings: F-048,
  F-148 (SBOM half).
- Parallel with: DEP-07. Hotspots: none.

### DEP-09 Installer and bootstrap
- Goal: G1. `install.ps1` plus the stdlib package `server/al/install/`
  (`cli`, `home`, `fetch`, `selftest`, `shell`): commands `install`,
  `repair`, `status`, `calc` (Design point 14).
- Files: scripts/install.ps1 (new), server/al/install/ (new),
  server/al/data/selftest/ (a synthetic fixture log from
  tools/synth_client.py), config/local.example.json (player keys only),
  tests/test_installer.py, tests/test_install_ps1.py.
- Behaviour: the bootstrap fetches SHA256SUMS.txt, release.json and the
  app zip, checks the hash, fetches and checks the pinned CPython zip,
  then hands over to `<python> boot.py server.al.install install`, which
  fetches Electron, lays out the home, writes the first-run config,
  self-tests, and only then writes the marker, two shortcuts and the
  uninstall entry, and starts the client. Hosts: github.com,
  release-assets.githubusercontent.com, objects.githubusercontent.com
  (the asset redirect hosts tools/tc_pin.py already allows) and
  www.python.org. User-Agent `AshLight/<ver> (installer)` on every
  request, from the bootstrap and the package alike. The pasted line
  itself names AshLight and the version too: `irm -UserAgent
  'AshLight/<ver> (installer)' <release address>/download/v<ver>/install.ps1
  | iex`, stamped by `bump` (DEP-14 writes it into README.md). Piped use
  takes `AL_INSTALL_DIR`; file use takes `-Zip`, `-RuntimeDir`,
  `-InstallDir`, `-NoStart`.
- Acceptance: scratch home with fakes: a clean install lays out marker,
  code, data and runtime; a tampered zip or a missing hash installs
  nothing; a failed self-test leaves no marker and one report; a re-run
  restores a deleted shipped file and upgrades an older marker; the
  script parses under PowerShell 5.1; no request goes to a host off the
  list and every request carries the installer User-Agent; no elevation
  call exists in either file (static test); the self-test core opens no
  log outside its fixture (exit 97 otherwise); the written `local.json`
  has `web_data` false, no Client.txt consent and no dev-only key;
  `calc --opt-in` with a forced hash mismatch leaves `tc_calc` unset;
  with web data on in a scratch home, an installed start runs the
  snapshot tool through `boot.py` under `<home>\cache` (F-072 step 2);
  every shell effect is injected (nothing real is written).
- ZERO-CLICK: one pasted line, then the app opens; the floor's Client.txt
  opt-in stays the one required click on the first window.
- Size: L. Depends on: F-011, DEP-05, DEP-06, DEP-07, DEP-08, F-072
  (step 2), F-132. Findings: F-050.
- Parallel with: DEP-10 (separate files). Hotspots: none.

### DEP-10 Uninstall
- Goal: G7; the Uninstall section, built.
- Files: scripts/uninstall.ps1 (new, self-contained: no dot-sourcing),
  README.md, tests/test_uninstall.py.
- Acceptance: a scratch home ends with only `data\`; `-Purge` leaves
  nothing (recycle injected); a held file gives exit 1 and the one line;
  `-DryRun` changes nothing; a link, task or key that points elsewhere is
  left; the last lines are byte-identical with and without such files on
  the machine; a static test finds no game-folder path and no listing or
  Test-Path outside the home; `-Checkout` never names `Worktree`,
  `Scratch` or `ClaudeHistory` for deletion; PowerShell 5.1 parse.
- ZERO-CLICK: one click in Apps and features; no question by default.
- Size: M. Depends on: DEP-05, DEP-07 (the layout); tested against
  DEP-09's home. Findings: F-063.
- Parallel with: DEP-09, DEP-11. Hotspots: README.md.

### DEP-11 Update and rollback, local half
- Goal: the swap, confirm and rollback of the layout section, driven by
  `update --zip FILE` (no network): `update`, `apply-staged`, `rollback`,
  `confirm`.
- Files: server/al/install/update.py (new), app/client/launcher.js
  (apply-staged before the core starts; relaunch from the marker),
  server/al/diag.py and server/al/state.py (an `install` entry: mode,
  version, previous, last update result), web/checks.js, web/app.js,
  tests/test_updater.py, app/test/launcher.test.js (new).
- Acceptance: N to N+2 from local zips keeps `data\` byte for byte; a
  tampered zip is refused with nothing changed; a failed self-test
  leaves the marker on N with exit 1; a new version that never answers
  health is rolled back at the second start and lands in
  update_skip.json; `rollback` restores N and reads back marker,
  shortcut and uninstall entry; `apply-staged` with nothing staged
  returns in under 300 ms; the copied report shows no path; the
  self-test runs at below-normal priority and waits while `game_idle` is
  false (a fake status, no process query); after a switch the new
  version serves its own web files (0050 F31: no old code with new
  pages).
- ZERO-CLICK: applied at the next start; one line names the version.
- Size: L. Depends on: DEP-09. Findings: F-077 (local half), 0050 F31.
- Parallel with: DEP-10. Not with DEP-16 or DEP-17 (state.py,
  web/app.js). Hotspots: state.py, web/app.js.

### DEP-12 Stage and publish gates
- Goal: `release.py stage`, `publish`, `publish --rehearse` and
  `prepush-check`, as in Release procedure, with git, gh and the clock
  injected.
- Files: tools/release.py, config/release.json (new: repository
  placeholder, `immutable_confirmed`), tests/test_release_gates.py,
  CLAUDE.md (one Gates line: who may publish). The one
  `release.py prepush-check` call in .githooks/pre-push is not part of
  this package: it goes into F-016's ready diff, which merges only after
  the operator's go (Q-23); until then every push is refused anyway and
  `publish` refuses for "no remote".
- Acceptance: every gate has a refusal test where nothing changed;
  rehearse makes 0 pushes and no tag; a digest mismatch fails the
  read-back; publish refuses under a headless marker; sandbox phases run
  only with `--sandbox`; the stage round trip writes no real shortcut,
  registry key or task (effects redirected, checked against a snapshot
  of the real locations taken before and after); a static test finds
  no process-list, window or Client.txt call in tools/release.py and no
  `release.py publish` or `git tag` in tools/al_loop.py, tools/al_lane.py
  and tools/loop_prompts.py; `prepush-check` refuses a `v*` ref with no
  matching PASS stage report and passes a branch ref untouched.
- ZERO-CLICK: one operator phrase per release; the rest is automatic.
- Size: M. Depends on: DEP-08, DEP-09, DEP-10, DEP-11. Findings: F-074.
- Parallel with: DEP-13, DEP-14. Hotspots: CLAUDE.md.

### DEP-13 Cut-over: the operator's live copy becomes an installed release
- Goal: G9 (Q-19).
- Files: server/al/install/migrate.py (new: an allow-list copy of player
  data from a checkout; never the token, never dev keys),
  tests/test_migrate.py; on this machine only: the gitignored
  config/local.json gets the dev port.
- Steps: build 0.2.0-rc.N; `install.ps1 -Zip ... -InstallDir
  <sidecar>\Install`; migrate; switch only while the live core reports
  `game_idle` (read from its own status, never a process check): stop
  through stop.request, start the installed copy on 8960, read back
  `/api/health` `mode: installed`; the checkout then runs on 8961.
- Acceptance: migrate is a copy (the checkout's files stay); consent and
  run history read the same in the installed copy; every installed path
  is inside the sidecar (tests/test_sidecar_paths.py); with both clients
  up the checkout client reports that the global hotkey is taken instead
  of failing silently; a re-run of the checkout's setup.ps1 leaves the
  installed copy's shortcuts and logon task alone (DEP-07's "points
  elsewhere" rule); a later `update --zip` round trip works on the live
  home.
- ZERO-CLICK: waits for `game_idle` by itself; no operator step.
- Size: M. Depends on: DEP-09, DEP-10, DEP-11. Findings: F-049, F-050
  (Q-19 part).
- Parallel with: DEP-12, DEP-14. Hotspots: none.

### DEP-14 Player docs: install, update, uninstall, verify, "Windows may warn"
- Goal: the README tells a player the real steps and what unsigned
  means.
- Files: README.md, SECURITY.md, THIRD-PARTY.md, tests/test_readme.py
  (new: section and wording lint).
- Acceptance: sections Install (the pasted line of DEP-09 with a
  placeholder address until Q-24, its version on an `al-version-stamp`
  line that DEP-03's stamp check holds to VERSION, and the verified
  `-Zip` route), Update, Uninstall,
  Verify your download (SHA256SUMS, `gh attestation verify`, `gh release
  verify-asset`), Windows may warn (each prompt named; never advice to
  switch protection off); the privacy text names the daily release read
  under web data; the disclaimer line is present; no repository address
  outside the placeholder before go-public.
- ZERO-CLICK: nothing for the player.
- Size: S. Depends on: DEP-03, DEP-09, DEP-10; shares README.md with
  F-020 (plan 07 orders them). Findings: F-148 (text half), F-020.
- Parallel with: DEP-12, DEP-13. Hotspots: README.md.

### DEP-15 Tag-triggered release workflow
- Goal: step 5 of Release procedure. The file is prepared and tested
  before the remote exists; it goes live with it.
- Files: .github/workflows/release.yml, tests/test_workflows.py.
- Acceptance: before the remote: every `uses:` carries a 40-hex commit;
  the only trigger is `v*` tags; permissions are the minimum (contents
  write, id-token write, attestations write); no step merges a pull
  request, pushes a commit or enables web data (static test). After the
  remote: an
  `-rc.` tag on the private repository yields a pre-release whose assets
  match SHA256SUMS; `gh attestation verify` and `gh release verify-asset`
  pass; a plain commit triggers nothing.
- ZERO-CLICK: pushing the tag is the only act.
- Size: M. Depends on: DEP-08, DEP-12, DEP-04; live half blocked on
  F-021 (Q-23). Findings: F-076, F-148.
- Parallel with: DEP-16. Hotspots: none.

### DEP-16 In-app update notice
- Goal: the daily release read and the Settings line.
- Files: server/al/updates.py (new), server/al/core.py,
  server/al/state.py, web/status.js, web/index.html, web/checks.js,
  web/app.js, tests/test_updates.py, README.md (privacy text).
- Acceptance: web data off: the injected transport is never called; on,
  with the wording acknowledged (`web_data_ack` at the current wording
  version): one call per 24 h, a 304 costs no parse, a 403 with a reset
  time and Retry-After are honoured; an earlier opt-in without the
  acknowledgement makes 0 requests; an empty repository constant = off;
  a settings import never sets the acknowledgement; no toast, no window;
  the web-data opt-in sentence in web/index.html names the daily update
  check and the automatic apply, and ticking it stores `web_data_ack`
  with the wording version; with web data off Settings shows the
  version and a releases link (none while the constant is empty) that
  opens in the player's own browser; the request goes only to
  api.github.com with the webfetch User-Agent and no cookie.
- ZERO-CLICK: the line appears by itself.
- Size: S. Depends on: DEP-03, F-027; live use blocked on a public
  release (Q-23, Q-24). Findings: F-055, F-077 (opt-in wording).
- Parallel with: DEP-15. Not with DEP-11 or DEP-17 (state.py,
  web/app.js). Hotspots: state.py, web/app.js, README.md.

### DEP-17 Update, network half
- Goal: G6: download, verify, stage by itself; "Update now"; the
  click-only switch.
- Files: server/al/install/update.py, server/al/updates.py,
  server/al/http.py (one token-guarded POST), server/al/state.py, web/
  (Settings), tests/test_updater.py.
- Acceptance: a fake release server: N to N+1 with web data on and the
  wording acknowledged needs no click; a size, SHA-256 or digest
  mismatch stages nothing; a release younger than 24 h is staged but not
  applied; click-only waits for "Update now"; web data off: 0 calls;
  download and extract run at below-normal priority and start only
  while `game_idle` is true or on a click; a release whose `release.json`
  changes a runtime pin fetches that runtime in the installer process
  (Design point 13), checked against the new pin; requests go only to
  api.github.com, github.com and the two asset hosts; a version in
  update_skip.json is never staged again.
- ZERO-CLICK: none with web data on; one acknowledgement click, once,
  for an earlier opt-in (the proof that the player has seen the new
  wording, Q-21).
- Size: M. Depends on: DEP-11, DEP-16, DEP-15 (file half). Findings:
  F-077 (network half).
- Parallel with: DEP-13, DEP-14. Hotspots: state.py, web/app.js.

### DEP-18 First release candidate and first public release
- Goal: run the procedure once end to end (REL-PREP-1).
- Files: docs/releases/0.2.0.md, CHANGELOG.md, the version files.
- Acceptance: `v0.2.0-rc.1` on the private repository passes DEP-15's
  live checks; after the flip `v0.2.0` is published, immutable, read
  back; the pasted line installs it on a machine that is not the dev
  host (stage `--sandbox`, or the tester run); the operator's live copy
  updates to it by itself.
- ZERO-CLICK: one operator phrase per tag.
- Size: M. Depends on: DEP-12 to DEP-17, DEP-19, F-021, F-006, F-016
  (merged after the go), F-046 (release constant). Findings: F-074,
  F-076.
- Parallel with: nothing. Hotspots: ROADMAP.md (REL-PREP rows).

### DEP-19 CPython pin watch
- Goal: security patches of the private CPython reach installs, as F-130
  does for Electron (0053 R10 names both; F-130 covers only Electron).
- Files: one more source in F-130's watcher (the tools/ file F-130
  creates), config/runtime_pins.json (read only), tests for that
  source.
- Behaviour: once per 24 h on the loop tick, a dev-tool read of
  python.org's downloads API (`www.python.org/api/v2/downloads/release/`,
  the host the installer already uses; a moved endpoint is recorded in
  the row, never guessed) for the pinned 3.14 line with the
  AshLight User-Agent (TC-DRIFT's shape, decision 0025); a newer patch
  release that still publishes an embeddable amd64 zip files one bump
  row (pin url, size, SHA-256 re-read at the move); a pin move ships as
  a 0.y.z release through REL-PREP. Never from the app.
- Acceptance: a fixture listing with 3.14.11 files exactly one row; the
  same listing again files nothing; a fixture without an embeddable zip
  files nothing and logs one line; 0 requests while `ops/loop/control/
  HALT` is set (unlike GGG-DOCS-WATCH, this one respects HALT).
- ZERO-CLICK: the watch runs on the loop tick; a pin move is a gated
  commit.
- Size: S. Depends on: F-130, DEP-06. Findings: F-130 (extension), 0053
  R10.
- Parallel with: DEP-07 to DEP-17 (own files). Hotspots: none.

Not packages now: the scoop manifest (F-210, deferred until after the
first public release; it needs `persist` for `data\` or an install
script calling `install.ps1 -Zip`), winget, a signed exe.

## Order

Critical path: F-034 -> DEP-01 -> DEP-06 -> DEP-08 -> DEP-09 -> DEP-11
-> DEP-12 -> DEP-15 (file half) -> DEP-17 -> (operator: remote, Q-23)
-> DEP-15 live -> DEP-18 (its last check is DEP-17 live: the operator's
copy updates itself).

- First, in parallel, no dependency on the spike: DEP-02 and DEP-03;
  then DEP-07 (after DEP-02, setup.ps1), DEP-04 (after DEP-03) and
  DEP-05 (after DEP-02).
- DEP-01 runs as soon as F-034 lands. A failed spike reverses Q-20 (as
  ruled, F-038). Proposed fallback, taken only after an adjudicator
  confirms it and recorded in D2: DEP-06 and DEP-09 use the player's own
  Python 3.13+ (found by the launcher, hash check dropped for it) and
  keep the pinned Electron zip, which F-044 fetches for the checkout
  anyway; G1 then reads "no Node" instead of "no Python and no Node";
  everything else is unchanged.
- paths.py is serial: DEP-02, then DEP-05, then DEP-06. setup.ps1 and
  autostart.ps1 are serial: DEP-02, then DEP-07, then DEP-06.
  tools/release.py is serial: DEP-03, DEP-04, DEP-08, DEP-12.
- DEP-09 and DEP-10 in parallel; then DEP-11; then DEP-12, DEP-13 and
  DEP-14 in parallel; DEP-16 any time after DEP-03 and F-027 but not
  beside DEP-11 or DEP-17; DEP-19 any time after DEP-06 and F-130.
- Everything through DEP-14, DEP-19, the file halves of DEP-15 and
  DEP-16, and DEP-17 against its fake release server needs no remote
  and no operator. DEP-15 live, DEP-17 live and DEP-18
  wait for plan 04's remote.
- Before any of it: F-014 (write path) and F-011 (ACL) from the P0 set.
- From other plan sections, each needed before the package named:
  F-034 (DEP-01), F-024 (DEP-04), F-044 (DEP-06), F-027 (DEP-08,
  DEP-16), F-046 (DEP-08), F-072 and F-132 (DEP-09), F-130 (DEP-19);
  blocked on the operator and needed only for the live halves: F-016
  and F-021 (Q-23), the address (Q-24).

## Decisions

Rulings this section relies on: Q-19 (home, `-InstallDir`, live copy
installed, dev port from the block), Q-20 (pinned runtimes fetched at
install, never bundled; gated on F-038), Q-21 (daily release read and
staged automatic apply under web data, wording named and re-shown), Q-22
(no signing at first), Q-23 (remote, first push, flip, immutable
releases: operator), Q-24 (the project's own address in tracked files, at
go-public). Floor audit reworks applied: F-049, F-063, F-074, F-077.

Decisions to record (numbers assigned when the plan lands, per
docs/plan/README.md "Then", each with its CLAUDE.md settled entry and
its "Reverses if"):

- D1 Installed-mode home and layout. Decision: per-user home
  `%LOCALAPPDATA%\Programs\AshLight`, `-InstallDir` override,
  `app\<version>\` plus marker, state in `data\`, the resolver refuses a
  game-folder home by path shape. Alternatives: extract-and-run folder
  with state inside; the sidecar path for everyone. Why: an update must
  not carry state and an uninstall must keep exactly one folder.
  Reverses if: the installed copy cannot serve daily dev use, or the
  override breaks the sidecar path test. Amends: the CLAUDE.md Sidecar
  rule by one sentence.
- D2 Installed-copy runtimes and launch. Decision: embeddable CPython
  3.14.x and the unmodified Electron zip, hash-pinned, fetched at
  install, never bundled; `boot.py` plus one command builder; no fuse
  flipped. Alternatives: the player's own Python; `npm ci` on the player
  path; a bundled full zip. Why: removes both heavy prerequisites and
  redistributes nothing. Reverses if: the spike fails, a publisher drops
  hash-verifiable assets, or a licence objection appears. Amends: the
  0002 stack note, 0010 (proven-ours Electron folder), 0041 point 8
  (shortcut target), one CLAUDE.md Stack sentence; holds the licence
  record for fetching both runtimes.
- D3 Release artifact and tool. Decision: app zip, install.ps1,
  release.json, SHA256SUMS, notes, SBOM from `tools/release.py build`;
  reproducible; no framework, no signing at first (Q-22); 0041 point 9
  stands with its trigger restated as "a public release exists and the
  operator holds a signing identity". Alternatives: electron-builder
  (276 packages), Forge with Squirrel (163), a portable full zip. Why:
  dependency cost, decision 0013, and no framework ships the Python
  core. Reverses if: the operator gets a signing identity, or SmartScreen
  friction measurably blocks installs.
- D4 Versioning and release trigger. Decision: SemVer 0.y.z, tag = `v`
  + VERSION, releases only from a REL-PREP milestone row or an explicit
  version request, published only on the operator's phrase, never by a
  lane or tick; CI rebuilds and publishes on the tag. Alternatives:
  release per merge; milestone rows that publish with no phrase (marked
  option, not adopted). Why: the operator's order. Reverses if: the
  operator rules that milestones may publish themselves.
- D5 Update policy. Decision: Q-21 as ruled, plus the client-side
  check: size, SHA-256 against SHA256SUMS and the API digest field; the
  attestation is verified by CI and by people, not by the installed
  updater (stdlib limit). Alternatives: click-only; no check; shipping a
  verifier binary. Why: minimal interaction with bounded risk (hold,
  self-test, rollback, immutable release). Reverses if: GitHub or GGG
  terms bar the daily read, a bad release auto-applies in practice, the
  operator wants click-only, or a stdlib-verifiable signature becomes
  available. Amends: decision 0013 and the 0018 item 6 wording.
- D6 Uninstall consent. Decision: data kept unless `-Purge`; nothing
  asked by default; no game folder read; a fixed closing sentence;
  checkout mode never removes dev history folders. Alternatives: a
  question on every uninstall; remove everything. Why: one click, and
  the floor's read list. Reverses if: players lose data they wanted kept
  or keep data they wanted gone, in practice.
- D7 Changelog. Decision: one generator, per-version notes files,
  CHANGELOG.md as their concatenation, commit types enforced by the
  hook, Security grouped by type not by id prefix. Alternatives:
  hand-written only; GitHub's generated notes (empty: this repo merges
  locally). Why: the operator asked for an auto-written changelog and
  done rows are pruned. Reverses if: the drafts need a rewrite every
  release.

## Operator acts

Each is something no agent can do (a grant, an account act, a physical
act) or the operator's own stated trigger.

1. Done: the operator's order of 2026-11-18 (hand-off OPERATOR GO lines)
   makes creating the repo, the first push and the flip agent steps (plan
   04 GP-09, GP-12). Immutable releases are switched on through the API;
   OA-3 applies only if that answers 404. (Amended 2026-11-18,
   adjudicator LE-01.)
2. Optional (OA-5); default signed-in account / AshLight; the real
   install line and update constant come from config/public_repo.json
   (GP-10). (Amended 2026-11-18, adjudicator LE-02.)
3. No `gh` sign-in is needed: `gh` is already authenticated on the dev
   host (research 0057; findings conflict "Operator act for the remote").
   Only if a publish or read-back reports a missing token scope does the
   operator re-grant it (OAuth). Blocks then: publish and the read-back.
4. Type `release X.Y.Z` once per release. Why: the operator's own order;
   it is the only trigger.
5. Optional: enable the Windows Sandbox feature (needs elevation and a
   restart) and allow `stage --sandbox` for the first public release.
   Default without it: the scratch-home round trip is the gate and the
   per-user uninstall key stays verified only on this machine.
6. Optional: one run of the pasted line on a Windows 11 PC with Smart
   App Control on (a second machine). Default without it: the README
   says the behaviour is unverified.
7. Optional: apply to a free open-source signing program after the first
   public release, or pay for signing (Q-22). Never funded from
   GGG-derived features.
8. Optional: say "click-only" to flip the update default (Q-21).
9. From plan 04, named because it gates release builds: the one message
   to poe.ninja (Q-05); until its yes, a release build makes no poe.ninja
   request (F-046). Optional since 2026-11-18: skipped in writing
   (adjudicator LE-38).

Not operator acts: the cut-over (DEP-13 waits for `game_idle` by itself),
unmarking a bad release as latest (a session does it with `gh`), every
build and stage.

## Risks and fallbacks

- The spike fails (the whole runtime design rests on it). Fallback: the
  player's own Python 3.13+ with the pinned Electron zip (Order).
- A release by accident. Held by: the typed phrase, the headless
  refusal, the pre-push stage check, no publish path in the loop tools,
  CI triggered by tags only.
- A bad release reaches installs. Held by: the 24 h hold (a session can
  unmark it as latest inside the hold), the self-test, the automatic
  rollback, update_skip.json, one kept previous version.
- The client cannot verify the attestation. Held by: an immutable
  release, two independent hash sources, CI verification. Stated plainly
  in SECURITY.md. If the API has no digest or immutable field at build
  time, DEP-17 records that and uses SHA256SUMS alone.
- SmartScreen or Smart App Control and the unsigned electron.exe:
  UNVERIFIED. The pasted line adds no Mark of the Web, so SmartScreen
  should not prompt; a Smart App Control block cannot be worked around
  and is documented, never bypassed.
- The per-user uninstall key is undocumented by the vendor. Fallback: if
  it fails on a tested Windows build, the entry is dropped there and the
  README names `uninstall.ps1`.
- Zip bytes differ between Python builds. Fallback: a stored zip; CI
  pins the builder's Python.
- Path regressions in paths.py. Held by: the two path tests and serial
  ordering of the three packages that touch it.
- Two clients on the dev host fight over the global hotkey. Held by:
  DEP-13's acceptance (the checkout says so and keeps running).
- Wrong folder deleted by the uninstaller. Held by: the marker check,
  fixed child names, "is it ours" on every external item, `-DryRun`.
- The pasted line runs remote code. Limited to the small bootstrap on an
  immutable release; the `-Zip` route is for reviewers.
- Pin upkeep: Electron 45 ends about 2027-04-27 (tentative); Electron
  pin moves come from F-130's watcher, CPython pin moves from DEP-19,
  and each ships as a 0.y.z release. An Electron bump that arrives as a
  Dependabot pull request is never merged on GitHub: the lane re-applies
  it locally as an operator commit (FLEET item 17, plan 04), and the
  release workflow merges nothing.
- GitHub rate limit (60 unauthenticated requests an hour per IP) and
  proxies: the check backs off and stays silent; the release page link
  is the fallback.
- Marked option, not adopted: a bundled offline full zip (about 172 MB).
  It needs a licence decision for redistributing Electron and CPython
  and would reverse part of Q-20's reasoning.

## Spike record

Amended 2026-11-18 (close-out, LE-164): DEP-01 writes its results to the
new file docs/ops/runtime-spike-record.md (F-038). This section stays
empty, because a final planning file is not edited by a package.

## Verification

Independent check, 2026-11-18, by a second agent (not the author).

Checked:

- Yardstick F point by point: one-step install (G1, DEP-09), versioned
  artifact (G2, G3, DEP-03, DEP-08), update path with web data on and
  off (G6, DEP-11, DEP-16, DEP-17), clean uninstall of processes, the
  logon task and the home, data and the checkout sidecar only by
  consent (G7, DEP-10), releases only on a REL-PREP milestone or an
  explicit version and the operator's phrase (G4, DEP-12), auto-written
  changelog from commit subjects and ROADMAP rows (G5, DEP-04), stdlib
  core, Electron exact pin, no runtime CDN and sidecar rules (G10).
- Repo claims, by opening the files: VERSION "0.1.0" in
  server/al/__init__.py and app/package.json; the webfetch User-Agent
  reads VERSION; ports.py has only AL_PORT 8960 in block 8960-8979;
  keepalive.py core_command and run_preflight use `-m server.al`;
  launcher.js; hotreload.py dev_enabled keys on `.git`; autostart.ps1
  registers "AshLight Autostart" through wscript and
  autostart_launch.vbs; setup.ps1 writes the Start Menu and Desktop
  links and has -TcCalc and -NoShortcut; run.ps1 has -NoOverlay,
  -NoBrowser and -Port; build.ps1 runs the snapshot as `-m
  server.al.theorycraft.snapshot`; procs.py's proven-ours rule;
  stop.request in stop.ps1; tools/tc_pin.py's asset hosts;
  .githooks/pre-push refuses every push and commit-msg runs the identity
  strip and the leak sweep; 13 packages in the lockfile and electron the
  only (dev) dependency; Electron `engines` `>= 22.12.0`; no
  `git tag` or publish path in the loop tools; merge subjects are
  `merge: <ROW-ID> ...`; the research numbers (0053 F7 to F9, the
  framework package counts, the 2027-04-27 end of life). Not present
  yet and named as new: config/electron_pin.json (F-044),
  config/runtime_pins.json, requirements-dev.txt, CHANGELOG.md,
  docs/releases/, .github/workflows/, server/al/buildinfo.py (F-027),
  scripts/install.ps1, scripts/uninstall.ps1, app/test/launcher.test.js.
- findings.json: every cited finding and ruling; dispositions (F-016,
  F-021 and F-076 blocked on Q-23; F-046 blocked for release builds;
  F-210 deferred); not-adopted 0052-X1 to X6 and 0053-X1 to X9; the
  install-shape, update, release, changelog, version-check, fuses and
  remote conflicts; the floor audit reworks of F-049, F-063, F-074,
  F-077, Q-21. Inputs 0052, 0053 (Fit section, R1 to R11, Rejected,
  Open questions), 0050 F29 and F31, 0039 R1 and R5, 0042, 0046 R9 and
  R10.
- Dependency graph: no cycle; every "Parallel with" checked against
  shared files and dependencies.

Corrected (27):

1. Launch sites: launcher.js runs `-m server.al.paths` and a hidden
   run.ps1, not `-m server.al`.
2. Operator act 3: `gh` is already authenticated (findings conflict);
   no sign-in act.
3. DEP-12 edited .githooks/pre-push, which rests on F-016 (blocked on
   Q-23): the call now rides F-016's ready diff.
4. Parallel claims that contradicted dependencies (DEP-08 with DEP-09,
   DEP-11 with DEP-12, DEP-17 with DEP-18) or shared files (DEP-02,
   DEP-07, DEP-06 on setup.ps1 and autostart.ps1; DEP-04 and DEP-08 on
   tools/release.py); the Order's first wave fixed to match.
5. Critical path put DEP-17 after DEP-18, which depends on it.
6. The commit-msg type list would have refused subject types main
   already uses (audit, design, verify, revert, done) and git's own
   `Merge branch` subjects.
7. The unattended REL-PREP lane wrote the hand-off; it now sets a
   BLOCKED row (CLAUDE.md loop rule; /done owns the hand-off).
8. DEP-01 named "4 more" tests without naming them, and the embeddable
   runtime has no pytest.
9. DEP-02's TEST-CLEAN-CLONE re-run was a ROADMAP row name, not a
   runnable test.
10. The stage round trip would have written the operator's real
    shortcuts, uninstall key and logon task.
11. Reproducibility left clock, SBOM timestamp and serial open, which
    would break CI's SHA256SUMS comparison.
12. Nothing enforced F-046 (release builds poll no poe.ninja until its
    yes): Design point 16, DEP-08 refusal, DEP-18 dependency.
13. Runtime fetch inside an update contradicted "never fetched by the
    running core" (F-047): Design point 13.
14. Dropped inputs: installed-mode game data (F-072 step 2, Q-04) and
    the calc opt-in (F-132): Design point 14, DEP-09.
15. First-run config: web data off and no Client.txt consent stated and
    tested (floor opt-in, decision 0013).
16. Floor read strictly: the pasted line and every installer request
    send an AshLight User-Agent with the version; bump stamps it.
17. Web data off: version plus releases link (0052 R6, 0053 Fit 4,
    F-077) added to G6 and DEP-16.
18. The new opt-in wording (F-077, Q-21) had no package: DEP-16.
19. Self-test priority and the `game_idle` gate (FPS floor).
20. CPython pin watch (0053 R10) was dropped: new DEP-19.
21. Checkout purge would have deleted agent temp folders and the
    installed home; now excluded.
22. "Byte-identical on every machine" contradicted printing the home
    path; narrowed to F-063's test.
23. Tag push named as one explicit ref; publish never pushes a branch.
24. CI: the identity guard is installed by plan 04, CI merges no pull
    request and pushes nothing; Dependabot bumps re-applied locally.
25. Asset hosts named.
26. Where the decisions get recorded (plan landing).
27. New test files marked new or named (app/test/launcher.test.js,
    tests/test_readme.py).

Left as stated: sizes L for DEP-09 and DEP-11 (one agent each, own
files); the offline full zip stays a marked option (Q-20 wins over
F-048); scoop stays deferred (F-210).

Amended 2026-11-18 (close-out; docs/plan/07, Rulings 2026-11-18
(close-out)); Status stays final: the 'final version without a tag'
refusal applies to `build --tag` only (LE-53); operator acts 1 and 2
follow the recorded go and the default address (LE-01, LE-02); the
poe.ninja message is optional (LE-38); the spike record moves to
docs/ops/runtime-spike-record.md (LE-164).
