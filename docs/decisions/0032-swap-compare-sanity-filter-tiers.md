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
  none of the off-hand words shield, buckler, focus, quiver, targe, nor
  the wordless shield names Glacial Fortress, Golden Flame, Venerable
  Defender (AREA-AUDIT P4-1)
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
  skipped, every tier name (unique bases and stackables: the base list
  holds both, AREA-AUDIT P4-2) is checked against the snapshot base list
  when it is cached. Tier blocks (Show only) go before the build block. Never a Hide block.
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

## Amendment 2026-11-17 (AREA-MATH b5, main-session ruling): weapon type

Ruling: an attack build at 0 DPS after a weapon swap read "Path of
Building's numbers don't add up", which misleads when the checked weapon
type is one the main skill cannot use: then it IS a real downgrade for this
build. MATH-WEAPON-TYPE:

- The bridge gains a read-only "main_skill" command (bridge.lua /
  Bridge.main_skill): PoB's own mainEnv.player.mainSkill state after the
  calc, {"found", "disabled", "reason", "name"}, where reason is PoB's
  disableReason (src/Modules/CalcActiveSkill.lua, the text its sidebar
  shows under "Skill disabled:"). No own skill database.
- calcwire asks it only after a swap into a "Weapon ..." slot and maps the
  four PoB weapon reasons (calcwire.WEAPON_REASONS: main hand / off hand
  not usable, no usable weapon, weapon types need to be different) to a
  `weapon_unusable` flag {"skill", "reason"}. A bridge without the
  command, an error from it or any other reason reads as no flag.
- delta raises CalcWeaponUnusable (a CalcError, NOT CalcImplausible) when
  the swap carries the flag and the base does not, before the 0 DPS guard.
- evaluate: that slot is a "downgrade" comparison with weapon_unusable
  {"skill"}, scored with the hand weights, no dps / ehp and no probes; a
  slot the skill can use always wins the headline. When the headline slot
  is unusable, calc = {"source": "pob", "notice": "weapon_type"}.
- Card (state.py, design-reviewer pass): overlay head "Downgrade - wrong
  weapon type", line "Main skill can't use this weapon"; dashboard "Your
  main skill can't use this weapon type, so this item is a downgrade for
  this build. Path of Building counts no damage from <skill> with it in
  <slot>." and per slot
  "Downgrade: your main skill can't use this weapon type in <slot>
  (<name>)."
- The sanity fallback (implausible) stays for every other 0 DPS or
  nonsense answer, including "This skill requires a Shield" (left out:
  not a weapon type; a follow-up may word it separately).

Alternatives: an own weapon-type table per skill (rejected, decision 0004:
never an own calc engine or skill database); show PoB's -100 % (rejected:
FullDPS can include other skills, and the number hides the cause); ask
main_skill on every calc (rejected: one extra round trip per probe on
non-weapon slots for nothing).

Reverses if: PoB renames its disableReason texts (update WEAPON_REASONS;
the live test reads the real one), PoB moves mainSkill out of
calcsTab.mainEnv, or players want shield requirements worded the same way.
