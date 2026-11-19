# 0052 - Worn-gear baseline: parsed mod lines in a bounded per-character file

Date: 2026-11-18. Source: package TC-WORN-STORE (wave 4); finding F-070
(docs/plan/02-findings.md, "Worn-gear baseline: 'I wear this'"); ruling
Q-26 (a) and (b) (docs/plan/02-findings.md, rulings; decision 0078).
Inputs: decisions 0003 (read policy), 0004 (theorycraft), 0032
(MATH-COMPARE slot choice), 0036 (bounded player-data files, .bak,
Clear run history), 0038 (character key), 0045 (BUILD-LIVE checked list).
This record covers the store and the baseline object
(server/al/theorycraft/worngear.py). The evaluate / LastEval wiring is
TC-WORN-BASELINE, the endpoint, switch and clear are TC-WORN-WIRE, the
optional key is TC-WORN-KEY.

## Decision

1. What is filed. The player can file an item they checked as the item
   they wear in its slot. The text is the one the item-check press
   already read (decision 0003); the store adds no read of its own and
   never reads the clipboard, the screen or the game log.
2. What is kept: per character and slot the item class, the rarity, the
   base type and the parsed mod lines (the stat text with roll ranges
   removed, and its section: explicit, implicit, rune, enchant and so on).
   Never the item name and never the raw item text (no item level,
   requirements, note, flavour or price note). A magic item whose base
   the parser could not split from its one name line keeps no base, since
   that line is the item's name.
3. Where and how much. One file, `<runtime>/worn_gear.json` (ops/runtime,
   gitignored; `worngear.default_path()` resolves it through
   server/al/paths.py). Bounds per decision 0036: at most 16 slots per
   character (only the PoB slot names of theorycraft/model.SLOTS, 15
   today), 12 characters (the one filed to least recently is dropped
   first), 40 mod lines of at most 200 characters each, 64-character
   names and fields, a 1 MB read cap. Written atomically with one `.bak`
   of the last good copy (jsonfile, F-014); a damaged main file is
   restored from a good .bak on load.
4. Damaged file. A damaged file with no good .bak reads as an empty set
   and is left as it is: only the next wear writes the file again, so a
   hand-broken file can still be looked at or fixed.
5. Clear. `WornGear.clear()` writes the empty set and removes the .bak;
   TC-WORN-WIRE calls it from Clear run history. On by default; the
   `worn_gear` switch is TC-WORN-WIRE's.
6. Characters. Keyed by the character name of decision 0038 (names stay
   on this computer); a wear made before the log names anyone goes to the
   unknown character `""` and is not moved later.
7. Slot choice for an item with more than one slot (rings, charms, a
   one-hand weapon of a dual wielder): an explicit slot wins (refused when
   the item cannot go there); else the slot the last item check of that
   character compared against, when that check's mod lines are the ones
   being filed (`note_compared`, kept in memory only); else a slot that
   already holds the same mod lines; else an empty slot; else the slot
   filed to longest ago. A one-hand weapon has Weapon 2 as a candidate
   only when the worn Weapon 2 (else the build's) holds a one-hand weapon
   (the dual-wield rule of decision 0032), or when the slot is named.
8. Baseline. `Baseline(store, character, build).equipped(slot)` answers
   from the worn item first and the PoB plan second; `source(slot)` says
   which ("worn", "plan" or None). A worn item comes back as a
   `model.Item` with no name whose text is rebuilt from the stored lines
   (explicit lines under an advanced `{ Modifier }` header, others with
   their `(tag)`), so the item parser gives back the same mod lines and
   stats; the evaluator needs no second code path.
9. The BUILD-LIVE checked list of decision 0045 stays memory-only (Q-26
   (b)); this file holds worn items only.

## Choices the package text left open (ruled by the builder)

- Rebuilt text instead of a second stats path. Alternatives: hand the
  evaluator stored stats directly. Why: evaluate.py and the PoB calc
  already take item text; one parse path keeps verdicts identical.
  Reverses if: a mod line shape fails to round-trip through the parser.
- Unknown character: no adoption of `""` wears by the first named
  character. Alternatives: merge them like the 0045 checked list. Why: a
  saved file outlives the session, and a merge could hand one
  character's gear to another. Reverses if: players file gear before the
  log names them and miss it.
- Slot ages by a per-character wear counter, not wall-clock time.
  Alternatives: timestamps. Why: deterministic, no clock in the file.
  Reverses if: the card needs to show when an item was filed.
- `remove(character, slot)` is offered for a player who takes an item
  off; nothing calls it yet. Reverses if: TC-WORN-WIRE has no use for it.

## Alternatives

- Off by default (Q-26 option): every player would have to find a switch
  before the compare works with no build; the file holds no name, no raw
  text and never leaves the PC. Rejected by ruling Q-26 (a).
- Memory only: a restart would lose every filed item, and one press per
  equipped item would be asked again after each start. Rejected.
- Persist the checked list too (Q-26 (b)): more item-derived data on disk
  for a list that rebuilds itself from presses. Rejected; it stays
  memory-only under decision 0045.
- Store the raw item text: simplest to rebuild, but it keeps names, notes
  and price notes. Rejected (F-070 acceptance: parsed mod lines only).

## Why

The item check today needs a PoB build to say anything about an item's
slot. A worn set filed by the player's own press lets it compare with no
build, and against what the player really wears when a build exists. A
bounded file of parsed lines, cleared with run history, is the smallest
record that survives a restart.

## Reverses if

The operator rules local item-derived files unwanted, or a stored
baseline is shown to leak names or paths.
