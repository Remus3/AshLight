# Tree view and Progression view

Package PROGRESSION-VIEW (operator order 2026-11-27, widened the same day
to the whole character progression). Decision:
[0088](../decisions/0088-progression-view.md). Copy sheet:
[copy/progression.md](copy/progression.md). Rules that bind every part:
[0001-design-system.md](0001-design-system.md).

## 1. What already rendered passives (investigated 2026-11-27)

- No drawing. Passives showed only as text: the Kindler plan card's
  Passives page (web/kindler.js, KINDLER-UI-RESULT: names, point count and
  budget per stage), the build view's named nodes
  (theorycraft/model.py TreeSpec.to_dict with treedata.resolve), the
  official viewer link (theorycraft/treeurl.py, TC-TREE-URL) and the
  game's .build download (theorycraft/buildfile.py, decision 0034).
- theorycraft/treedata.py read only ids, names, stats, kind flags, class
  and ascendancy starts and the attribute overrides. archetypes.tree_graph
  read the out / in links for the Kindler validator only.

## 2. The cached GGG tree export

`<sidecar>\Cache\gamedata\skilltree.json` (GGG's public skill tree
export, decision 0009 fetch-only), checked 2026-11-27, 5,140,821 bytes:

- top level: `tree` ("Default"), `classes` (12, each with `ascendancies`
  {id, name}), `groups` (1,623, each {x, y, orbits, nodes}), `nodes`
  (5,153), `edges` (6,076 {from, to}), `skillOverrides` (80), `jewelSlots`
  (31), `min_x` -22597, `min_y` -18720, `max_x` 21814, `max_y` 20053;
- a node: `skill`, `id`, `name`, `icon` (a GGG art path: never used),
  `stats`, `group`, `orbit`, `orbitIndex`, `x`, `y` (the drawing
  position, already resolved from group and orbit), `out` / `in` (linked
  ids as strings; "root" for the pseudo node), `edges` (indexes into the
  top-level list), and the flags `isNotable` (1,192), `isKeystone` (33),
  `isJewelSocket` (19), `isMastery` (368), `isAscendancyStart` (36),
  `classStartIndex` (6), `ascendancyId` (669 nodes over 36 ascendancies),
  `hideConnection` (12), plus `isGenericAttribute`, `grantedSkill` and
  others not used here;
- the main tree spans about -12,600 to 12,650 in both axes; each
  ascendancy tree sits apart (for example x about -22,600).

treedata.Node now keeps `x`, `y`, `links` (out and in, numeric ids only)
and `mastery`; `group` / `orbit` are not kept (x / y already place the
node; lines are drawn straight, not as orbit arcs).

## 3. The model (server/al/theorycraft/progression.py)

```
{schema, source: pob|kindler|none, source_line, level, note, key,
 tree: {box: [x, y, w, h], n: [[id, x, y, kind, state]],
        e: [[i, j, state]], names: {id: [name, stat, stat]}},
 asc: {... same, name}, new: [ids], due: [ids],
 skills: [{name, level, need, checked, ready, meta, with,
           supports: [{name, level, need, checked, ready, applies}]}],
 points: [lines], next: [{kind, text}], empty, counts}
```

- kind: s small, n notable, k keystone, j jewel socket, c class start,
  a ascendancy start. state: h planned by this level, d take next,
  l planned later, o not in the plan.
- Framing: the box is the planned nodes plus 600 export units (at least
  2,400 wide and tall), else the class start. The view takes the planned
  nodes, then their neighbours ring by ring inside the box, then the
  nearest rest, up to 700 nodes; links among them up to 1,400.
- Bounds: 260 named nodes, 2 stat lines each (90 characters), 60
  characters a name, 8 skill rows of 6 supports, 3 next-up steps of 60
  characters, 160 KB in all (stat lines, then far unplanned nodes go
  first).
- key: 16 hex of the model's own JSON, so the page re-reads only on a
  real change.

## 4. Moving on by itself

The plug's tick (server/al/plug/progression.py) rebuilds the model when
the build object, the published level, area id or zone change (looked at
every core pass), or when the tree export, the Kindler tab result, the
gems snapshot or the guide change (looked at most every 2 s), and
publishes the summary as the snapshot's "progression" view. The page
reads the whole model (GET /api/progression) when the key changes. A
level-up, a new or hot-reloaded build, a TC-SPEC-FOLLOW spec change, a new
Kindler result or a zone with a point book all reach the view with no
click and no page timer. Kindler stages follow the published values only
(kindlerplan.current_stage), never a claim of progress.

TC-SPEC-FOLLOW wires its spec chooser in `spec_picker(core)` of
server/al/plug/progression.py; until then the active spec shows.
TC-UNCUT-GEM and TC-GEM-UNLOCK add next-up steps with
`progression.add_next_source(name, fn, order)`.

## 5. Placement and fit

- Play, region I: the "Next up" view (head "Next up" and the level, the
  strip, the mini-tree framed on the due nodes and their planned
  neighbours, the legend and, with an item check present, one "Item
  check" button). It shows when the progression moves on (level, build,
  source) and no newer check came in; a new check shows the item card.
  In the cockpit classes it is absolute inside region I's box with a
  1.25rem foot (the I slack of 16 / 6 px at s = 1), so the region's track
  never changes. Measured (tests/test_progress_fit.py, worst-case model):
  slack 20 px at s = 1 (25 at s = 1.25), no clip, 21 to 22 visible
  elements and 45 to 47 words against the region I caps of 60 words; the
  mini-tree is 174 to 247 px tall at s = 1.
- Build and items: the Progression card spans the card grid (rows 2 and
  3 under the Builds row) like the Kindler card: three columns in the
  cockpit (tree with its hover line and legend; next up and skills;
  ascendancy and points), one in the flow class. Measured: card slack 4
  to 5 px, no column clips, tree 388 x 430 px at 1024x700 and 749 x 615
  px at 1920x950.
- Flow class: everything stacks, the trees take fixed heights (12rem
  mini, 18rem full, 8rem ascendancy), no horizontal scroll at 320 px.

## 6. Self-review against design 0001 (2026-11-27)

- C1, C2: text uses --fk-text, --al-text-body and --fk-text-muted on the
  surfaces of the 5.2 block; the drawing's informative marks use
  --fk-accent (planned) and --fk-status-warn (due), both kit status and
  accent tokens measured for 3:1 non-text contrast in 5.2; unplanned
  nodes are --fk-border on purpose (context, not state).
- C3: no literal colour in progression.css (tests/test_progression_ui.py).
- C4: every state has a shape or line style (filled, dashed ring, thin
  ring, dot, outer ring) and a legend in words; forced colours map to
  Highlight / CanvasText / GrayText.
- C6: dark and light both checked by screenshot.
- C7: text sizes from the type tokens only (row-micro, row-meta,
  row-body, row-title, card-h3).
- P1 to P8: plain words, honest unknowns ("unchecked", "level unknown"),
  no claim of progress; the empty strip says "Nothing new is due at this
  level."
- N1, N2: no new required click; no modal. N6: no live region added. N7:
  region I keeps its size; the swap is a state change inside it.
- O1 to O8: the overlay is unchanged.
- S2: the three buttons are 24 px; S3: 320 px without horizontal scroll;
  S4: native buttons, focus ring of the page; the trees are role="img"
  with a label and every fact on them is also in text (strip, points).
- Motion: none (principle 3); see decision 0088 point 9.
