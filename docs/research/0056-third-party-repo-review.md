# 0056 - Third-party repo review (ideas only)

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension C a
reviewed third-party repo set. Scope: what a set of public third-party
repositories does, how each gets game data and where that sits against the
ToS floor, which ideas AshLight should learn from (ranked, each with a
floor-safe adaptation), licence status for any reuse, cautions, and which
dimension note 0035-0058 each idea informs. No code from the set is copied.
Status: verified

## Sources (all accessed 2026-11-18)

- TP: public source repositories, reviewed on the access date, identity
  withheld at the operator's request. Referred to below only as "a reviewed
  third-party repo" or by the labels repo A to repo G.
- L1: https://choosealicense.com/no-permission/ (no licence means exclusive
  copyright by default; nobody may copy, distribute or modify).
- L2: https://choosealicense.com/licenses/mit/ (MIT permits reuse on the
  condition that the licence and copyright notice travel with the code).
- L3: a public PoE2 game-guide page found by web search on 2026-11-18
  whose search summary names "SSF Standard" and an "SSF <challenge
  league>" form for PoE2; the page itself returned HTTP 402 to a fetch and
  the community wiki returned a bot wall, so the naming stays UNVERIFIED.
- Repo files (this tree, read at HEAD 040e97a; every cited line re-read by
  the verifier at HEAD 5ec96b8): server/al/theorycraft/
  weights.py, evaluate.py, item.py, snapshot.py, bridge.py, waystone.py;
  server/al/hotreload.py, zonenotes.py, underlevel.py, state.py, hints.py,
  parser.py, langguard.py, ninja.py, trade.py, core.py, settingsio.py,
  campaign.py; web/tc.js; app/shared/render_gate.js, format.js.
- Sibling notes cross-referenced: 0036, 0037, 0038, 0039, 0040, 0042,
  0043, 0044, 0048, 0050, 0051, 0054, 0058 (all drafts or verified in this
  ultraplan).

## Summary

- The set holds 39 public repositories (count from the review data; the
  verifier had only the 7 reviewed clones). 7 were deep-reviewed (repo A
  to repo G); 32 were not, for low relevance or the review cap.
- 6 of the 7 are plugins for third-party HUD frameworks that read game
  process memory and draw inside the game; one of those also sends
  synthesized input. The 7th is a data-mining tool that reads installed
  game archives or an undocumented patch CDN. Every live data path in the
  set is outside the floor. Nothing about those paths is carried here.
- What transfers is product and engineering ideas: how settings, rule
  tables, zone notes, caches and drift are handled. 58 ideas were logged
  across the 7 repos (review data); 12 recommendations below draw on them,
  and the rest are merged into sibling notes, already present, deferred or
  rejected.
- Best three for AshLight: store only the player's weight changes over
  shipped defaults (today a default change never reaches an existing
  install, weights.py:197-200); a campaign keep-or-vendor rule check that
  works with no build loaded (today the item check stops at "no build
  loaded", evaluate.py:327-329); and the hot reload fix below (R4).
- One small defect surfaced while checking an idea: hot reload records a
  file's stat signature before loading it, so a read error that happens
  after the file's last write (for example a scanner holding it) pins the
  last good copy until the file changes again (hotreload.py:143-155).
- Code reuse: none recommended. 2 repos are MIT but their useful logic is
  tied to a memory-reading host or a TypeScript stack; 5 state no licence,
  which means all rights reserved (L1). Ideas only.

## Current state

What AshLight already does in the areas the ideas touch:

- Stat weights: one per-host file `<runtime>/theorycraft/weights.json`
  (weights.py:8-9, 182). On first run the full default document is written
  to disk (weights.py:197-200), so later edits to `DEFAULT_WEIGHTS`
  (weights.py:37) only reach new installs. A broken file falls back to
  defaults with `load_error` set (weights.py:204-212). No per-row reset, no
  "changed from default" marker.
- Item check without a build: returns `error: "no build loaded"` and no
  verdict (evaluate.py:327-329). The campaign hints cover boss resist,
  flask base and boots speed, and need a build (campaign.py:11-20, 28-29).
- Item parser: English client strings; unknown lines and sections are
  ignored, odd input goes to `warnings` (item.py:9-10). Mod lines with no
  weight are listed per press as `unweighted` (evaluate.py:318) and shown
  on the card as "Not counted" (web/tc.js:188-216), but nothing keeps them
  past the press or collects them across presses.
- Hot reload: a stat signature `(mtime_ns, size)` (hotreload.py:110-115)
  gates re-reads; `get()` stores the new signature before `check` and
  `loader` run (hotreload.py:143, 147-150), and any exception keeps the
  last good value with a one-line note (hotreload.py:151-155).
- Zone notes: looked up by the act of the area id, then by the English
  zone name from the log, with an act default (zonenotes.py:46-66).
  AshLight-written only; no player layer.
- Hideout flag: from the scene line's `is_hideout` (state.py:1467), which
  the parser sets by an English substring test on the scene name
  (parser.py:76, 120-121, 176; the code marks it UNVERIFIED); the
  `area_entered` branch does the same on the zone name (state.py:1491),
  but that line is a PoE1 form PoE2 never writes (langguard.py:5,
  parser.py:33). hints.py:86-90 already has an area-id based `is_town`.
  The overlay shows the zone in a hideout with an "(HO)" tag
  (render_gate.js:144, format.js:56-61).
- Under-level word: one-sided, shows only when the player is at least the
  threshold under the zone, quiet in towns and hideouts
  (underlevel.py:16-28, 35, 61-85; ROADMAP UTIL-UNDERLEVEL, no XP formula).
- Snapshot fetch: manifest with URL, date, SHA-256, size, ETag per file
  (snapshot.py:5-11, 193-216); sources listed at snapshot.py:73-80. No
  shape probe, no record-count drift report (0037 R8 proposes the probe).
- Price cache: refresh gates read persisted timestamps
  (`overview_attempt_at`, ninja.py:162-168, 264), so a restart does not
  refetch inside the hour. A configured league is used verbatim
  (ninja.py:182-189); the trade link uses the configured text or
  "Standard" (trade.py:122-126). No SSF handling anywhere (grep: no hit).
- PoB bridge: one re-entrant lock serialises calls (bridge.py:125, 267),
  replies framed `ALB1 ` (bridge.py:36). Two quick presses queue, they do
  not run in parallel (core.py:260-274 has no own guard).
- Settings transfer: an allow-list (settingsio.py:10-23, 83); weights are
  not in it yet (0039 R11 proposes adding them).

## Findings

F1. The set is not a model for AshLight's data path. Evidence: TP review
data; repos B-G take zone, player, inventory, UI tree and entity data from
a host that reads process memory, and draw through that host's in-game
renderer; repo F also synthesizes keyboard and mouse input; repo A reads
installed game archives or downloads from an undocumented patch CDN
through a third-party proxy. Why it matters: these are the exact acts the
floor bars (CLAUDE.md "Game ToS floor"). The note records them once,
under Rejected, and never describes how they work.

F2. Technique floor status, one line each (TP):
- Process-memory read through a HUD host (repos B, C, D, E, F, G): outside.
- Drawing through a host's in-game renderer (B, C, D, E, G): outside.
- Synthesized input to the game (F): outside.
- Reading installed game archives (A): outside (game files are not on the
  permitted-read list).
- Undocumented patch CDN download via a proxy (A): outside.
- Statistical type inference over undocumented binary tables (A): outside.
- Host area-change callback (B, C, F): outside as built; the same signal
  is inside when taken from Client.txt area lines (state.py:1477-1487).
- Host-read tool hotkeys that send nothing to the game (G): adaptable;
  AshLight's own hotkeys already do this (decision 0003).
- Cross-plugin price bridge (G): adaptable; AshLight fetches poe.ninja
  itself under decision 0026.
- Public price aggregator over HTTPS with a disk cache (D): inside, but
  sent no truthful User-Agent or contact; AshLight's rule is stricter
  (decisions 0015, 0026).
- Fetched community schema with a format-version gate (A): adaptable.
- Declarative per-column export config (A): adaptable.
- Hand-authored data tables shipped with the tool (B, C): inside.
- Player-written JSON or rule files from a local folder (B, E): inside.

F3. Default-then-override is the strongest transferable pattern. Repo C
stores a weight override only when it differs from the shipped default,
keyed by a stable id, so a later default change still reaches every row
the player never touched; it adds per-row Reset, Reset All and a count of
changed rows (TP). AshLight writes the whole default document on first run
(weights.py:197-200), freezing it. Why it matters: any future tuning of
`DEFAULT_WEIGHTS` (weights.py:37) or the sidegrade band (weights.py:78)
silently skips every existing player; the player also cannot see which
rows they changed.

F4. Campaign players without a build get no item verdict. Repo E's
leveling rules count how many of several thresholds an item meets (life,
each resistance) with thresholds that rise by level band and a count-of-N
rule, plus a separate boots band for movement speed (TP). AshLight returns
"no build loaded" (evaluate.py:327-329). Why it matters: during the
campaign most players have no PoB build pasted; the item hotkey is the one
press they make, and today it tells them nothing about keep or vendor.

F5. Patch catch-up has only a per-press signal on the item side. Repo C
logs each unrecognised option once per area visit (its seen-set clears on
area change) with its raw text, behind a default-on setting, so the table
can be extended after a patch (TP). AshLight already shows the player the
mod lines with no weight on each card (evaluate.py:318, web/tc.js:188-216)
but keeps no list across presses, so the operator cannot see after a
patch which lines players keep hitting. 0051 R1 (OBS-PARSE-LEDGER) and
0050 R11 (LOG-DRIFT) cover the Client.txt side only. Why it matters:
after the 1.0 patch, a diagnostics report could carry the zero-weight
lines without the player retyping them.

F6. Hot reload can pin a stale copy after a transient read error. Repo E
retries a locked rule file up to 10 times at 100 ms (TP). AshLight's
`Watched.get()` sets `self._sig = sig` (hotreload.py:143) before the
loader runs; an OSError from a sharing violation (editor mid-save,
antivirus scan) lands in the except branch (hotreload.py:151-155) and the
next poll sees the same signature and returns the old value
(hotreload.py:141-142). The file is re-read only when its mtime or size
changes again. A lock held while the writer is still writing usually
heals itself (the finished write changes the mtime); the pinning case is
a lock taken after the last write, such as a scanner reading the new
file. Why it matters: a hand edit of zone notes or the zone guide can
then silently not apply, while the Checks note says the last good copy is
in use; the operator would think the edit is broken.

F7. Snapshot drift is caught late. Repo A gates a fetched schema on a
format-version field, keys its cache by version and prunes old versions,
and prints a per-table drift list (row count, schema fit, row growth)
after a patch (TP). AshLight keeps SHA-256 and ETag only (snapshot.py:
193-216). 0037 R8 (TC-SNAP-PROBE) already proposes a pre-replace shape
probe and 0037 R11 a field trim; the record-count delta and missing-field
list are the parts not yet planned.

F8. Showing nothing is a design rule in the set. Repo B draws no panel
when every section is empty, hides in town and hideout by default (each a
setting) and draws separators only between drawn sections; repo E has a
setting to run its highlight outside towns and hideouts, default on, so
the safe-area gate there is opt-out, not opt-in (TP). AshLight's overlay
keeps zone text in hideouts with an "(HO)" tag (app/shared/
render_gate.js:144, format.js:56-61) and decides hideout by an English
substring of the scene name (parser.py:120-121). Why it matters: fewer
pixels over the game is the overlay's FPS and glance budget (decision
0002, 0043, 0048); the substring test also breaks on a non-English client
whose scene names are translated (LANG-GUARD, decision 0040), while the
area id from the generation line is language-independent.

F9. Zone-scoped state lacks one reset point. Repos D, F and G clear all
per-zone state in one place on area change, and repo F ties async work to
a per-area cancellation token (TP). AshLight updates zone fields in
several branches of one handler (state.py:1462-1494, 1495-1512) and in
helpers (maps, hints, visits). Why it matters: a missed field leaks a
card or timer into the next zone; one function plus a test makes that
provable. Effect is small today; it grows with every per-zone card that
0038 R2 and 0054 R4 add.

F10. Price edge cases the set handles. Repo D maps a solo-self-found
league to its trade league for prices and offers the permanent leagues as
fallback; it prefers a direct base-currency rate over a derived one and
warns when expected entries are zero (TP). AshLight uses a configured
league verbatim for poe.ninja and the trade link (ninja.py:182-189,
trade.py:122-126). Repo D strips an "SSF " prefix, but it targets the
first game, so that says nothing about PoE2. For PoE2 a search summary
names "SSF Standard" and an "SSF <challenge league>" form (L3), but no
primary page could be read: UNVERIFIED. 0036 R4 (PRICE-SHAPE-GUARD)
already covers the zero-entry warning.

F11. Player-owned layers over authored data. Repo B layers a per-build
player note over a general zone note and shows the build layer last, dim
labelled; repo G lets the player override any market price, flagged as
overridden (TP). AshLight has authored zone notes (zonenotes.py) and the
poe.ninja book, but no player layer for either. Repo B keys notes by the
English display name, which AshLight also does inside an act
(zonenotes.py:59-60); the area id is the robust key.

F12. Provenance of authored facts. Repo G comments every game constant
with how it was measured and where an inherited value was wrong (TP).
AshLight's authored tables (boss elements, waystone rules, zone guide)
cite research notes but carry no per-entry source or check date. Why it
matters: the 1.0 patch will invalidate some entries and the re-verify list
should come from the data, not from memory (0058 watchers).

F13. Engineering hygiene in the set is weak and not a model: 0 of 7 repos
have tests, 0 have a changelog, 1 has CI (gh-pages and a tarball, with
caret ranges and an unpinned toolchain). AshLight's exact-pin and test
gates (decision 0002, Gates in CLAUDE.md) are already stricter.

## Recommendations

R1. WEIGHTS-DELTA: keep only the player's weight changes.
- Action: store `weights.json` as overrides over `DEFAULT_WEIGHTS` and
  `DEFAULT_SIDEGRADE` (only rows that differ); merge at load; the settings
  panel marks changed rows with the default beside them, a Reset per row,
  Reset All and a "N changed" count; an existing full file migrates by
  dropping rows equal to the current default.
- Impact: H. Every future default tuning reaches existing players; the
  player sees what they changed. It also makes the 0039 R11 export small
  and safe (deltas only).
- Effort: M.
- Risk: a migration that drops a deliberate value equal to the old
  default; mitigated because equal-to-default means no behaviour change at
  migration time. Keep a one-time backup copy under ops/runtime.
- ToS check: local settings only; no game read, no web, no input
  (decision 0003 untouched).
- Depends on: nothing; coordinate with 0039 R11 so the export schema
  carries the delta form.
- Files likely touched: server/al/theorycraft/weights.py, evaluate.py
  (`_weights_of`), web settings panel JS, tests/test_math_weights.py and
  tests/test_tc_eval.py (the existing WeightsStore tests).
- Acceptance test: a test changes one default in a patched module and
  shows an install with an untouched row picks it up while a changed row
  keeps the player value; reset row and reset all return to defaults; a
  schema-1 full file migrates with no score change.
- ZERO-CLICK: migration and merge run at load with no action; the reset
  buttons exist only for a player who chose to tune.

R2. CAMPAIGN-KEEP: a keep-or-vendor check with no build loaded.
- Action: add an AshLight-authored, hot-reloaded rule table (JSON
  conditions, never eval) of level bands from Client.txt and acts from
  HUD-ACT; each band lists thresholds for life, each resistance and
  boots movement speed with a count-of-N rule; when `build is None` the
  item card shows "worth keeping: meets 2 of 3 for level 24" or "vendor"
  instead of "no build loaded".
- Impact: H. Gives every campaign player a verdict on the one press they
  make; today it says nothing (evaluate.py:327-329).
- Effort: M (table, evaluator, card text, tests).
- Risk: thresholds feel wrong for some builds; label it a levelling rule,
  show which thresholds held, and let the table be tuned (hot reload,
  decision 0042). The boots band must agree with campaign.py's
  `boots_speed_level` default 16 (campaign.py:28-29).
- ToS check: item text from the one clipboard read per manual press
  (decision 0003); level from the opted-in Client.txt; act from HUD-ACT;
  thresholds are AshLight's own numbers; nothing is copied from repo E.
- Depends on: nothing hard; 0038 R1 (worn-gear baseline) would later
  replace it with a real comparison once worn gear is known.
- Files likely touched: new server/al/theorycraft/levelrules.py and
  server/al/data/level_rules.json, evaluate.py (the no-build branch),
  app/shared card render, tests.
- Acceptance test: fixture items at levels 10, 30 and 60 give the
  expected keep or vendor verdict and list the thresholds met; a broken
  rule file keeps the last good copy with a Checks note; a loaded build
  still uses the normal comparison.
- ZERO-CLICK: no new press; it rides the existing item-check hotkey, the
  minimum the floor allows (decision 0003, one read per manual press).

R3. UNKNOWN-ITEM-TEXT: keep the per-press "Not counted" lines for a
session.
- Action: collect the `unweighted` list that every press already computes
  (evaluate.py:318) into an in-memory, deduplicated session list, at most
  200 entries; show the count on the Checks card and include the lines in
  the redacted diagnostics report that the player copies on a click
  (DIAG-SELF). The per-press card text stays as it is (web/tc.js:188-216).
- Impact: L-M. After a patch the operator sees which lines players keep
  hitting with zero weight, and a player report carries them without
  retyping. The player-facing part already exists, so the gain is
  operator-side only.
- Effort: S.
- Risk: memory growth (capped); privacy is low because mod text is game
  text, but the line list stays out of any file to keep decision 0045's
  "item text in memory only".
- ToS check: no new read; it reuses text from the per-press clipboard read
  (decision 0003); the report leaves only on the player's click (decision
  0040).
- Depends on: complements 0051 R1 (log side) and 0050 R11.
- Files likely touched: server/al/theorycraft/live.py or evaluate.py,
  server/al/diag.py, Checks card JS, tests/test_diag_self.py.
- Acceptance test: pressing a fixture with one invented mod line twice
  yields one entry and a Checks count of 1; the copied report contains the
  line and no path; a restart clears it.
- ZERO-CLICK: collected silently on presses the player already makes; the
  report copy stays a click by decision 0040.

R4. HOTRELOAD-RETRY: never pin a stale copy on a transient read error.
- Action: in `Watched.get()` record the new signature only after a load
  that succeeded or failed on content (parse or check error); on OSError
  leave `_sig` unchanged so the next poll retries, and add a short bounded
  retry (3 tries, 100 ms) before giving up for this poll.
- Impact: M. A hand edit of zone notes, the zone guide or a rule table
  always lands; the Checks note stops claiming a problem that has gone.
- Effort: S.
- Risk: a file that is unreadable forever retries every poll; the poll is
  one stat plus one open per second at most, well inside the overlay
  budget (0048); keep the note text stable so the Checks card does not
  flicker.
- ToS check: own data files only; nothing game-side.
- Depends on: nothing. Belongs with 0050 (reliability).
- Files likely touched: server/al/hotreload.py, tests/test_hot_reload.py.
- Acceptance test: a test loader raises PermissionError once then
  succeeds with the same mtime and size; the next `get()` returns the new
  value; a JSON syntax error still keeps the last good copy without a
  retry storm.
- ZERO-CLICK: fully automatic.

R5. SNAP-DRIFT-REPORT: add counts and lost fields to the snapshot probe.
- Action: extend 0037 R8 (TC-SNAP-PROBE): at each refresh write, per
  source, the record count and the set of top-level keys used by AshLight
  readers versus the previous file into a Logs file and one Checks line
  ("world_areas: 412 to 431 records, field connections missing"); key the
  cached file by the source's release tag or fetch date and keep only the
  current and one previous copy.
- Impact: M. A shape change after the 1.0 patch shows at refresh time,
  not as a wrong card in play; the cache stops growing per patch.
- Effort: S on top of 0037 R8.
- Risk: noise on harmless growth; report only lost fields and count
  changes over 20 percent.
- ToS check: public repoe-fork files already allowed as build-time
  snapshots (decisions 0009, 0013); nothing new is fetched.
- Depends on: 0037 R8; 0037 R11 (field trim) supplies the allow-list.
- Files likely touched: server/al/theorycraft/snapshot.py, diag or Checks
  note source, tests/test_tc_snap.py.
- Acceptance test: a fixture pair where one record loses a field and the
  count drops 25 percent produces one Checks line naming both; an
  unchanged refresh produces none; old cached copies beyond one are
  pruned.
- ZERO-CLICK: runs inside the opted-in refresh; no player action.

R6. QUIET-OVERLAY: draw nothing when there is nothing, and fix the
hideout test.
- Action: (a) the overlay hides the HUD card entirely when no part has
  content; (b) a setting "hide in town and hideout" (default on for the
  zone line, off for cards the player asked for); (c) once the generation
  line has given an area id, decide `in_hideout` from it with the
  hints.is_town rule (hints.py:86-90) instead of the English scene-name
  substring (parser.py:120-121); keep the substring only as the fallback
  before any area id is known, and drop it from the PoE1-only
  `area_entered` branch (state.py:1491) the same way.
- Impact: M. Fewer overlay pixels in safe areas and empty moments; the
  hideout flag works on any client language.
- Effort: S for (c), M for (a)+(b) with tests.
- Risk: a player who wants the zone line in hideouts; the setting covers
  it. Coordinate wording and budgets with 0043 R2 and 0054 R2 (parts
  chooser) so this is one settings row, not two.
- ToS check: data from the opted-in Client.txt only; the overlay stays a
  separate click-through window (decision 0002).
- Depends on: 0054 R2 and 0043 R2 if they land first (share the setting).
- Files likely touched: server/al/state.py, server/al/parser.py,
  server/al/hints.py (shared helper), app/shared/render_gate.js, overlay
  page, tests/test_bus_state.py, tests/test_parser.py, app tests.
- Acceptance test: a fixture log whose generation line names a hideout
  area id followed by a scene line with a non-English name sets
  in_hideout; a town scene with "hideout" in a translated name but a
  non-hideout id does not; the overlay test shows no card element when
  all parts are empty.
- ZERO-CLICK: automatic on every zone change.

R7. ZONE-RESET: one function clears per-zone state.
- Action: move every per-zone field reset into one `_enter_zone()` called
  from the scene, area-generated and area-entered branches, with a zone
  generation counter that per-zone timers and cards check before they
  publish; add a test that lists zone-scoped fields and asserts each is
  reset.
- Impact: L now, M as per-zone cards grow (0038 R2, 0054 R4).
- Effort: S.
- Risk: changing LIVE-RESUME replay order; keep `_REPLAY_TYPES`
  (state.py:1747) and run the resume tests.
- ToS check: Client.txt lines only.
- Depends on: none; land before 0038 R2.
- Files likely touched: server/al/state.py, tests/test_bus_state.py,
  tests/test_resume.py.
- Acceptance test: a card scheduled in zone 1 never publishes after a
  zone 2 generation line; the field list test fails if a new zone field
  skips the reset.
- ZERO-CLICK: automatic.

R8. PLAYER-NOTES: a player-written note layer per zone.
- Action: a bounded file under ops/runtime (at most 300 zones, 200
  characters each) keyed by area id and the decision 0038 character or
  decision 0045 build; edited on the dashboard zone guide; shown after
  the AshLight note, dim labelled "your note"; never exported unless the
  player picks it in settings export.
- Impact: M for players who level many characters; L for others.
- Effort: M.
- Risk: dashboard edit surface needs the token and size checks
  (0045); keep it plain text, no markup.
- ToS check: player's own text, local file, Client.txt area id as key;
  nothing game-side.
- Depends on: R4 (reload must not pin stale), R7.
- Files likely touched: new server/al/playernotes.py, server/al/
  zonenotes.py consumer, http.py route, zone guide JS, tests.
- Acceptance test: a note saved for an area id shows on the next zone
  entry for that character only; a malformed file keeps the last good copy
  with a Checks note; the file never exceeds its caps.
- ZERO-CLICK: shown automatically on zone entry; writing the note is the
  player's own choice.

R9. PROVENANCE: a source and check date on every authored fact.
- Action: add `src` (research key) and `checked` (date) fields to entries
  in the authored data files (boss elements, waystone rules, zone guide,
  zone notes, R2 level rules); a test fails on an entry missing them; the
  1.0 re-verify list is generated from entries older than the patch.
- Impact: M at the 1.0 patch; L otherwise.
- Effort: S per file.
- Risk: churn in data files; fields are ignored by readers.
- ToS check: own data files; facts stay in own words (decisions 0039,
  0043).
- Depends on: 0058 (watchers) consumes the re-verify list.
- Files likely touched: server/al/data/zone_notes.json and
  zone_guide.json, the boss table in server/al/campaign.py:42, the rule
  table in server/al/theorycraft/waystone.py, R2's new rule file, a data
  test.
- Acceptance test: the data test lists zero entries without `src` and
  `checked`; a script prints entries checked before a given date.
- ZERO-CLICK: the list is produced by the loop or a test, no player act.

R10. LEAGUE-SSF: price lookups follow the trade league for a solo league.
- Action: when the configured league starts with a solo prefix, use the
  matching trade league for poe.ninja and the trade link and say "prices
  from <league>" on the card; first confirm PoE2's solo league naming.
- Impact: L-M (solo players get prices instead of a 404).
- Effort: S once the naming is confirmed.
- Risk: the naming is UNVERIFIED for PoE2 (F10, L3); a wrong guess would
  send a solo player to the wrong book, so the card must name the league.
- ToS check: poe.ninja under decision 0026; the trade link stays a URL
  the player opens (decision 0017).
- Depends on: 0036 R2 / R8 (league picker and follow); fold into them.
- Files likely touched: server/al/ninja.py, server/al/trade.py, tests.
- Acceptance test: configured "SSF X" yields lookups and a link for "X"
  and the card names "X".
- ZERO-CLICK: automatic from the configured or auto league.

R11. PRICE-OVERRIDE: player price overrides over the poe.ninja book.
- Action: a small local table of name to value that wins over the cached
  book on the price card, flagged "your price"; settings export carries it
  only if the player opts in.
- Impact: L (for illiquid items poe.ninja prices badly).
- Effort: S.
- Risk: stale overrides mislead; show the override date.
- ToS check: local only; poe.ninja reads unchanged; no trade call.
- Depends on: none; place near 0036 R10 (variant).
- Files likely touched: server/al/price.py, pricebook.py, settings JS.
- Acceptance test: an override replaces the book value on the card and is
  marked; removing it restores the book value.
- ZERO-CLICK: applies on presses the player already makes.

R12. HOLD-BACK: no verdict while an input is missing.
- Action: on any comparing card (upgrade, waystone, R2) show which input
  is missing ("worn boots unknown") instead of a guessed verdict, and pair
  every green or red mark with a word.
- Impact: L; mostly a wording rule for 0040 and 0044.
- Effort: S.
- Risk: none.
- ToS check: presentation only.
- Depends on: 0040, 0044 token and contrast rules.
- Files likely touched: app/shared card renderers, tests.
- Acceptance test: card tests for missing-input cases assert the missing
  input text and no verdict word; a contrast test covers the colours.
- ZERO-CLICK: automatic.

## Where each idea belongs in the plan

- 0036 poe.ninja: R10, R11; repo D zero-entry warning (already 0036 R4);
  warm start from persisted gate (already true, ninja.py:162-168).
- 0037 data sources: R5; repo A schema gate and declarative allow-list
  (0037 R8, R11).
- 0038 features: R2, R8; repo C pick-one-of-N recommender (Open
  questions).
- 0039 utilities: R1 (with 0039 R11 export), R11.
- 0040 visual design and 0044 accessibility: R12; relative good / bad
  colouring always with a word.
- 0042 usability: R1 reset controls, R8 editor; repo C searchable
  settings list and repo G grouped settings with one help line each.
- 0043 glanceability and 0048 performance: R6; repo E safe-area gate for
  heavy cards (a default-on "run outside town" toggle there).
- 0050 reliability: R4, R7.
- 0051 observability: R3; repo G in-app A/B diagnostics (deferred).
- 0054 competitive PoE tools: R6 shares the parts chooser (0054 R2); the
  tunable model constants of repo D sit with 0054 R5 (tunable waystone
  card).
- 0058 automation and watchers: R9 feeds the re-verify list.

## Cut or merge

- Merged into 0037 R8 / R11: repo A schema-version gate and declarative
  export allow-list. Only the drift counts are new (R5).
- Merged into 0036 R4: repo D "warn on missing or zero entries"; its
  "prefer the direct base-currency rate" only applies if poe.ninja's PoE2
  overview carries both shapes (ninja.py:113 reads `primaryValue` only).
- Merged into 0054 R5: repo D tunable model constants with defaults and
  bounds (waystone thresholds, sidegrade band, price tiers).
- Merged into 0050 R11 / 0051 R1: repo F "pattern not found means layout
  changed, degrade" for Client.txt parsers.
- Not needed: repo D price cache warm start; AshLight already persists
  its gate timestamps (ninja.py:162-168, 264).
- Not needed: repo F single in-flight guard for presses; the bridge lock
  already serialises (bridge.py:125, 267) and dropping a newer press would
  hide the item the player just copied.
- Deferred: repo B two-sided pacing word (also flag "over-levelled, move
  on"). It adds an overlay word most players do not need and risks noise
  against the 2-line HUD rule; revisit only if a player asks.
- Deferred: repo G time-budgeted background search that publishes the
  best result so far; useful only if 0048 shows PoB probes past their
  budget (decision 0024 R7).
- Deferred: repo A worker-thread parsing in the dashboard; no measured
  main-thread stall today (0048).

## Rejected

- Reading game process memory through a HUD host (repos B-G): outside the
  floor (no memory reads). Not detailed.
- Drawing inside the game through a host renderer (repos B, C, D, E, G):
  outside the floor; AshLight's overlay is a separate click-through
  window.
- Synthesized input, including an automated logout (repo F): outside the
  floor (no input of any kind, not even one key).
- Reading installed game archives or the undocumented patch CDN, and
  type inference over undocumented tables (repo A): outside the floor
  (game files not permitted; GGG endpoints only if documented).
- World-anchored markers and minimap routes (repos D, G): need entity
  positions from memory; the floor-safe remainder is an ordered text list
  in the zone guide, which ZONE-GUIDE already provides.
- Hovered-tooltip dimming (repo E): needs the tooltip position from
  memory; the safe remainder is a player-chosen card anchor away from the
  screen centre (0054 R2).
- A donation request on the README (repo G): bars nothing by itself, but
  a donation gate on GGG-derived features is outside the floor; AshLight
  adds none.
- Any code copy: 5 repos state no licence, so all rights are reserved
  (L1); the 2 MIT repos would need the notice kept (L2) and a licence
  check recorded in docs/decisions plus a THIRD-PARTY entry, and nothing
  in them fits a stdlib Python core. Ideas only.

## Licence classes and the check a decision would record

- Repo A: MIT in its two sub-packages; the root has no licence file and
  the notice names the original upstream author. Class: permissive.
- Repo E: MIT. Class: permissive.
- Repos B, C, D, F, G: no licence stated. Class: none (all rights
  reserved, L1). Ideas only; no data tables either (repo B zone rewards
  and notes, repo C modifier catalog stay uncopied).
- Check a decision would have to record before any reuse from an MIT
  repo: the exact file and commit, the licence text found at that commit
  (root and sub-package), the copyright holder, that the notice is kept
  in the copied file and in THIRD-PARTY, and that the copied code calls
  nothing outside the floor. GPL, AGPL, NC or no licence: ideas only, no
  decision can permit a copy.

## Cautions

- Every live data path in the set is outside the floor; adapt results,
  never techniques (F1, F2).
- Do not copy authored tables from the set: zone rewards, personal
  levelling notes and modifier weights are someone else's work and go
  stale per league (repos B, C).
- Key data by Client.txt area id, never the English display name (repo B
  does; AshLight does too at zonenotes.py:59-60 and parser.py:120-121).
- Repo B swallows JSON and write errors silently; AshLight shows a Checks
  note instead (decision 0042), and R4 keeps that note truthful.
- Repo D's price fetch sends no truthful User-Agent and no contact;
  AshLight keeps both (decisions 0015, 0026).
- Repo D's memo key is a 32-bit hash string; collisions give wrong
  answers. If AshLight memoises PoB deltas, key by the full input or a
  SHA-256.
- Repo E's rule files are executable expressions; AshLight's rule files
  (R2) are declarative JSON, never evaluated as code.
- Release automation in the set (caret ranges, unpinned toolchain) is the
  opposite of AshLight's exact pins.

## Open questions

- Q1. PoE2 solo league naming (prefix form) for R10: UNVERIFIED here (a
  search summary suggests "SSF <league>", L3); settle by the 0036 league
  picker work, which reads the leagues list.
- Q2. A pick-one-of-N choice recommender (repo C idea: rank the options
  of an in-game choose-one screen from an own table). The options are not
  items, so the clipboard may not carry them; it would need the per-press
  screen read that 0043 R7 is spiking. Decide after that spike; no
  adjudicator needed now.
- Q3. Whether R2's thresholds should be a pure AshLight table or derived
  from the base_items snapshot plus level; recommend the own table first
  (simpler, hot-reloaded), revisit after one live levelling run.

## Verification

Independent verifier, 2026-11-18, at HEAD 5ec96b8.

- Code claims: 34 path:line citations re-read in this tree. 27 held as
  written. Corrected: weights first-write range (197-200); campaign hints
  also cover the flask base and need a build (campaign.py:11-20); the
  item side already lists zero-weight mods per press (evaluate.py:318,
  web/tc.js:188-216), so F5 and R3 were narrowed and R3 dropped from M to
  L-M and out of the Summary's best three (R4 took its place); the PoE2
  hideout flag comes from the parser's scene-name substring
  (parser.py:120-121), while state.py:1491 sits on a PoE1-only line PoE2
  never writes (langguard.py:5), so F8, R6 (c) and its acceptance test
  were rewritten; F6 narrowed to locks taken after the last write; seven
  "Files likely touched" paths fixed to real test files and data
  locations (waystone.py, campaign.py:42, server/al/data/).
- Third-party claims: 21 claims re-checked read-only against the local
  clones (licence files and fields, override-only weights with per-row
  and all reset and a changed count, unknown-option log, 10 x 100 ms
  retry, count-of-N levelling rules with a boots band, town and hideout
  hide defaults, separators, swallowed JSON errors, notes keyed by
  display name, prefix strip, rate preference, missing-data warning, no
  User-Agent header, 32-bit memo hash, synthesized input with a per-area
  cancellation token, a donation line, price overrides, zero tests, one
  repo with CI on caret ranges). 19 held; 2 corrected: repo C logs once
  per area visit, not per session; repo E's outside-town toggle defaults
  on (opt-out), not opt-in. Nothing from the clones was run.
- Web claims: L1 and L2 re-fetched 2026-11-18 and hold. PoE2 solo league
  naming searched
  again (L3): still UNVERIFIED; F10, R10 and Q1 say so.
- ToS floor: all 12 recommendations re-tested against every floor rule;
  all stay inside (local files, Client.txt, the per-press clipboard read,
  poe.ninja under decision 0026, a trade URL the player opens). Q2 would
  need the per-press screen read, which decision 0003 permits. Nothing
  moved to Rejected; the Rejected list already holds every outside path.
- Settled decisions: none contradicted (0003, 0009, 0013, 0017, 0026,
  0036, 0039, 0040, 0042, 0045 checked against R1-R12).
- Brief: every point covered (set, techniques with floor status, ranked
  ideas with adaptations, licence classes and the decision check, cautions,
  plan placement, standard recommendation fields). Hygiene: identity of
  the set withheld; one Q2 phrase made generic.
- Still UNVERIFIED: the set size (39) and idea count (58), from the review
  data only; PoE2 solo league naming.
