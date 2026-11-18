# 0034 - Zone guide facts (campaign, interludes, maps)

Date: 2026-11-17. For ROADMAP ZONE-GUIDE, decision 0041. Patch read: 0.5.x
(maxroll levelling guide marked 0.5.5); no 1.0 campaign change found.
Facts only: the guide file (`server/al/data/zone_guide.json`) is written in
AshLight's own words. poe2db and the wiki are CC BY-NC-SA; nothing of
theirs is copied or redistributed.

## Sources (all accessed 2026-11-17)

- DB1-DB6: https://poe2db.tw/us/Act_1 .. https://poe2db.tw/us/Act_6
  (bosses, waypoints per zone; poe2db files the interludes as "Act 6").
- DBQ: https://poe2db.tw/us/Quest ; DBB: https://poe2db.tw/us/Book_of_Specialisation
- MXP: https://maxroll.gg/poe2/getting-started/permanent-stats-from-campaign
  (updated 2026-09-18)
- MXL: https://maxroll.gg/poe2/getting-started/comprehensive-league-start-leveling-guide
  (0.5.5, 2026-09-08)
- MXC: https://maxroll.gg/poe2/getting-started/path-of-exile-2-campaign-guide
- MXS: https://maxroll.gg/poe2/getting-started/act-1-campaign-secrets (0.3.0)
- Map completion: poe2wiki Map_Boss and the 0.3.1 patch notes, seen only
  through search summaries (poe2wiki.net and mobalytics refused automated
  fetches).
- Waypoints and zone links: the cached repoe-fork world_areas snapshot
  (`has_waypoint`, `connections`; decision 0020, research 0033).

## Findings used (high / medium confidence)

- Lasting campaign rewards (MXP): spirit +30 (Freythorn, King in the
  Mists), +30 (Azak Bog, Ignagduk), +40 (Kriar Village, Lythara); +10%
  cold (Clearfell, Beira), lightning (Spires of Deshar shrine), fire
  (Jiquani's Machinarium, Blackjaw); +20 life (Ogham Manor, Candlemass);
  +5% life (Khari Crossing shrine); +5% mana (Eye of Hinekora silent
  hall); charm bonus (Valley of the Titans relic altar); Servi's pick
  (Venom Crypts); defence pick (Whakapanu fin); flask recovery pick
  (Abandoned Prison); tattoo picks (Halls of the Dead); Qimah pillar pick.
- Skill point books (medium: MXP says passive points, DBB says weapon-set
  points, DBQ says passive plus respec): Crowbell, Una's lute, Kabala,
  Deshar letter, Silverfist, Aggorat heart, Omniphobia, Trial of the
  Ancestors, Wolvenhold, Khari Crossing arena, Howling Caves. The guide
  says "a book of 2 skill points" without naming the kind.
- Main-path order per act and per-zone bosses: DB1-DB6, MXL, MXC.
- Layout tendencies (medium): Mud Burrow by the Clearfell waypoint; Keth
  exit across a bridge opposite the entrance; Venom Crypts by the Jungle
  Ruins waypoint; Temple of Kopec stairs in the corners; Hunting Grounds
  points of interest near the corners.
- Maps: a map completes when its boss dies; killing all rares stopped
  being required in 0.3.1.

## Left out (not confirmed)

Root Hollow, Library of Kamasa, Isle of Decay and Brinerot Cove (in the
snapshot, in no guide); Halani Gates and Matlan Waterways waypoint
(sources disagree; the snapshot flag is shown instead); the Red Vale
entrance heuristic (one guide, low); the Act 4 Blind Beast potion
(unconfirmed); whether dying loses a waystone today.

## Client.txt quest lines

No evidence that PoE2 writes NPC dialogue or quest lines to Client.txt
(the only hint is a PoE1 tool reading NPC speech with a dialogue option
on). The tracker therefore uses zone entries only (decision 0041).
UNVERIFIED until a live sample (LIVE-1).
