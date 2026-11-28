# 0094 - Uncut gem advice on the item-check press (TC-UNCUT-GEM)

Date: 2026-11-28. Row: TC-UNCUT-GEM (research 0064 G2). Reuses the loop's
WIP (keep ref of the row, filed there as 0088; that number was taken on
main by another decision, so this record is 0094).

## Decision

1. A card part (`server/al/theorycraft/cardparts/uncut.py`) over the one
   gem lookup helper `server/al/theorycraft/gemadvice.py` answers on the
   existing item-check press when the pressed text is an Uncut Skill,
   Support or Spirit Gem of level N. It names the build's gems of that
   kind that a level N cut can make and that the build does not show as
   socketed at that level. The build is the pasted PoB build, else the
   Kindler stage the Progression view shows (decision 0092 model, ctx key
   `plan_gems` from `server/al/plug/gemadvice.py`; no Kindler run and no
   calc is started). No build or no gems snapshot adds nothing.
2. Words are dashboard notes only (`server/al/text/gemadvice.py`, copy
   sheet `docs/design/copy/gemadvice.md`, at most 20 words each); the
   verdict word, tone and head stay as they were, so no design 0001
   section 9 word is added. No line says the player owns or socketed a
   gem.
3. Inputs: the press's own item text (the one clipboard read, decision
   0003), the build's gems and the cached repoe-fork gems snapshot
   (DATA-GEMS-SNAP, decision 0009), read through hotreload with the last
   good copy kept. Nothing is fetched or sent.
4. Uncut text: the name line `Uncut <Kind> Gem (Level N)` (the base_items
   snapshot's own base names) or the `Item Class: Uncut <Kind> Gems`
   header gives the kind; N comes from a `Level: N` property, else the
   name's `(Level N)`. The item level is never read as the cut level.
5. Gem kind: an explicit snapshot `gem_type`, else `is_support`, else a
   persistent / meta / spirit tag (spirit), else a SupportGem base id
   (support), else skill. Unreleased and legacy entries are skipped.
6. Tiers are never guessed: a gem whose snapshot tier (`gem_tier` /
   `tier`) is above N is left out; a gem the snapshot gives no tier is
   named in a separate "check the cut in game" note, never claimed
   makeable. The level made is N clamped to the highest `per_level`
   level. Socketed at that level: enabled group, enabled gem, PoB level at
   least the level made (a Kindler stage has no socketed level). Build
   gems absent from the snapshot are left out.

## Deviation from ACCEPT

The ACCEPT line asks for "real uncut gem item text fixtures". No live
Ctrl+C text of an uncut gem is in the tree or its fixtures, and the forum
is not a permitted source (decision 0050). `tests/fixtures/uncut_gems/`
holds SYNTHETIC texts in the item-text structure the item parser handles,
with the cached base_items snapshot's own name, description and direction
lines for those bases; the "Item Class:" display words are assumed. A
second shape (the level as a `Level: N` property) is covered too. A
dev-host press sample (decision 0045 amendment) replaces them when one is
captured.

## Alternatives

- Tier from the gem's level-1 requirement: rejected, PoE2 requirements
  follow the gem level, not the gem tier, so it would mislead.
- Treat a gem with no snapshot tier as makeable: rejected (a guess).
- Drop a gem with no snapshot tier silently: rejected, the player would
  not learn the build has a candidate; it is named as unchecked instead.
- A new verdict word on the overlay card: rejected for now, it needs a
  design 0001 section 9 entry first; the notes are enough for the row.

## Reverses if

The live copy shape differs from both fixture shapes (then fix the parser
from the captured sample), repoe-fork names the tier or kind under another
field, GGG changes how uncut gems cut, or players need the advice on the
overlay card itself.
