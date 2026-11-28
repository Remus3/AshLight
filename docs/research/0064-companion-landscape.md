# 0064 - Companion landscape, November 2026 (gap dive)

Date: 2026-11-27. Verdict: NO change to the ToS floor. Nine floor-safe gaps
ranked, nine proposed rows at the end. Builds on 0006 (tools, 2026-11-16),
0020 / 0023 (feature ranks), 0054 (design patterns, 30 tools) and 0056
(third-party repo, ideas only); it does not repeat what those settled. It
looks for what the tools shipped since and what AshLight still lacks.

Method: every read went through `tools/webfetch.py` (decision 0050: one
allow-list, AshLight User-Agent, no cookie). The worktree has no
config/local.json, so the reads ran the same tool from the main checkout,
whose dev-host `web_data` is true (decision 0013); nothing else was used.
Only `api.github.com/repos/<owner>/<repo>` (metadata, `/readme`,
`/releases`) is on the list for third-party tools. No code was read or
copied; READMEs and release notes only. GPL / LGPL tools (Xiletrade) are
ideas only (CLAUDE.md third-party rule).

## 1. Sources (all accessed 2026-11-27)

Read (HTTP 200, via tools/webfetch.py get):

- S1 https://api.github.com/repos/Kvan7/Exiled-Exchange-2 (+ /readme,
  /releases): MIT, TypeScript, pushed 2026-11-27, latest v0.16.3
  (2026-09-06).
- S2 https://api.github.com/repos/SnosMe/awakened-poe-trade (+ /readme):
  MIT, TypeScript / Electron / Vue, pushed 2026-11-27.
- S3 https://api.github.com/repos/Sidekick-Poe/Sidekick (+ /readme,
  /releases): MIT, C# (.NET 10, Avalonia + Blazor), latest v2026.11.10
  (2026-11-22).
- S4 https://api.github.com/repos/PoE-Overlay-Community/PoE-Overlay-Community-Fork
  (+ /readme): MIT, TypeScript / Electron / Angular, pushed 2026-11-27.
- S5 https://api.github.com/repos/C1rdec/Poe-Lurker (+ /readme,
  /releases): MIT, C#, latest 2.3.4 (2026-11-28 UTC).
- S6 https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding-PoE2
  (+ /readme): licence NOASSERTION in the API (the MIT text is recorded
  in 0011 / 0037), Lua, pushed 2026-11-27.
- S7 https://api.github.com/repos/Lailloken/Exile-UI (+ /readme,
  /releases): MIT, AutoHotkey, formerly Lailloken UI, latest v1.66.2
  (2026-11-26).
- S8 https://api.github.com/repos/HeartofPhos/exile-leveling (+ /readme):
  MIT, TypeScript, pushed 2026-11-12.
- S9 https://api.github.com/repos/maxensas/xiletrade (+ /readme): no SPDX
  in the API; README states WPF UI GPLv3, library LGPLv3, C# .NET.

Refused by the allow-list (`tools/webfetch.py check`, nothing sent):

- poe.ninja (builds pages; also excluded for builds by poe.ninja's own
  terms, 0019), maxroll.gg, mobalytics.gg, exile-leveling.com
  (HeartofPhos's hosted app), pobb.in, sidekick-poe.github.io,
  www.poelurker.com, github.com and raw.githubusercontent.com (wiki pages,
  DEVELOPING.md, images): "host not allowed".
- poe2db.tw, www.poe2wiki.net: "never read by a dive (decision 0050)".
- www.pathofexile.com/forum (decision 0050, Q-07) and /trade2 (decision
  0017).

Not reached: no PoE2-only levelling overlay other than Exile-UI and
exile-leveling could be found without a search endpoint (`/search` is not
under `/repos/`). Maxroll and Mobalytics planners are covered only from
what 0054 recorded.

Proposed allow-list additions (for the operator; not made here):
github.com/<owner>/<repo>/wiki pages read-only, the same rule as the API
(the Exile-UI feature pages live there), and raw.githubusercontent.com for
a repo's own docs/*.md. Both are third-party docs, never GGG.

## 2. Comparison

Floor column: what the tool does that AshLight may NOT do. "OK" = nothing
beyond what AshLight already does.

| Tool | Licence | Main job | Reads game data by | Beyond AshLight's floor |
|---|---|---|---|---|
| Exiled Exchange 2 (S1) | MIT | price check overlay (fork of APT) | sends Ctrl+C via libuiohook, clipboard, Client.txt; trade2 search | input to game; trade2 calls; poeprices.info |
| Awakened PoE Trade (S2) | MIT | PoE1 price check | same as EE2 | same as EE2 |
| Sidekick (S3) | MIT | price check, map mod danger check | sends the copy key (asks KDE for "Remote Control" on Linux), clipboard; trade API; poe2scout.com, poe.ninja, poeprices.info | input; trade2; hotkey blocking |
| PoE Overlay CF (S4) | MIT | price check, trade companion, stash grid, vendor recipes | copy key, Client.txt whispers, account sign-in (stashes) | input (F5 /hideout, Alt+F); trade2; stash via account; in-game browser |
| Poe Lurker (S5) | MIT | trade manager, PoE2 build planner sync, build loot filters | Client.txt, a thread-level hook (Winook), PoB build folder, writes the game's Build Planner | hook; writes game planner folder (decision 0034); reads the PoB folder (ruling: no PoB folder read) |
| PoB PoE2 (S6) | MIT (0011) | offline calc | player paste | OK (AshLight uses it as a pinned subprocess) |
| Exile-UI (S7) | MIT | AHK QoL overlay: act tracker, item info, map info, Statlas, Stash-/Rune-Ninja, Vaal Street, chat macros, recombinator sim | Client.txt (level, area, NPC dialogue); sends key presses; screen checks and OCR on key press | input (copy key, chat commands, search typing); screen checks that hunt for open UIs; clone frames |
| exile-leveling (S8) | MIT | web levelling route with gem steps and PoB import | player paste | OK (web app, no game read) |
| Xiletrade (S9) | GPLv3 / LGPLv3 | price check overlay | copy key, clipboard, trade API | input; trade2; GPL (ideas only) |

What changed since 0054 (2026-11-18), from the release notes:

- EE2 v0.16.x: "Item editor V2": apply augments and catalyst quality to
  the checked item to see the price before spending; an option to fully
  hide the overlay while playing; the 250-character regex limit (S1).
- Poe Lurker 2.3.x: PoE2 build selector, automatic sync of a PoB build
  into the game's Build Planner, a "Poe Lurker" planner entry, a
  NeverSink base filter plus per-build extra conditions, a pinnable
  build overlay (S5).
- Exile-UI 1.66.x: map tracker tracks mirages and a named boss fight,
  map info shows atlas drops, act tracker prompts for a quest NPC before a
  zone (S7).
- Sidekick credits poe2scout.com as a price source next to poe.ninja (S3).

## 3. What AshLight already covers (not gaps)

Price on the press (poe.ninja, trade link only), waystone risk and
rewards, trade cards from Client.txt, PoB deltas and upgrade notices, act
splits, zone guide and quest prompts, Kindler with gem steps and ordered
passives, filter snippet and filter merge, `.build` download on click,
map ladder per area level, pace, under-level, session summary, price
watch and movers, worn gear, player notes, item info popover with a
poe2db link, roll potential and mod tiers from advanced text, build search
strings copied on click, hotkey rebinding, a hide-while-idle overlay.
Rejected in 0054 and still rejected: reply / invite buttons, stash price
tags, screen mirrors, account sign-in, sounds, chat commands.

## 4. Ranked gaps (floor-safe)

Each: what, who has it, floor verdict, effort, ZERO-CLICK.

G1. PoB tree spec follows the character level. Exile-UI (PoB tree
overlays) and Poe Lurker (passive tree, sync) follow a build's stages;
guide exports from planners carry several PoB tree specs titled by level
("Level 30", "Act 4"), and AshLight uses only PoB's active spec
(server/al/theorycraft/model.py active_spec; spec_titles are shown, never
chosen). Pick the spec whose title names the nearest level at or below
the character's (decision 0038 level), fall back to the active spec when
no title parses; feed it to the tree view, the tree link, the `.build`
download and the calc. Floor: YES (player-pasted build text, Client.txt
level). Effort M (bridge needs a spec select command). ZERO-CLICK: the
switch happens on the player's own level-up line; no picker.

G2. Uncut gem advice on the item-check press. Exile-UI ships a
gemcutting overlay (S7); no tool ties it to the player's build. When the
pressed item is an Uncut Skill / Support / Spirit Gem of level N, the card
names the loaded build's gems that this cut could make at N and the
character does not have yet (PoB build skills + cached gems snapshot
levels, DATA-GEMS-SNAP). Floor: YES (one press, cached data). Effort S.
ZERO-CLICK: rides the existing press; no new key.

G3. Gem unlock card for a pasted build. exile-leveling and Exile-UI show
gem steps for any imported build; AshLight's gem steps exist only for a
Kindler plan. On the player's level-up line, when the loaded build has a
skill or support whose snapshot level requirement is now met and the
build expects it, one zone-style card: "Level 14: <gem> is usable now".
Floor: YES (Client.txt level + build + snapshot). Effort S. ZERO-CLICK:
level-up line; the card expires by itself (decision 0014 card times).

G4. Augment and quality what-if on the press. EE2's Item Editor V2 (S1)
prices augments before spending, via trade2 (floor: NO for that half).
The calc half fits: for a pressed item with an empty rune socket or room
for catalyst quality, the staged PoB stage ranks the cached augment mods
(base_items / mods snapshot; source to verify, see open question 1) by DPS
/ EHP delta for the loaded build and names the best one. Floor: YES for
PoB deltas, NO for trade prices (decision 0017). Effort M. ZERO-CLICK:
computed in the existing staged calc of the press (decision 0024), at most
delta.MAX_PROBES calcs.

G5. Per-map stats by map name (Exile-UI Statlas, PoE2 only). The map
ladder groups by area level; players also ask "how do I do on this map".
Add a per-area-id table (runs, deaths, median time, last run) from the
same run records; show the current map's line on the map context card.
Floor: YES (Client.txt only, decision 0036 bounds). Effort S. ZERO-CLICK:
filled from the log; shown on map entry.

G6. Map content tags from Client.txt. Exile-UI's map tracker records
mirages and a named boss fight and fires map-event notifications from NPC
dialogue lines (S7). AshLight could tag a map run with a mechanic only
where a verified, anchored log line names it. Floor: YES (log only) but
UNVERIFIED: which PoE2 lines exist must come from AshLight's own masked
shape ledger (decision 0071) or an operator-pasted log, never from
Exile-UI's tables. Effort M (research first). ZERO-CLICK: tags fill from
the log; no player action.

G7. A price source for release builds. Release builds make no poe.ninja
request until poe.ninja says yes (decision 0072), so a public install
prices nothing. Sidekick credits poe2scout.com (S3). Any second source is
a floor change (the floor names GGG documented endpoints and poe.ninja
only) and needs the owner's written app-use permission. Floor: NO today;
operator act. Effort S to ask, M to add a provider behind the same opt-in.
ZERO-CLICK: once permitted, prices ride the existing refresh.

G8. Session sales tally. Trade managers (S4, S5, Exile-UI Vaal Street)
log sales. PoE2 whispers carry the item and listed price, which AshLight
already parses for trade cards; a finished trade closes one card
(decision 0019). A per-session in-memory tally ("3 trades, about 12 ex")
on the session summary. 0023 rated a trade log low value assuming no
price data; the whisper does carry it, so this re-opens with a narrower
scope. Floor: YES (Client.txt only; no chat text stored, only counts and
sums). Effort M; the oldest-card pairing guess (decision 0019) makes the
sum an estimate. ZERO-CLICK: counted from the log, shown on the summary
card that already appears by itself.

G9. Localised clients. EE2 (Weblate) and Exile-UI (community
translations) parse non-English item text and logs; AshLight shows a
non-English notice only (decision 0040). Floor: YES. Effort L (per-language
item and log grammar, test fixtures). ZERO-CLICK: language detected from
the same signals langguard already uses. Ranked last: scope and upkeep.

Not adopted (with reason): automatic Build Planner sync (Lurker; decision
0034, never writes the planner folder), PoB folder watch (Lurker; ruling:
no PoB folder read), recombinator simulator (Exile-UI; no permitted
source for outcome odds), price distribution graph and augment prices
(PoE Overlay, EE2; trade2), stash-ninja price tags (0054 rejected), chat
macros and /hideout keys (input), poeprices.info estimates (not a floor
source; trained on trade listings, 0054), clone frames and UI-hunting
screen checks (decision 0003), Linux and web-mode builds (out of scope;
web mode with no login rejected in 0054).

## 5. Open questions

1. Which cached snapshot names PoE2 augment (rune / soul core) mods with
   stat ids: repoe-fork base_items plus mods, or a separate file? Verify
   before G4 (no guessed table).
2. How often PoE2 guide builds title their tree specs by level; G1's
   parse rule needs two or three real exports as fixtures (operator paste).

## 6. Verification

- Every source above was read on 2026-11-27 through tools/webfetch.py; the
  refused hosts were checked with `tools/webfetch.py check` and sent
  nothing.
- Coverage claims in section 3 were checked against server/al (module
  docstrings: mapladder, pace, summary, underlevel, potential, searchstr,
  pricewatch, trade, lootfilter; theorycraft/model.py active_spec).

## Proposed ROADMAP rows

- [ ] TC-SPEC-FOLLOW (build) Pick the loaded PoB build's tree spec by character level: parse a level from each spec title ("Level 30", "lvl 30", "30"), use the spec with the highest parsed level at or below the decision 0038 character level, else PoB's active spec; feed it to the tree view, the tree link, the .build download and the calc (bridge selects the spec); the dashboard names the spec in use (research 0064 G1). ACCEPT: python -m pytest -q tests/test_tc_spec_follow.py passes with a three-spec fixture and a level-up that switches the spec. ZERO-CLICK: the spec switches on the player's own level-up line; there is no picker.
- [ ] TC-UNCUT-GEM (build) Uncut gem advice on the item-check press: for an Uncut Skill, Support or Spirit Gem of level N, the card names the loaded build's gems of that kind that a level N cut can make and that the build does not show as socketed at that level yet, from the PoB build skills and the cached gems snapshot (DATA-GEMS-SNAP); no build or no snapshot shows nothing (research 0064 G2). ACCEPT: python -m pytest -q tests/test_tc_uncut_gem.py passes with real uncut gem item text fixtures. ZERO-CLICK: rides the existing item-check press; no new key or click.
- [ ] TC-GEM-UNLOCK (build) Gem unlock card for a pasted build: on the player's level-up line, when a skill or support gem of the loaded build has a snapshot level requirement now met, publish one card naming it (at most one card per level-up, decision 0014 card time, dashboard twin row) (research 0064 G3). ACCEPT: python -m pytest -q tests/test_tc_gem_unlock.py passes, covering no build, no snapshot and two gems at one level. ZERO-CLICK: driven by the level-up line; the card expires by itself.
- [ ] RES-AUGMENT-DATA (data) Find the permitted cached source of PoE2 augment (rune, soul core) mods with stat ids and socket rules among the repoe-fork snapshots (decision 0009), record it in a research note with access dates, or record that none exists (research 0064 open question 1). ACCEPT: the note exists and docs/research/README.md indexes it. ZERO-CLICK: a desk read by the loop; no player action.
- [ ] TC-AUGMENT-WHATIF (build) Augment and quality what-if on the press: for a pressed item with an empty augment socket or quality below 20, the staged PoB stage ranks the cached augment mods by the decision 0024 blend for the loaded build and names the best one with its DPS / EHP delta; never a price (decision 0017), at most delta.MAX_PROBES calcs, cancelled by a newer press (research 0064 G4). ACCEPT: python -m pytest -q tests/test_tc_augment_whatif.py passes with a socketed weapon fixture. ZERO-CLICK: computed in the press's existing staged calc. DEPENDS: RES-AUGMENT-DATA. BLOCKED: gate (waits on RES-AUGMENT-DATA naming a permitted augment data source).
- [ ] UTIL-MAP-STATS (build) Per-map stats by map area id next to the map ladder: runs, deaths, median time and last run per area id from the same run records (decision 0036 bounds, cleared by Clear run history), and the current map's line on the map context card (research 0064 G5). ACCEPT: python -m pytest -q tests/test_map_stats.py passes with a fixture log of two maps run twice each. ZERO-CLICK: filled from Client.txt; shown on map entry.
- [ ] RES-MAP-CONTENT-LINES (data) List the PoE2 Client.txt lines that name a map mechanic or a named boss encounter, from AshLight's own masked shape ledger (decision 0071) and operator-pasted log only, each anchored and with a sighting count; propose map content tags for the map ladder (research 0064 G6). ACCEPT: a research note lists each line with its source and count, indexed in docs/research/README.md. ZERO-CLICK: the ledger fills while the operator plays; the read is the loop's. BLOCKED: gate (needs the ledger consent on and at least one week of masked shapes).
- [ ] UTIL-SALES-TALLY (build) Session sales tally: count finished trades and sum the listed prices of the cards they closed (decision 0019 pairing) per currency for the play stretch, in memory only, shown on the session summary card as an estimate; no chat text or name stored (research 0064 G8). ACCEPT: python -m pytest -q tests/test_sales_tally.py passes with a fixture log of three sales in two currencies. ZERO-CLICK: counted from Client.txt; the summary card appears by itself.
- [ ] DATA-PRICE-ALT-ASK (data) Ask a second PoE2 price source (poe2scout.com first) for written app-use permission and its contact and rate terms, then record the answer in a decision; a yes still needs the operator's floor amendment before any provider row (research 0064 G7; decision 0072 silence is not consent). ACCEPT: a decision file records the request, the answer or its absence, and the operator's ruling. ZERO-CLICK: one message sent by the operator; the rest is desk work. BLOCKED: operator act (send the permission request; rule on the floor amendment).
