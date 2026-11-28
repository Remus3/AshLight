# Copy sheet: iteminfo

Templates for the item info family: `server/al/text/iteminfo.py`
(`name_long` and the constants beside it), imported by
server/al/iteminfo.py (the cache-only lookup) and
server/al/plug/iteminfo.py (GET /api/iteminfo). The rules that bind every
template (one event, one sentence; missing fields read honestly; an
exact-output test per template) stay in design 0001 section 9
([0001-design-system.md](../0001-design-system.md)). This sheet holds the
templates only, moved word for word out of server/al/iteminfo.py
(ITEM-INFO-CORE fix round, wave 38; tests/test_structure.py rule 2); a
new or changed item info template is edited here and in the module in
one change. tests/test_iteminfo.py
(`test_every_sentence_is_pinned_exactly`) pins every sentence below.

## Templates

- Name refusals (returned as the `error` of GET /api/iteminfo with
  status 400, each with a next step): `AshLight needs one item name. Open
  the item again.` (NO_NAME: no name or an empty one), `Look up one item
  at a time.` (MANY_NAMES: more than one name), `An item name is at most <n>
  characters. Use the name as the game shows it.` (`name_long`, n =
  iteminfo.NAME_MAX, 120), `An item name is one line of text. Use the name
  as the game shows it.` (ONE_LINE: a control character in the name),
  `A gem level is a whole number from 1 to <n>. Open the gem again.`
  (`bad_level`, n = gemdetail.LEVEL_MAX, 40: a level query that is not
  one whole number from 1 to n; ITEM-INFO-GEM-DETAIL). An API-only
  refusal: the page only asks for a level its button holds (1 to n), so
  the popover never shows it.
- Market credit (decision 0083 point 1): `Prices: poe.ninja` (CREDIT, the
  same words as ninja.SHORT_CREDIT), shown with the cache age.
- Rarity word: `Unique` (UNIQUE), given only to items in the cached
  uniques list; currency and bases get no rarity (decision 0083).
- Hot reload names of the two cached tables (decision 0042):
  `Item base list` (BASES_NAME) and `Unique item list`
  (UNIQUES_NAME). The lookup keeps both out of the Checks registry, so
  today neither name is shown; the core's own base list watch reports a
  bad base_items file.
- Not in this module: the popover's own labels, the poe2db line and the
  credit line layout belong to ITEM-INFO-UI (web/iteminfo.js), and so do
  the gem rows (Gem, Tags, Gem level, Cost, Reservation, Cast time,
  Cooldown, Cost multiplier) and the "At gem level <n>" / "Effect"
  section titles of ITEM-INFO-GEM-DETAIL (with more than one stat set a
  title adds ": <set label>", else ": Set <n>"); a gem's stat lines are the
  repoe-fork export's own words. Field
  values (descriptions, directions, flavour text, names) are the sources'
  own text, shown as text only, never reworded beyond reading repoe-fork
  markup such as `[ItemRarity|Rare]` as its shown words.
