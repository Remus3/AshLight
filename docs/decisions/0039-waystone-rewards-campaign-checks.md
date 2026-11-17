# 0039 - Waystone reward totals and campaign checks

Date: 2026-11-17. Lane AREA-UTIL batch 11. Inputs: CLAUDE.md "Game ToS
floor", decisions 0003 (read policy), 0004 (theorycraft scope), 0009
(data license), 0030 (waystone check), research 0031 sections 1 and 4
with adjudicator ruling H, ROADMAP rows UTIL-WAYSTONE-REWARD and
UTIL-CAMPAIGN-CHECKS.

## Decision

1. UTIL-WAYSTONE-REWARD. The same item-check press (one clipboard read per
   manual press, decision 0003) totals a waystone's reward kinds: item
   quantity, item rarity, pack size, magic monsters, rare monsters,
   waystone drops (`server/al/theorycraft/waystone.py` REWARDS). In the
   repoe-fork mods snapshot (fetched 2026-11-17) every waystone prefix /
   suffix carries its reward as a hidden `_from_map` stat with no English
   translation, so the game prints the summed values as properties under
   the tier line ("Item Rarity: +38% (augmented)"); the rule reads those
   property lines and also any plain "N% increased <reward>" mod line,
   summed per kind. The dashboard says "Rewards: ..." under the risk
   sentence; the overlay card's item line becomes the compact reward line
   (as a price line replaces it, design 0001 section 10), never a third
   line. An unidentified waystone says to identify it. No tablet rules.
2. UTIL-CAMPAIGN-CHECKS (`server/al/campaign.py`). Under ruling H only:
   player level and area id from the opted-in Client.txt tail, the loaded
   PoB build's gear and PlayerStat resistances, and the build-time
   base_items snapshot in the sidecar cache (flask drop levels read at
   start; no snapshot data in tracked files). Hints, in a campaign area
   (`G<n>_` ids) only and only with a known level and a loaded build:
   - boss: in G1_15 (Ogham Manor) cold, in G2_10_2 (Mawdun Mine, Rudja)
     fire, the build's resistance to that element. AshLight-authored
     restated facts; the guide (research 0031 section 1) is credited in
     docs only. The guide places Rudja in "Act 3"; the world_areas
     snapshot lists Rudja as the G2_10_2 boss, and data wins (the same
     research note: take levels from data, not guide text);
   - flask: a higher life / mana flask base can drop at the player's
     level than the one the build has;
   - boots: the build's boots have no movement speed at or past the
     "boots_speed_level" setting (default 16, the guide's "about level
     16"; importable via settings io).
   Dashboard: a hint list under the zone tip in the Act times card (not a
   live region). Overlay: the first hint's word (<= 15 chars) in the HUD
   status slot, last in its order (after AFK / DND).

## Alternatives

- Reward rules on mod lines only: rejected, waystone reward stats have no
  translation, so the mod lines never carry them; the properties do.
- Reward line as a third overlay line: forbidden (design 0001 2-line HUD /
  card line budget).
- Boss table from guide text for every act boss: rejected, only two
  elements are stated by the cited source; more wait for UTIL-1.0-POST.
- Flask levels hard-coded from the guide: rejected, the guide disagrees
  with itself; the snapshot is authoritative and not bundled.
- The campaign word merged into the under-level word: rejected in design
  review (it hid AFK / DND).

## Reverses if

GGG prints waystone rewards differently (property names change), ruling H
is withdrawn, decision 0009 reverses for repoe-fork, or live play shows
the boss elements wrong.
