# Copy sheet: playernotes

Templates for the player notes family: `server/al/text/playernotes.py`
(`text_long`, `file_long`, `file_many`, `file_chars` and the constants
beside them), re-exported by server/al/playernotes.py under the same
names. The rules that bind every template (one event, one sentence;
player text quoted; missing fields read honestly; overlay register; line
limits; plurals; time words; passive notifications; an exact-output test
per template) stay in design 0001 section 9
([0001-design-system.md](../0001-design-system.md)). This sheet holds the
templates only, moved word for word out of server/al/playernotes.py
(PLAY-F-186A fix round, wave 32); a new or changed player notes template
is edited here, not in design 0001. This sheet and
server/al/text/playernotes.py are edited in both places together, in one
change: the exact-output test
`test_every_sentence_is_pinned_exactly` in tests/test_player_notes.py pins
every sentence below word for word against the module (PN-6, PLAY-F-186B).

## Templates

- Save refusals (PLAY-F-186A, decision 0074, PN-2; returned as the
  `error` of POST /api/player-note with status 400, each a sentence with
  a next step): `Your note is over <n> characters. Shorten it and save
  again.` (`text_long`, n = playernotes.MAX_NOTE), `Your note has a
  character AshLight can't keep. Use plain letters, digits and
  punctuation.` (TEXT_BAD), `AshLight doesn't know your character yet.
  Enter a zone, then save again.` (NO_CHARACTER), `AshLight doesn't know
  this zone yet. Enter a zone, then save again.` (NO_ZONE). A refused
  note is never cut or rewritten.
- Route refusals (PN-5, PLAY-F-186B; moved out of server/al/http.py,
  which imports them): `Save one zone at a time.` (ONE_ZONE, status 400,
  a query naming more than one zone) and `Your note is too long. Shorten
  it and save again.` (TOO_BIG, status 413, a body over the route's byte
  cap; nothing is read past the cap).
- notes file reasons (PN-1; the reason inside the hot reload note
  `<NAME> ... The last good copy stays in use.` of decision 0042, so they
  start lower case): `the file is not in AshLight's notes format`
  (FILE_FORMAT), `a note is not in the right form` (FILE_ROW), `two notes
  share one zone` (FILE_TWO), `a note is over <n> characters`
  (`file_long`), `the file holds more than <n> notes` (`file_many`, n =
  MAX_ZONES), `the file holds notes of more than <n> characters`
  (`file_chars`, n = MAX_CHARACTERS), `the file is too large` (FILE_BIG).
- Checks note name `Your notes` (NAME), and the fix appended after the
  held-copy note's last sentence (HELD_TAIL, hot reload's own wording):
  `Fix the file, or save a note to replace it.` (FIX_TAIL).
- Not in this module: the guide row lead `Your note: ` stays in
  server/al/playcards.py (NOTE_LEAD, on its EXEMPT entry) and the save
  failure `AshLight couldn't save your note. Try again.` in
  server/al/http.py (NOTE_SAVE_FAILED, on its EXEMPT entry). The note
  itself is the player's text: shown as text only, never reworded.
