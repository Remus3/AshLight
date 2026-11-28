# Copy sheet: gemadvice

Templates of the gem advice family: `server/al/text/gemadvice.py`
(`cut_notes`, `join`, `plural` and the constants beside them), used by
the uncut gem card part `server/al/theorycraft/cardparts/uncut.py`
(TC-UNCUT-GEM, decision 0094). The rules that bind every template stay in
design 0001 section 9 ([0001-design-system.md](../0001-design-system.md)).
This sheet holds the templates only; a new or changed template is edited
here and in the module together, in one change. The exact-output tests in
tests/test_tc_uncut_gem.py (`test_notes_are_pinned_exactly`,
`test_the_copy_sheet_lists_every_template`) pin every template below.

No line says the player owns, holds or socketed a gem: the names are the
build's plan (the pasted build, or the Kindler stage shown), the levels
and tiers the cached skill gem list's. Names join as `A`, `A and B`, `A,
B and C`; a non-ASCII character in a name is dropped.

## Uncut gem press (dashboard notes, at most 20 words each)

- `A level {level} {kind} cut can make your build's {names}.` (kind
  `skill`, `support` or `spirit`)
- `A level {level} {kind} cut can make your build's {names} and {n} more.`
  (names joined with ", " and cut until the sentence fits 20 words)
- `A level {level} {kind} cut can make {n} {gems} of your build.` (when no
  name fits; `gem` for 1, else `gems`)
- `No {kind} gem of your build needs a level {level} cut.`
- `The skill gem list gives no tier for {names}, so check the cut in game.`
  (a second note for build gems the list gives no tier; never claimed
  makeable)
- `The skill gem list gives no tier for {n} {gems}, so check the cut in game.`
