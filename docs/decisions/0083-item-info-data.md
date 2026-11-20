# 0083 - Item info popover: data sources

Date: 2026-11-19. Status: ruled by an adjudicator agent the same day
(operator request 2026-11-19, item 1, data side). Input: research 0060
section 3. Pairs with decision 0082 part 1 (the UI). Amends decision
0037 (point 3 below). Plan: docs/plan/10-operator-requests-2026-11-19.md
(packages ITEM-INFO-*).

## Decision

1. The popover reads local caches only; nothing goes on the network when
   it opens. Fields, in this order, each left out when unknown:
   - name, and the icon from the poe.ninja cache (web_data on);
   - "Item class" from repoe-fork base_items item_class (for example
     Stackable Currency). "Rarity" is shown only as Unique for items in
     the uniques cache or from a pressed item's own Rarity line; currency
     has no rarity field and none is invented;
   - market: price in divine, 7-day trend, volume or listing count from
     the cached price book (decision 0026, web_data on), with "Prices:
     poe.ninja" and the cache age;
   - stack size and full_stack_turns_into ("10 shards become 1 <orb>");
   - description and directions (repoe-fork); unique flavour text
     (poe.ninja cache);
   - release_state when it is not "released" (legacy, unreleased,
     unique only);
   - where found: the boss and zone of PoB's Source lines (about 51
     uniques) and "No longer obtainable", credited "Path of Building
     (MIT), community-written, may be out of date".
2. drop_level is not shown: it is the lowest area level a base may drop
   in, not a drop fact, and players would read it as one. If the
   operator asks for it, the exact text is "Minimum area level for this
   base to drop (a game-file value, not a drop chance)", for bases only.
3. Amendment to decision 0037: CurrencyNames.lua, WorldAreas.lua and
   Uniques/*.lua of the pinned PoB-PoE2 checkout join TradeSiteStats.lua
   as text-parse-only sources under the same conditions: only while the
   optional calc component is installed, each file's sha256 equal to its
   config/tc_pins.json pob2_files entry (a mismatch omits the field),
   never run as Lua, repoe-fork wins any conflict. They feed only this
   popover. Without the checkout the "where found" rows do not appear.
4. The GGG currency-exchange endpoint stays out (history only; no call
   without a registered client, ruling of 2026-11-17, research 0018 and
   0035).
5. Cut, because no permitted source exists: drop rates (GGG publishes
   none; never shown), monster drop lists beyond PoB's Source lines, NPC
   vendor prices, disenchant / salvage yields and rates, a per-league
   drop-disabled flag.
6. The popover ends with "Drops, vendor and disenchant: see poe2db
   (community site)" and a "More on poe2db" link built from the item
   name; it opens only on the player's click (shell.openExternal in the
   client; poe2db.tw is already in config/link_hosts.json). No poe2db or
   wiki text is fetched or copied (decision 0050; CC BY-NC-SA 3.0 cannot
   enter Apache-2.0 AshLight, decision 0047).

## Alternatives

Show drop_level as a labelled inference; show a rarity for currency;
call the GGG exchange without a registered client; read poe2db or the
wiki; defer the PoB parsing (leaves "where found" empty almost always);
link both poe2db and the wiki (one is enough; the wiki is behind a bot
wall).

## Why

Only facts a permitted source states are shown; unknown is omitted,
never guessed. The PoB files use the same hash-pinned, text-only
discipline 0037 already accepted, and they are the only permitted source
of boss names. The link sends the player, not AshLight, to the community
data.

## Reverses if

A permitted source for drops, vendor or disenchant data appears; GGG
opens registration (then revisit point 4); PoB relicenses or a Source
line proves wrong in play; poe2db objects to deep links or leaves
config/link_hosts.json; or the operator asks for drop_level.

## Amendment 2026-11-19 (operator follow-up: licence)

Operator question: "non-commercial licence - explain; if AshLight uses a
different licence, will that allow it?" Ruled by an adjudicator agent the
same day. Input: research 0060 section 7 (follow-up 2026-11-19).

Decision:

1. AshLight keeps Apache-2.0 (decision 0047). It is not relicensed to
   CC BY-NC-SA or to Apache plus a non-commercial clause.
2. Link only stays (point 6): no poe2db or poe2wiki text or data is
   fetched, bundled or snapshotted now. Decision 0009 item 4 stands as
   written and decision 0050 stands (dives never read those hosts).
3. The one future route is decision 0009's own pattern: a build-time,
   opt-in (web_data), attributed fetch into the player's own sidecar
   cache, never committed to the repo and never in a release. It opens
   only when a source publishes an API or terms that permit app use
   (0009's existing reverses-if). AshLight's code licence is untouched by
   that route: the player's local copy stays under the source's licence
   and its credit line is shown.
4. A community drop rate, vendor value or disenchant yield is never shown
   as fact. If that route ever opens, each such field carries
   "community estimate", the source name and the snapshot date.

Alternatives: relicense AshLight to CC BY-NC-SA (does not fix access,
makes AshLight non-OSI, clashes with the Apache vendored kit, and CC
advises against CC licences for software); Apache plus an NC clause
(same, and the ToS floor already bars revenue, so NC adds nothing);
fetch the wiki api.php now (reachability mixed, bot wall, 0050 refuses
the host); bundle the data (0009).

Why: the blocker is access and permission, not AshLight's licence.
poe2db states CC BY-NC-SA 3.0 for its wiki content but offers no API and
no app-use terms; the wiki states CC BY-NC-SA 3.0 Unported (search
summary only) and puts its pages behind a bot wall. ShareAlike binds
adaptations of the licensed material, not independent code that reads
it, so a relicence would not be needed for a local cache and would not
grant the missing permission. CC 3.0 Unported does not license
sui-generis database rights. The data is community-sourced with unknown
freshness.

Reverses if: a source publishes an API or app-use terms; a source owner
gives written permission; or a source states its data is under a
licence that allows this use (then point 3 applies, code stays
Apache-2.0).
