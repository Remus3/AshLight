# 0041 - Live zone guide and quest tracker

Date: 2026-11-17. Row ZONE-GUIDE. Inputs: CLAUDE.md "Game ToS floor",
decisions 0003 (read policy), 0009 (no bundled game data), 0020 (zone
table from the world_areas snapshot), 0030 (own zone notes), 0036 (bounded
local history files), 0038 (per-character keying), research 0033 (live
character data; world_areas connections / waypoint fields) and research
0034 (zone guide facts).

## Decision

1. PoE2 zone layouts are random per instance, so "optimal pathing" is
   per-zone guidance, not a drawn route. On every zone change the core
   publishes `zone_guide` in the snapshot (server/al/zoneguide.py); the
   dashboard fills `#zone-guide` (web/zoneguide.js; through
   `ALTabs.fill(document, "zone-guide", node)` when the Play tab provides
   that slot). Zone, goal, first bonus, level lean, waypoint and next zone
   always show; the rest folds under "More for this zone" so the Play tab
   stays short. Zero clicks.
2. Guide content lives in the tracked file
   `server/al/data/zone_guide.json`, keyed by act key and the zone name the
   `[SCENE]` line gives (the same keys as zone_notes.json): objective,
   optional content with a permanent reward (kind + text), a layout
   tendency, and the next zone on the main path. All of it is AshLight's
   own short wording. Public sources (research 0034) were read for facts
   only; no sentence is copied, and the wiki / poe2db pages are CC BY-NC-SA,
   so nothing of theirs is redistributed. A fact we could not confirm is
   left out, never guessed. Endgame maps get one generic entry.
3. Waypoint facts come from the cached world_areas snapshot
   (`has_waypoint`, `is_town`, `connections`; decision 0020, read only,
   never fetched here): "Waypoint in this zone" or the nearest waypoint by
   a breadth-first walk of the connections (at most 6 hops). Without the
   snapshot the line is simply absent.
4. Clear-or-push lean: the log's area level (else the snapshot's) against
   the character's level. More than 2 levels under: clear fully. Over by
   more than 3 + level / 16 (the usual experience-penalty band): push to
   the exit. Otherwise "fits". This is AshLight's heuristic, not a game
   formula we verified.
5. Quest tracker, per character (decision 0038 keys; visits before the
   name is known join the character once named): the zones the character
   entered, from the already tailed `[SCENE]` lines with the act from the
   area generation id. A main-path step is done once the zone after it was
   entered. A bonus reward counts only as "zone visited" or "skipped" (its
   zone never entered, and the character has entered a later act). The log
   never says a reward was taken, so AshLight never claims it was. No NPC
   or quest line is parsed (none is verified in a PoE2 log).
6. Visited zones persist in one bounded runtime file
   (`zone_visits.json`: 12 characters, 16 acts, 48 zones each), written
   only while run history is on and emptied by the same Clear button
   (decision 0036). LIVE-RESUME still rebuilds the current game run's
   visits from Client.txt (decision 0008 untouched).
7. Hot reload: the core stats the guide file (and the snapshot) once per
   loop tick and re-reads it only on a new mtime / size.
8. Overlay: it has no zone-notes slot today, so the guide is dashboard
   only; the view carries a 120-character `line` for a future overlay slot
   under the overlay budgets.

9. Design review (design-reviewer, 2026-11-17): PASS WITH FINDINGS; ZG-1
   to ZG-10 applied (steps read "zones passed", a step back to a hub town
   counts on its own zone, the act's last step counts on the next act's
   zone, Act 4 is any order; bonus rows lead with the reward under one
   "Bonus:" label; "not entered yet" instead of "skipped"; "AshLight can't
   see pickups"). ZG-11: the imperative is the guide's register, kept.

## Alternatives

- Draw a route on a map: impossible without reading the game (layouts are
  per instance; screen capture without a press is barred).
- Parse NPC / quest dialogue lines: not verified to exist in PoE2's
  Client.txt; rejected until a live sample shows them (LIVE-1).
- Copy a wiki walkthrough: licence (CC BY-NC-SA) and decision 0009 bar it.
- Key by area id: the scene name is what zone_notes already uses and what
  the log names; the area id is used only for the act and waypoint graph.

## Why

The player gets what to do here, what is worth a detour and whether to
clear, the moment a zone loads, from data already read, with no new read
of the game and no copied text.

## Reverses if

GGG's tool rules change, a source's licence objection appears, a live log
shows quest / NPC lines worth tracking (then mark steps from them), or the
operator rules the visits file unwanted.
