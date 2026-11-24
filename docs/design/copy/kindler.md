# Copy sheet: Kindler

Words of the Kindler build generator card and plan card, word for word as
`web/kindler.js` (and the sub-tab row of `web/index.html`) has them, and
the server words of `server/al/text/kindler.py` (last section).
Decision 0081 (KINDLER-UI-TABS, KINDLER-UI-RESULT; design finding KT-8,
wave 42). Rules that bind every template (one event, one sentence; a
refusal gives a next step; text through textContent only) stay in design
0001 section 9 ([0001-design-system.md](../0001-design-system.md)). A new
or changed Kindler word is edited here and in web/kindler.js in one
change. Tests: tests/test_kindler_tabs_ui.py, tests/test_ux_review.py.

## Sub-tab row (web/index.html)

- Group label: `Builds`.
- Fixed sub-tab: `Pasted build`.
- Add button: `New Kindler tab` (aria-disabled while 6 tabs exist).
- Full note (the store's `full_text`, else this fallback): `You can keep 6
  Kindler tabs. Close one to add another.`
- A tab with no usable label reads `Kindler`.

## Editor card

- Heading: the tab's name (default `Kindler`); muted line beside it:
  `Kindler: build generator`.
- Tool buttons: `Move left`, `Move right`, `Rename`, `Close tab`.
- Rename: label `Name`, buttons `Save name` and `Cancel`, hint `Up to 32
  characters. Empty keeps the usual name.`
- Close confirm: question `Close <name>?`, buttons `Close` and `Keep`.
- Class: label `Class`, first option `Any class`, then Druid, Huntress,
  Mercenary, Monk, Ranger, Sorceress, Warrior, Witch.
- League: label `League`, placeholder `Standard`; line `Not sure sets no
  limit. The league changes only prices and trade links.`
- Toggle group names (legends): `Melee`, `Spells`, `Minions`, `Bow`,
  `Critical hits`, `Defence`. Choices for the first five: `Yes`, `No`,
  `Not sure`. Defence choices: `Life`, `Energy shield`, `Life and
  shield`, `Not sure`.
- Button: `Generate`.

## Status line (beside Generate)

- `Generating. Path of Building scores up to 12 builds, about a minute at
  most.` (working)
- `Another Kindler tab is generating. Press Generate again when it is
  done.` (busy)
- `Still generating. The result shows here when it is done.` (slow)
- `Not saved. Try again.` (not saved)
- `Can't reach AshLight - is it running?` (no reach)
- A server refusal shows the answer's own `error` text.

## Result line

- None yet: `No result yet. Pick what you want, then press Generate.`
- No match: `No build fits these choices. Set one to Not sure and press
  Generate again.`
- Scored: `<label>: <dps> DPS, <ehp> EHP. Scored by Path of Building.`
- Not scored: `<label>: <reason>.` with the reason `not scored (calc off).
  Turn the calc on in Settings, Checks` (calc off), `not scored. The
  passive tree data is still loading` (no tree), `not scored. Path of
  Building could not score these` (no score), else `not scored`.
- Partial suffix: ` Time ran out, so this is the best of the builds
  scored so far.`
- Announcement (polite line, only while the Build tab shows): `<label>:
  result ready.`
- Out of date: badge `Out of date`, with `Your choices changed. Press
  Generate to update.`

## Plan card

- Heading `Plan` (empty until the plan loads); muted line `<name>, <ascendancy>` (ascendancy when
  known).
- Follow chip: `Follow Play guidance`; why: `Shows the stage that matches
  where you are.` (on) or `Pick a stage with Previous stage and Next
  stage.` (off).
- Empty: `Reading the plan.`; `No plan for this result. Press Generate to
  make a new one.`; `Can't read the plan right now. AshLight tries again
  when something changes.`
- Stage: `Stage <i> of <n>: <label>`; buttons `Previous stage`, `Next
  stage`; badge `Now`; why `This stage matches <your zone | your act |
  your area level | your level | where you are>.`
- Trigger line: `For character level <min> to <max>`, `For area level
  <min> to <max>`, `For Act <n>` (no trigger line for a zone stage).
- Pages (group label `Plan parts`): `Skills and gems`, `Passives`, `Item
  focus`. Part buttons `Previous part`, `Next part`; label `Part <i> of
  <n>` (blank with one part).
- Skills page: heads `Skills`, `Gem changes`; ` Links: ` with ` (not used
  by this skill)`; `No skills planned for this stage.`; `No gem changes at
  this stage.`; steps `Swap <gem> for <gem>`, `Drop <gem>`, `Pick up
  <gem>`; credit `Path of Building says which links a skill uses.`
- Passives page: `<n> passive to take, in this order.` or `<n> passives to
  take, in this order.`; ` <p> of <b> points planned so far.`; `No
  passives added at this stage.`; head `Ascendancy`; `After your <first
  to eighth> Ascendancy trial:` or `After an Ascendancy trial:`; unknown
  node `Unnamed passive`.
- Item focus page: `No item focus for this stage.`; notes `Stats ranked by
  Path of Building for this build.`, `AshLight's own order for now. Path
  of Building is ranking these stats.`, `AshLight's own order (calc off).
  Turn the calc on in Settings, Checks.`, `AshLight's own order. Path of
  Building could not rank these stats.`, `AshLight's own order. The item
  data is still loading.`, `AshLight's own order. The passive tree data is
  still loading.`

## Server words (server/al/text/kindler.py)

KINDLER-WEAPON-BASE. Imported by server/al/theorycraft/archetypes.py and
server/al/theorycraft/kindler.py; pinned by tests/test_kindler_data.py
(test_server_words_are_pinned_exactly).

- Hot reload names (decision 0042): `Kindler templates`, `Passive tree
  (Kindler)`, `Gems snapshot`, `Weapon bases (Kindler)`; the engine's own
  copies `Kindler templates (engine)`, `Passive tree (Kindler engine)`,
  `Gems snapshot (Kindler engine)`, `Weapon bases (Kindler engine)`. Only
  `Kindler templates` is in the core's Checks registry, so it is the one
  a player can see (a Checks note when the table fails to load). Every
  other watch is made with registry=False and its name is never shown;
  the suffixes only tell the copies apart in a log or a test.
- Weapon kinds an attack template's base may be, the item class names of
  the base_items snapshot word for word (so a base matches its entry):
  melee `One Hand Mace`, `Two Hand Mace`, `One Hand Sword`, `Two Hand
  Sword`, `One Hand Axe`, `Two Hand Axe`, `Dagger`, `Claw`, `Spear`,
  `Flail`, `Warstaff`; ranged `Bow`, `Crossbow`; the bow toggle takes
  `Bow` only.
- Resolve note for a weapon base the snapshot does not name: `<template
  id>: weapon <base> is not a weapon base in the base_items snapshot; not
  composed`. It shows only in author and test output and never reaches a
  card, Checks or an API answer. resolve() notes stay in the resolved view;
  the engine's result, the plan and the Generate route never carry them.
  tests/test_kindler_data.py (test_weapon_note_never_reaches_a_player)
  pins this.
- The validator check() (archetypes.py) writes its problems and notes
  inline. They are for tests and the template package only, because
  check() is never called at run time, so they are not player words and
  are not listed here.
