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

## Amendment 2026-11-28 (ITEM-INFO-GEM-DETAIL: gem details in the popover)

Operator ask: the popover of a gem name (Kindler, Progression) should show
the gem's in-game details, for example Spark's spell effect lines.

Decision:

1. A skill, spirit or support gem name answers a "gem" field from the
   repoe-fork poe2 export only: skill_gems.json (cached under the reader
   name gems.json), skills.json and gem_tags.json, all three in
   snapshot.SOURCES under decision 0009 (one web_data opt-in, sidecar
   cache, AshLight User-Agent, repoe-fork credit; probes "gems",
   "skills", "gem_tags"). The export already words each level's stat
   lines with the game's own stat description files, so neither the
   stat_translations snapshot nor a Path of Building file is needed; the
   lines are shown as written, markup read as its shown words.
2. Fields, each only when the export holds it: kind, tags (tags with no
   shown word are left out), description (the active skill's
   description, or the support text, filling "description" when
   base_items has none), max_level, the asked level, costs (known cost
   types only), Spirit reservation, cooldown, cast time (non-attack
   skills only), cost multiplier (supports), and per stat set its label
   (only when there is more than one set), attack damage percent, critical
   hit chance and lines in the game's tooltip order. GET /api/iteminfo
   takes an optional level=1..40 (default 1); a button made with
   button(doc, name, level) asks for it.
3. The snapshot tool, in its own process, turns the 28 MB skills.json
   into one small file per gem name under <cache>/gem_details/ (about
   1100 files, 60 KB at most, 5.8 MB in all, rebuilt only when the
   three inputs' sha256 change). The core reads one file per popover
   look and never parses skills.json (decision 0002 budgets).
4. Left out, with no permitted local source or no safe reading: quality
   lines (their numbers need the game's per-quality maths), attack
   speed multipliers (the export does not say how the game words them),
   per-level attribute and character level requirements (not in the
   export), the extra skills a gem grants beside its first one, and gem
   icons (a DDS path, not a shown image).
5. DATA-GEMS-SNAP's URL moved: the poe2 export has no gems.json (HTTP 404
   on 2026-11-28; the export's poe2 parser writes skill_gems.json). Its
   entries carry the name under base_item.display_name, which
   archetypes.gem_index already reads, so Kindler's gem names now read
   checked; the export has no gem level requirement, so Kindler gem
   levels stay unchecked. The CLAUDE.md DATA-GEMS-SNAP entry still names
   gems.json; the integrator updates its wording (not this package's
   file to write).

Alternatives: parse skills.json in the core on first look (about 250 MB
peak in the core, past decision 0002); render stat lines from
stat_translations ourselves (the export already ships the game's own
wording, and an own renderer would drift); read PoB-PoE2 skill Lua files
as text (repoe-fork already holds every needed field, and repoe-fork wins
conflicts anyway); compute quality lines (guessing the game's maths).

Why: the export holds the in-game tooltip words per level, it is the same
licensed, attributed, opt-in cache as base_items, and per-gem files keep
the core's cost to one small read per click.

Reverses if: repoe-fork drops or reshapes skills.json / skill_gems.json /
gem_tags.json (the probes fail and the last good copy stays), its terms
forbid this use, a shown line proves different from the game's tooltip
in play, or the derived folder costs the snapshot run's budget.
