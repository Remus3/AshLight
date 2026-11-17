# 0007 - TC-CODE: PoB2 share-code codec, build model, paste API

Date: 2026-11-16. Trigger: ROADMAP row TC-CODE (decision 0004 phase C).
Forks ruled by an adjudicator agent the same day; rulings recorded below.

## Decision

Code: `server/al/theorycraft/` (stdlib only).
- `codec.py`: URL-safe base64 + deflate. Encode writes zlib framing
  (level 9; shared codes start "eN" = a 0x78 zlib header). Decode accepts
  either base64 alphabet, whitespace and missing padding, and auto-detects
  zlib, raw deflate and gzip. Input capped at 2 MB, inflated XML at 8 MB
  (incremental, bomb-safe). Round trip is byte-exact on the XML; non-UTF-8
  bytes ride through as surrogate escapes.
- `model.py`: read-only typed view (class, ascendancy, level, tree specs
  with nodes / URL / jewel sockets, items by id and gear by slot of the
  active item set, skill groups and gems of the active skill set, PoB's
  saved PlayerStat values, notes). The Build keeps `raw_xml`, so
  `to_code()` is lossless. DTDs / entities are refused before parsing.
- `store.py`: the last good code in `ops/runtime/build/last-code.txt`,
  reloaded when the core starts; a bad paste never replaces a good build.
- API (token-gated): `POST /api/build-code` (JSON {"code"}; own 256 KB body
  limit, the global 4 KB limit unchanged) and `GET /api/build`.

Rulings:
- F1 (a) Fixtures are synthetic (`tests/tc_fixtures.py`), produced by our
  own encoder from hand-written XML. Alternatives: (b) a web-fetched public
  code; (c) block. Why: no PoB2 install, licensing of user builds unclear,
  no network in tests. Follow-up row TC-CODE-REAL confirms the framing on a
  real PoB2 v0.23.1 export. Reverses if a real export fails to decode.
- F2 (a) A share URL is recognized and answered with "share URL fetch is
  not supported yet" (HTTP 422). Alternative: (b) fetch now. Why: fetching
  a pasted URL is network access needing its own policy, User-Agent and
  SSRF review. Follow-up row TC-URL. Reverses if the operator orders TC-URL.
- F3 (a) The API ships now with small additive edits to `core.py` and
  `http.py`. Alternative: (b) API in a later row. Why: usable and testable
  now. Reverses if the store conflicts with concurrent core work (then ship
  codec and model only).
- F4 (a) `codec.looks_like_build_code(text)` is exposed for the clipboard
  hotkey row (PRICE-1 owns the per-press read, decision 0003); no
  clipboard code here. Alternative: (b) read the clipboard now. Reverses
  when the clipboard row lands and wires it.
- F5 Lossless = decode(encode(xml)) == xml and to_code(parse(code)) decodes
  to the identical XML; the typed model is a view only. Alternative: a
  writable model. Why: lossless without a full schema. Reverses when a
  later TC-* row needs to edit builds.

## License note

Format knowledge comes from research 0010 section 1 (PoB2 `ImportTab.lua`
read for the format only; PoB2 is MIT, "Copyright (c) 2016 David Gowor")
and from the publicly observed element / attribute names of PoB build XML.
No PoB code, data or real user build is copied; every fixture value is
invented.

## Reverses if

A real PoB2 export uses a framing or root element the decoder rejects
(TC-CODE-REAL), or PoB2 changes its share-code format.
