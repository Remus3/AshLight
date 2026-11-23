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
  (empty slot: `<Verdict> <+delta> - <slot> empty`; over 26 characters
  the verdict and the slot name stay and the number gives way (CL-2): it
  rounds to a whole one, then leaves the head (`<Verdict> vs <slot>`,
  `<Verdict>: <slot> empty`) and the dashboard sentence carries it; only
  a slot too long beside the verdict drops: `<Verdict> <+delta> - slot
  empty`, `<Verdict>: slot empty`, then `<Verdict> <+delta>`; examples
  `Upgrade +5 - Gloves empty`, `Upgrade: Body Armour empty`;
  CARD-LINE-LIMIT-COPY), item name, top
  counted stat (`+35 to maximum Life`; a flag mod `Gains: <mod>` /
  `Loses: <mod>`); dashboard `Upgrade: <n> points more than your <slot>
  (<name>).`, `Downgrade: <n> points less than ...`, `Sidegrade: about
  the same as your <slot> (<name>), <+n> points.`; errors `No build
  loaded`, `Not an item`, `Can't compare this` with the next step;
  a press that held no item (`Not an item`, `Copy the item first`)
  names no item: the item line is empty, never `Unnamed item`, the
  price card head is `Price check`, and the Play card's price row reads
  `No price for this check` instead of repeating the card's words
  (RUN-NO-DEAD-ENDS, research 0042 F20 d);
  a press that held a copied build (TC-PRESS-BUILD) is a status card:
  word and head `Build loaded` (edge tone note, never colour alone),
  line 2 `<ascendancy or class>, level <n>`, line 3 `Item checks use it
  now`, one dashboard note naming the build and character; a share link
  not loaded reads `Build not loaded` (word `Not checked`), `See the
  dashboard`, with the reason as the dashboard note; the error line 3s
  are `Paste a build first` (no build), `Copy an item in game first`
  (not an item) and `Only gear is compared`; an unidentified item's
  third line is `Mods hidden: identify it` (CARD-LINE-LIMIT-COPY)
- dashboard stat rows (Last item card, web/tc.js `statRowText`; CL-3):
  `<slot>: <mod text> (<points>)`, e.g. `Ring: +35 to maximum Life (+35
  points)` or `Ring: +Some stat 4 (not counted)` (`not counted` is the
  honest word for a mod AshLight cannot weigh); the points sit in
  brackets like the sentence's `(<+n> points)`, never run on from the mod
  text after a bare space; with no points the row is `<slot>: <mod text>`
- keep or vendor (TC-CAMPAIGN-KEEP, decision 0057, cardparts/keep.py):
  with no build the overlay head is `<Keep|Vendor> - <k> of <n> met, Lv
  <lv>` or, for a missed must check, `Vendor - no <label>, Lv <lv>`; over
  26 characters `, Lv <lv>` drops (`Vendor - no move speed`), so the head
  never clips and a count never reads like a pass (CARD-LINE-LIMIT-COPY)
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
  decision 0032 amendment) the overlay head is `Downgrade - wrong
  weapon`, the third line `Main skill can't use it` (both within 26
  characters, CARD-LINE-LIMIT-COPY2), the dashboard
  adds `Your main skill can't use this weapon type, so this item is a
  downgrade for this build. Path of Building counts no damage from
  <skill> with it in <slot>.` (`that skill` without a name) and that
  slot's sentence reads `Downgrade: your main skill can't use this weapon
  type in <slot> (<name>).` (no name for an empty slot); otherwise the dashboard
  adds `Scored with your stat weights. To see DPS and EHP, press "Set up
  the calc" under Settings, Checks in the AshLight window.` (off;
  RUN-NO-DEAD-ENDS: the Checks row's button, never a file) or
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
