# 0081 - Kindler: generated builds within PoB interop

Date: 2026-11-19. Status: ruled by an adjudicator agent the same day
(operator request 2026-11-19, item 2). Input: research 0060 section 4.
Amends decision 0004 (items 2, 3, 7 and 9 stand; this adds what a
generated build may be). Plan: docs/plan/10-operator-requests-2026-11-19.md
(packages KINDLER-*).

## Decision

1. Name. The theory engine had no name. It is "Kindler" (own word, no GGG
   trademark or game proper noun, no hit among the tools of research
   0054, 0055 and 0006; checked in the repo and the sidecar game-data
   caches 2026-11-19, not on the open web). UI label "Kindler: build
   generator"; UI copy still credits Path of Building as the calculator
   ("Scored by Path of Building").
2. What a generated build is. An AshLight-authored archetype template
   (main skill and support picks by name, a tree route as passive node
   id lists, item stat priorities per slot) in
   server/al/data/archetypes.json, scored only by Path of Building
   through the TC-BRIDGE commands (decision 0022: load_build XML, then
   outputs) over a bounded candidate set. AshLight owns no calc, no free
   tree search and no optimiser. Templates are JSON, never run as code,
   hot reloaded (decision 0042), each entry carrying src and checked
   (decision 0057 style); nothing is copied from another tool.
3. Bounds. At most 12 candidates per Generate, one at a time on the
   existing daemon worker (decision 0024), 60 s in total; on time-out the
   best so far is shown, labelled partial. The 384 MB Lua heap ceiling
   and the calc budgets of 0024 R7 / 0028 stand. Results are cached per
   toggle hash.
4. Trigger. Only the player's Generate click runs it. A toggle change
   marks the result stale (a "stale" chip); nothing regenerates by itself,
   because calc work must not compete with the game for CPU (decision
   0002 budgets outrank the zero-click aim here).
5. Calc component off. The top template by toggle match and stat weights
   is shown, labelled "not scored (calc off)", with no DPS or EHP number.
6. Tree routes. Node ids are checked against the cached GGG tree export
   (decision 0034); an unmapped node is dropped with a note, never
   guessed.
7. Persistence. ops/runtime/gen_builds.json, schema 1, one .bak, a
   jsonfile Saver retry (RUN-DURABLE-STORES), at most 6 generator tabs in
   all (a seventh is refused with a note). Per tab: id, label, class,
   league, toggle values, chosen template id, a result summary (template
   id, PoB headline numbers, time) and the candidate count. Never item
   text. Emptied by Clear run history; included in settings export as an
   allow-listed block; an import never turns web_data on (decision 0036).
   The tab list and the shown tab survive a reload and an app exit.
8. League. Picked from the cached poe.ninja league list (decision 0026)
   while web_data is on, else "Standard" plus a typed value; no new
   request. League changes only price-aware item suggestions and trade
   links (decision 0017); it never changes the template or PoB scoring.
9. Toggles (first slice), each with "not sure": melee, spell, minion,
   bow, crit, and defence (life / energy shield / hybrid). "Not sure" is
   no constraint and lowers no score; several archetype yeses mean a mix,
   ranked by how many chosen groups a template covers. Fast clear vs
   bossing and budget come in slice two.
10. Items shown open the shared item info popover (decision 0082 part 1).

## Alternatives

- Free search over the passive tree: a de facto own calc engine (barred
  by 0004) with unbounded cost.
- Stat weights only: cheap, but no PoB-scored claim.
- Auto-run on every toggle change: CPU contention with the game.
- Per-character generator tabs (decision 0045 style): the operator asked
  for a list of what the player envisions, not per character.
- State in config/local.json: grows the config with player data.
- Names "Hearthwright" (runner-up; "Emberwright" is a test character name
  in tests/test_parser.py, so not used).

## Why

Authored tables plus PoB scoring stay inside 0004's "PoB interop, never
an own calc engine", and the bounds reuse patterns already ruled in 0057,
0034, 0024 and 0036. The calc-off mode says plainly what it did not
score.

## Reverses if

PoB drift makes route XML unreliable; 12 candidates in 60 s breach the
0024 / 0028 budgets; players want automatic regeneration and it is shown
to cost no FPS; 6 tabs prove too few; a name collision or GGG use of the
word is found; or the operator rules generated builds out of scope.

## Amendment 2026-11-19 (operator follow-ups: tabs, determinism, detail, gems, follow)

Ruled by an adjudicator agent the same day. Points 1 to 10 stand except
where changed here. Plan: docs/plan/10 section 3 (KINDLER-* split into
seven packages).

11. Tabs. The Pasted build sub-tab is fixed first and cannot be closed,
    renamed or moved. Kindler tabs: order is the list order in
    gen_builds.json; Move left / Move right buttons (keyboard reachable,
    no drag in slice 1); rename in place, player text capped at 32
    characters, control characters stripped, empty means the default
    label; close needs an inline confirm ("Close <label>? Close / Keep",
    focus on Keep; never window.confirm). The 6-tab cap and the 0036
    bounds stand.
12. Determinism. Same inputs give the same result. Result key = sha256
    of (class, toggle values, archetypes.json sha256, PoB pin, tree
    export version, level band). Candidates are ranked by PoB outputs
    only, using the fixed 50/50 DPS / EHP blend of decision 0024; ties
    break by template id ascending, then variant index ascending. No
    random source, no clock input. A partial result (point 3, 60 s cut)
    is labelled and never cached as final. With the calc off (point 5)
    the one template shown is picked by toggle-match count, then template
    id; it carries no DPS or EHP number.
13. Correctness checks (tests): two runs on one key are byte-identical;
    the 0028 reference build composed through Kindler's XML path scores
    within 0.1 percent of the bridge's direct numbers; every route prefix
    is connected from the class start and inside the point budget at its
    stage's level (a breadth-first connectivity check in the validator
    and tests only); node ids exist in the cached tree export (0034); gem
    names exist in the cached repoe-fork gems snapshot (else
    checked=false); a support that PoB reports as not applying to its
    skill fails the template check. Live checks skip when the calc
    component is off.
14. Passive order. Each stage holds an authored, ordered node list,
    ascendancy nodes listed apart in their own order. No runtime
    pathfinding (point 6 and the rejected free search stand).
15. Stages (levelling to maps). A template is a list of stages. A
    trigger is a character level band (decision 0038's character), an
    act or zone id from the snapshot world_areas, or for the endgame an
    area level band from the log's area generation line; a waystone
    tier name is shown only where a sourced mapping exists. Each stage
    carries: the skills in use; per skill its support gems (the link
    setup, support count bounded by the sockets the stage authors);
    gems to pick up, swap or drop at this stage, with the trigger; the
    passive prefix; per-slot item focus (the stats to aim for, ranked by
    PoB per-mod weights of decision 0024 when the calc is on, by the
    authored priority otherwise; the mods are opened in the item info
    popover); ascendancy points as "after your Nth Ascendancy trial",
    never a claim that the trial was done.
16. Gem timing. The level a gem can be used at comes from the cached
    gems snapshot; else the template's authored level with
    checked=false. Skill numbers per gem come only from PoB through the
    bridge; no own gem calc.
17. Follow Play guidance. A per-tab boolean in gen_builds.json, on by
    default. While on, the result card highlights the stage whose
    trigger matches the zone, act and level the snapshot already
    publishes (ZONE-GUIDE, decision 0043; 0038): no new read, no new log
    parse. It never claims a step was done.
18. Trimmed, plainly: a free optimiser or own tree search (0004); drop
    locations, vendor shopping and crafting steps for levelling items,
    uniques by where they drop, and which quest gives which gem (no
    permitted source, decision 0083 and its amendment); any DPS or EHP
    claim with the calc off; automatic regeneration (point 4); drag and
    drop reorder (slice 2 at most); any input to the game (ToS floor);
    the .build file stays a download on the player's click (decision
    0034), never a write into the game's folder; waystone tier names
    without a sourced mapping.

Alternatives: shortest-path fill between authored waypoint nodes (edges
toward an own search); follow off by default (against the zero-click
aim); fewer, larger packages (the 90-minute package cap).

Why: authored stages plus PoB numbers give a full levelling-to-maps plan
without an own calc or search; a fixed key and a fixed tie order make
the output reproducible and testable; following the Play guidance reuses
state already published.

Reverses if: authored node lists prove too costly to keep (then rule a
waypoint fill again); a real PoB output makes the repeat-run test
non-identical; the follow default annoys players in play; or PoB stops
reporting support applicability through the bridge.
