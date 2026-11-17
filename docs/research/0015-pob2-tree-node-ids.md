# 0015 - PoB2 spec node ids vs GGG tree export skill ids (DATA-TREE-IDS)

Question: a Path of Building PoE2 build's `<Spec nodes="...">` list is
passed to `treedata.TreeData.resolve`, which looks the numbers up as the
`skill` ids of GGG's PoE2 tree export (`data.json`, research 0014). Are the
two the same id space?

Answer: YES, identical. No mapping table is needed. `resolve` maps 1:1 and
`TreeData.id_match` guards the assumption at run time.

All pages accessed 2026-11-17. Read-only GETs, no cookies, User-Agent
`AshLight/0.1`. PoB-PoE2 is MIT-licensed; its code was READ for this note,
nothing is copied into AshLight (no license record needed; CLAUDE.md
third-party rule). The tree files were compared in a scratch directory
outside the repo and are NOT committed (decision 0009); no excerpt is kept.

## Sources

1. PoB-PoE2 `src/Classes/PassiveSpec.lua` (dev branch):
   https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/PassiveSpec.lua
   Load splits the Spec `nodes` attribute into integers and allocates
   `self.nodes[id]`; `self.nodes` is keyed by each tree node's `id`. Save
   writes the sorted allocated ids back comma-joined. There is no node id
   remap table; the only legacy table maps class ids per tree version, and
   `hashOverrides` swaps attribute node bodies, not ids.
2. PoB-PoE2 `src/Classes/PassiveTree.lua` (dev branch):
   https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/PassiveTree.lua
   Each loaded node gets `id` copied from its `skill` field, no conversion.
   Per tree version it loads `TreeData/<ver>/tree.lua`, else falls back to
   a GGG-format `data.json` in the same folder (optionally downloaded from
   pathofexile.com) and converts it as is.
3. PoB-PoE2 `src/Export/Scripts/passivetree_ggg.lua` (dev branch):
   https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Export/Scripts/passivetree_ggg.lua
   Reads GGG's `data.json` and writes PoB's `tree.lua`, keeping each GGG
   node key as both the PoB node key and its `skill` (only the `root`
   pseudo node becomes 0). No renumbering.
4. PoB-PoE2 `src/Export/Scripts/passivetree.lua` (dev branch):
   https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Export/Scripts/passivetree.lua
   The game-file path: node `skill` and key are the passive id read from
   the game's passive skill graph (.psg). GGG's export uses the same graph
   ids, as item 5 shows.
5. Empirical cross-check (scratch only):
   - GGG: https://raw.githubusercontent.com/grindinggear/poe2-skilltree-export/main/data.json
     (200, 5,140,821 bytes; tree `Default`, 5152 real nodes).
   - PoB2: https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/TreeData/0_5/tree.json
     (200, 2,052,797 bytes; 4914 nodes, `skill` equals the key on all).
   - PoB2: https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/TreeData/0_4/tree.json
     (200, 1,943,959 bytes; 4701 nodes, `skill` equals the key on all).

## Findings

- PoB2 0_5 vs GGG export: all 4914 PoB2 ids exist in the export (0 only in
  PoB2). After stripping the export's `[Key|Shown]` markup
  (`treedata.display_stat`), 4908 names match exactly. The 6 that differ
  are ascendancy start / ascendancy nodes that PoB2 names after the
  ascendancy while the export uses an internal label or an empty name; the
  ids still point at the same ascendancy (export `ascendancyId` agrees
  with PoB2's ascendancy name). Notable and keystone flags agree on
  4913 / 4914. The 238 export-only ids all have empty names (placeholder
  nodes in the newer export).
- PoB2 0_4 vs the same (newer) export: 4680 / 4701 ids shared, 4593 of them
  with the same name; the rest are node reworks between game versions.
  This is version drift, not a different id space: a foreign id space
  would hit about 8 percent by chance (about 5k nodes over a 16-bit range).

## What AshLight does

- `treedata.TreeData.resolve` keeps the 1:1 lookup (documented in the
  module docstring, citing this note).
- `treedata.TreeData.id_match(ids)` returns {known, total, ok}; ok is False
  when fewer than `MIN_ID_MATCH` (0.5) of a spec's ids exist in the loaded
  tree. `model.TreeSpec.to_dict(tree)` always adds `tree_match` and adds
  `named_nodes` only when ok, so a wrong id space or a far-off tree version
  shows no names rather than wrong ones.
- Tests: `tests/test_tc_tree_ids.py` (real-shaped synthetic export and
  PoB2 XML; same-space mapping, version drift, foreign-space guard).
- Known residual: an ascendancy start node can read with the export's
  internal label instead of the ascendancy name PoB2 shows. Cosmetic; the
  `ascendancy` field is correct.

Reverses if: a PoB2 release adds a node id remap table to PassiveSpec, or a
real PoB2 export's spec ids fail `id_match` against the matching export.
