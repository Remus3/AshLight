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
