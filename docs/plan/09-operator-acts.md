# 09 - Operator acts (the one batched ask)

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md).
Status: final

This is the single list of what only the operator can do or decide.
Agents do everything else. No open wave waits on any entry: every entry
has a default in force. A package that cannot land without the act is
parked in wave 99 until the act is recorded; a package whose act is
optional (GP-03, GP-05, GP-09, PUB-LOCAL-ONLY-TEXT, RUN-LEDGER-WIRE,
DATA-PRICE-CADENCE, DATA-GUIDE-FACTS, DEP-14, REL-STAGE-SANDBOX) lands in
its open wave on the default. Answer in one message, any subset, in any
order; a session copies the answers into the hand-off and reads them
back.

Inputs: docs/plan/findings.json (operator_decisions, rulings), the
rulings and questions of the planning scratch set (needs_operator items),
docs/plan/01 (OP-ACTS, OP-PHONE-LAN, WT-SIDECAR-WIRE, FLEET-KIT-GATE-
REPORT), 02 (operator decisions list), 04 (Operator acts OA-1 to OA-6),
05 (Operator acts 1 to 9), 06 (Operator acts 1 to 9), 07 (Operator go
for publishing, Coverage) and docs/plan/packages.json (blocked.who
operator, operator_act), AL-NEXT-SESSION.txt (OPERATOR ACTS a to k, the
phone decision, the kit defect), decision 0012.

## Checked on this machine (2026-11-18)

- gh: signed in; the token carries the scopes repo and workflow. OA-1 is
  expected to be nothing.
- git: no remote configured. .githooks/pre-push is the guarded push of
  decision 0046 since commits 7fe4993 and 01c2216 (only main and v*
  release tags, tools/push_guard.py, the identity check and the leak
  sweep over every pushed object; no override); when these lines were
  first written it still refused every push. (Corrected 2026-11-18,
  close-out 2.)
- .claude/settings.json: no WorktreeCreate and no WorktreeRemove entry
  (decision 0012 is not wired); line 17 still holds
  "Bash(python tools/ash_lane.py:*)" and tools/ash_lane.py does not exist.
- config/local.json (gitignored): web_data is true; no contact key; no
  loop.dest_inboxes entry; no dev_press_samples or loop_push key.
  FLEET_ROSTER is not set.
- Scheduled tasks: \AshLightOps\LaneLoop is Ready and
  ops/loop/control/HALT exists (loop paused); the logon autostart task of
  decision 0011 is not installed (OFF).
- Windows optional feature Windows Sandbox: Enabled.
- ops/runtime/ggg_docs/REG_OPEN: absent (GGG OAuth registration still
  closed). ops/runtime/verdicts.json: absent. The sidecar cache holds no
  skilltree.json and no poe.ninja book.
- ops/fleet_kit/fleet_suite_gate.py line 672 still reads each ticket
  twice (`_rec(a) and _rec(a).get(...)`): the kit defect is unreported.
  So is the kit fleet_identity pre-push gap (no tag object, three
  trailer keys; ruling R3, 2026-11-18): both ride in the one note of
  AUTO-25 and LOOP-KIT-REPORT-SEND (Not for the operator, below).
- Worktrees: a hand-made sidecar worktree was probed on 2026-11-18
  (docs/plan/08 section 2): Edit, Write, named tests, a commit through
  the git lock and a progress write were all allowed, so wave 1 does
  not need OA-12.

## How to read an entry

Each entry: the ask in one line; kind (physical act | sign-in or grant |
decision); why only the operator; exact steps or command; what it
unblocks (package ids of docs/plan/packages.json); the default in force
if unanswered; when it is needed. Floor questions (the Game ToS floor in
CLAUDE.md) offer the strict answer first; only the operator words the
floor, no adjudicator can widen it.

Ids OA-1 to OA-6 are those of docs/plan/04; OA-7 to OA-11 are the ids
docs/plan/07 and packages.json already use; OA-12 onward are new here.
Where docs/plan/04 ("The go"), 05 (operator act 1) or 06 (operator act
2) read differently on ruling Q-23, docs/plan/07 section "Operator go
for publishing" wins: creating the repository, the first push and the
public flip each need the operator's own words recorded in the hand-off
(OA-10). 2026-11-18: the go is recorded; 04, 05 and 06 now agree
(adjudicator LE-01).

## A - Needed before wave 1

Nothing is strictly needed: wave 1 runs on the defaults. One act is
recommended before wave 1 because wave 1 spawns 11 isolated agents;
since the probe of 2026-11-18 passed (docs/plan/08 section 2) the
default works without it.

### OA-12 Wire the worktree hook of decision 0012

- Ask: paste the two hook entries of decision 0012 into
  .claude/settings.json.
- Kind: physical act (a settings edit).
- Why only the operator: the harness refuses agent edits of
  .claude/settings.json (decision 0012 notes, 2026-11-17).
- Steps: under "hooks" in .claude/settings.json add the WorktreeCreate
  and WorktreeRemove entries exactly as written in
  docs/decisions/0012-worktree-sidecar-hook.md (each runs
  tools/wt_sidecar_hook.py). In the same edit do OA-6 (drop line 17).
  A session then spawns one isolated agent, checks its path is under the
  sidecar Worktree folder and runs tests/test_wt_sidecar_hook.py, whose
  wiring test stops skipping by itself once both entries are present.
- Unblocks: AUTO-26 (F-057, WT-SIDECAR-WIRE).
- Default (F-057; docs/plan/08 section 2): each wave builder makes its
  own worktree under the sidecar Worktree folder by running
  tools/wt_sidecar_hook.py by hand. The repository's gitignored
  .claude/worktrees is only the fallback if the permission system refuses
  edits under the sidecar path; it breaks the Sidecar placement rule
  (decision 0012, Alternatives) and gets one NOTE line in the hand-off.
  Default in force (adjudicator LE-92, LE-99, LE-100): the unwired
  method, because the probe passed (it ran on 2026-11-18 in the planning
  session); else .claude/worktrees, taken without waiting as a recorded
  temporary fallback and reaped at /done. This act moves to the top of
  the ask only if the fallback is ever used.
- When: before wave 1 (recommended; wave 1 does not wait for it).

## B - Before the first push

Since 2026-11-18 the only remaining ask in this part is OA-1, and it is
conditional and expected to be nothing: the Q-23 go is recorded (OA-10)
and the repository address has a default (OA-5).

### OA-10 The Q-23 go in the operator's own words

Recorded 2026-11-18 (steps 1 and 4) from the operator's session brief.
Nothing to do.

- Ask: none. The operator's go-public order of 2026-11-18 is the go for
  step 1 (create the private GitHub repository and push main) and for
  step 4 (make it public once the plan-04 gates pass); adjudicator LE-01.
- Kind: decision (recorded).
- Why only the operator: CLAUDE.md called creating the remote an
  operator act and ruling Q-23 asked for the operator's own words; a plan
  sentence is not the record.
- Steps: none for the operator. PLAN-LANDING writes
  `OPERATOR GO Q-23 step 1 (2026-11-18): "<the operator's words>"` and
  the step 4 line into AL-NEXT-SESSION.txt, copied verbatim from the
  brief by the main session, and reads them back with grep (docs/plan/07,
  "Operator go for publishing").
- Unblocks: step 1: GP-02, PUB-GO-DECISION, PUB-LOCAL-ONLY-TEXT (wave 4),
  GP-09 (wave 5), PUB-DEPBOT-ACTIONS and PUB-DEPBOT-TICK (wave 18),
  PUB-DEPBOT-NPM (wave 19), PUB-HOOK-RELEASE-CHECK (wave 22); behind
  GP-09: PUB-DEPBOT-FIRST-RUN, GP-10, GP-11, AUTO-19, LOOP-CI-ISSUES,
  DATA-CONTACT-DEFAULT, PUB-GUIDE-DOWNLOAD-PLACE, REL-RC-LIVE; step 4:
  GP-12 (it waits for packages only), then GP-13, GP-15, GP-16, AUTO-20,
  DEP-18.
- Default (Q-23), in force only if the lines cannot be written verbatim:
  stay local and prepare everything: no remote is created and nothing
  is pushed (GP-09 gate 1 stops; the pre-push hook itself is the
  guarded push of decision 0046 since commits 7fe4993 and 01c2216 and
  no longer refuses every push); the eight step 1 packages go back to
  wave 99. Checked 2026-11-18 (close-out 2): the lines are in the
  hand-off and match the brief word for word; that they are the go is
  the reading of ruling LE-01, not the operator's wording.
- When: done.

### OA-1 gh sign-in (conditional)

- Ask: run `gh auth login` only if `gh auth status` fails or lacks the
  scopes repo and workflow.
- Kind: sign-in or grant.
- Why only the operator: a credential and an OAuth grant.
- Steps: `gh auth login` (GitHub.com, HTTPS, browser), then
  `gh auth refresh -s repo,workflow` if a scope is missing.
- Unblocks: GP-05 (action SHA re-read), GP-09 (repository creation).
- Default: checked 2026-11-18: signed in with both scopes, so nothing is
  needed; GP-05 uses the SHAs recorded in docs/plan/04.
- When: before the first push, only if the check fails then.

### OA-5 Owner, repository name and copyright holder (Q-24)

- Ask: optionally name another copyright holder, owner or repository
  name than the defaults.
- Kind: decision.
- Why only the operator: only the operator names the account and the
  holder.
- Steps: one line, for example "holder: <name>; repo: <owner>/<name>".
- Unblocks: GP-03 (licence holder), GP-09 (repository name), GP-10 and
  DEP-18 (the real install line and update constant).
- Default (Q-24): signed-in gh account / AshLight, read at GP-09; holder
  "The AshLight authors"; nothing waits for it. No address sits in a
  tracked file until GP-10 writes config/public_repo.json from origin
  (features needing it stay off); the leak-sweep allow-list entry is
  added only at go-public (adjudicator LE-02).
- When: before the first push (GP-03 lands before GP-09).

### OA-3 Immutable releases (conditional)

- Ask: switch on immutable releases in the repository settings page,
  only if the API call answers 404.
- Kind: physical act (a settings page click).
- Why only the operator: no working command is known.
- Steps: repository Settings, General, Releases: enable immutable
  releases; tell the session, which records immutable_confirmed.
- Unblocks: GP-15, REL-RC-LIVE, DEP-15 and DEP-17 live halves.
- Default: no v* tag is pushed (REL-PUBLISH-GATES refuses).
- When: after the first push, before the first v* tag.

### OA-13 The release phrase

- Ask: type `release 0.2.0-rc.1` (and later `release X.Y.Z`) in an
  interactive session, once per release.
- Kind: decision.
- Why only the operator: the operator's order of session 5 (releases
  only on a milestone or an explicit tag); the phrase is the only
  trigger (docs/plan/05 operator act 4).
- Steps: type the phrase `release <version>`; the session runs the
  publish gates (`python tools/release.py publish`, built by
  REL-PUBLISH-GATES, wave 21).
- Unblocks: REL-RC-LIVE (rc.1, private phase), DEP-18 (0.2.0, after the
  flip).
- Default: no release; local release candidates only
  (`python tools/release.py build --ref`, no tag, never pushed).
- When: after the first push (GP-09) and OA-3 (rc); after the public flip
  (0.2.0).

## C - Before going public

Nothing is asked in this part since 2026-11-18: OA-2 is skipped in
writing and the step 4 go is recorded (OA-10, part B).

### OA-2 One message to poe.ninja (Q-05)

Skipped in writing 2026-11-18 (operator order). Optional: sending the
message later only serves DATA-NINJA-RELEASE-ON, which needs poe.ninja's
written yes.

- Ask: none required. Optionally send poe.ninja one message asking
  whether per-install polling at the tiered cadence (about 200 overview
  requests a day) is acceptable, or a project mirror is wanted.
- Kind: physical act (a message to a third party in the operator's
  name), optional.
- Why only the operator: it speaks for the project to a third party.
- Steps: if wanted, send the message through poe.ninja's published
  contact and paste the reply when it comes.
- Unblocks: DATA-NINJA-RELEASE-ON and the poe.ninja prices of DEP-18's
  release builds (both need the written yes; silence is not consent).
  GP-12 no longer waits for it: its gate 5 reads the hand-off line
  `OA-2 SKIPPED IN WRITING` (adjudicator LE-38). DATA-PRICE-CADENCE lands
  either way.
- Default (Q-05): the tiered cadence ships for source checkouts; release
  builds make no poe.ninja request and show the trade link only.
- When: any time; never a gate.

## D - Decisions with a safe default already in force

### OA-18 Floor question A-01: GGG developer-docs pages

- Ask: one floor line saying whether GGG's developer-docs pages outside
  the API Reference and Data Exports (index, authorization, changelog,
  game) may be read.
- Kind: decision (floor).
- Why only the operator: only the operator words the floor; Q-07 reads
  the GGG clause as binding every GGG host read, while settled decision
  0044 reads all six pages daily.
- Steps: the strict answer first: "no: only the API Reference and Data
  Exports"; or the operator's own read-list line allowing named pages.
- Unblocks: AUTO-24 (F-051); the changelog parts of F-115, F-171, AUTO-04
  and AUTO-11.
- Default (A-01): no new work reads those four pages; the 0044 watch is
  left as it is. An explicit no files a session row narrowing the 0044
  watch to the two pages (REG_OPEN, F-149 and F-080 then need another
  signal, for example OA-36's "REG OPEN (operator)" line).
- When: any time.

### OA-29 Floor question A-03: Steam library scan for Client.txt

- Ask: one floor line: is finding Client.txt through Steam's registry
  key and libraryfolders.vdf on the read list?
- Kind: decision (floor).
- Why only the operator: only the operator words the floor.
- Steps: the strict answer first: "the Steam library scan is not on the
  read list" (the typed path becomes the only route); or the read-list
  line that allows it.
- Unblocks: SEC-STEAM-SCAN-A03 (either branch).
- Default (A-03): no finding widens discovery (F-098 typed path, F-001,
  F-049); once SEC-LOG-PATH-FIELD lands and no answer is recorded, the
  strict branch is built and today's scan is removed.
- When: before SEC-LOG-PATH-FIELD's row flips (any time).

### OA-28 Floor question A-02 (optional): User-Agent and package tools

- Ask: does the User-Agent bullet bind package tools that setup runs
  (npm, pip) or only AshLight's own requests?
- Kind: decision (floor).
- Why only the operator: floor wording.
- Steps: the strict answer first: "it binds them"; or "own requests
  only".
- Unblocks: nothing; "own requests only" drops the .npmrc line (F-037).
- Default (A-02): strict: npm sends an AshLight User-Agent (F-037),
  Electron comes only through AshLight's own fetch code (F-044), no
  AshLight script runs pip (F-089).
- When: any time.

### OA-24 Floor question Q-01: reading PoB's builds folder

- Ask: add one line to the CLAUDE.md read list allowing an opt-in read
  of Path of Building's builds folder (optionally its API answer file),
  path shown?
- Kind: decision (floor).
- Why only the operator: the read list reads as exhaustive.
- Steps: the strict answer first: "no"; or the operator's own read-list
  line.
- Unblocks: F-071 (not adopted until the floor text changes; then a new
  decision, no rework).
- Default (Q-01): no; the item-hotkey build load (F-042) carries the
  build pain.
- When: any time.

### OA-25 Floor question Q-02: a build file the player picks

- Ask: add one line to the CLAUDE.md read list allowing a file the
  player picks in AshLight's own page (bytes only, never a path or a
  stored copy)?
- Kind: decision (floor).
- Why only the operator: floor wording; the same line would put the
  filter pick of decision 0033 beyond doubt.
- Steps: the strict answer first: "no"; or the operator's own read-list
  line.
- Unblocks: TC-BUILD-FILEPICK (F-058).
- Default (Q-02): no file pick for builds; the hotkey load ships alone.
- When: any time.

### OA-22 Q-07: GGG patch-notes forum (optional)

- Ask: amend the floor to allow robots-respecting research reads of
  GGG's patch-notes forum, or paste the 1.0 patch notes once.
- Kind: decision (floor) or physical act (a paste).
- Why only the operator: floor wording; a paste is the operator's text.
- Steps: the strict answer first: "no forum reads"; optionally paste the
  notes into a text file under the sidecar Scratch folder for
  UTIL-10-NOTES.
- Unblocks: nothing (F-171, AUTO-07, AUTO-13 work without it).
- Default (Q-07): no forum reads by any agent or tool; dives use
  operator-pasted text, public repositories and the API Reference and
  Data Exports pages.
- When: any time; a paste is most useful after 2026-12-11.

### OA-27 Q-11: phone view

- Ask: is any phone view wanted, and which design: P1 (same-PC
  companion window), B (operator-run private tunnel) or C (opt-in
  read-only LAN listener, lifts the bind rule)?
- Kind: decision.
- Why only the operator: "Bind 127.0.0.1 only; LAN access stays off" is
  a CLAUDE.md rule only the operator lifts.
- Steps: one word: P0 (none), P1, B or C. A decision is recorded before
  any work.
- Unblocks: F-205, OPEN-18, CARRY-19 (operator-gated units; no package).
- Default (Q-11): P0: no AshLight network path for a phone; bind
  127.0.0.1, LAN off, per-start token; no stream key.
- When: any time.

### OA-9 Review decision 0017 (hand-off act k) and Q-06 wording

- Ask: should decision 0017 (the app calls no trade endpoint, it only
  builds a search URL the player opens) be reversed?
- Kind: decision.
- Why only the operator: 0017's reverses-if names "the operator rules
  otherwise".
- Steps: "keep 0017" or "reverse 0017" (a reversal still cannot call
  undocumented trade2 endpoints: floor, ToU 7i).
- Unblocks: CARRY-18 (operator-gated unit). DATA-PRICE-CARD-TEXT and
  OVL-COPY-FIRST already follow Q-06's ruled wording.
- Default (Q-06): 0017 stands; the overlay card shows the item name
  instead of "Trade link ready" when no poe.ninja value exists.
- When: any time.

### OA-30 Confirm "NLM" (hand-off act h, Q-15)

- Ask: does "NLM" in the design order mean natural-language messaging?
- Kind: decision.
- Why only the operator: it was the operator's own word.
- Steps: one word: "yes", or what it meant.
- Unblocks: nothing; a different meaning reworks docs/design/0001
  section 9 and DS-NLM.
- Default (Q-15): natural-language messaging; the interpretation note
  becomes a plain definition.
- When: any time.

### OA-26 Q-09: two one-minute key checks

- Ask: with two keyboard layouts installed, press Alt+Shift+E and
  Alt+Shift+A and say whether the layout changes; in the game's key
  binds name one unbound Ctrl+letter next to C.
- Kind: physical act.
- Why only the operator: it needs the operator's keyboard and game key
  binds; AshLight never sends input to the game.
- Steps: as asked; reply "flip: yes/no; free: Ctrl+<letter>".
- Unblocks: OVL-ITEM-KEY-CTRL (F-054).
- Default (Q-09): the item key stays Alt+Shift+E and the second key
  Alt+Shift+A.
- When: any time.

### OA-8 Contact on the dev host (hand-off act g)

- Ask: set the User-Agent contact on the dev host (web_data is already
  on there).
- Kind: decision (a personal value in a gitignored file).
- Why only the operator: the contact is the operator's identity and
  cannot be guessed (decisions 0015, 0016).
- Steps: after DATA-CONTACT-UI (wave 24; it adds the write-only field
  to the "Prices and web data" card on top of the DATA-CONTACT-FIELD
  setter of wave 17): type it once in the dashboard field; before that:
  "contact": "<value>" in config/local.json. Keep "Use web data" ticked.
- Unblocks: TC-TREE-URL, DATA-PRICE-TYPE-PROOF, DATA-GUIDE-ACTS-5-6
  (snapshot refresh; `scripts/build.ps1 -Snapshot` once is the
  alternative there), the W6 watcher; CARRY-16.
- Default: no contact: no poe.ninja request and no GGG tree export on
  the dev host; the trade link only. Once public the project issues page
  is the default contact (Q-03).
- When: any time.

### OA-17 Update default (Q-21, optional)

- Ask: say "click-only" to make updates wait for a click.
- Kind: decision.
- Why only the operator: a product default the operator may override.
- Steps: one word.
- Unblocks: nothing (DEP-16 and DEP-17 ship either way).
- Default: a verified update is staged and applied at the next start
  after a 24 h hold; a Settings switch gives click-only.
- When: before the first public release.

### OA-23 Electron source while web data is off (optional)

- Ask: say in writing whether the Electron release watch may read while
  the dev host's web_data is off.
- Kind: decision.
- Why only the operator: it widens the web_data opt-in (decision 0013).
- Steps: one line.
- Unblocks: nothing today: web_data is on on the dev host (checked).
- Default: the Electron source waits for web_data (docs/plan/06 operator
  act 9).
- When: only if web_data is turned off.

## E - Optional and conditional acts

### OA-19 Tick the parse-ledger consent once

- Ask: tick the new ledger consent line once in Settings.
- Kind: physical act (a consent click).
- Why only the operator: consent is the player's.
- Steps: after RUN-METRICS-SITES and RUN-LEDGER-WIRE land (waves 15 and
  16): Settings, tick the ledger consent line.
- Unblocks: RUN-LEDGER-WIRE (its live half), RUN-LIVE1-FIXTURES,
  PLAY-MAP-MODE-ON, DATA-GUIDE-GAP-TUNE, RUN-LIVE-CLICKS-CLOSE.
- Default: the ledger stays idle; LIVE-1 lines stay unseen;
  GATE-ACT5-SEEN relies on run history alone.
- When: after wave 16.

### OA-20 Play as usual with the client running

- Ask: play normally with the client running: log in once, run a map,
  and after the 1.0 launch play one session.
- Kind: physical act.
- Why only the operator: the floor allows a log read only of the
  operator's own play; no agent plays or sends input.
- Steps: none beyond normal play (after OA-19). No separate LIVE-1 play
  session is asked (hand-off act b is replaced; CARRY-12).
- Unblocks: RUN-LIVE1-FIXTURES, RUN-LIVE-CLICKS-CLOSE, RUN-OVL-BUDGET-
  CLOSE (the RAM half of hand-off act a), PLAY-MAP-MODE-ON,
  DATA-GUIDE-GAP-TUNE (14 days of campaign play), UTIL-10-LOG.
- Default: those rows stay parked; nothing else waits.
- When: any time after wave 16 (budget log: after wave 24).

### OA-33 One map for the FPS check (hand-off act a)

- Ask: play one map in Windowed Fullscreen with the game's FPS display
  on while tools/ovl_check.py is armed; answer "same" or "dropped" once.
- Kind: physical act.
- Why only the operator: only the player sees the game's own FPS
  display; decision 0006 bars PresentMon / ETW.
- Steps: a session arms tools/ovl_check.py (after OVL-CHECK, wave 21);
  play one map; type the answer at the end.
- Unblocks: OVL-FPS.
- Default: OVL-FPS stays open; budgets rest on the tests and budget log.
- When: after wave 21.

### OA-34 Three in-game tries with a verdict click each

- Ask: load one AshLight-made .build in the game's planner, paste one
  search string with a leading "!", and import the filter snippet plus
  one merged real filter; press Worked or Refused on the "Tried in game"
  card for each.
- Kind: physical act.
- Why only the operator: AshLight never writes game folders or sends
  input; only the player loads files in game.
- Steps: after RUN-VERDICTS-UI (wave 19): save each file from the
  dashboard, use it in game, click the verdict.
- Unblocks: RUN-BUILDFILE-LIVE-CLOSE, RUN-VERDICTS-CLOSE.
- Default: TC-BUILDFILE-LIVE, LIVE-SEARCHSTR, LIVE-FILTER and
  LIVE-FILTER-MERGE stay open.
- When: after wave 19.

### OA-32 Six sample presses (Q-27)

- Ask: allow the dev-host sample switch and press the item key once on
  each of six item kinds in normal play.
- Kind: physical act.
- Why only the operator: the per-press clipboard read happens only on
  the player's own press.
- Steps: after TC-PRESS-SAMPLES (wave 20): "dev_press_samples": true in
  config/local.json (a session sets it on the operator's yes); press on a
  rare, a unique, a currency stack, a waystone, a tablet, a gem (plain
  and advanced copy).
- Unblocks: TC-PRESS-FIXTURES, DATA-LOOT-TALLY; through
  TC-PRESS-FIXTURES also TC-WAYSTONE-TUNE, TC-WAYSTONE-TUNE-UI and
  TC-AFFIX-LINE.
- Default: switch off; fixtures stay synthetic.
- When: after wave 20.

### OA-35 One screen-reader run

- Ask: with the game closed, allow one run with speech output and a
  visible browser on this machine.
- Kind: decision (a permission on the operator's own machine).
- Why only the operator: it speaks aloud and opens a visible window on
  the play machine; only the operator confirms the game is closed.
- Steps: after PLAY-F-204A-SR-TOOL (wave 29): say "game closed, run the
  screen-reader pass"; the session runs tools/sr_pass.py with the
  operator flag once and commits the transcript.
- Unblocks: PLAY-F-204B-SR-RUN.
- Default: no real screen-reader pass; the CDP checks stand.
- When: after wave 29.

### OA-36 GGG OAuth application (hand-off act c)

- Ask: when registration reopens, send the prepared application from
  your own GGG account and paste GGG's reply.
- Kind: sign-in or grant.
- Why only the operator: a registration belongs to the operator's
  account.
- Steps: when the session-start check finds REG_OPEN (or you see it and
  write "REG OPEN (operator)"): send the text DATA-GGG-APPLICATION
  prepared; the client id goes only into config/local.json; one live
  smoke follows.
- Unblocks: TC-OAUTH-REG, TC-IMPORT, then TC-IMPORT-UI (event fetches
  also wait for GGG's written answers to F-083 questions 1 and 2).
- Default: no OAuth client; the ggg_api provider stays a no-request stub.
- When: when REG_OPEN appears (absent on 2026-11-18).

### OA-21 Fleet owner's inbox for outbound notes

- Ask: give the fleet owner's inbox as a loop.dest_inboxes entry in
  config/local.json, or have the fleet owner supply it.
- Kind: decision (a location outside this tree).
- Why only the operator: the value is outside this tree and never goes
  into a tracked file or a note.
- Steps: add the entry on the host (key loop.dest_inboxes, name MAIN).
- Unblocks: LOOP-KIT-REPORT-SEND (the kit defect report, see below).
- Default: the drafted note waits; nothing is sent.
- When: any time.

### OA-7 Logon autostart (hand-off act e)

- Ask: optionally turn on start with Windows.
- Kind: decision.
- Why only the operator: decision 0011 keeps it opt-in, OFF by default.
- Steps: today `scripts\autostart.ps1 -Enable`; after
  REL-AUTOSTART-SWITCH (wave 14) one tick in the tray menu.
- Unblocks: nothing (CARRY-15).
- Default: OFF (checked: no autostart task installed).
- When: any time.

### OA-11 Loop push switch

- Ask: optionally let the headless loop push its own commits.
- Kind: decision.
- Why only the operator: a per-host switch in a gitignored file.
- Steps: "loop_push": true in config/local.json.
- Unblocks: nothing required (PUB-LOCAL-ONLY-TEXT, reopened 2026-11-18
  by ruling R2, builds the switch in wave 4 and ships it off; GP-09
  waits for it, so no remote exists before the switch).
- Default: off; a session reads the loop's commits and pushes.
- When: after the first push.

### OA-6 Settings cleanup (batched with OA-12)

- Ask: drop the stale line "Bash(python tools/ash_lane.py:*)" (line 17)
  from .claude/settings.json; and, only if the harness denies them, make
  the two wording changes of GP-02 in .claude/commands/done.md and
  .claude/agents/adjudicator.md.
- Kind: physical act.
- Why only the operator: settings edits under .claude/ are refused to
  agents.
- Steps: delete the line in the same edit as OA-12; paste the GP-02
  wording only if a session reports the denial.
- Unblocks: GP-16 (F-200); PUB-LOCAL-ONLY-TEXT (only on a denial).
- Default: the line stays; it grants nothing because the file does not
  exist.
- When: any time.

### OA-4 Social preview image

- Ask: upload assets/brand/social-preview.png as the repository's
  social preview.
- Kind: physical act.
- Why only the operator: no write command is known.
- Steps: repository Settings, General, Social preview, upload.
- Unblocks: GP-11 (its optional half).
- Default: GitHub's generated text card (no art, floor-safe).
- When: after the first push.

### OA-14 Windows Sandbox for the first public release

- Ask: allow `python tools/release.py stage --sandbox` (the flag
  REL-STAGE-SANDBOX adds, off by default) for the first public release.
- Kind: decision.
- Why only the operator: it starts a sandbox VM on the play machine.
- Steps: the feature is already Enabled (checked); say "allow sandbox
  stage".
- Unblocks: REL-STAGE-SANDBOX; the second-machine claim of DEP-18.
- Default: the scratch-home round trip is the gate; the per-user
  uninstall key is verified only on this machine.
- When: before the first public release.

### OA-15 One install on a second machine

- Ask: run the pasted install line once on a machine that is not the dev
  host, ideally Windows 11 with Smart App Control on.
- Kind: physical act.
- Why only the operator: it needs a second machine.
- Steps: paste the README install line there; report what Windows shows.
- Unblocks: DEP-14 (README wording), DEP-18 (its optional check).
- Default: the README says the behaviour is unverified; the claim rests
  on the REL-STAGE-SANDBOX run.
- When: after the first public release.

### OA-16 Code signing (Q-22)

- Ask: optionally apply to a free open-source signing program after the
  first public release, or pay for signing.
- Kind: sign-in or grant.
- Why only the operator: an application in the project's name; never
  funded from GGG-derived features.
- Steps: apply; tell the session the outcome.
- Unblocks: DEP-14 and DEP-08 (signed artifacts instead of the unsigned
  note).
- Default: unsigned releases; the README states what unsigned means and
  how to verify hashes.
- When: after the first public release.

### OA-37 Zone-guide facts (optional paste)

- Ask: paste the in-game reward text of the point books and one line per
  blank zone (Root Hollow, Library of Kamasa, Isle of Decay, Brinerot
  Cove).
- Kind: physical act (a paste of text seen in game).
- Why only the operator: the facts come from the operator's own play;
  nothing is copied from third-party guides.
- Steps: paste into the session; it rewrites them in AshLight's words.
- Unblocks: DATA-GUIDE-FACTS (its blank entries).
- Default: those entries are left out or neutral.
- When: any time.

### OA-31 Monitor and viewing distance (Q-14, optional)

- Ask: send monitor size, resolution and viewing distance.
- Kind: decision.
- Why only the operator: only the operator knows the setup.
- Steps: one line.
- Unblocks: nothing (PLAY-TD-03-TOKENS ships on the reference setup).
- Default: 24 inch 1080p, dashboard at 80 cm, overlay at 60 cm.
- When: any time.

## Index: packages and units that name an operator act

Packages whose operator_act or coverage names the act. Packages that
wait only through another package (for example AUTO-19 behind GP-09)
appear in the entry's Unblocks line, not here.

- OA-1: GP-05, GP-09. OA-2: DATA-PRICE-CADENCE, DATA-NINJA-RELEASE-ON,
  DEP-18. OA-3: GP-15, REL-RC-LIVE. OA-4: GP-11. OA-5: GP-03, GP-09,
  DEP-18. OA-6: GP-16, PUB-LOCAL-ONLY-TEXT.
- OA-7: CARRY-15. OA-8: TC-TREE-URL, DATA-PRICE-TYPE-PROOF,
  DATA-GUIDE-ACTS-5-6, CARRY-16. OA-9: CARRY-18. OA-10: none (recorded
  2026-11-18). OA-11: PUB-LOCAL-ONLY-TEXT.
- OA-12: AUTO-26. OA-13: REL-RC-LIVE, DEP-18. OA-14: REL-STAGE-SANDBOX.
  OA-15: DEP-14, DEP-18. OA-16: DEP-14.
- OA-18: AUTO-24. OA-19: RUN-LEDGER-WIRE, RUN-LIVE1-FIXTURES,
  PLAY-MAP-MODE-ON, DATA-GUIDE-GAP-TUNE, RUN-LIVE-CLICKS-CLOSE. OA-20:
  RUN-LIVE1-FIXTURES, RUN-LIVE-CLICKS-CLOSE, RUN-OVL-BUDGET-CLOSE,
  PLAY-MAP-MODE-ON, DATA-GUIDE-GAP-TUNE. OA-21: LOOP-KIT-REPORT-SEND.
- OA-25: TC-BUILD-FILEPICK. OA-26: OVL-ITEM-KEY-CTRL. OA-27: F-205,
  OPEN-18, CARRY-19. OA-28: A-02. OA-29: SEC-STEAM-SCAN-A03.
- OA-32: TC-PRESS-FIXTURES, DATA-LOOT-TALLY. OA-33: OVL-FPS. OA-34:
  RUN-BUILDFILE-LIVE-CLOSE, RUN-VERDICTS-CLOSE. OA-35: PLAY-F-204B-SR-RUN.
  OA-36: TC-OAUTH-REG, TC-IMPORT. OA-37: DATA-GUIDE-FACTS.

Hand-off acts mapped: a = OA-33 (FPS) and OA-20 (RAM via the budget
log); b = OA-19 and OA-20 (no separate session); c = OA-36; d = OA-10;
e = OA-7; g = OA-8; h = OA-30; k = OA-9. Letters absent from today's
hand-off (traced by docs/plan/01 OP-ACTS): f = OA-12 (dropped in session
4 without being acted on, carried as WT-SIDECAR-WIRE); i is replaced by
decision 0027 and j is done (decision 0021). The hand-off's phone decision
is OA-27. docs/plan/05 acts 1 to 9 = OA-10 with OA-3, OA-5, OA-1, OA-13,
OA-14, OA-15, OA-16, OA-17, OA-2. docs/plan/06 acts 1 to 9 = OA-18,
OA-10, OA-12, OA-19, OA-8, OA-20, OA-21, OA-22, OA-23.

## Not for the operator

- MAIN (fleet owner): the kit defect in ops/fleet_kit/fleet_suite_gate.py
  line 672 (`_rec(a) and _rec(a).get("exclusive")` reads a ticket twice;
  a ticket removed between the reads raises AttributeError; one read
  bound to a name fixes it). How: LOOP-KIT-REPORT-SEND sends one note
  under the 12 a day cap once a delivery path exists (OA-21, or MAIN
  supplies the inbox); kit files are never edited locally (FLEET item
  11). The same note carries GP-13's two peer gaps (Dependabot security
  updates, the identity guard as a required check) and, since ruling R3
  (2026-11-18), the gap of the kit fleet_identity pre-push check (no tag
  object, tagger or tag message; three trailer keys and three names),
  which tools/push_guard.py covers locally. Nothing of it is reported
  yet. Any Dependabot pull
  request on the vendored identity guard is closed and reported to MAIN
  (GP-14). A history rewrite runs only on MAIN's ORDER via
  fleet_rewrite.py; none is needed (Q-25: needle scan clean).
- GGG: reopen OAuth application registration (watched daily by the
  decision 0044 watch, which raises REG_OPEN); answer F-083 questions 1
  and 2 and question 3 of DATA-GGG-APPLICATION (Currency Exchange
  exemption, which TC-CURX / OPEN-09 wait on). How: the operator sends
  the prepared application when registration opens (OA-36); agents
  never contact GGG.
- poe.ninja: answer the Q-05 message (yes, or a mirror request that
  opens a new decision). How: only if the operator chooses to send it
  (OA-2, optional since 2026-11-18) and pastes the reply; silence is not
  consent.
- Sessions (not operator acts): removing HALT (AUTO-21, no later than
  2026-12-04), setting tc_calc on the dev host (Q-10, the integrator of
  TC-PRESS-STAGED-LIVE), creating the repository, pushing with gh and
  the public flip (GP-09, GP-12; OA-10 is recorded), every build, stage
  and tag after the release phrase, unmarking a bad release as latest.

## Verification record

Independent verifier, 2026-11-18, HEAD 1fb7aae. Read-only on the
machine: no app, core, overlay or loop started, no Client.txt read, only
this file changed.

Checked:
- Every package id named here against docs/plan/packages.json (396
  packages; every other id is a coverage unit, a finding of
  docs/plan/findings.json, a ROADMAP row or a hand-off item). Every
  package whose operator_act is not empty is named; the index matches
  the OA ids each operator_act names, both ways; the seven units whose
  coverage starts with "operator:" are named; every operator_decisions
  qid (Q-01, Q-02, Q-05, Q-07, Q-09, Q-11, Q-23, Q-24, A-01, A-02, A-03)
  stands beside "Default"; every ruling of the planning scratch set with
  needs_operator true (Q-01, Q-05, Q-07, Q-09, Q-11, Q-23, Q-24) has an
  entry; A-01 and A-03 carry "floor" and the strict answer first.
- Wave numbers of every package named as a precondition (DATA-CONTACT-
  FIELD 17, REL-AUTOSTART-SWITCH 14, RUN-METRICS-SITES 15,
  RUN-LEDGER-WIRE 16, RUN-VERDICTS-UI 19, TC-PRESS-SAMPLES 20, OVL-CHECK
  21, REL-PUBLISH-GATES 21, RUN-BUDGET-TESTS-LIVE 24, PLAY-F-204A-SR-TOOL
  29); wave 1 has 11 worktree-isolated packages.
- Commands and flags: `gh auth login`, `gh auth refresh -s` (gh help);
  `scripts\autostart.ps1 -Enable` and `scripts/build.ps1 -Snapshot`
  (param blocks); tools/wt_sidecar_hook.py, tests/test_wt_sidecar_hook.py
  and decision 0012's two entries exist; ops/fleet_kit/fleet_rewrite.py
  exists; tools/release.py (build --ref, stage --sandbox, publish),
  tools/ovl_check.py and tools/sr_pass.py are future files of
  DEP-08 / REL-STAGE-SANDBOX / REL-PUBLISH-GATES, OVL-CHECK and
  PLAY-F-204A-SR-TOOL and are named as such; loop.dest_inboxes is the key
  tools/loop_base.py and tools/loop_inbox.py read (MAIN entry).
- Machine facts re-read: gh signed in with repo and workflow; no git
  remote; .claude/settings.json line 17 is the ash_lane line, no
  Worktree hook entry, tools/ash_lane.py absent; config/local.json has
  web_data true, no contact key, an empty loop.dest_inboxes, no
  dev_press_samples or loop_push; FLEET_ROSTER unset; \AshLightOps\LaneLoop
  Ready, HALT present, no \AshLight Autostart task; Windows Sandbox
  Enabled; REG_OPEN and verdicts.json absent, no skilltree.json or
  book.json in the sidecar cache; fleet_suite_gate.py line 672 unchanged.
- Sources: docs/plan/01 OP-ACTS (letters a to k), OP-PHONE-LAN,
  WT-SIDECAR-WIRE, FLEET-KIT-GATE-REPORT; 04 OA-1 to OA-6; 05 and 06
  operator acts 1 to 9; 07 "Operator go for publishing"; the hand-off
  OPERATOR ACTS, phone decision and kit defect. Floor and CLAUDE.md: no
  entry asks for input to the game, a game-folder write, an undocumented
  trade call, a forum read or a LAN bind without the operator's own
  words; every floor change is offered strict first and worded only by
  the operator. No private name, machine path or account id.

Changed:
- Intro: only packages that cannot land without the act are parked; the
  seven packages with an optional act land in open waves on the default.
- OA-8: the dashboard contact field lands with DATA-CONTACT-UI (wave
  24), not DATA-CONTACT-FIELD (wave 17, the setter only); added the
  build.ps1 -Snapshot alternative for DATA-GUIDE-ACTS-5-6.
- OA-10: Kind no longer says agents do an OAuth grant; the builder
  switch is named with its file; Unblocks adds PUB-DEPBOT-FIRST-RUN,
  AUTO-19, LOOP-CI-ISSUES, DATA-CONTACT-DEFAULT, PUB-GUIDE-DOWNLOAD-PLACE
  (step 1) and AUTO-20 (step 4, with OA-2), as docs/plan/06 act 2 and the
  parked blocks require.
- OA-12: the hook test skips by itself while unwired (nothing to
  un-skip).
- OA-13, OA-14: the bare `build --ref` and `stage --sandbox` are now
  full tools/release.py commands with the package that builds them; the
  phrase is written `release <version>`.
- OA-32: adds TC-WAYSTONE-TUNE, TC-WAYSTONE-TUNE-UI and TC-AFFIX-LINE
  (parked behind TC-PRESS-FIXTURES). OA-36: adds TC-IMPORT-UI.
- Index: states its rule. Hand-off map: letters f, i and j traced.

Close-out, 2026-11-18 (docs/plan/07, Rulings 2026-11-18 (close-out)):
- OA-10: recorded (steps 1 and 4); PLAN-LANDING writes the hand-off
  lines; the eight step 1 packages are scheduled in waves 4, 5, 18, 19
  and 22 (LE-01).
- OA-2: skipped in writing; optional; no longer a flip gate (LE-38).
- OA-5: the default address is read live at GP-09; no placeholder in a
  tracked file (LE-02). OA-12: the default follows docs/plan/08 section 2
  (LE-91). OA-13: needs the first push, not an operator go.
- Parts B and C: the only remaining ask is OA-1, conditional. The index
  follows the operator_act fields of packages.json again: OA-10 names no
  package, GP-12 left OA-2.
- The "Checked" lines above describe the plan before the close-out.

Close-out 2, 2026-11-18 (docs/plan/07, Rulings 2026-11-18 (close-out 2)):
- Checked on this machine and OA-10: the pre-push hook is the guarded
  push of decision 0046 (commits 7fe4993 and 01c2216); it no longer
  refuses every push.
- OA-12: default in force after the probe of 2026-11-18 (LE-92, LE-99,
  LE-100). OA-11: the switch is still to be built by PUB-LOCAL-ONLY-TEXT
  (R2). Not for the operator: the second kit gap rides in the one note
  (R3).
- OA-10: the hand-off lines were compared with the brief; the reading
  that they are the go belongs to ruling LE-01, the OA-2 skip to ruling
  LE-38.
