# 0088 - The loaded build's tree spec follows the character level

Status: accepted 2026-11-27 (ROADMAP TC-SPEC-FOLLOW, research 0064 G1).

## Decision

1. A pasted PoB build with several tree specs uses the spec whose title
   names a level band holding the character level of decision 0038 (the
   level-up line in the player's own Client.txt). The rule is
   server/al/theorycraft/specfollow.py, plain text matching only:
   "Level 30", "lvl 30", "Lv. 30" and a bare "30" open a band at 30;
   "Level 1-30", "lvl 31 to 69" are closed bands; "lvl 70+" / "70+" is
   open. A title with no level, two levels, a level outside 1 to 100 or an
   upper end below its start names no band.
2. Of the bands holding the level, the one with the highest start wins. No
   band, no known level, or a tie at the top that does not hold PoB's own
   active spec keeps PoB's active spec (`<Tree activeSpec>`): never a
   guess.
3. The followed build is one view for every reader: the tree view, the
   tree link (TC-TREE-URL), the `.build` download (TC-BUILDFILE) and the
   calc read `Build.active_spec` and `Build.raw_xml`. raw_xml differs from
   the pasted XML only in the one `<Tree>` tag's activeSpec value; the
   result is parsed again and must give the same specs and the picked
   index, else PoB's active spec stays. The share code (Copy code, the
   stored file) is always the player's own XML.
4. The calc needs no new bridge command: PoB's unmodified load
   (TreeTab:Load calling SetActiveSpec(tonumber(xml.attrib.activeSpec)))
   selects the spec the XML names. bridge.lua, its lockdown and the drift
   guard are unchanged; tests/test_tc_spec_follow.py checks that line of
   the pinned TreeTab.lua as text when the checkout is installed.
5. BuildStore.sync (tick_build, the core loop) re-picks when the level
   changes and returns "spec" when the spec in use moves; the listeners
   re-publish the build and re-score as for a reload. The build view
   carries `spec_follow` {index, title, by_level, level, pob_index}; the
   dashboard's tree line already names the title of the spec in use.
   Nothing is fetched, stored or run; no Lua is parsed.

## Alternatives

- A bridge `select_spec` command calling PoB's SetActiveSpec after the
  load: rejected, it widens bridge.lua and the drift guard for what PoB's
  own XML load already does.
- Nearest level above or below, or the Build level of the XML when the
  log has none: rejected as guesses.
- A spec picker on the dashboard: rejected (ZERO-CLICK; the row asks for
  none).

## Why

Guide exports carry one spec per levelling stage; following the level puts
the tree, link, download and calc numbers on the stage being played with no
click.

## Reverses if

PoB stops selecting the spec from `<Tree activeSpec>` at load (then a
bridge command through PoB's own SetActiveSpec), real guide exports title
specs in a shape the rule misreads (fixture first), players want PoB's
active spec kept (then a setting), or decision 0038's level source changes.
