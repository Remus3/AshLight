# 0032 - Swap compare on the card, PoB sanity guard, filter value tiers

Date: 2026-11-17. Lane AREA-MATH batch 4. Rows MATH-COMPARE,
MATH-DPS-SANITY, UTIL-FILTER-2 (price-tier part). Inputs: decision 0004
(never an own calc engine), 0024 (TC-DELTA), 0028 (live proof), 0030,
0031 (filter download), research 0025 section 2 (filter grammar).

## Decision

- MATH-COMPARE. The card's Path of Building sentence names the slot and
  the equipped item the swap replaces ("this item in Gloves replaces Old
  Grip", "this item goes in the empty Gloves slot"); for an item that fits several
  slots it adds "(the better of the N slots it fits)", and every other
  compared slot carries its own "Path of Building: DPS x%, EHP y%." line
  (state.eval_card_text `comparisons[].calc`, shown by web/app.js under
  that slot). A one-hand weapon is compared against Weapon 2 too when the
  build dual wields: the equipped Weapon 2 is a one-hand weapon by its item
  class, or (PoB item text has no class line) its base / name line holds
  none of the off-hand words shield, buckler, focus, quiver
  (evaluate.slots_for_build). The headline stays the better slot (highest
  PoB blended delta), as TC-DELTA already picked for rings.
- MATH-DPS-SANITY. delta.CalcImplausible (a CalcError) is raised for
  negative DPS, negative or zero EHP, and an attack build (base DPS above 0)
  at exactly 0 DPS after one swap or probe. NaN / inf were already refused.
  The card then scores with the stat weights (or this build's cached PoB
  weights) and says "DPS and EHP are not shown because Path of Building's
  numbers for this item don't add up. Try the check again." (calc notice
  "implausible").
- UTIL-FILTER-2 tiers. ninja.RatesClient.filter_prices reads the cached
  currency rates and price book (no request; None while web data is off,
  without a league or without a Divine Orb rate) and converts to Divine
  Orbs. lootfilter.tiers: top >= 1.0 Divine Orb, worth picking up >= 0.05;
  a unique base is tiered by its CHEAPEST unique with 10+ listings (the
  filter cannot tell uniques of one base apart), stackables with trade
  volume under 1 are skipped, names the grammar cannot carry unchanged are
  skipped, unique bases are checked against the snapshot base list. Tier
  blocks (Show only) go before the build block. Never a Hide block.
  The merge part of UTIL-FILTER-2 stays open.

## Alternatives

- Compare a one-hand weapon against Weapon 2 always: rejected, a shield or
  quiver build would get a nonsense "replace your shield" line.
- Show PoB's 0 DPS after a weapon swap as -100 %: rejected per the lane
  order; a skill PoB stops counting (wrong weapon type) reads as a
  verdict the player cannot act on. The weights still score the item.
- Tier a unique base by its most valuable unique: rejected, it would
  highlight every drop of a base for one rare chase item (not conservative).
- Hide cheap items: rejected, AshLight never hides (the player's filter
  decides).

## Why

The card must say what it replaces and by how much, using only PoB's own
numbers (decision 0004); a wrong number is worse than a weights score with
an honest notice. Filter tiers reuse the hourly cached prices, so they cost
no request and refresh by themselves (ZERO-CLICK).

## Reverses if

- A PoB release reports a legitimate 0 DPS state after a swap that players
  want shown (then show it with its own wording instead of the guard).
- Off-hand base names stop carrying the four off-hand words, or PoB item
  text gains an item class line (then use the class only).
- poe.ninja stops giving a Divine Orb rate, or players report the
  thresholds highlight too much / too little (move TOP_DIVINE /
  PICK_DIVINE in lootfilter.py, one place).
