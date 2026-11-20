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
