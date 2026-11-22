# Copy sheet: itemcheck

Templates for the item check family: `server/al/text/itemcheck.py`
(`eval_card_text`, `stat_delta_text`, `_calc_text`) and the item check
card lines the dashboard prints. The rules that bind every template (one
event, one sentence; player text quoted; missing fields read honestly;
overlay register; line limits; plurals; time words; passive notifications;
an exact-output test per template) stay in design 0001 section 9
([0001-design-system.md](../0001-design-system.md)). This sheet holds the
templates only, moved word for word out of design 0001 (TEST-COPY-SHEETS);
a new or changed itemcheck template is edited here, not in design 0001.

## Templates

- item check (TC-EVAL-UI): overlay head `<Verdict> <+delta> vs <slot>`
  (empty slot: `<Verdict> <+delta> - <slot> empty`), item name, top
  counted stat (`+35 to maximum Life`; a flag mod `Gains: <mod>` /
  `Loses: <mod>`); dashboard `Upgrade: <n> points more than your <slot>
  (<name>).`, `Downgrade: <n> points less than ...`, `Sidegrade: about
  the same as your <slot> (<name>), <+n> points.`; errors `No build
  loaded`, `Not an item`, `Can't compare this` with the next step;
  a press that held a copied build (TC-PRESS-BUILD) is a status card:
  word and head `Build loaded` (edge tone note, never colour alone),
  line 2 `<ascendancy or class>, level <n>`, line 3 `Item checks use it
  now`, one dashboard note naming the build and character; a share link
  not loaded reads `Build not loaded` (word `Not checked`), `See the
  dashboard`, with the reason as the dashboard note
- item check scoring source (TC-DELTA, decision 0024, `_calc_text`):
  when Path of Building scored the item the overlay third line is `DPS
  <+pct>%, EHP <+pct>%` (a 0 base reads `unknown`) and the dashboard adds
  `Path of Building: this item in <slot> replaces <name>. DPS <+pct>%
  (from <old> to <new>). EHP <+pct>% (from <old> to <new>).` (`this item
  goes in the empty <slot> slot.` for an empty slot; `(the better of the
  <n> slots it fits)` after the slot when it fits several; MATH-COMPARE,
  decision 0032) and each other compared slot shows `Path of Building:
  DPS <+pct>%, EHP <+pct>%.` under its sentence; when PoB's numbers make
  no sense (MATH-DPS-SANITY) it adds `Scored with your stat weights. DPS
  and EHP are not shown because Path of Building's numbers for this item
  don't add up. Try the check again.` (implausible); when PoB says the
  main skill cannot use the checked weapon type (MATH-WEAPON-TYPE,
  decision 0032 amendment) the overlay head is `Downgrade - wrong weapon
  type`, the third line `Main skill can't use this weapon`, the dashboard
  adds `Your main skill can't use this weapon type, so this item is a
  downgrade for this build. Path of Building counts no damage from
  <skill> with it in <slot>.` (`that skill` without a name) and that
  slot's sentence reads `Downgrade: your main skill can't use this weapon
  type in <slot> (<name>).` (no name for an empty slot); otherwise the dashboard
  adds `Scored with your stat weights. To see DPS and EHP, turn on the
  optional Path of Building calc in AshLight's settings file.` (off) or
  `Scored with your stat weights. DPS and EHP are not shown because Path
  of Building could not be reached. Try the check again.` (failed); with
  PoB scoring, uncounted mods read `Not counted (the mod has no number):
  <mods>.`
- cached PoB weights (MATH-WEIGHTS, `CALC_CACHED_TEXT`): with the calc
  off or failing but weights Path of Building measured earlier for the
  same build, the dashboard adds `Scored with the stat weights Path of
  Building measured for this build earlier. DPS and EHP are not shown
  because the Path of Building calc is off.` (off) or `... because Path
  of Building could not be reached. Try the check again.` (failed) or
  `... because its numbers for this item don't add up. Try the check
  again.` (implausible); uncounted mods read `Not counted (Path of
  Building has not measured
  these for this build yet): <mods>.`
- roll potential (MATH-POTENTIAL-UI, web/tc.js `rollsText`): muted line
  on the item check card, `Rolls: worth <n> points now, <n> at the worst
  and <n> at the best, so <pct>% of the way up.`; at the top `Rolls:
  worth <n> points now, the best these rolls can be.`; hidden when there
  is no spread, the numbers are junk or the check failed.
