# 0093 - Augment what-if on the item-check press

Date: 2026-11-28. Status: decided by the TC-AUGMENT-WHATIF package
(research 0064 G4, research 0065, decision 0091). Amends decision 0024
(staged press, R7 budgets) by one more stage; uses decision 0091's
augment rows; keeps decisions 0017 and 0037 (no price, no trade call).

## Decision

1. A fourth press stage, "augment" (evaluate.stages(), STAGE_AUGMENT),
   runs after the per-mod stage "mods" on the same LastEval stage worker,
   only when all hold: the calc is on (a calc callable and a build), the
   core's augment source answers rows (pobtext.Augments, read only while
   the calc component is opted in, "tc_calc" true; decision 0091's pin and
   marker conditions), the headline slot has a PoB delta (not a weapon the
   main skill cannot use), and the item has room:
   - a known class (theorycraft/augment.py CLASS_KEYS, from PoB's
     Classes/Item.lua GetSocketedAugmentTypes and its Bases files at pin
     7d6f530c: base key weapon / armour / caster plus PoB's lower-case
     base type); any other class gets nothing, never guessed;
   - not corrupted, mirrored or unmodifiable;
   - a possible free socket (the Sockets line names more sockets than the
     item has rune lines; the game shows two equal runes as one line, so
     the words say "for a free socket", never claim one).
   With no rows (no pin, a hash mismatch, the calc off) there is no stage.
2. An augment applies as PoB applies it: the stat lines of its base-type
   row plus its specific-type row; "Bonded:" lines are left out (they need
   a bonded ascendancy the card does not know). Augments whose lines differ
   only in numbers are one family; only the highest rank (then the larger
   numbers) is measured.
3. Each candidate is probed by appending its lines to the pressed item in
   the headline slot (delta.with_line, as the per-mod probes do). The change is
   measured against the build with the pressed item in that slot (stage
   "pob" already has it: no extra call) and ranked by the decision 0024
   blend (50/50 DPS / EHP). The best is named only when its blend is above
   0; otherwise the card says none raises DPS or EHP.
4. Budget: at most delta.MAX_PROBES (24) calc calls for the whole stage
   and at most 12 s, cut to 5 s by the 2026-11-28 amendment (the R7 warm-check probe
   ceiling, amendment 2026-11-18); past either the stage ranks what it
   measured and says how many it tried. The hand stat weights only choose
   which candidates are measured first (weighted above 0, then unweighted
   in file order, then negative); PoB's numbers alone rank them.
5. Cancellation: the stage checks the press generation before every calc
   call; a newer press, a re-score or close ends it with no further call
   and nothing published. The "mods" card carries augment pending, so the
   stage part's "numbers are coming" note stays until the augment card.
   A calc error in the stage gives an "augment failed" note and keeps the
   mods card's verdict and numbers.
6. Words: dashboard notes only (server/al/text/augment.py, copy sheet
   docs/design/copy/augment.md): the best augment with its DPS / EHP
   change (or that none of the N tried raises either), the decision 0091
   credit line after it, and one sentence when the calc is off and the
   item may have a free socket. No overlay line, word, tone or head
   changes; never a price, never a trade link of its own.
7. No quality what-if (the row's "quality below 20" half): the bridge's
   set_item calls PoB's Item:NormaliseQuality, which already scores every
   modifiable item below its base's top quality at PoB's default quality.
   Measured on the real bridge 2026-11-28 with the reference build: an
   invented bow at Quality 0, +20% (augmented), 20 and with no Quality line
   gave the same DPS and EHP to the last digit. A quality probe would
   always read 0, so the card says nothing about quality; the item's own
   PoB numbers already assume full quality. Live check of the stage on the
   same bridge: 24 calls, 24 augments measured, 17.7 s for the whole first
   press with every stage, 13.1 s warm (the stage stops itself at 12 s).

## Alternatives

- Use PoB's own "Rune: <name>" item lines: rejected for now; the game's
  copied text carries rune effect lines, not rune names, and PoB then
  rebuilds runes from those lines, so mixing both forms risks a double
  count. Appending the effect lines is what the per-mod probes already do.
- Probe every augment: rejected; 40 to 80 candidates per slot breaks
  MAX_PROBES and the R7 ceilings.
- Show the stage with the calc off (stat weights): rejected; the weights
  cannot value most augment lines, and the row asks for PoB's numbers.
- Rank by a trade price or link per augment: rejected (decision 0017).
- A quality probe that drops NormaliseQuality in the bridge: rejected;
  bridge.lua's lockdown and item path stay as decision 0022 fixed them,
  and every other item check would then change its numbers.

## Why

Research 0064 G4 names this as a calc-only gap other tools fill with
trade2; decision 0091 admitted the one source that joins an augment to its
stat and slot. The press's staged calc is already running for the item, so
the what-if costs no click (ZERO-CLICK) and stays inside the existing
budget rule.

## Reverses if

PoB changes GetSocketedAugmentTypes or the slot keys of ModRunes.lua, or
the bridge stops normalising quality (then add the quality probe); a
real item shows the free-socket rule misleads in play; the stage breaches
the R7 budgets on the real bridge; the game starts showing socketed rune
names in copied text (then count sockets exactly); or decision 0091
reverses.

## Amendment 2026-11-28 (integrator R7 check)

Decision: the stage's time bound (augment.TIME_S) is 5 s, not 12 s. The
R7 ceilings (decision 0024 amendment 2026-11-18, tests/tc_live_util.py
BUDGET) bound every probe of a press up to its last stage: a first press
30 s, a warm press 12 s. The live check measured 17.7 s for a whole first
press (inside 30 s) but 13.1 s for a whole warm press, over the 12 s warm
ceiling, because the 12 s stage bound sat on top of the pob and mods
stages. With those stages at up to 5.5 s warm (R7), 5 s plus one call
past the bound (about 0.5 s) keeps a warm press at about 11 s at worst,
and a first press at about 18 s. The staged-press rule is unchanged: the
stat-weight card still shows at once and every PoB stage is an update.
About 10 augments fit in 5 s; the hand weights choose which go first.

Reverses if: a re-measure on the real bridge puts a warm press with the
stage over 12 s again (cut further), or the calc gets fast enough that a
longer bound fits.
