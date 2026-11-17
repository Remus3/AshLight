# 0001 - Name: AshLight (code AL)

Date: 2026-11-16. Decided by: adjudicator agent (distinct from the producer),
then the operator's spelling correction the same day.

## Decision

The app is named **AshLight**. Fleet short code **AL**. Repo root
the repo root on the operator machine, hand-off `AL-NEXT-SESSION.txt` (the siblings name the hand-off
after their short code: EW-, HOM-, RC-, MAIN-NEXT-SESSION.txt).

## Evidence

`docs/decisions/name-check-2026-11-16.md` (2026-11-16): npm, PyPI and
crates.io have no `ashlight` package (404). GitHub has about 32 small,
unrelated repos with "ashlight" in the name (0 to 4 stars: an ASCII dungeon
crawler, an ESPHome lamp, a Metroidvania), none a Path of Exile tool. A search
for "ashlight path of exile" returned nothing.

## Alternatives

- Vigilmark - cleanest fallback (npm / PyPI free, only empty GitHub repos).
- Runelight - rejected: real RuneScape projects, confusable with RuneLite.
- Waystone Lantern - rejected: "Waystone" is a PoE2 in-game term (trademark
  confusion risk).

## Why

- The operator's test is a REAL collision (a GitHub repo, npm / PyPI package or
  PoE tool already called Ashlight doing this job). Same-name hobby repos in an
  unrelated domain under other owners do not block a repo under the operator's
  own account.
- The name carries no GGG trademark.

## Reverses if

A verified PoE/PoE2 tool, or an npm/PyPI package named AshLight doing this job,
appears, or "Ashlight" is confirmed as a GGG proper noun (manual poe2wiki check
before publishing is ROADMAP row PUB-NAME). Then switch to Vigilmark.

PUB-NAME check done 2026-11-17: poe2wiki.net and poewiki.net have 0
search hits and no page for "Ashlight" / "Ash Light" (research 0009,
"Re-check 2026-11-17"). Not a GGG proper noun; the name stands.
