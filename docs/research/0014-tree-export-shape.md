# 0014 - GGG PoE2 tree export shape (DATA-TREE-SHAPE)

All pages accessed 2026-11-17. Read-only GETs, no cookies, User-Agent
`AshLight/0.1`, 3 requests. The file was inspected in a scratch directory
outside the repo and is NOT committed; no excerpt is kept (GGG data, no
license file, decision 0009 item 3). Key names below are described in our
own words.

Sources:
- https://api.github.com/repos/grindinggear/poe2-skilltree-export/contents/
  (listing: README.md, assets/, data.json)
- https://raw.githubusercontent.com/grindinggear/poe2-skilltree-export/main/README.md
  (one line of description plus a pointer to the GGG OAuth docs)
- https://raw.githubusercontent.com/grindinggear/poe2-skilltree-export/main/data.json
  (about 5.1 MB, 200)

## Top-level keys

- tree: string (a tree name).
- classes: list of 12; each has name, three base attribute values, image
  info, ascendancies (list; each has id such as `Witch1`, name, image and
  flavour fields). Some classes list none.
- groups: object keyed by group number; x, y, orbits, nodes (id strings).
- nodes: object keyed by the node id as a string, 5153 entries.
- edges: list of {from, to}; from may be the string `root`, to is an int.
- skillOverrides: object keyed by id (80), small replacement node bodies.
- jewelSlots: list of ints.
- min_x, min_y, max_x, max_y: ints.

## Node keys

Common to every real node: skill (int), id (string slug, or null on 240),
name, icon, stats (list of strings), group, orbit, orbitIndex, x, y, out
and in (lists of id strings), edges (list of ints). A pseudo node keyed
`root` has no skill or name, only group, orbit, out, in, edges.

Flags and extras seen: isNotable, isKeystone, isJewelSocket, isMastery,
isGenericAttribute, isAscendancyStart, isBlighted, isFree, isMultipleChoice,
isMultipleChoiceOption (with multipleChoiceParent), hideConnection,
ascendancyId (string such as `Warrior3`; 669 nodes), unlockConstraint
(object), grantedSkill (object, large), granted* attribute and point
counts, keystonesInRadius, recipe, flavourText (list), activeEffectImage.
classStartIndex is present on 6 nodes and is a LIST of class indexes (the
Marauder start node carries two entries). Stat strings can hold newlines
and bracket markup of the form [Key|Shown].

## Comparison with treedata.py and the fixture

- nodes keyed by id string, `skill` equals the key on all 5152 real nodes:
  MATCH.
- name, stats (list of strings): MATCH.
- isNotable, isKeystone, isJewelSocket booleans: MATCH.
- classes[].name and ascendancies[].id / name: MATCH.
- top-level `nodes` object and `classes` list: MATCH.
- ascendancyName on a node: MISMATCH. The real key is ascendancyId (an id
  like `Warrior3`, not a name); the name lives in classes[].ascendancies.
  The reader returns ascendancy None for every node.
- classStartIndex as int: MISMATCH. It is a list of ints. The reader's
  isinstance(int) check drops all class starts. classesStart: not present
  in the real file (harmless).
- `root` key with no skill or name: handled (no skill, key not numeric, so
  skipped).
- Stats markup and embedded newlines: not an assumption failure, but a
  consumer that shows or matches stats must strip bracket markup.
- PoB2 spec node ids equal export skill ids: NOT verifiable from this file
  alone (no PoB2 data was read); left open in DATA-TREE-FIX.

Fixture (skilltree_synthetic.json) mirrors the wrong assumptions for
ascendancyName and int classStartIndex, so the tests pass while the real
file would give no ascendancy and no class starts.
