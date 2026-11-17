# 0026 - The game's `.build` file: schema and passive id mapping (TC-BUILDFILE)

Date: 2026-11-17. Lane AREA-MATH batch 6. Inputs: research 0014 (tree
export shape), 0015 (PoB2 node ids == export `skill`), 0018 section 3
(File Formats page first read), decision 0009 (build-time data only).

## 1. GGG's documented format

GGG's File Formats page, section "Build Planner (PoE2 only)"
(https://www.pathofexile.com/developer/docs/game , accessed 2026-11-17):

- The game reads `*.build` files from the player's local planner folder
  (a file watcher picks up changes); each file is JSON "containing a single
  Build object". There is NO version key: "Version 1 (Experimental)" is a
  heading label, not a field.
- Build: `name` (string, required), optional `author`, `link`,
  `description`, `ascendancy` (strings), `passives` (array of string or
  BuildPassive), `skills` (array of string or BuildSkill),
  `inventory_slots` (array of BuildInventorySlot). Optional fields are
  marked `?`.
- BuildPassive: `id` ("a PassiveSkills table id. Example: `strength89`"),
  `level_interval` (uint or [uint, uint], e.g. `[0, 100]`), `weapon_set`
  (uint 0 to 2), `additional_text`.
- BuildSkill: `id` (a BaseItemTypes id, e.g.
  `Metadata/Items/Gems/SkillGemEarthquake`), `level_interval`,
  `additional_text`, `support_skills` (array of string or BuildSupport:
  `id`, `level_interval`, `additional_text`). "Meta gems are currently not
  supported."
- BuildInventorySlot: `inventory_id` ("an Inventories table id", example
  `Weapon1`), `slot_x` / `slot_y` (uint, default 0), `level_interval`,
  `unique_name` (a UniqueName from the Words table), `additional_text`.
- The example build uses ascendancy `Warrior1`; passive ids `melee17`,
  `marauder_brute_notable1`, `strength89`, `attributes65`,
  `jewel_slot1956`, `AscendancyWarrior1Small3`; inventory ids `Weapon1`,
  `Helm1`, `BodyArmour1`, `Gloves1`, `Boots1`, `Belt1`, `Amulet1`,
  `Ring1`, `Ring2`. One support id in the example reads
  `Metadata/Items/Gem/...` (singular), most likely a typo.
- `additional_text` markup: `<b>{...}`, colour keys, nestable.

## 2. Passive ids: from GGG's own tree export, no table

- GGG's Data Exports page lists the PoE2 passive tree export as its only
  PoE2 data (https://www.pathofexile.com/developer/docs/data , accessed
  2026-11-17, via research 0018).
- The export (`data.json`, https://github.com/grindinggear/poe2-skilltree-export ,
  latest commit "0.5.5", 2026-09-04; accessed 2026-11-17) gives each real
  node an int `skill` and a string `id`. Read-back of one download
  (5,140,821 bytes, 2026-11-17): 5,152 real nodes, 240 with a null `id`
  (blank placeholder nodes with no name). ALL six passive ids of GGG's
  example build (section 1) are export `id` values. Ascendancy entries are
  `{"id": "Warrior1", "name": "Titan"}` style.
- PoB2 spec node ids are export `skill` ids (research 0015, 4,914-node
  cross-check).

So: PoB node id -> export node with that `skill` -> its `id` -> the
`.build` passive id. It comes from the cached export AshLight already
fetches at build/opt-in time (decision 0009, `treedata.TreeCache`); no
bundled or hand-made table. Ascendancy: PoB's ascendancy name -> export
`classes[].ascendancies[]` id.

## 3. Path of Building's export (ideas only)

PoB-PoE2 PR #2432 "Add Path of Exile 2 BuildPlanner (.build) export",
merged into `dev` 2026-08-27
(https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/pull/2432 ,
accessed 2026-11-17). License: MIT
(https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/blob/dev/LICENSE.md ,
accessed 2026-11-17). No code was copied; ideas confirmed:

- PoB emits passive ids as "PassiveSkills.Id strings" and had to add a
  `stringId` to its tree data from the game files; AshLight gets the same
  ids from GGG's published export instead.
- Skill ids use PoB's Gems table key (`Metadata/Items/Gems/...`), not its
  `gameId`, because about 486 `gameId` values carry the singular
  `Metadata/Items/Gem/` typo (AshLight's pinned PoB checkout: 498). PoB's
  saved `gemId` attribute is that key.
- PoB writes the file into the game's planner folder itself. AshLight does
  NOT (adjudicator ruling 2026-11-17, decision 0034): download only.
- PoB exports one loadout per file and no level details.

## 4. What AshLight writes (decision 0034)

name, description, ascendancy (when mapped), passives (bare id strings),
skills (`id` + `support_skills` from enabled groups, only ids matching
`Metadata/Items/Gems/<word>`), inventory_slots (only the nine inventory
ids GGG shows; uniques by `unique_name`, other items as plain
`additional_text`). Anything that does not map is dropped and named in a
note on the dashboard; nothing is guessed.

## UNVERIFIED

- No AshLight-made `.build` has been loaded in game yet (needs the player;
  TC-BUILDFILE-LIVE check). Whether the game accepts placeholder or class
  start node ids, or meta gems in `skills`, is not documented; AshLight
  passes meta gems through as PoB has them.
- Off-hand / weapon swap / flask / charm inventory ids are not shown on
  GGG's page, so those slots are left out.

## Reverses if

A `.build` made this way fails to load in game; GGG's page names another
passive id source; the export drops its `id` field.

## Sources

- https://www.pathofexile.com/developer/docs/game (accessed 2026-11-17)
- https://www.pathofexile.com/developer/docs/data (accessed 2026-11-17, via research 0018)
- https://github.com/grindinggear/poe2-skilltree-export (accessed 2026-11-17; data.json read back)
- https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/pull/2432 (accessed 2026-11-17)
- https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/blob/dev/LICENSE.md (accessed 2026-11-17)
