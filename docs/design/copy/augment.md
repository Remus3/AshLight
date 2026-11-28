# Copy sheet: augment

Templates for the augment what-if (TC-AUGMENT-WHATIF, research
0064 G4, decision 0093): `server/al/text/augment.py` (`best_text`,
`none_text` and the constants beside them), used by the
item check card part server/al/theorycraft/cardparts/augment.py. The rules
that bind every template (one event, one sentence; missing fields read
honestly; line limits; plurals; an exact-output test per template) stay
in design 0001 section 9 ([0001-design-system.md](../0001-design-system.md)).
This sheet and server/al/text/augment.py are edited in both places
together, in one change: tests/test_tc_augment_whatif.py pins every
sentence below word for word.

## Templates

All are dashboard notes of the item check card (at most 20 words each,
cardparts NOTES_MAX); none reaches the 3-line overlay card, and none
names a price (decision 0017).

- Best augment (`best_text`): `Best augment for a free socket: <augment>,
  DPS <+pct>%, EHP <+pct>% (Path of Building).` The key word leads (rule
  7), so a long name still leaves the line at 20 words. The augment name is Path of
  Building's own (at most 40 characters). A zero change reads `0%`; a
  number Path of Building could not give reads `unknown`. "a free socket"
  because the game shows two equal runes as one line, so the socket is
  possible, never claimed.
- No augment helps (`none_text`): `Path of Building tried <n> augment(s)
  for a free socket; none raises DPS or EHP.`
- Credit, after any augment line (decision 0091 point 5; CREDIT_TEXT):
  `Augment data: Path of Building (MIT), community-written, may be out of
  date.`
- Calc failed during the stage (FAILED_TEXT): `Path of Building could not
  rank augments for this item.`
- Calc off, item with a possible free socket (NEEDS_CALC_TEXT; the card's
  calc sentence already names the Checks button): `Augment ranking for this
  item needs the Path of Building calc.`
