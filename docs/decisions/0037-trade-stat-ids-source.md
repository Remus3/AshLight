# 0037 - Trade stat ids from the repoe-fork snapshot (TC-UPGRADE-STATS)

Date: 2026-11-17. Trigger: ROADMAP row TC-UPGRADE-STATS (decision 0017
item 3). Evidence: research 0030. Ruled by a distinct adjudicator agent
(FLEET item 1). Supersedes the unmerged lane draft "0022 - no permitted
source yet" (commit 7aa228c), which had no web access; its item 2 already
allowed a third-party table as a decision 0009 snapshot after a provenance
check, and research 0030 is that check.

## Decision

Use the `trade_stats` ids in the repoe-fork `stat_translations` snapshot
(a decision 0009 source, fetched at build time into the sidecar cache, only
with web_data on, decision 0013) to add one weighted stat group to the
offline upgrade-search `?q=` URL (decision 0017). Conditions:

1. Read ids only from the sidecar cache copy (`server/al/tradestats.py`).
   No bundled table, excerpt or derived id list in the repo; no new fetch
   host.
2. Ids are used only inside the offline URL builder
   (`trade.upgrade_query`). No trade endpoint call at runtime or build
   time, no validation of ids against the trade site.
3. A stat with no id, a missing snapshot, or web_data off gives no filter
   for it. No guessed id, no fallback to another source.
4. The attribution says the stat ids come from Grinding Gear Games' trade
   site data (`datacredit.ATTRIBUTION`); the non-affiliation line stays.
5. A test fails if any app code names a trade data / API URL other than
   the refusal check (`tests/test_tc_upgrade_stats.py`).

## Alternatives

- PoB-PoE2 `TradeSiteStats.lua` / `QueryMods.lua`: same provenance (a dump
  of `/api/trade2/data/stats`), but a second, unvetted source and a Lua
  parse. Rejected; needs its own 0009 check if ever wanted.
- Record "no permitted source": safe, but forfeits mod filters for a small
  risk. Kept as the fallback if this decision reverses.
- Call `/api/trade2/data/stats` from AshLight (runtime or build): barred
  by ToU 7i and decision 0017.

## Why

No GGG source exists (API Reference and Data Exports, read 2026-11-17).
AshLight never contacts the trade site; the ids are GGG-owned data in a file
already accepted under 0009, and they only shape a URL the user opens in
their own browser. repoe-fork's build-time request is its own conduct. The
change is small to undo and nothing is bundled.

## Reverses if

GGG states that third-party use of trade stat ids is not permitted,
repoe-fork drops the `trade_stats` field, the repoe-fork data license is
found to forbid this use, or the operator rules otherwise.

## Amendment 2026-11-17 - PoB-PoE2 fallback (MATH-TRADESTAT-POB)

Trigger: research 0030 section 6 (repoe-fork gives ids for only 11 of 39
default weights). Ruled YES by a distinct adjudicator agent (FLEET item 1).
Record, verbatim:

> A read-only fallback to PoB-PoE2 src/Data/TradeSiteStats.lua is allowed
> ONLY when the optional calc component (0018) is installed and the file
> hash matches config/tc_pins.json. It fills only keys repoe-fork lacks, by
> exact tradestats.norm match, through a bounded stdlib text parser (never
> run as Lua). Nothing is bundled, tests use a self-made fixture, and
> datacredit.py names PoB-PoE2 (MIT) and GGG as data owner. Vetting: 0 id
> conflicts on the overlapping keys (coverage 11/39 -> 39/39) and the hash
> pin. This is the 0009 check the Alternatives section required. Same
> GGG-owned data as repoe-fork; AshLight calls no trade endpoint (0017).

This amends item 3 ("no fallback to another source") and replaces the PoB
line under Alternatives. Checks behind the ruling: the checkout's
LICENSE.md opens with PoB's MIT grant (the file itself says "Game data (c)
Grinding Gear Games" and names the trade2 stats endpoint as its origin, so
MIT covers PoB's format and code, the ids stay GGG data exactly as under
this decision); ToU 7i concerns the conduct of whoever calls an undocumented
endpoint, and AshLight still calls none, validates nothing, and only shapes
the offline URL. Alternatives: keep 11/39 (zero risk, 28 keys unfiltered);
author ids by hand (bundles GGG data, barred by 0009).

Implementation: `server/al/tradestats.py` (`parse_pob_trade_stats`,
`load_pob_index`, `merge`, `IndexCache(pob=...)`), wired in core only for the
real runtime. The file is used only when the checkout's `.al-extracted.json`
names the pinned archive sha256 AND the file's sha256 equals
`pob2_files["src/Data/TradeSiteStats.lua"].sha256` in config/tc_pins.json
(outside the setup pin digest, so no re-fetch); size cap 8 MB, 400000
lines; a value with a Lua escape is skipped. repoe-fork wins a conflict,
logged. Guard: tests/test_tc_pob_drift_guard.py (presence, shape, hash).

Reverses if: PoB relicenses or its file header disclaims reuse, a real id
conflict with repoe-fork appears, GGG rules against relaying trade2-derived
data, repoe-fork gains full coverage (then the fallback is dead weight), or
the operator rules otherwise.
