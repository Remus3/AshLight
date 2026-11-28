# 0091 - Augment data from PoB-PoE2 ModRunes.lua, read as text

Date: 2026-11-27. Status: ruled by an adjudicator agent the same day
(row DATA-AUGMENT-POB-TEXT). Input: research 0065 (augment data
source), which found no permitted source among the cached repoe-fork
snapshots and named one candidate outside that route. Amends, by
reference, decision 0037 and its 2026-11-17 amendment (MATH-TRADESTAT-POB),
decision 0083 point 3 (ITEM-INFO-POB-TEXT) and the KINDLER-GEM-VARIANT
entry of decision 0081: one more pinned PoB-PoE2 data file, read the same
way.

## Decision

1. `src/Data/ModRunes.lua` of the pinned Path of Building PoE2 checkout
   is an admitted source, under the same conditions as TradeSiteStats.lua,
   WorldAreas.lua, the Uniques files and Gems.lua:
   - it has its own config/tc_pins.json "pob2_files" entry {sha256, size,
     commit} (commit 7d6f530cbdab20389ff8bc6ba97a37ac27f74e41, 188915
     bytes, sha256 85d5f1d2...a6fb387, read 2026-11-27 from the sidecar
     checkout);
   - it is read only while the checkout marker names the pinned archive
     sha256 and the file matches its entry, so only while the optional
     calc component (decision 0018) is installed;
   - it is read as text by a line scanner,
     server/al/theorycraft/pobtext.py load_augments / Augments, and never
     run as Lua; capped at 1 MB; parsed once per pin and kept in memory.
2. What is read, per augment name and per slot key: type, the stat line
   strings, statOrder, tradeHashes, isSocketBound and rank. A slot block
   that is not exactly that shape, an augment with no slot left, or a
   name given twice is left out. Nothing is guessed. A missing file, a
   missing pin, a sha256 mismatch or a wrong marker gives no rows.
3. Use: augment effect, value and slot lookup only. The tradeHashes
   numbers are used only as the `rune.stat_<n>` trade ids of decision
   0037. No price, no trade2 call (decision 0017), nothing sent anywhere.
4. repoe-fork wins any conflict: a caller takes names, item classes and
   trade ids from the repoe-fork snapshots first and uses these rows only
   where they agree or repoe-fork is silent.
5. Credit follows decision 0083: the source id `path-of-building`, "Path
   of Building (MIT), community-written, may be out of date", wherever a
   row reaches the player.
6. tests/test_tc_pob_drift_guard.py checks the entry on every run and the
   file's hash and parse (287 augments at this pin) when the checkout is
   present; tools/tc_drift.py re-hashes it on a pin move like every other
   pob2_files entry.

## Alternatives

- Stay blocked (TC-AUGMENT-WHATIF waits for repoe-fork to publish the
  augment to stat join): rejected; the data exists in an MIT source the
  tree already pins and reads the same way, and no repoe-fork date is
  known.
- Build an own rule table from the base_items description text
  ("Place into an empty Augment Socket in a Helmet ..."): rejected; the
  text gives the slot but not the stat or value, so the table would be a
  guess (decision 0037: a missing id means no filter, never guessed).
- Pin the file with no decision: rejected; every PoB data file AshLight
  reads has a recorded ruling (decisions 0037, 0083, 0081), and the use
  limits (no price, ids only per 0037) need a record.

## Why

Research 0065 section 4: ModRunes.lua holds exactly the join the cached
repoe-fork files lack (287 augments, 20 slot keys, the tradeHashes are the
same numbers as the rune.stat_<n> trade ids), in a file generated from
game data under PoB's MIT licence. Augment what-if ranking is a PoB calc
stage, so it runs only while the calc component is installed anyway; the
pin and marker conditions add no new state for the player.

## Reverses if

PoB relicenses, or drops or reshapes ModRunes.lua; repoe-fork publishes
the augment to stat join (then repoe-fork alone); GGG objects to the
relay; a real augment line proves wrong in play; or the operator rules
otherwise.
