# 0030 - Player helpers: waystone check, search strings, zone notes

Date: 2026-11-17. Lane AREA-UTIL batch 5. Inputs: CLAUDE.md "Game ToS
floor", decisions 0003 (read policy), 0004 (theorycraft scope), 0009
(data license), 0014 (clipboard write on the player's click), research
0022 (loot filters) and 0023 (player value gaps), ROADMAP rows
UTIL-WAYSTONE, UTIL-SEARCHSTR, UX-ZONE-NOTES.

## Decision

1. UTIL-WAYSTONE. The existing item-check press (one clipboard read per
   manual press, decision 0003) also recognises a waystone (item class
   `Waystones` or a `Waystone` base) and flags its mods that are risky for
   the loaded Path of Building build. Rules are an AshLight-authored,
   data-driven table (`server/al/theorycraft/waystone.py` RULES: id,
   regex on the mod line, condition, label, short overlay word, search
   term). Conditions read only the build's PoB PlayerStat numbers
   (FireResist, ColdResist, LightningResist, ChaosResist, Life,
   EnergyShield): an element the build resists below 75% (chaos below 0%
   for poison), a pool that is at least half of life + energy shield, or
   always. A missing number is unknown and unknown is risky. The result
   rides the eval card (`eval.waystone`); the overlay shows "Risky for
   this build" plus short words within the 34-character card line; the
   dashboard says the full sentence. No new read, no new button.
2. UTIL-SEARCHSTR. The core builds stash / vendor search strings from the
   loaded build (resistances it still needs, life or energy shield,
   movement speed, its own gear bases) and a waystone "avoid" string from
   the same RULES, each at most 250 characters (the reported search box
   limit, unverified in game, research 0023), dropping whole terms, never
   cutting one. The dashboard shows them with a Copy button that writes
   the clipboard only on the player's click (decision 0014). AshLight
   never types into the game.
3. UX-ZONE-NOTES. One short AshLight-written note per campaign zone (Acts
   1-4 and Interludes), kept in a tracked data file written by us
   (`server/al/data/zone_notes.json`), keyed by act and zone name, with an
   act default so every campaign area id has a note. Shown in the
   dashboard act card on zone entry; no wiki or poe2db prose (decision
   0009). Notes are general guidance and not yet checked in play.

## Alternatives

- Waystone: a third-party mod list (poe2.re, Exile-UI): rejected, copied
  data and licence work for little gain; flagging every mod without the
  build: rejected, noise; a separate waystone hotkey: rejected, the
  existing press is enough (ZERO-CLICK).
- Search strings: typing the string into the game: forbidden (no input to
  the game). Auto-copy when the build loads: rejected, decision 0014 limits
  clipboard writes to the player's click.
- Zone notes: area-id keyed notes only: rejected for now, the ids of Acts
  3-4 and the Interludes are not seen live yet; names come from the same
  log line and the act default covers any id.

## Why

All three use inputs AshLight already has (the per-press item text, the
loaded build, the tailed area line) and add no read, no write into game
folders and no input to the game.

## Reverses if

GGG's overlay or tool rules change for item text or clipboard use; the
search box rejects these strings or its limit is not 250 characters (then
the cap changes, not the design); a zone note is found copied from a
licensed source (then it is rewritten); a real waystone shape is not
recognised (then the parser, not the rule table, changes).
