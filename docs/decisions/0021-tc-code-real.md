# 0021 - TC-CODE-REAL: real PoB2 export check, fixture sources, round-trip scope

Date: 2026-11-17. Trigger: ROADMAP row TC-CODE-REAL (follow-up of decision
0007 F1). Ruled by the build lane itself (CLAUDE.md FLEET item 1).

## Decision

`tests/test_tc_code_real.py` runs the acceptance checks on every real PoB2
v0.23.1 share code it finds and skips when there is none:
- sources: `tests/fixtures/pob2_real/*.txt` (tracked, ONLY with the build
  owner's permission recorded in that folder's README), the gitignored
  `ops/runtime/tc_real/*.txt`, and the file named by env `AL_TC_REAL_CODE`;
- framing: zlib (research 0010 left it UNVERIFIED); root element:
  `PathOfBuilding2`; parse: class, level 1-100, an active tree spec;
- PlayerStat names: Life, Mana and the four resistances present, and at
  least that many of the dashboard's KEY_STATS (read from `web/tc.js`);
- round trip: the decoded XML bytes survive `codec.encode` and
  `Build.to_code()` byte for byte, and our own code is stable.

Rulings:
- R1 No real code was available to this lane (no PoB2 install, no operator
  code, no network in tests). The row's ACCEPT is met by the skip-when-absent
  test plus harness tests on synthetic PoB-shaped codes that prove each
  check passes and fails as intended. Alternatives: (b) fetch a public build
  code from the web - rejected: owner permission unknown, network in tests;
  (c) block the row - rejected: the test makes the real check zero-click the
  moment a code is dropped in. Reverses if: a real code is supplied and a
  check fails (then decision 0007's reverse clause fires and the codec or
  model is fixed).
- R2 "Byte-exact round trip" is the XML (decision 0007 F5), not the share
  code string. The code string is also compared: the decoded XML is
  re-compressed at each zlib level in the bucket the code's header names
  (RFC 1950 FLEVEL); a match records the level, a mismatch makes the test
  xfail, not fail. Alternatives: (b) assert the code string strictly -
  rejected: PoB's `Deflate` (SimpleGraphic) may use another zlib build or
  settings, which no decoder controls and which loses nothing; (c) keep the
  pasted code and return it verbatim from `to_code()` - deferred, no row
  needs the original string yet. Reverses if: a feature needs the exact
  pasted string (then the store / Build keeps it).
- R3 The "eN" prefix is not asserted: it only holds for zlib levels 7-9;
  level 6 writes "eJ". Decision 0007 encodes at level 9 and decodes any
  level. Reverses if: never (informational).

## Reverses if

See R1-R3.
