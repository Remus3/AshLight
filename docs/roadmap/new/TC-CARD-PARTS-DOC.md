- [ ] TC-CARD-PARTS-DOC (build) Item card words in design 0001 section 9 (TCP-8 of the TC-CARD-PARTS
  review): one line naming the mark words (Upgrade, Sidegrade, Downgrade, Not checked, Risky, No risky
  mods), the tones of cardparts.TONES and the rule that a part changes only WORD_KEYS, plus a doc
  test that the section 9 list matches the module. ACCEPT: python -m pytest -q
  tests/test_tc_cardparts.py passes with that doc test. ZERO-CLICK: No click: a doc and test edit
  the loop lands by itself. DEPENDS: TC-CARD-PARTS.
