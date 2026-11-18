# 0078 - Ultraplan rulings ledger: Q, A and LE calls with their defaults (ULTRAPLAN)

Date: 2026-11-18. Source: the rulings of a distinct adjudicator on the 28
open decisions of the plan (docs/plan/findings.json `rulings`,
docs/plan/02 Rulings), the floor audit of the same day by three lenses
(findings.json `floor_audit`, `operator_decisions`), the close-out
rulings on the loose ends (docs/plan/07, Rulings 2026-11-18 (close-out)),
the one batched operator ask (docs/plan/09) and the target design
(docs/plan/03, design 0001 amendment 2026-11-18).

## Decision

The calls below are settled. An execution session does not reopen one;
it reopens only on the entry's own Reverses-if. Where the entry names a
package, that package writes the decision or the dated amendment and its
Settled bullet when it lands (the numbers are the reserved ones of
docs/plan/07); this ledger changes no other decision's text. Entries
marked OPERATOR wait on the operator alone: the default named is in
force and no open wave waits for the answer. The wording here is the
ruling after the floor audit and the close-out; where an earlier draft
of a ruling read looser, this text wins.

Rule of the floor audit, kept for every later doubt: an item flagged by
two or three lenses takes the strictest fix; an item flagged by one lens
takes the stricter reading too unless the flag is plainly mistaken; no
doubt is resolved in favour of the looser reading; no adjudicator and no
settled decision widens the Game ToS floor.

### Build input paths

- Q-01 (OPERATOR, OA-24) Reading files Path of Building writes on disk.
  - Decision: outside the current floor text. No read of PoB's builds
    folder or its API answer file. Default in force: no.
  - Alternatives: an opt-in folder read under a new decision plus a
    read-list line; the folder plus the API answer file.
  - Why: the floor's READ ONLY list names Client.txt, the per-press
    clipboard / screen read and public web data, and reads as
    exhaustive. The hotkey build load covers most of the paste pain.
  - Reverses if: the operator adds a read-list line in their own words;
    then the folder source lands under a new decision with no rework.
  - Record: none (F-071 stays not adopted).
- Q-02 (hotkey half settled; file half OPERATOR, OA-25) What counts as
  player-supplied build text.
  - Decision: a build loaded by the item-check hotkey press (the same
    single clipboard read) counts. A save file the player picks in
    AshLight's own page is held: the read list does not name it. Default
    in force: no file pick for builds; the hotkey load ships alone.
  - Alternatives: paste box only; both halves at once (the first ruling,
    struck by the floor audit).
  - Why: the hotkey load is the player's own act and keeps one read per
    manual press. The pick has the shape of decision 0033 (bytes, never
    a path), but neither an adjudicator nor a settled decision may add a
    read source.
  - Reverses if: the operator adds the read-list line (then
    TC-BUILD-FILEPICK leaves wave 99), rules the build load needs its
    own hotkey, or decision 0003 reverses.
  - Record: TC-PRESS-BUILD (wave 3) amends decision 0004 and the
    CLAUDE.md Stack sentence.

### Data sources and web requests

- Q-03 Default User-Agent contact once public.
  - Decision: once the repository is public the default contact of
    every install, of the CI watcher and of the OAuth application is the
    project's issues page; a typed per-install contact stays an optional
    override. Until the address exists, decisions 0015 and 0016 stand as
    written.
  - Alternatives: per-install contact only; no default.
  - Why: truthful and reachable, keeps personal contacts out of tracked
    files, removes the one typed step before prices. The User-Agent
    still names AshLight and its version.
  - Reverses if: poe.ninja or GGG say a per-user contact is required, or
    the issues page is not monitored.
  - Record: DATA-CONTACT-DEFAULT (parked until GP-10 is on main) amends
    decisions 0015 and 0016.
- Q-04 Game-data snapshot at start time.
  - Decision: the fetch may run at build time or at start time, by the
    snapshot tool as its own hidden low-priority process, only while
    web_data is on and the cache is missing or over 24 h old. The core
    never fetches. poe2db / wiki data stays build-time attributed
    snapshots only.
  - Alternatives: build time only, with setup.ps1 running it when
    web_data is already on.
  - Why: an installed copy has no build step, which is the 0013
    amendment's own Reverses-if. Same opt-in, sources, User-Agent and
    contact.
  - Reverses if: a source objects to start-time fetches, or the hidden
    process costs overlay budget in play.
  - Record: DATA-SNAP-AT-START (wave 13) amends decisions 0009 and 0013.
- Q-05 with LE-38 (OPERATOR, OA-2, optional) poe.ninja and public
  releases.
  - Decision: the tiered cadence (at most about 200 overview requests a
    day) ships for source checkouts. A release build makes no poe.ninja
    request and shows the trade link only until poe.ninja's written yes,
    an approved mirror or the operator's written ruling is recorded.
    The message to poe.ninja is no flip gate: the operator's order of
    2026-11-18 is its written skip (the hand-off line `OA-2 SKIPPED IN
    WRITING`). Default in force: release builds are link-only.
  - Alternatives: ship the cadence in release builds regardless (the
    first ruling, struck by the floor audit: silence is not consent);
    keep the message as an operator act that gates the public flip.
  - Why: poe.ninja asks desktop apps to proxy through their own backend
    and a public release multiplies requests. Not polling from releases
    serves the ruling's aim better than polling while waiting. One
    constant reverses it.
  - Reverses if: poe.ninja replies yes (DATA-NINJA-RELEASE-ON flips the
    constant); it asks for a mirror or less polling (new decision); the
    operator wants to send the message before the flip (the gate
    returns); or source-checkout polling draws an objection (gate it the
    same way).
  - Record: DATA-PRICE-CADENCE (wave 18, reserved 0072).
- Q-06 (OPERATOR review of 0017, OA-9) Trade link wording.
  - Decision: decision 0017 stands unchanged. The overlay card shows the
    item name instead of "Trade link ready" when no poe.ninja value
    exists. Default in force: 0017 stands.
  - Alternatives: keep the old wording; reverse 0017 (a reversal still
    could not call the undocumented trade2 endpoints).
  - Why: only a URL the player opens is built; the wording is display
    text and the name is more useful.
  - Reverses if: GGG documents trade endpoints or permits third-party
    use in writing, or the operator rules otherwise (0017's own terms).
  - Record: OVL-COPY-FIRST (wave 10) amends decision 0016.
- Q-07 (in force now; OPERATOR option OA-22) GGG's patch-notes forum.
  - Decision: the floor's GGG clause binds dev research reads. No agent
    or tool reads GGG's patch-notes forum. Dives use operator-pasted
    text, public repositories and GGG's API Reference and Data Exports
    pages; the developer-docs changelog only if the operator's floor
    line (A-01) allows it. Default in force: no forum reads.
  - Alternatives: robots-respecting low-frequency research reads.
  - Why: the floor allows GGG endpoints only if they are in the API
    Reference or Data Exports; the forum is a GGG host outside both and
    the floor cannot be read more loosely.
  - Reverses if: the operator amends the floor to permit such reads, or
    GGG documents the forum as a permitted source.
  - Record: AUTO-04 (wave 2, reserved 0050) and its edits of research
    0029 and the runbook.

### Settings, hotkeys and autostart

- Q-08 Logon task and preload actions.
  - Decision: the opt-in logon task may start the client tray-only (no
    companion window, overlay hidden until the log wakes); the client
    page may expose a small fixed set of named, argument-free preload
    actions.
  - Alternatives: a tray item only; core at logon and the player starts
    the client.
  - Why: removes the last start click; the task stays opt-in and OFF by
    default; fixed names without arguments keep the preload surface
    minimal.
  - Reverses if: idle tray-mode RAM exceeds the decision 0002 budget, a
    preload action is shown to take arguments or paths, or the task is
    refused for a standard user.
  - Record: REL-AUTOSTART-TRAY (wave 12), REL-AUTOSTART-SWITCH (wave 14)
    and TC-CALC-OPTIN-BUTTON (wave 16) amend decisions 0011 and 0041.
- Q-09 (OPERATOR, OA-26) Item key.
  - Decision: the keys stay Alt+Shift+E and Alt+Shift+A (at most two
    global keys) until the operator reports both one-minute checks. The
    item key moves to Ctrl+<letter> only on a letter the operator names
    as free; the Alt+Shift pair is replaced only if it flips the
    keyboard layout. Default in force: the current keys.
  - Alternatives: keep the keys for good; guess a Ctrl letter from
    outside documents.
  - Why: both checks are physical acts; AshLight never reads the game's
    key binds, so code cannot derive a free letter.
  - Reverses if: the operator reports a layout flip or names a free
    letter (then OVL-ITEM-KEY-CTRL leaves wave 99).
  - Record: none.
- Q-10 Calc on the dev host.
  - Decision: tc_calc is turned on in the dev host's gitignored
    config/local.json. The default stays off for everyone else
    (decision 0018).
  - Alternatives: leave it off.
  - Why: the component is installed there; real numbers for the pin and
    the calc budgets before 1.0; local and reversible.
  - Reverses if: calc use breaks a budget (decision 0024 R7), slows
    presses, or the dev host should mirror a default user.
  - Record: none (TC-PRESS-STAGED-LIVE, wave 9, relies on it).

### Security and phone view

- Q-11 (OPERATOR, OA-27) Phone view.
  - Decision: no AshLight network path for a phone. The 127.0.0.1-only
    bind, the LAN-off rule and the per-start token stand; no read-only
    stream key is built. Default in force: none (P0); a wireless second
    display through third-party software needs no AshLight change.
  - Alternatives: P1 a narrow same-PC companion window; B an
    operator-run private tunnel; C an opt-in read-only LAN listener
    (lifts the bind rule).
  - Why: the bind rule is a settled CLAUDE.md rule and no evidence meets
    a reversal condition; residual risk rises from P0 to C.
  - Reverses if: the operator picks P1, B or C; then a decision scoping
    or lifting the bind rule is recorded before any work.
  - Record: none.

### Loop, HALT and watchers

- Q-12 Unattended row-file commits.
  - Decision: once built, the tick may commit add-only row files
    (docs/roadmap/new|done/<ID>.md) from tracked templates and validated
    tokens, at most 3 filed rows a local day, with the operator
    identity, only through the kit git lock, never while HALT exists.
    Pin moves stay session commits.
  - Alternatives: watchers only report in the checklist.
  - Why: the narrowest possible auto-commit: no existing file changes,
    no upstream prose, reverted by one git revert.
  - Reverses if: a tick commit touches a non-row path, a bad row lands,
    tokens fail validation, or the operator rules unattended commits
    unwanted.
  - Record: LOOP-WATCH-WIRE (wave 17) amends decision 0025.
- Q-13 Watchers under HALT.
  - Decision: read yes, act no. Once built, the PoB release check
    (static trial only) and the Electron release watch read while HALT
    exists; no bump, no candidate-Lua trial and no commit while HALTed.
    Until then only the docs watch of decision 0044 reads under HALT.
  - Alternatives: respect HALT fully.
  - Why: mirrors decision 0044; HALT should not blind drift detection;
    one anonymous read per 24 h that decision 0025 already permits.
  - Reverses if: GitHub limits or terms bar the daily read, or the
    operator rules HALT must stop all network reads.
  - Record: AUTO-05 (wave 13, reserved 0069) and LOOP-WATCH-WIRE (wave
    17, amends decision 0025).

### Design tokens, layout and theme

- Q-14 (OPERATOR option, OA-31) Reference setup of the type scale.
  - Decision: ship with the stated reference setup (24 inch 1080p,
    dashboard at 80 cm, overlay at 60 cm).
  - Alternatives: wait for the operator's measurement.
  - Why: sizes are tokens and the distance rule is a test, so a later
    measurement changes values only.
  - Reverses if: the operator supplies a real size, resolution, distance
    or a contrast complaint.
  - Record: none (PLAY-TD-03-TOKENS, wave 4).
- Q-15 (OPERATOR option, OA-30) "NLM".
  - Decision: NLM means natural-language messaging; design 0001 spells
    it out and drops its interpretation note.
  - Alternatives: leave the note open until the operator replies.
  - Why: design 0001 section 9 and the DS-NLM work already read it so.
  - Reverses if: the operator says it meant something else.
  - Record: none (PLAY-TD-03-TOKENS, wave 4).
- TD Target design.
  - Decision: the base is design A, the fixed cockpit, with grafts G-01
    to G-19 and the corrections of docs/plan/03 section 1: Play is 7
    regions with fixed tracks, four tabs (Play, Build and items, Run,
    Settings), dark by default with a Theme choice, the overlay stays 2
    HUD lines plus one card. The amendment of 2026-11-18 in design 0001
    is the rule text for each TD-nn package; sections 1 to 11 of design
    0001 stay in force for shipped UI until the package that names a
    section lands.
  - Alternatives: design B (phase-adaptive), design C (overlay-first),
    the three-tab set (option O-4), a third HUD line (option O-5).
  - Why: A ranks first by total (238 against 219 and 195) and by two of
    three judges; fixed tracks make "no scroll" and "same place" hold by
    construction; the overlay window stays 280 x 176, so the decision
    0002 budgets are not reopened.
  - Reverses if: a play state needs two contexts at once in region C,
    the no-scroll rule cannot hold with real strings at scale 1, players
    report hunting through Settings more than once a session, or the
    corner map proves routinely covered by the 2-line HUD.
  - Record: PLAY-TD-23-RECORDS (wave 31, reserved 0075) writes the
    decision for what shipped and rewrites design 0001.

### Tests and tooling

- Q-16 Parallel test runs.
  - Decision: pytest-xdist when importable (an optional dev extra,
    pinned), serial otherwise, adopted once the three diagnosed runs
    clear it of the red loop-gate runs. Never imported by server/,
    tools/ or app code.
  - Alternatives: a stdlib shard tool only; xdist required.
  - Why: a dev-only plugin beside pytest keeps shipped code stdlib-only;
    the serial fallback always works.
  - Reverses if: the diagnosed runs show xdist caused flakes or lost
    workers, or the operator rules tests must be stdlib-only.
  - Record: TEST-SUITE-RUNNER (wave 9) amends decision 0002 and the
    CLAUDE.md Stack sentence, after TEST-XDIST-DIAG (wave 8).
- Q-17 (in force from wave 1) Subset runs outside the suite gate.
  - Decision: file-named runs of a package's selected tests may run
    outside the suite gate, with no timing tests and at most 90 s per
    subset; main moves only after one whole green suite through the gate
    per merge batch (decision 0077 point 5).
  - Alternatives: no cap; a whole suite per package.
  - Why: the kit hook already gates only runs that name no file; the cap
    protects against timing flakes and box load; the batch suite keeps
    the commit gate.
  - Reverses if: subset runs cause machine contention or missed
    regressions, or MAIN's kit changes item 16 c to forbid ungated runs.
  - Record: TEST-WAVE-GATE-POLICY (wave 9, reserved 0060).
- Q-18 (OPERATOR act OA-33 closes the row) OVL-FPS acceptance.
  - Decision: (a) the acceptance is budget B19, documented as a proxy:
    no change on the game's own FPS display with the HUD on, AshLight's
    own CPU under 1 percent, system totals within their noise; (b) no
    saved screen capture; (c) no measurement switch ships in overlay
    code: a phase switch lives in tools/ and drives the overlay through
    existing calls. Default in force: the character-select proxy of
    decision 0006 and the static budget tests.
  - Alternatives: all three yes; keep the 1 percent FPS acceptance.
  - Why: B19 is the strongest claim the methods decision 0006 clears can
    support, and decision 0006 item 4 says nothing from the measurement
    ships.
  - Reverses if: existing overlay calls cannot produce the load (re-ask
    with evidence), or the operator clears a per-press cropped capture
    or amends decision 0006 item 4.
  - Record: OVL-CHECK (wave 21) amends decision 0006; decision 0002 is
    not changed.

### Packaging and release

- Q-19 Install home.
  - Decision: players install to a per-user home under the local
    programs folder with state in data\; this machine installs with
    -InstallDir under the AL sidecar; the operator's live copy becomes
    an installed release and the checkout runs on the dev port 8961.
  - Alternatives: the operator keeps running the checkout; the sidecar
    path for everyone.
  - Why: the Sidecar rule stays intact here, players get the reference
    pattern, and every release is used before strangers get it.
  - Reverses if: the installed copy cannot serve daily dev use, or the
    override breaks tests/test_sidecar_paths.py.
  - Record: DEP-05 (wave 7, reserved 0059); the cutover is
    REL-CUTOVER-LIVE (wave 24).
- Q-20 Runtimes of installed copies.
  - Decision: a hash-pinned Electron zip and a private embeddable
    CPython, named by exact version and sha256, fetched at install from
    their publishers and never bundled; the checkout keeps npm ci and
    the system Python. Gated on the spike DEP-01 (wave 8) passing.
  - Alternatives: the pinned Electron zip with the player's own Python;
    npm ci plus the player's Python.
  - Why: removes the two heaviest player prerequisites, follows the
    hash-pin pattern of decisions 0018 and 0027, redistributes nothing.
  - Reverses if: the spike fails, a publisher drops hash-verifiable
    assets, or a licence objection appears.
  - Record: REL-RUNTIME-PINS (wave 10, reserved 0063).
- Q-21 (OPERATOR option, OA-17) Updates.
  - Decision: (a) one read-only GitHub releases check per 24 h, only
    while web_data is on, truthful User-Agent, Retry-After obeyed; (b) a
    verified update is staged and applied at the next start after a 24 h
    hold, the previous version kept, with a Settings switch for
    click-only. The opt-in sentence names the update check and the
    automatic apply; an opt-in given before that wording makes no update
    request until the player has seen it once. Default in force:
    automatic apply.
  - Alternatives: (b) click only; no check, a notice from the release
    page only.
  - Why: mirrors the settled TC-DRIFT daily read and the single opt-in
    of decision 0013; hash checks, hold and rollback bound the risk.
  - Reverses if: GitHub or GGG terms bar the daily read, a bad release
    auto-applies in practice, or the operator wants click-only.
  - Record: DEP-16 (wave 11, reserved 0065); REL-UPDATE-WIRE (wave 22)
    amends decision 0013.
- Q-22 (OPERATOR option, OA-16) Code signing.
  - Decision: none at first; apply to a free open-source signing
    program after the first public release; the README says what
    unsigned means and how to verify hashes (decision 0046 point 11).
  - Alternatives: paid individual signing now.
  - Why: no revenue, and signing must not be funded by GGG-derived
    features; reversible with no rework.
  - Reverses if: SmartScreen friction measurably blocks installs, a free
    program accepts the project, or the operator chooses to pay.
  - Record: DEP-08 (wave 10, reserved 0064).

### Go-public

- Q-23 with LE-01, LE-05, LE-27, LE-79, LE-81, LE-107, LE-140, LE-160
  Who creates the repository, pushes and flips.
  - Decision: the operator's go-public order in the session brief of
    2026-11-18 is the recorded go for step 1 (create the private
    repository and push main) and step 4 (make it public once the
    plan-04 gates pass). Agents create the repository, push and flip.
    The record is the operator's words quoted verbatim in the hand-off
    lines `OPERATOR GO Q-23 step 1` and `step 4`; a sentence in a plan
    document is not the record. The stay-local fallback stays as a live
    safeguard in GP-09 gate 1. The only operator act left is OA-1 (gh
    sign-in), and only if `gh auth status` fails. Immutable releases are
    on before the first v* tag (OA-3 only if the API call fails).
  - Alternatives: the operator creates or confirms the remote and the
    flip (the first ruling); step 1 only; a plan sentence as the record;
    removing the fallback text.
  - Why: the order is the operator's own instruction; FLEET item 1 keeps
    only physical acts, passwords and OAuth grants for the operator; the
    safeguards stay as gates (identity scan 0, leak sweep 0 with the
    needles armed, private first, the flip only on P0 green plus re-run
    scans); the hygiene lift and the guarded hook land before any push.
    This is not a Game ToS floor question.
  - Reverses if: the main session cannot quote the brief verbatim (then
    stay local and the publishing packages go back to wave 99); the
    operator withdraws or narrows the order; a scan finds a hit (then
    stay local or private and file a rewrite request to MAIN); or `gh
    auth status` fails (then OA-1 is the one ask).
  - Record: decision 0046 (GP-02, landed); the hand-off lines are
    written by PLAN-LANDING.
- Q-24 with LE-02 (OPERATOR option, OA-5) The project's own address.
  - Decision: the project's own repository address may appear in
    tracked files through one leak-sweep allow entry. Default address:
    the account gh is signed in as and the name AshLight, read live at
    GP-09. No address and no placeholder sits in a tracked file until
    GP-10 writes config/public_repo.json from the real origin remote;
    features that need it stay off until then. An existing repository of
    that name stops GP-09; it is never reused or overwritten.
  - Alternatives: the address only in release assets and local config;
    the operator supplies owner and name and GP-09 waits; a placeholder
    constant in tracked config.
  - Why: a public project must say where to get it; the operator's
    order leaves gh sign-in as the only act; no placeholder means
    nothing to forget.
  - Reverses if: the operator names another owner or name before GP-09,
    the leak sweep shows the entry masks other ids, or the operator
    prefers an address-free README.
  - Record: decision 0046 point 8 and CLAUDE.md Public-repo hygiene
    (landed); GP-09 (wave 5), PUB-SWEEP-OWN-ADDRESS (wave 17).
- Q-25 A needle hit in history.
  - Decision: only if a scan finds a hit: the affected commits are
    rewritten only on MAIN's ORDER via fleet_rewrite.py, and the
    repository stays private until done. The scans read clean on
    2026-11-18 and no rewrite is requested.
  - Alternatives: a fresh root commit; publishing with hits (never).
  - Why: a rewrite is allowed only on ORDER (FLEET item 17); full
    history keeps the safety record.
  - Reverses if: a rewrite is refused or impractical (then a fresh root
    for the public repository).
  - Record: decision 0046 point 2; GP-01 (wave 1) re-runs the scans.
- LE-28 The floating CI job.
  - Decision: the job test-newest keeps a floating Python 3.14 and Node
    24 as a non-required job with continue-on-error, fenced by tests.
  - Alternatives: exact patch versions; drop the job.
  - Why: the exact-pin rule covers dependencies; this job still installs
    from the hash-pinned requirements file and the lockfile with pinned
    action SHAs; only the runner's interpreter floats, which is its
    purpose (early warning); it cannot gate a release.
  - Reverses if: the job's noise hides real failures, private-phase
    Actions minutes become a real cost, or MAIN's kit or the operator
    rules every CI runtime must be exact.
  - Record: GP-05 (wave 4).
- LE-53 Building a final version before its tag.
  - Decision: the refusal "a final version without a tag" applies to
    `build --tag` only; `--ref` builds the staged final version before
    the tag exists. No artifact carries a tag field, so the `--ref` and
    `--tag` builds of one commit are byte-identical.
  - Alternatives: refuse every untagged final build with a pre-tag flag
    for the stage; tag first, then stage.
  - Why: the procedure of docs/plan/05 stages before tagging and the tag
    message binds the staged SHA256SUMS; a tag field inside an artifact
    would fail the CI byte comparison of every release; tagging first
    would push a tag before the PASS report exists.
  - Reverses if: the operator wants final versions buildable only from a
    tag, or CI's byte comparison is dropped.
  - Record: DEP-08 (wave 10).

### Storage of player data

- Q-26 Local stores derived from item text.
  - Decision: (a) the worn-gear baseline is kept as parsed mod lines in
    one bounded per-character file, on by default; (b) the BUILD-LIVE
    upgrade list stays memory-only (decision 0045).
  - Alternatives: baseline off by default; baseline memory-only; persist
    both.
  - Why: without (a) the baseline dies at every restart; parsed stats
    are not raw item text; local, bounded, no new read source.
  - Reverses if: the operator rules local item-derived files unwanted,
    or a stored baseline is shown to leak names or paths; (b) only on a
    Reverses-if of decision 0045.
  - Record: TC-WORN-STORE (wave 4, reserved 0052).
- Q-27 (OPERATOR act OA-32 uses it) Dev fixture capture.
  - Decision: a dev-host-only switch (a gitignored config/local.json
    key, not a player setting), off by default, may save the sanitized
    item text of presses as fixture candidates in the sidecar. Tracked
    fixtures hold only invented item text.
  - Alternatives: masked property-block shapes in the parse ledger only.
  - Why: the operator's own text from the permitted per-press read; it
    never leaves the dev host; players keep the memory-only rule.
  - Reverses if: the operator rules item text must not be written even
    on the dev host, or a sample holds unmasked names or account data.
  - Record: TC-PRESS-SAMPLES (wave 20) amends decision 0045.
- Q-28 Opening the 1.0 log row.
  - Decision: the dev loop may read AshLight's own run-history file for
    the Act 5 split, falling back to the parse ledger's first Act 5 hit
    when run history is off.
  - Alternatives: a session opens the row by hand.
  - Why: AshLight's own bounded local file, nothing from the game; it
    removes a reminder.
  - Reverses if: the operator rules the dev loop must not read
    player-data files, or a run-history schema change makes the split
    unreliable.
  - Record: none (AUTO-07, wave 16; decision 0036 is untouched).

### Floor audit questions (the operator words the floor)

- A-01 (OPERATOR, OA-18) GGG developer-docs pages outside the API
  Reference and Data Exports (index, authorization, changelog, game).
  - Decision: no new work reads those four pages. The settled watch of
    decision 0044 is left as it is. Default in force: as stated; F-051
    is blocked, the shape topic runs on the reference and data pages
    only, dives skip the changelog.
  - Alternatives: narrow the 0044 watch to two pages now; treat decision
    0044 as having settled the reading.
  - Why: Q-07 reads the GGG clause as binding every GGG host read, while
    decision 0044 reads six pages daily; only the operator words the
    floor, and a settled decision cannot widen it.
  - Reverses if: the operator writes the floor line. An explicit no
    files a session row narrowing the 0044 watch to the two pages (the
    registration signal then needs another source); a line allowing
    named pages releases AUTO-24 and the changelog parts.
  - Record: none.
- A-02 (OPERATOR option, OA-28) User-Agent and package tools.
  - Decision: the strict reading is in force: npm sends an AshLight
    User-Agent, Electron comes only through AshLight's own fetch code,
    no AshLight script runs pip.
  - Alternatives: the bullet binds AshLight's own requests only.
  - Why: the stricter reading wins while the operator has not worded it.
  - Reverses if: the operator answers "own requests only" (the .npmrc
    line is then dropped).
  - Record: OVL-NPM-LOCK (wave 12), OVL-ELECTRON-SETUP (wave 13,
    reserved 0068).
- A-03 (OPERATOR, OA-29) The Steam library scan for Client.txt.
  - Decision: no finding widens discovery. SEC-NO-DISCOVERY (wave 1)
    narrows today's scan to the real entry point with no configured log
    path. Default in force: once the typed path field
    (SEC-LOG-PATH-FIELD, wave 25) is on main and no answer is recorded,
    the strict branch is built and the scan is removed.
  - Alternatives: remove the scan at once (it would leave an install
    with no way to name its log); keep the scan for good.
  - Why: the read list reads as exhaustive and only the operator can add
    the registry key and the library file to it.
  - Reverses if: the operator adds the read-list line (the scan stays,
    narrowed) or answers no earlier (the strict branch is built then).
  - Record: SEC-STEAM-SCAN-A03 (parked) replaces the NO-DISCOVERY
    bullet by the branch taken.

### Close-out rulings not listed above

- LE-39 One agent read of poe.ninja's public economy pages.
  - Decision: the DATA-GUIDE-ONE-BLOCK agent may make one dated read
    pass of poe.ninja's public, human-facing economy pages to record
    their URL forms: robots.txt first and obeyed, a truthful AshLight
    User-Agent, at most one GET per category page form, 30 GETs in all,
    1 s apart, no API or data route, no page body in a tracked file. The
    app requests nothing; it only builds a link the player opens.
  - Alternatives: a landing-page link only; derived or guessed slugs.
  - Why: the floor governs what the app reads; poe.ninja is on the
    permitted list and research already cites dated reads; a guessed
    link misleads the player.
  - Reverses if: poe.ninja's robots.txt or terms disallow such reads,
    poe.ninja objects, or the operator rules agents may not make web
    reads for research (then: the landing-page link only).
  - Record: DATA-GUIDE-ONE-BLOCK (wave 36).
- Fixed without a ruling at the close-out (docs/plan/07 lists each):
  LE-20, LE-32, LE-35, LE-54, LE-80, LE-91, LE-93, LE-101, LE-132,
  LE-148, LE-150, LE-163, LE-164, LE-165, LE-166.
- NOT settled (no usable ruling reached the close-out; each needs its
  ruling before the package or section it names runs): LE-69 (a dated
  pointer in decision 0002 to budget B19), LE-76 (the CI fetch of
  AUTO-19 beside decision 0013), LE-92, LE-99 and LE-100 (the
  `.claude/worktrees/` fallback before OA-12), LE-96 (the Workflow
  equivalent of the kill at 3x).

## Alternatives

- One decision file per ruling: rejected; about 40 files, most of which
  a package will supersede with the real record when it lands, and the
  reserved numbers 0047 to 0076 already name those records.
- Leave the rulings in docs/plan only: rejected; the plan sections are
  long, three of them word Q-23 through dated amendments, and a session
  starts from CLAUDE.md Settled, not from the plan.
- Write every amendment of an existing decision now: rejected; each
  takes effect only when its package lands, the package owns the
  decision file in its wave (one editor a wave), and a Settled line
  ahead of the code would describe behaviour the tree does not have.
- Record the operator items as open questions only: rejected; a session
  must know the default in force, not only that a question exists.

## Why

Execution runs in about ten long sessions, each starting from the
hand-off and CLAUDE.md. Without one settled list, every session meets
the same 28 questions and the floor-audit corrections again, and the
looser first wording of five rulings (Q-01, Q-02, Q-05, Q-07, Q-21) is
still on disk beside the audited one. The ledger names the audited
wording, the default in force for each operator item, and the package
that will write the lasting record, so a session neither reopens a call
nor pre-empts a package.

## Reverses if

- An entry's own Reverses-if is met: that entry alone is re-ruled by a
  distinct adjudicator (or by the operator where it is marked OPERATOR)
  and this file gets a dated amendment.
- The operator answers an item of docs/plan/09: the answer, recorded
  verbatim in the hand-off, replaces the default.
- A package lands the decision or amendment named in an entry's Record
  line: that record then outranks the entry.
- GGG's tool rules change (research 0001 is re-read and every entry
  that cites the floor is checked again).
