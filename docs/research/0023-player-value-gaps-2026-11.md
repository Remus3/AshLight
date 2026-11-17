# 0023 - Player-value features still missing (Nov 2026)

Date 2026-11-17. Compares AshLight (ROADMAP state of 2026-11-17: price
check with uniques / stackables, trade link, item check with PoB delta,
map runs, death recap, level pace, act splits, price movers) with popular
companions. Ideas only, no code read or copied. Licenses: Exile-UI MIT,
Sidekick MIT, Exiled Exchange 2 MIT (0006); poe2.re is a website (study
only). Ranked by player value under the ToS floor; floor status per item.
Top 3 filed as ROADMAP rows.

## Companion feature survey

- Exile-UI (MIT, AutoHotkey): item-info tooltip, Act-Tracker levelling
  guide with gem-setup overlays, Map-Tracker, Map-info panel ("map-mod
  tooltip and panel"), Search-strings ("single-hotkey menu for in-game
  searches, such as vendors"), Stash-Ninja / Rune-Ninja price overlays,
  FilterSpoon filter editor, Vaal Street trade logging, clone-frames
  (projects screen areas) (https://github.com/Lailloken/Exile-UI ,
  accessed 2026-11-17).
- Sidekick (MIT): price check and "dangerous map-mod warnings"
  (https://github.com/Sidekick-Poe/Sidekick , accessed 2026-11-16, via
  0006).
- Exiled Exchange 2 (MIT): price check plus a stash-search widget; points
  users to poe2.re for regexes
  (https://kvan7.github.io/Exiled-Exchange-2/stash-search.html , search
  snippet, accessed 2026-11-17).
- poe2.re: regex builder for stash / vendor search, "all Waystone
  affixes" (https://red.127.pp.ua/r/PathOfExile2/comments/1ik79i1/poe2re_big_waystone_modifier_regex_update ,
  search snippet, accessed 2026-11-17). Stash search box limit reported as
  250 characters - UNVERIFIED
  (https://vulkk.com/2026/05/29/path-of-exile-2-regex-system-explained/ ,
  search snippet, accessed 2026-11-17).

## Ranked (top 5 under the floor)

1. Waystone mod check on the item-check press (UTIL-WAYSTONE). Floor: YES -
   same per-press clipboard read (decision 0003), no new read. The card
   flags mods dangerous for the loaded build (e.g. reduced recovery, no
   regen, extra elemental damage vs the build's weakest res, monster crit)
   and shows tier / area level. Today evaluate.py skips waystones. Value:
   high, every map is rolled and checked. Rules are AshLight-authored from
   mod text, no third-party list copied.
2. Search-string builder (UTIL-SEARCHSTR). Floor: YES - the dashboard
   builds a stash / vendor search string from the loaded build (wanted
   bases, resistances, life / ES) and from the waystone "avoid" set; Copy
   on the player's click is the decision 0014 clipboard write; the player
   pastes it. AshLight never types into the game (no input, floor). Value:
   high; vendor shopping while levelling and waystone sorting. Risk: the
   250-char limit is UNVERIFIED; verify in game.
3. Zone notes while levelling (UX-ZONE-NOTES). Floor: YES - triggered by the
   already-tailed `[SCENE]` / area lines; one short AshLight-authored line
   per campaign zone (objective, quest reward to take) in the overlay status
   slot. Data: own text only (no poe2db / wiki prose, decision 0009 limits).
   Value: high for 1.0 free-to-play newcomers; cost is writing the notes and
   updating them for Acts 5-6 after launch.
4. Loot filter snippet (UTIL-FILTER, research 0022, already filed). Floor:
   YES as a user-saved download only (adjudicator ruling in 0022).
5. Trade log (Vaal Street idea). Floor: YES (Client.txt trade lines only)
   but the log carries no item or price data, so it can only list
   counterparty and time; low value. Not filed.

Not feasible under the floor (not ranked): stash price overlay positioned
over the game's stash (needs screen capture or stash API), clone-frames
(continuous screen capture, decision 0003), wealth / profit tracking (stash
API, OAuth, TC-OAUTH-REG), chat macros (input to the game).

## Sources

- https://github.com/Lailloken/Exile-UI (accessed 2026-11-17)
- docs/research/0006-existing-tools.md (Sidekick, Exiled Exchange 2 licenses; 2026-11-16)
- https://kvan7.github.io/Exiled-Exchange-2/stash-search.html (search snippet, accessed 2026-11-17)
- https://red.127.pp.ua/r/PathOfExile2/comments/1ik79i1/poe2re_big_waystone_modifier_regex_update (search snippet, accessed 2026-11-17)
- https://vulkk.com/2026/05/29/path-of-exile-2-regex-system-explained/ (search snippet, accessed 2026-11-17)
- docs/research/0022-loot-filters.md (2026-11-17)
