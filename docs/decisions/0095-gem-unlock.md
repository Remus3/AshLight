# 0095 - Gem unlock card and next-up steps for a pasted build (TC-GEM-UNLOCK)

Date: 2026-11-28. Row: TC-GEM-UNLOCK (research 0064 G3). Reuses the loop's
WIP (keep ref of the row: the card, its event row, the plug and the
state hook), moved onto the one gem helper of decision 0094.

## Decision

1. On the player's own level-up line (decision 0038 character), the build
   gems of the pasted PoB build (enabled group and gem) whose cached gems
   snapshot level requirement L has prev < L <= level (only L == level
   when prev is unknown) unlock. The lookup is
   `server/al/theorycraft/gemadvice.py` (`table`, `pob_gems`, `unlocked`;
   decision 0094), the snapshot the cached repoe-fork gems.json beside the
   core's base list (DATA-GEMS-SNAP, decision 0009), read only while a
   build is loaded.
2. Card: at most one per level-up, naming every gem that unlocked
   (`Gem usable at level <n>` / `<n> gems usable at level <n>`, then the
   names), the overlayview CARD_HOLDERS "gem" holder after the moment
   card and before the key hint, for the layout's card time (decision
   0014: 20 / 60 / 200 s), under parts.moment; a press or a new game run
   drops it. Dashboard twin: one Recent row `Level <n> unlocks <names>`.
3. Next-up steps (decision 0092 hook): `progression.add_next_source`
   ("gem-unlock", order 15: after the passive step, before the built-in
   gem step) adds one step per build gem whose snapshot level is exactly
   the player's level, at most 2 steps of 52 characters, the last one
   counting the rest (`Gem usable now: <name>`, `Support usable now
   (+<n>): <name>`). Only for a pasted build: a Kindler plan already has
   its own gem steps (decision 0092), so it adds nothing there.
4. Words in `server/al/text/gemunlock.py` (copy sheet
   `docs/design/copy/gemunlock.md`). No word says the player owns,
   picked up or socketed a gem; the names are the build's plan.
5. No build, no snapshot, a gem the snapshot does not name or gives no
   level, another player's level-up or a disabled gem: nothing.

## Alternatives

- One step naming all the gems: rejected, the brief asks for a step per
  gem; the 2-step cap keeps the passive step in the 3-step strip.
- Steps for every gem usable at or below the level: rejected, the strip
  is "due now"; the Skills list already marks every gem ready.
- A step for a Kindler plan too: rejected, it would double the plan's own
  `Gem ready` step.
- The loop WIP's head `New gem at level <n>`: reworded to `Gem usable at
  level <n>`, so the card cannot read as a gem the player got.

## Reverses if

The 2-step cap hides needed steps in play, GGG changes gem level
requirements so the snapshot level misleads, the level-up line format
changes, or players want the steps for a Kindler plan too.
