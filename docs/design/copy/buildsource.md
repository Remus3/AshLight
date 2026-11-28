# Copy sheet: buildsource

Templates for the build choice: `server/al/text/buildsource.py`, used by
server/al/plug/buildsource.py (the refusals of POST /api/build-source)
and server/al/playview.py `build_view` (the Play build line, region B).
ACTIVE-BUILD-PICK, decision 0096. The rules that bind every template stay
in design 0001 section 9 ([0001-design-system.md](../0001-design-system.md)).
This sheet holds the templates only; a new or changed template is edited
here and in the module together, in one change. The exact-output test
`test_the_play_build_line_names_the_source_and_one_switch` in
tests/test_build_source.py pins the Play words.

The page's own words (web/kindler.js USE_WORDS, web/buildline.js
SWITCH_FAILED, web/panels/build.js SOURCE_WORDS "kindler") are listed
here too, so one sheet holds the whole choice.

## Templates

- Region B row 1 while a Kindler plan is in use:
  `Kindler: {tab label}, level {n}` (KINDLER_NAME, then the tab's label;
  `Kindler plan (generated)` when the label is empty), ellipsis as today.
- Region B row 2 (at most 36 characters): `Kindler plan (generated)`
  (SRC_KINDLER) while a Kindler plan is in use; `Pasted build`
  (SRC_PASTED) while the pasted build is in use and a Kindler plan could
  be; `Or paste a PoB code on Build.` (PASTE_TOO) while no build is
  loaded and the switch takes the paste button's place; otherwise
  today's words.
- Region B switch, one button in row 1: `Use Kindler plan` (USE_KINDLER)
  while the pasted build is in use and a Kindler tab has a result;
  `Use pasted build` (USE_PASTED) while a Kindler plan is in use and the
  character has a pasted build. Hidden when there is nothing to switch to.
- Refusals: `AshLight couldn't save your build choice.` (SAVE_FAILED),
  `That choice isn't available. Pick it again.` (BAD),
  `Play a character first.` (NO_CHARACTER),
  `Generate this Kindler plan first.` (NO_RESULT). With the page's lead
  each line stays at 12 words or fewer (design 0001 N6).
- Reason words (BUILD-SWITCH-COPY, REASONS): every refusal of POST
  /api/build-source is `{"error": <sentence>, "reason": <word>}` with one
  fixed word: `bad` (BAD), `no_character` (NO_CHARACTER), `no_result`
  (NO_RESULT). Never a path, a name or free text. The Play switch says
  `The build didn't switch. ` followed by that sentence, e.g.
  `The build didn't switch. Play a character first.`; an unknown word, no answer or no reach keeps
  `The build didn't switch. Try again.`
- Page words: `Use this plan for Play` (the chip on the Kindler plan
  card), `Use pasted build for Play` (the chip on the Pasted build's Build
  card), `Not saved. Try again.`,
  `The build didn't switch. Try again.` (the switch failed for no known
  reason), `The build didn't switch. ` (web/buildline.js SWITCH_REFUSED,
  the lead before a reason's sentence), and the Build
  card's source line `Kindler plan (generated)`.
