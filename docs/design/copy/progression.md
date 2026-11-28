# Copy sheet: Progression

Words of the Progression view (PROGRESSION-VIEW, decision 0092), word for
word: the server-composed words of `server/al/text/progression.py` and the
page's own headings, labels and legend in `web/panels/progression.js`
(WORDS) and `web/panels/tree.js` (hover line words). Rules that bind every
template stay in design 0001 section 9. No word claims the player took a
passive, slotted a gem, finished a trial or picked up a book. Tests:
tests/test_progression.py (test_the_words_are_pinned_exactly,
test_the_copy_sheet_lists_every_template).

## Source line (server)

- `From your pasted build`
- `From your pasted build, tree {title}` (a build with more than one tree)
- `From Kindler tab {label}`
- `No build yet. Paste one on Build and items.`
- `Passive tree data isn't on this computer yet. Turn on web data in Settings, Reading and web data.`
- `This build's passives don't match the saved tree data. Paste the build again.`

## Next-up strip (server; at most 3 steps of 52 characters)

- `Take next: {names}` and `Take next (+{n}): {names}`; a name next to
  itself is said once with its count, `Attribute (2)`.
- `Next tree: {n} more {passives}` (passive / passives).
- `{kind} ready: {name}` and `{kind} at level {level}: {name}`, kind `Gem`
  or `Support`.
- `After ascendancy trial {trial}: {names}` and `After ascendancy trial {trial} (+{n}): {names}`.
- `Here: {text}` (the guide's own book line of this zone).
- Empty: `Nothing new is due at this level.`

## Point lines (server)

- `Passives: {have} planned by level {level}`
- `Passives: {have} in this tree`
- `{budget} {points} at level {level}, not counting books` (left out for a Kindler plan when it equals the planned count)
- `Ascendancy: {have} planned, {due} after the next trial`
- `Ascendancy: {have} planned, {later} for later trials`
- `Ascendancy: {have} planned`
- `Spirit: {spirit} ({free} free), from Path of Building`
- `Spirit: {spirit}, from Path of Building`
- `Weapon set points: {one} on set 1, {two} on set 2`
- `The guide lists {n} {books} of 2 points in {act}: {zones}`
- `The guide lists no point books in {act}.`
- `Point books show once AshLight knows your act.`
- `level unknown`

## Gem rows (server)

- Timing: `ready`, `level {level}`, `unchecked`; with the PoB gem level
  first, `gem level {level}`.
- Supports: `with {names}`, each `<name> (<timing>)` or `<name> (doesn't fit)`
  (`doesn't fit`: Path of Building's own KINDLER-SUPPORT-FIT answer);
  none: `no supports linked`.

## Play, region I (page)

- Head: `Next up`, then `Level {n}` or `Level unknown`. The steps are 20 px rows. The region's screen-reader heading reads `Next up` while the view shows, else `Item check`.
- Legend: `Filled: planned. Dashed: next. Thin: later.`
- Button: `Item check` (shows the item card again).
- Tree label: `Passive tree`.

## Build and items card (page)

- Builds row button: `Progression` (aria-pressed while open).
- Heading `Progression`; the source line and ` - Level {n}` beside it;
  button `Back to build`.
- Column headings: `Next up`, `Skills and supports`, `Ascendancy`
  (`Ascendancy: {name}` when known), `Points`.
- Hover line: `Hover a node to read it.`; empty tree: `No tree to draw
  yet.`; a node reads `<name> (<state>): <first stat>`, the state one of
  `planned by this level`, `take next`, `planned later`, `not in the
  plan`; a nameless node reads its kind: `Passive`, `Notable passive`,
  `Keystone`, `Jewel socket`, `Class start`, `Ascendancy start`.
- Legend: `Filled: planned by this level. Dashed ring: take next. Thin
  ring: later. Dot: not in the plan. Grey lines: context. Outer ring: new
  since the last change.` (14 px, muted)
- More rows (skills, then points, when the column is full): `+{n} more`.
- Tree labels: `Passive tree`, `Ascendancy tree`.
