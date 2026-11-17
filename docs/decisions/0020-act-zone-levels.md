# 0020 - HUD-ACT: act splits from the log, zone levels from repoe-fork world_areas

Date: 2026-11-17. Trigger: ROADMAP row HUD-ACT ("act / zone level table
from an attributed build-time data snapshot (license checked first,
research 0005); zone timer splits per act"). Inputs: decision 0009 (and
its DATA-LICENSE-VERIFY results, research 0011), decision 0013, research
0002 section 7, research 0005 section "Act / zone levels (HUD-ACT)". No
adjudicator was needed: both parts apply existing rulings, no new fork.
Number check: main held 0001-0019 and no worktree held a 0020 at write
time; renumber at merge if a sibling branch also took 0020.

## Decision

1. Splits need no data. The core derives the act from the area id of
   `Generating level N area "<id>"` (`G<n>_` Act n, verified live for G1_1
   and G1_town; `C_G<n>_` Cruel Act n and `P<n>_` Interlude n inferred, not
   yet seen live; `Map...` ends the campaign). `server/al/acts.py` folds
   them into per-act splits (first entry into a new act opens its split;
   going back to an old act keeps counting into the current one; G1_1 at
   player level 2 or less starts a new run; a run that did not start at
   G1_1 marks its first split partial). Published in the state snapshot as
   `acts`; the dashboard's "Act times" card shows act, time in act and
   total. Receipt times; a core restart starts an empty run (no persisted
   state, as decision 0008).
2. Zone levels come from repoe-fork's PoE2 `world_areas.json`
   (https://repoe-fork.github.io/poe2/world_areas.json), added to the
   decision 0009 item 2 file list as source `world_areas` in
   `server/al/theorycraft/snapshot.py`. Same source, same terms, same
   conditions as the four files already ruled: the repoe-fork code is MIT
   and the data is GGG-owned (research 0011 lines 1-3); fetched only by the
   build-time snapshot on the user's machine into
   `<sidecar>\Cache\gamedata\world_areas.json`, with the manifest, the
   conditional request, the 24 h minimum age, the https host allowlist and
   the truthful User-Agent; never committed, never bundled, never
   redistributed. Nothing from the file is in the tracked tree (the tests
   use a hand-written tmp_path stand-in with our own field values).
3. The core only READS the cache (`acts.TableCache`, at start; a missing
   file means no level table and the card says so). No runtime fetch, so
   the decision 0013 `web_data` opt-in is untouched: with web data off,
   nothing goes on the network at run time, exactly as before. The
   build-time fetch keeps the decision 0009 opt-out (`AL_NO_SNAPSHOT`).
4. Attribution: `acts.ATTRIBUTION` ("Zone levels from the RePoE fork
   community export (repoe-fork), downloaded to this computer at build
   time. Game data (c) Grinding Gear Games.") is shown under the zone level
   table whenever the table is shown (decision 0009 item 2 "wherever the
   data is used"). The general snapshot ATTRIBUTION text is left to
   TC-SNAP-UI (a parallel row owns the footer / About line).
5. Shape relied on (checked 2026-11-17 against the hosted file): an object
   keyed by area id; per area `name`, `area_level`, `is_town` (also `act`,
   `has_waypoint`, `connections` and more, unused). Rows: campaign ids only,
   a name seen twice in one act keeps its lowest level, sorted by level then
   name, at most 40 per act, `area_level` < 1 or non-int skipped (the
   `NULL` placeholder entry has 0).

## Alternatives

- poe2db or the PoE2 wiki act tables: rejected (decision 0009 item 4:
  CC BY-NC-SA 3.0, no sanctioned API, bot walls).
- A hand-typed level table in the repo: rejected; it is a derived table of
  GGG data, which decision 0009 item 1 forbids committing.
- Use the file's own `act` field instead of the id prefix: not taken for
  the split key (the prefix is what the live log shows and needs no data,
  so splits work without the cache); may be revisited once interlude / cruel
  ids are seen live (LIVE-1).
- Persist splits across a core restart: deferred (decision 0008 keeps the
  core stateless; a backward scan of area-generation lines with their line
  timestamps is a possible follow-up, HUD-ACT-RESUME).

## Why

The splits use only what the core already reads. The level table uses the
one source decision 0009 already cleared for build-time, cache-only use,
under its existing conditions; adding a file from the same export is the
same act the ruling already permits.

## Reverses if

- Decision 0009 reverses for repoe-fork (license or GGG objection): drop
  the `world_areas` source; the splits stay.
- Live logs show cruel / interlude ids that do not match the inferred
  prefixes: fix `acts.act_of` (LIVE-1 fixture first).
- repoe-fork renames or reshapes `world_areas.json`: the table reads as
  missing (never an error) until the reader is fixed.
