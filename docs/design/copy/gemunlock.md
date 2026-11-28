# Copy sheet: gemunlock

Templates for the gem unlock card, its event row and its next-up steps:
`server/al/text/gemunlock.py` (`card_lines`, `row_text`, `step_lines`
and the constants beside them), used by server/al/overlayview.py (the
card holder "gem"), server/al/state.py (the recent events row, type
`gem_unlock`) and server/al/gemunlock.py `next_steps` (the Progression
next-up source, decision 0092 hook). TC-GEM-UNLOCK, research 0064 G3,
decision 0095. The rules that bind every template stay in design 0001
section 9 ([0001-design-system.md](../0001-design-system.md)). This sheet
holds the templates only; a new or changed template is edited here and in
the module together, in one change. The exact-output tests
`test_card_and_row_words_fit_and_name_every_gem`,
`test_step_words_are_pinned_and_fit_52` and
`test_the_copy_sheet_lists_every_template` in tests/test_tc_gem_unlock.py
pin every template below.

No line says the player owns or socketed a gem: the names are the pasted
build's plan, the level the cached skill gem list's.

## Templates

- Card line 1 (the answer first, at most 26 characters):
  `Gem usable at level {level}` (HEAD_ONE, one gem) and
  `{n} gems usable at level {level}` (HEAD_MANY, two or more), or
  `{n} gems usable, Lv {level}` (HEAD_MANY_SHORT) when HEAD_MANY would
  pass 26 characters, so the level never clips.
- Card lines 2 and 3: the first gem's name, then the second gem's name
  for two gems, or `and {n} more` (MORE_LINE, n = the other gems) for
  three or more; one gem leaves line 3 empty. Gem names are the build's
  own, non-ASCII characters dropped, clipped with "..." at 26 characters.
- Recent events row, the card's dashboard twin, one sentence subject
  first: `Level {level} makes {names} usable` (ROW_TEXT). Names (each
  clipped at 26 characters) join with " and "; past ROW_NAMES (2) names
  the row names two and ends `and <n> more`.
- Progression next-up steps (at most STEPS_MAX, 2, each at most 52
  characters, the name clipped with "..."): `{kind} usable now: {name}`
  (STEP_ONE) and, on the last step when more gems are usable,
  `{kind} usable now (+{n}): {name}` (STEP_MORE); kind `Gem` (GEM_WORD)
  or `Support` (SUPPORT_WORD).
