# 0038 - Features review: player value, gaps, cut or merge

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B2
features. Scope: every player-facing feature except the utilities (filter
tools, build file, settings export / import, run history, diagnostics,
multi-character, hot reload: note 0039, cross-referenced only). PoE2 1.0
launches 2026-12-11, 24 days after this note.
Status: verified

## Sources (accessed 2026-11-17; re-fetched 2026-11-18 where marked V)

Web (facts restated in own words; nothing copied):
- GGG (V): https://www.pathofexile.com/developer/docs (policy; OAuth
  registration still closed on 2026-11-18).
- DBT (V): https://poe2db.tw/Tools (community tool list, 26 entries on
  2026-11-18).
- BM (2026-05-19): https://boostmatch.gg/blog/poe-2/articles/poe2-third-party-tools-guide
- EUI: https://github.com/Lailloken/Exile-UI (module list, 1.4k stars).
- EE2: https://github.com/Kvan7/Exiled-Exchange-2 (1.2k stars); EE2X:
  https://kvan7.github.io/Exiled-Exchange-2/xp-tracker.html
- SK: https://github.com/Sidekick-Poe/Sidekick ; EC: https://exilecompass.com/
- POV: https://www.poeoverlay.com/ ; POVC (entries to 1.69.0, 2026-10-23):
  https://www.poeoverlay.com/changelog/poe-overlay-ii ; POVW:
  https://www.overwolf.com/app/kyusung4698-poe_overlay_ii
- EXP: https://github.com/andreins/ExileXP ; QUTM: https://github.com/Vyary/qutm
- POL2: https://kami-guru.github.io/path-of-levelling-2
- DILLA: https://doofdilla.github.io/dillapoe2stat ; EXB: https://exiles.build/
- NT (2026-06-07, updated 2026-07-20): https://nexttier.pro/guide/poe2-trade-guide
- PV: https://www.poe-vault.com/poe2/news/path-of-exile-2-gets-full-in-game-trading-with-merchant-tabs
- FRVR (2026-05-12): https://frvr.com/blog/news/path-of-exile-2-build-planner-will-never-include-official-ggg-builds/
- PCGN (2026-08-31): https://www.pcgamesn.com/path-of-exile-2/campaign-final-acts-interview-gamescom
- RPGS (2026-08-25): https://www.rpgsite.net/news/21188-path-exile-2-reaches-its-10-full-release-on-december-11
- EE (2026-11-08, one outlet): https://everythingedinburgh.com/?p=31851
- GOL (V, 2026-11-09): https://www.gamingonlinux.com/2026/11/path-of-exile-2-releases-december-11-with-a-huge-update-it-goes-free-to-play/
  (1.0 contents: Acts 5-6 with 24 areas and 18 bosses, Shadow with
  Assassin and Infiltrator, Duelist with Knight and Master-at-Arms, a
  passive tree rework).
- V also: BM, POVC, PV, NT, FRVR, PCGN, RPGS, EE, EUI, EE2X, DILLA, EXB
  re-fetched 2026-11-18 and the claims below checked against them.
- PH (user comments, about 4 months old): https://www.producthunt.com/products/poe2builds
- SNIP: search-result summaries only (pages not opened or fetch refused):
  a 2025 r/PathOfExile2 levelling overlay thread; GGG forum threads
  3843068 and 3897182 (seeing what sold, sale notices); a Mobalytics "0.5
  campaign checklist" guide title. UNVERIFIED hints only.

Repository: ROADMAP.md, AL-NEXT-SESSION.txt, CLAUDE.md, research 0001,
0003, 0006, 0018-0021, 0023, 0028, 0031-0034, the decisions named below,
design 0001, and the code (path:line). Short names: index.html is
web/index.html; .py files are under server/al or server/al/theorycraft;
render_gate.js and format.js are under app/shared.

## Summary

AshLight has 35 player-facing features outside the utilities. The
zero-press half (zone, timers, level, deaths, act and map times, zone
guide) is sound. The press and build halves hang on a pasted Path of
Building build: with none the item check answers "No build loaded"
(evaluate.py:327-329), and with a guide build it compares drops against
endgame gear. Build first: R1 a worn-gear baseline by a second AshLight
hotkey; R2 zone and act cards in the overlay's one card slot; R3 a contact
field at the web-data opt-in (every price feature waits on it); R4 one
live capture session (15 of 35 features lean on shapes never recorded
live); R5 one guide file ready for 1.0 (the interludes go, 24 areas come).
Freeze trade cards, graphics advisor, tips and price watch; merge zone
notes, the boss table and the level-gap rule into the guide; cut the dead
bits. Do not chase one-press price overlays or stash trackers: they sit
outside the floor or behind closed OAuth registration [GGG].

## Current state

### Surfaces

- Overlay: 2 HUD lines plus one 3-line card (app/overlay/index.html:13-27;
  design 0001 lines 598-603). Row 1 zone and timer; row 2 level, deaths
  and one status word, picked in the order connection, log state, trade
  count, under-level, AFK / DND, campaign hint (render_gate.js:170-173).
  The card is a trade request, or for 20 s the item / price / waystone
  check (state.py:35, 750-798).
- Play tab: zone tile with zone tip, campaign hints and zone guide; level,
  deaths, session tiles; last session; trades; build alert and upgrades;
  tip; item check with upgrade link and price (web/index.html:67-228). A
  new item card, trade or build alert shows Play by itself
  (web/tabs.js:8-11).
- Other tabs: Run and history (index.html:230-319), Build (321-434),
  Items and prices (436-507), Settings (509-599).

### Inventory

Per feature: what the player learns (Glance), where it shows, how often
it helps (Use: estimated times per hour of play; C campaign, M mapping, T
trading) and whether a recorded live sample backs its input (Live;
ROADMAP.md:9-31). Interaction cost and upkeep are given per group.

A. Live HUD from Client.txt. Cost: none after the one opt-in. Upkeep:
the log line shapes (English text; 1.0 may add lines).

- A1 Zone and zone timer. Glance: where I am, for how long. Overlay row
  1; Play zone tile. Use: C 6-20, M 8-15, T 2-4 (zone changes). Live:
  yes. (parser.py:26-28; index.html:93-98)
- A2 Level, character, class. Overlay row 2; Play level tile. Use: C
  4-10 (level-ups), M under 1. Live: yes. (parser.py:36)
- A3 Deaths this session. Overlay row 2; Play tile. Use: per death.
  Live: no; the death wording is unverified for PoE2 (parser.py:37-38).
- A4 Session time, AFK / DND. Play session tile; overlay word. Use: an
  occasional glance. Live: AFK ON was seen in a PoE2 sample, AFK OFF is
  inferred and DND is unverified (parser.py:39-42); LIVE-1 still lists
  both as not recorded live (ROADMAP.md:9-31).
- A5 Level pace: time per level, levels per hour. Play level tile. Use:
  C 4-10, M under 1. Live: yes. (pace.py:12-13)
- A6 Under-level warning. Play level tile; overlay word. Use: C when a
  zone is 3 or more levels above me; M 0. Live: yes. (underlevel.py:16)
- A7 Act times and the act's zone levels. Run tab. Use: C 1 split per
  act; M 0. Needs the area snapshot. Live: Act 1 ids only. (acts.py:53-58)
- A8 Recent events, 30 rows. Run tab. Use: after the fact. (state.py:26)
- A9 Death list ("Death recap"): zone, levels and time before each
  death. Run tab. Use: after deaths. Live: no. (runs.py:242)
- A10 Map runs: maps run, time per map, maps per hour, deaths per map;
  the overlay timer becomes time in this map. Run tab; overlay row 1.
  Use: M 8-15; C 0. Live: no; the `Map` id prefix is unverified
  (acts.py:58; runs.py:191-226; render_gate.js:93-110).
- A11 Map ladder: maps, deaths, median time per map level. Run tab. Use:
  M between sessions. Live: no (as A10). (mapladder.py:27-32)
- A12 Last session card: time, levels, maps, deaths. Play, under the
  tiles, until the next card. Use: once per session start.
  (summary.py:70-102; state.py:1686-1693)
- A13 New-character tips: 4, 10 min each, to level 30. Play tip card;
  Recent. Use: C 4 per new character. Live: 2 of 4 triggers unverified.
  (hints.py:36-56)

B. Campaign guide. Cost: none. Upkeep: high; hand-written per zone and
"not checked every patch" by its own label (zoneguide.py:60-61).

- B1 Zone tip: one line on what to do here. Play zone tile. Use: C 6-20;
  M 0. Data: 65 zone notes plus act defaults. Live: zone names unchecked
  in play past Act 1. (zonenotes.py:52-63)
- B2 Zone guide and quest tracker: goal, bonus reward, level lean, next
  zone; folded: waypoint, layout, main-path steps, skipped bonus zones.
  Play zone tile. Use: C 6-20; M one fixed line. Data: 93 zones, 88
  goals, 38 bonus rewards in 36 zones, 8 layout notes. Live: as B1.
  (zoneguide.py:437-481; web/zoneguide.js:30-69)
- B3 Campaign hints: boss element against my resist (2 zones), a better
  flask base, boots without speed. Play zone tile; overlay word, last in
  priority. Use: a few per run. Needs a build. (campaign.py:42, 135-181)

C. Trade. Cost: none (Dismiss is optional). Upkeep: whisper wording.

- C1 Trade whisper cards: who wants what, price, stash tab and position.
  Overlay card; Play. Up to 5 cards, 10 min each. Use: T per direct-trade
  whisper; C, M rare. Live: no; the templates are unverified for PoE2
  (parser.py:58-66; state.py:28-31).

D. The item hotkey. Cost: 2 key presses per item (copy in game, then the
AshLight key; app/eval_hotkey.js:23-48, app/main.js:33-34). Upkeep: item
text format, poe.ninja shapes, the PoB pin, 11 waystone rules.

- D1 Item check: upgrade / sidegrade / downgrade against a slot, top
  stat, roll potential; PoB DPS / EHP change with the optional calc.
  Overlay card 20 s; Play right column. Use: C, M 5-30 presses, the
  player's choice. Needs a build. Live: PoB path proven on a real build
  with hand-written item text (decision 0028;
  tests/math_live_items.py:1-10); no real clipboard sample (research 0003
  line 116). (evaluate.py:274-349)
- D2 Price on the same press: poe.ninja value for uniques (9 types),
  stackables (13 types), currency; a trade search link for any item.
  Overlay price line; Play price box. Values need web data and a
  contact; the link needs neither. Live: no. (price.py:1-28;
  pricebook.py:38-45)
- D3 Price and points: the item's own note price per score point. Play,
  hidden when absent. Its trigger was never seen. (index.html:218-224)
- D4 Upgrade search link for the checked slot. Play item card. Cost: 1
  more click. Use: T a few. (upgrade.py:96)
- D5 Waystone risk (11 rules against my build) and rewards (6 kinds).
  Overlay card; Play. Use: M 8-15 if every waystone is checked. Live: no
  real waystone text. (waystone.py:44-85, 187-205)
- D6 Upgrade notices: items checked earlier that beat my gear now. Play
  notice slot. 10 per character, memory only. Use: after a build or
  weight change. (buildlive.py:23, 141-160; live.py:148-180)
- D7 Stale-build alert, per-character build swap: build missing, wrong
  class, or 5 levels behind. Play notice slot. Use: on a character
  switch; every 5 levels until re-pasted. (buildlive.py:22, 46-71)

E. Build. Cost: one paste per character, repeated to stay current, plus
Copy clicks. Upkeep: PoB export format and pin, tree export. Use: between
sessions and in town; none in a fight. Live: real PoB exports decode
(decision 0021); in-game use of the strings is unchecked.

- On the Build tab: E1 Build view (stats, gear, skills, tree link, notes;
  index.html:323-373); E2 Damage by skill (skillsplit.py:79); E3 Build
  health, defence and sustain (health.py:221); E4 Look for next, the
  stat to shop for per slot, with Copy (health.py:330); E5 Search
  strings for the stash and vendor search, with Copy (searchstr.py:26,
  109).
- E6 Stat weights editor. Items and prices tab. Use: set once, if at
  all. (index.html:481-505)
- E7 Optional PoB calc. Cost: one setup switch. (decisions 0018, 0024)

P. Prices. Cost: the web-data switch plus a contact typed into a file
(finding F4). Upkeep: poe.ninja type names per league. Items and prices
tab. Use: T a few looks per session. Live: no; never fetched on the live
install.

- P1 Currency values (index.html:450-454); P2 Price movers, 5 up and 5
  down (pricebook.py:49-51); P3 Price watch, 20 priced presses, flags 25
  percent moves (pricewatch.py:26-29).

G. Other.
- G1 Graphics advisor: suggested settings for this computer. Settings
  tab, two folds deep. Cost: 3 clicks. Use: once per install. Upkeep:
  option labels per patch. Live: advice unchecked in game. (gfx.py:1-17;
  index.html:543-596)

### Live proof

- Recorded live: line prefix, scene, area generation, instance connect,
  level-up, chat, the log-opening marker, consent and tailing
  (ROADMAP.md:9-31). That backs A1, A2, A5, A6, A7 (Act 1), B2's trigger.
- No recorded sample: the death line, whisper and trade templates, AFK /
  DND, joined / left, hideout names, interlude ids, the `Map` prefix, any
  real copied item or waystone text, the in-game search syntax, a fresh
  run read back from the API (TEST-LIVE-CLICKS). 15 of 35 features lean
  on at least one: A3, A4, A9-A13, B1, B2, C1, D1, D2, D3, D5, E5.
- Overlay: real-desktop checks done; in-map RAM and FPS unmeasured
  (OVL-BUDGET, OVL-FPS).
- The one install in live use (flags read today from the local config
  and the runtime folder): web data on, no contact, calc off, one build
  saved, no price cache file. No price was ever fetched there: the value
  half of D2 and all of group P have never run for the one real user.

## Findings

F1. The item check is dead without a PoB build and misleading with a
guide build. With no build, gear returns the error "no build loaded"
(evaluate.py:327-329). With a build, the baseline is the build's own item
in that slot (evaluate.py:330), and decision 0045 (lines 75-76) treats a
build planned for a higher level as the normal levelling case, so a level
12 drop is scored against level 90 gear. PoB is rated recommended, not
critical [BM], and 1.0 is free-to-play [RPGS]: most new players will
likely have no build (an estimate; no source counts PoB use), and guide
followers get false downgrades. A key-press item overlay is rated
critical [BM] and 4 price checkers are on the community list [DBT];
AshLight's version gives these players nothing today.

F2. The overlay carries no guide and no map facts. The zone guide already
builds a one-line form of at most 120 characters (zoneguide.py:46,
423-434) but the overlay has no slot for it yet (ROADMAP.md:2048-2050,
S5-FOLLOWUP item a). The campaign overlays surveyed draw
their guide over the game [EUI, POVC, EC, EXP, POL2, QUTM]. AshLight's
two HUD lines mostly repeat what the game shows (zone name, level); its
own value is the timer, the death count, the status word and the card. A
single-screen player gets none of the guide.

F3. Play is campaign-shaped and carries a stale card. In a map the zone
tile shows one fixed sentence (the `endgame` entry of zone_guide.json;
zoneguide.py:447-457) while map count, time, rate and deaths sit on the
Run tab (index.html:272-302). The Last session card stays on Play, above
trades and the build alert, until the next session ends
(state.py:1686-1693), and Play's fit with both slots full is still
unmeasured (ROADMAP.md:2037-2041).

F4. All price features wait on a hand-edited file. poe.ninja requests are
refused without a contact (ninja.py:227-229) and the only fix offered is
to add a key to config/local.json (diag.py:40; state.py:559-561). No
dashboard field exists. The Play copy is also stale: it says price
checks need a contact "for the trade site" and suggests an email
(state.py:560-561), but the contact goes to poe.ninja and the app calls
no trade endpoint (decision 0017). That blocks D2 values, D3, P1, P2, P3 and the
filter price tiers. On the live install the contact is unset.

F5. Live proof is thin where it matters most. The press path (D1, D2,
D5) has never been fed a real copied item; deaths, trades and maps rest
on unverified wording or ids (parser.py:37-66; acts.py:58). One wrong
regex silently zeroes a headline number (deaths) for every user.

F6. Trade whisper cards lost weight. Since 0.3.0 (2025-08-29; PV gives
the day without the year, NT names the patch) buyers take merchant-tab
items through the market panel with the seller offline; only direct
player trade still starts with a whisper [NT, PV]. AshLight may never
answer for the player (no input, floor), while a rival panel handles
invites and messages [POVW]. The card is a read-only notice whose
templates are unverified.

F7. Campaign data is duplicated, thin on bosses and about to shift. Zone
tip (65 notes) and zone guide (88 goals) describe the same zones in two
files and both print in the zone tile (index.html:102-108). Boss hints
cover 2 zones (campaign.py:42). At 1.0 the three interludes are removed
[PCGN], which strands 22 guide entries (all 22 interlude zones in
zone_guide.json, recounted), and Acts 5-6 add 24 areas and 18 bosses
(research 0021; GOL).

F8. The level-gap advice exists twice and states an XP fact it cannot
back. underlevel.py warns at a configurable gap (default 3,
underlevel.py:16); zoneguide.advice hard-codes that gap and adds a "push
on" rule of 3 + level // 16 with the words "it gives less experience"
(zoneguide.py:64-65, 373-378). A changed setting makes the two disagree.
The rule has the shape of the PoE1 experience safe zone (UNVERIFIED for
PoE2); a rival tool that models the penalty describes its formula as
PoE1-like, fitted to speedrunner data, and warns that it may be off
above level 70 [EE2X]. Research 0028 ruling B kept XP formulas out.

F9. What players use and ask for (dated sources):
- Rated critical: a loot filter, a price-check overlay, the trade site,
  poe.ninja, a mod database; PoB is recommended [BM, 2026-05-19]. The
  community list holds 4 price-check overlays, 4 filter tools, 6 build
  sites and 1 campaign overlay [DBT].
- Campaign overlays are a crowded, active field: guide steps that
  advance from the log, quest and reward tracking, layout notes, act
  split timers, PoB import [EUI, EC, EXP, POL2, QUTM]; the leading
  overlay added a campaign guide on 2026-05-24 [POVC]; a campaign
  rewards checklist is a published guide topic [SNIP]. B2 matches this
  on the dashboard only (F2).
- A home view of session activity, recent maps and market moves shipped
  in the leading overlay on 2026-09-01 [POVC]: the Play tab idea is
  validated; its map half is missing (F3).
- Map checks: dangerous map mods [SK], waystone filters [POVC], a map
  tracker [EUI, DILLA]. None of these sources describes a check against
  the player's own build numbers; D5 does that.
- A planned-passives overlay is asked for [PH]; the game's Build Planner
  (0.5.0, 2026-05-29) highlights a guide's picks from a build file
  [FRVR]. AshLight's `.build` export feeds exactly that (note 0039).
- Stash value and loot per map need OAuth or the inventory API; one tool
  says the API is disabled, one has paused until registration reopens
  [DILLA, EXB]. Registration is still closed [GGG].
- A log of currency-exchange and merchant-tab trades is a module in the
  largest overlay suite [EUI, "Vaal Street"]; how it reads its data was
  not checked, so it is no evidence of a permitted source (see the
  rejected "sold" feed).
- An in-game death recap (damage by type, attackers, mitigation) is
  reported for 1.0 [EE; one outlet, UNVERIFIED]. A9 carries the same
  name but only lists where and when.
- The game director names new-player understanding as the weakest area
  [PCGN, 2026-08-31]: first-hours help has an audience at launch.

F10. Build-derived helpers describe the paste, not the character. E3,
E4, E5 and the flask and boots hints of B3 read the PoB build's stats and
gear (health.py:221, 330; campaign.py:99-125): true for a player who
exports their own character from PoB, a description of the guide for
everyone else.

F11. Dead or unused parts: `recent_whispers` is sent in every snapshot
(state.py:1832) and read by no file in web/ or app/; POST
/api/clipboard-read is a 501 stub (http.py:311-317); the session card
appends market movers to a play summary (summary.py:96-98).

F12. The calc half will sag in launch week. The PoB pin is v0.23.1
(2026-07-28) and 1.0 overhauls the passive tree (research 0021 lines
63-76). Until a PoB 1.0 release is pinned, PoB deltas are unavailable;
anything that works on stat weights alone (R1) keeps working.

F13. 1.0 names are now public but not in the class map. Launch press
names Shadow (Assassin, Infiltrator) and Duelist (Knight,
Master-at-Arms) [GOL]; charjson.py:30-35 still says the ascendancy names
are unpublished and has no entry for them, so a build of those classes
shows the ascendancy as the class name (the pass-through is safe, not a
crash). A four-line data change at launch, re-checked against the GGG
patch notes; it belongs to the 1.0 runbook (UTIL-1.0-READY), not to a
new feature.

## Recommendations

R1. Worn-gear baseline by a second hotkey.
- Action: add an AshLight "I wear this" hotkey (default Alt+Shift+W)
  whose press reads the clipboard once and files that item as the worn
  item of its slot for the current character; the item check compares
  against the worn item first and the PoB plan second, and works with no
  build on the default stat weights.
- Impact: H. D1, D4 and D6 work with no PoB build and turn truthful for
  guide followers (F1, F10); independent of the PoB pin (F12).
- Effort: M. Risk: slot choice for rings and one-hand weapons (reuse the
  slot the last check compared against when the texts match, else the
  empty or older slot); a third global hotkey; one press per equip to
  learn. Store parsed stats, name and base only, bounded (16 slots x 12
  characters), with a switch and a clear button.
- ToS check: data = the clipboard text of one manual press. Floor rule
  "clipboard ... once per manual press of an AshLight hotkey": one read
  per press, the player copies in game, no input is sent, nothing leaves
  the computer. Decision 0004 holds: existing weight scoring, no formula.
- Depends on: a new decision for the worn-gear file, ruled by an
  adjudicator. It does not reverse decision 0045 (checked items stay in
  memory only; none of 0045's "Reverses if" conditions is claimed): worn
  items are a separate, player-filed set, bounded like the 0036 files and
  kept out of the settings export. ROADMAP S5-FOLLOWUP (b) already asks
  the same file question for the upgrade list (ROADMAP.md:2050-2051).
  R4 for real item samples. The default key must pass the game-key
  refusal list (app/hotkey.js:21-24; server/al/hotkeys.py:25-26).
- Files likely touched: app/main.js, app/eval_hotkey.js, app/hotkey.js,
  server/al/hotkeys.py, http.py, core.py, state.py,
  server/al/theorycraft/evaluate.py, live.py, a new worn-gear module,
  web/app.js, web/index.html, tests.
- Acceptance test: with no build, a wear press on ring A then a check
  press on ring B gives an `ok` card naming ring A (today: the error);
  with a build the card carries both lines; a restart keeps the worn set
  and Clear empties it; one clipboard read per wear press, none on key
  repeat inside 1200 ms; test_floor_static and test_sidecar_paths green.
- ZERO-CLICK: one manual press per equipped item (the floor requires a
  press for any clipboard read); verdicts then follow by themselves.

R2. Overlay moment cards: zone card and act card.
- Action: let the one card slot also show a zone card for 12 s on the
  first entry of a campaign zone with a goal (goal on two lines, then a
  bonus or level-lean line), and an act card for 12 s when an act split
  closes (act time, gap to the saved best); both yield to the item card
  and to an open trade card.
- Impact: H. Puts the guide in front of single-screen players in the
  campaign, where every 1.0 newcomer starts (F2, F9).
- Effort: S to M. No new authoring: 84 of 88 goals wrap into two 34
  character lines (measured today), the rest clip; the bonus line comes
  from the reward kind (zoneguide.py:55-57).
- Risk: the card covers the corner map for 12 s per new zone (design
  0001 section 10 placement). Limit to the first visit per game run,
  never over another card, with an on / off setting.
- ToS check: data = the opted-in Client.txt tail and AshLight's own
  guide file, drawn in the separate click-through window; no screen
  read, no input; overlay budgets (decision 0002) re-run.
- Depends on: a design 0001 section 10 amendment (card kinds) through
  the design reviewer; plan section 03.
- Files likely touched: server/al/state.py (overlay_card),
  server/al/zoneguide.py, app/shared/render_gate.js and format.js, app
  tests, docs/design/0001, tests/test_budgets.py, test_overlay_smoke.py.
- Acceptance test: a replayed log entering a guided zone publishes a
  card of kind `zone` with 3 lines of at most 34 characters for 12 s; a
  trade request or item press takes the slot; a re-entry shows nothing;
  a data test proves every goal fits or clips; a closed act with a saved
  best shows the gap; static budget tests green.
- ZERO-CLICK: shows and leaves by itself.

R3. A contact field at the web-data opt-in.
- Action: when the player ticks "Use web data", ask for the contact in
  the same card and save it to the gitignored local config; the Play
  price box names this one step while prices are blocked, and its copy
  says poe.ninja, not "the trade site" (state.py:559-561).
- Impact: H for the price group (F4): unblocks D2 values, D3, P1, P2, P3
  and the filter tiers with one field instead of a file edit.
- Effort: S. Risk: the contact is personal; keep it out of the state,
  the report and the settings export, as today.
- ToS check: data = a contact the player types, which lets poe.ninja
  (public web data) be asked. Floor rule "truthful User-Agent"; decision
  0015 holds (read only from config/local.json; only the entry is new).
- Depends on: notes 0039 and 0043 (the same gap from their side).
- Files likely touched: server/al/http.py, core.py, state.py, diag.py,
  web/index.html, web/prices.js, web/app.js, tests.
- Acceptance test: a POST with a valid contact writes the key and the
  web-data GET says `contact_set` true without the value; a value with
  parentheses or over 120 characters is refused with a sentence; with a
  mock transport the next refresh fetches; the value appears in no
  snapshot, report or export.
- ZERO-CLICK: one field, once, at an opt-in the player makes anyway.

R4. One live capture session before 1.0.
- Action: add an off-by-default "keep this as a test sample" switch and
  a sanitizer, then have the operator play about 30 minutes: one press
  each on rare gear, a unique, a currency stack, a waystone, a tablet
  and a gem (plain and advanced copy), plus a death, a whisper, a direct
  trade, AFK, a party join, a map and the hideout.
- Impact: H. Turns 15 features from assumed to proven and fixes wrong
  patterns before free-to-play players arrive (F5).
- Effort: S for the agent, plus one operator act. Risk: samples hold
  names and chat; sanitize and review before commit.
- ToS check: data = the same reads as normal use (opted-in tail; one
  clipboard read per press); samples stay local until sanitized.
- Depends on: the batched operator ask (plan section 09); rows LIVE-1
  and TEST-LIVE-CLICKS.
- Files likely touched: tools/ (capture helper), tests/fixtures/, parser
  and item tests, ROADMAP.md LIVE-1.
- Acceptance test: a fixture and a passing test per shape; the LIVE-1
  "remains" list is empty or each item says why it was not reachable;
  the UNVERIFIED comments in parser.py:33-66 are updated.
- ZERO-CLICK: a one-time check.

R5. One guide file, ready for 1.0.
- Action: now, fold zone_notes.json and the boss table into
  zone_guide.json (goal, bonus, layout, next, boss element) and print
  one guide block; at launch, drop the interlude acts once the live ids
  confirm it and write Acts 5-6 entries within 48 hours.
- Impact: H in launch week, M after (F7).
- Effort: M (the merge is S; 24 zones of own-word notes is the rest).
  Risk: thin sources in the first two days; ship goals first, leave
  unsure facts out (decision 0043 rule).
- ToS check: data = public pages read as facts and restated in own
  words (decisions 0009, 0043), plus the build-time area snapshot under
  the web-data opt-in.
- Depends on: UTIL-1.0-POST steps 3 and 4; BLOCKED for the Acts 5-6
  part until 2026-12-11.
- Files likely touched: server/al/data/zone_guide.json, zone_notes.json
  and zonenotes.py (removed), server/al/zoneguide.py, campaign.py,
  state.py, web/app.js, web/index.html, tests, the 1.0 launch runbook.
- Acceptance test: one data file; every campaign area id in the cached
  snapshot has a goal or an explicit skip; the zone tile shows no
  separate "Zone tip"; a boss hint fires for every zone with a boss
  element; after launch the G5 and G6 ids are covered.
- ZERO-CLICK: data only; the file hot-reloads (decision 0042).

R6. Play follows the context.
- Action: in a map (and in the hideout between maps) the zone tile shows
  this map's time and deaths, maps this session, maps per hour and the
  average, in place of the campaign block; Last session moves to the Run
  tab and shows on Play only while the game is idle; build alert,
  upgrades and the tip share one notice slot.
- Impact: M to H. Mapping is where a kept player spends most hours (F3).
- Effort: M. Risk: needs the `Map` prefix proven (R4); Play height must
  be re-measured.
- ToS check: data = Client.txt-derived state already in the snapshot;
  dashboard only; no new read.
- Depends on: R4; plan section 03; the design reviewer.
- Files likely touched: web/index.html, web/app.js, web/runs.js,
  web/zoneguide.js, web/summary.js, web/tabs.js, web/app.css, app tests.
- Acceptance test: a replayed session shows the map block in a map, the
  guide in a campaign zone, Last session on Play only while idle; Play
  fits the viewport at 1280x760 and 1920x950 with a trade and a notice.
- ZERO-CLICK: follows the log.

R7. Upgrade search per slot from the build.
- Action: put the trade-search link (same builder) on every "Look for
  next" row, so a search for any slot needs no item press first.
- Impact: M. Today the link exists only after a press on an item of
  that slot (upgrade.py:96).
- Effort: S. Depends on: none. Risk: the `?q=` link form is
  undocumented (decision 0017 clause).
- ToS check: data = the pasted build and the cached stat-id snapshot.
  Decision 0017: a URL the player opens in their own browser; the app
  calls no trade endpoint; ids per decision 0037.
- Files likely touched: server/al/upgrade.py,
  server/al/theorycraft/health.py, web/health.js, tests.
- Acceptance test: each next-look row with terms carries a valid search
  URL (trade.is_search_link); no trade host in the fetch allow-list.
- ZERO-CLICK: links rebuild with the build; opening one is the click.

R8. Loot tally from presses.
- Action: add up the cached value times stack size of every priced press
  per map and per session, shown in the R6 map block and the session
  card, labelled "from the items you checked".
- Impact: M for farmers; the stash route is closed to every tool (F9).
- Effort: M. Depends on: R3, R4, R6. Risk: partial by nature; the
  stack-size text is unverified (research 0003 line 51); repeat presses
  must not count twice.
- ToS check: data = per-press item text and cached poe.ninja prices
  (web data on); no new read. Decision 0036 holds: the tally re-reads
  only the cached book, only while web_data is on, and any stored tally
  is a bounded file under ops/runtime like price watch.
- Files likely touched: server/al/pricewatch.py or server/al/runs.py,
  server/al/theorycraft/live.py, server/al/state.py, web/runs.js.
- Acceptance test: 3 presses in one map, one repeated, count 2 items and
  their sum; web data off shows no tally.
- ZERO-CLICK: counted on presses the player already makes.

R9. Affix line on the item card.
- Action: when the pressed text is the advanced copy, add one line with
  the prefix and suffix counts and the best tier found.
- Impact: L to M (crafting and selling).
- Effort: S; the parser already keeps kind, name and tier
  (item.py:125-127, 237-252). Depends on: R4.
- Risk: "open slots" needs per-rarity limits, a small own table; print
  counts only until 1.0 confirms the limits.
- ToS check: data = the text of the same press; nothing new is read.
- Files likely touched: theorycraft/live.py, state.py, web/tc.js, tests.
- Acceptance test: an advanced fixture gives the line; a plain copy
  gives none.
- ZERO-CLICK: same press.

## Cut or merge

Merge:
- M1 Zone tip into the zone guide (part of R5). One file, one block.
- M2 Boss table into the guide file (part of R5); grow it from 2 zones
  to every act boss AshLight can state in its own words.
- M3 One level-gap rule: zoneguide.advice reads the `underlevel_gap`
  setting; the Level tile line goes, the guide line and the overlay word
  stay; RUSH_TEXT drops the XP claim. Test: gap setting 5 is silent at 4.
- M4 One notice slot on Play for build alert, upgrades and tip (R6).
- M5 Price watch and movers in one card: "your checked items that
  moved" first, then the market.

Cut:
- X1 `recent_whispers` from the snapshot (state.py:1832): unused, and
  it carries chat text.
- X2 POST /api/clipboard-read (http.py:311-317) and its test line: a
  stub with no caller.
- X3 The movers line in the session card (summary.py:96-98).
- X4 D3 Price and points, unless R4 shows a note price on a real copied
  item; today its trigger is a guess.

Rename: A9 "Death recap" becomes "Deaths", so it promises no more than
it shows if the game ships its own recap [EE].

Freeze (keep, spend nothing): C1 trade whisper cards, no history and no
reply helpers (F6); G1 graphics advisor, one label re-check after the
1.0 notes; A13 tips, re-check the two death-penalty tips at 1.0; P3
price watch beyond M5.

Promote: B2 to the overlay (R2); A10 to Play in maps (R6); D4 to the
Build tab (R7); act split results to the overlay (R2).

Demote: A12 Last session to the Run tab (R6); E6 weights editor and the
web-data switch to Settings, leaving the Items and prices tab for prices
only; the
character picker to the Run tab (note 0039).

## Rejected

- One-press item check that sends the copy key, as rival overlays do
  (research 0006; decision 0003): the floor forbids any input to the game.
- Listing-based or model-based prices for rares [POV, POVC]: the app
  never calls the trade site (decision 0017); no permitted source exists.
- Stash value or loot from the account APIs: needs an OAuth client;
  registration is closed [GGG]. Stays BLOCKED on TC-OAUTH-REG.
- Clone frames, stash price overlays, atlas overlays [EUI]: need
  repeated screen reads; the floor allows one per manual press.
- Trade reply helpers (invites, messages from a panel) [POVW]: input to
  the game.
- An XP multiplier or penalty number [EE2X]: a formula AshLight cannot
  verify for PoE2; research 0028 ruling B stands.
- Meta or build data from poe.ninja: excluded for third parties
  (research 0019). Own DPS or EHP numbers without PoB: decision 0004.
- Reading the reported in-game death recap from the screen on a press:
  inside the floor, but OCR is a new dependency (the core is stdlib
  only, decision 0002) for something the game already shows.
- A "sold while away" feed for merchant-tab sales: players ask for it
  [SNIP], but no permitted source is known (no log line seen).
- Gem swap planner: needs per-build guide prose (decision 0009);
  research 0031 item 8 stands.
- Hiding the overlay by a foreground-window check [EXP]: close to the
  process check decision 0029 ruled out; passed to note 0042 as a
  question, not recommended here.

## Open questions

- Does Client.txt write a line for a merchant-tab sale or a currency
  exchange fill? R4 can answer; it decides the "sold" feed.
- Does an item copied in a seller's shop carry a note price? Decides X4.
- The 1.0 patch notes are not out: atlas, waystone and tablet changes
  (D5 rules), the death penalty facts (A13), the death recap (A9), the
  interlude ids (R5). Re-check when published.
- R1 storage: parsed stats in a bounded local file, switch on by
  default? Needs an adjudicator ruling and a decision record.
- R2 default: zone card on for the first run? Recommended on; an
  operator taste call if play shows the corner map is covered too often.
- Atlas progress tracker (research 0031, 0032): decide after a 1.0
  endgame log; the ids are unverified and the atlas changes at 1.0.
- Non-English clients at a worldwide free launch: level, death, whisper
  and item paths need English text; language packs wait on samples
  (research 0032). Left to note 0057.

## Verification

Independent check, 2026-11-18, by a second agent.

Checked:
- Code: about 40 path:line citations opened, the ones the findings and
  recommendations rest on first (evaluate.py, zoneguide.py,
  parser.py, acts.py, state.py, render_gate.js, ninja.py, diag.py,
  http.py, summary.py, underlevel.py, campaign.py, upgrade.py,
  buildlive.py, item.py, pricewatch.py, pricebook.py, hints.py,
  eval_hotkey.js, main.js, hotkey.js, tabs.js, index.html, charjson.py,
  decision 0045, research 0021, ROADMAP.md). All hold within a line or
  two; none had to be withdrawn. Not opened (inventory-only citations):
  health.py, waystone.py, runs.py, mapladder.py, skillsplit.py,
  searchstr.py, gfx.py, price.py.
- Numbers recounted from the data files: 93 guide zones, 88 goals, 38
  bonus rewards in 36 zones, 8 layout notes, 22 interlude zones, 65 zone
  notes, 84 of 88 goals wrap into two 34-character lines; 35 features
  and the 15-feature unproven list recounted from the inventory; repeat
  gap 1200 ms (eval_hotkey.js:18); PoB pin v0.23.1 (config/tc_pins.json).
- Web: 15 sources re-fetched (marked V). Confirmed: 1.0 on 2026-12-11 and
  free-to-play [RPGS]; interludes removed and the new-player remark
  [PCGN]; BM ratings; POVC versions and dates (1.38.0 on 2026-05-24,
  1.61.0 on 2026-09-01, 1.69.0 latest); merchant tabs work with the
  seller offline [PV, NT]; Build Planner from 0.5 on 2026-05-29 [FRVR];
  death recap report [EE]; registration closed [GGG]; DILLA and EXB
  outage notes; EUI 1.4k stars and modules.
- ToS floor: all 9 recommendations, 5 merges, 4 cuts and the promote /
  demote moves tested against every floor rule; all stay inside (R1 and
  R9 are one clipboard read per AshLight press; R2 draws only AshLight's
  window; R3, R8 touch only poe.ninja; R7 builds a URL only). The 11
  rejected items stay rejected.
- Settled decisions: none contradicted. R1 needs a new decision next to
  0045, not a reversal; R3 keeps decision 0015's read source; R7 stays
  inside 0017 and 0037; R8 inside 0036.

Corrected:
- DBT now lists 26 entries, not 24 (counts of 4 / 4 / 6 / 1 still hold).
- EE2X does not call its formula an approximation; restated as what the
  page says (PoE1-like, fitted to speedrunner data, off above 70).
- A4: AFK ON was seen in a sample; only AFK OFF and DND are unproven.
- F1: "most new players have no build" labelled as an estimate.
- F2: the overlay line quote replaced by a paraphrase with the 120
  character cap (zoneguide.py:46).
- F6: the merchant-tab date source split stated (PV day, NT patch).
- Demote wording fixed (the Items and prices tab, not Settings).

Added:
- F4 / R3: stale "contact for the trade site" copy (state.py:560-561).
- F9: the EUI trade-log module, as a data point only.
- F13: 1.0 ascendancy names [GOL] missing from charjson.py:30-35.
- R1: the 0045 relation spelled out and the game-key refusal list;
  R8: the 0036 bounds.

UNVERIFIED (left labelled in the text):
- The SNIP hints (forum threads, a levelling thread, a checklist guide).
- The 1.0 death recap rests on one outlet [EE].
- The PoE1 safe-zone shape for PoE2 XP (F8).
- Use-per-hour figures in the inventory are estimates, not measured.
- PH user comments were not re-fetched; POV, POVW, SK, EC, EXP, QUTM,
  POL2 were sampled through DBT and EUI only, not re-fetched.
