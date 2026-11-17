# 0040 - Self checks and the non-English client notice

Date: 2026-11-17. Lane AREA-UTIL batch 12. Inputs: CLAUDE.md "Game ToS
floor", decisions 0003 (read policy), 0013 (web data), 0014 (clipboard
writes on a click), 0020 (zone table), research 0002 (live log facts),
research 0032 sections 3 to 6 with adjudicator rulings J and K, ROADMAP
rows DIAG-SELF and LANG-GUARD.

## Decision

1. DIAG-SELF (`server/al/diag.py`). The core builds one checks view every
   5 s from its loop (`Core.tick_diag`): Client.txt found, permission,
   reading, last log line age, character seen, game language, web data
   and contact, price book age and last fetch error, calc component
   installed and matching its pins (`calcwire.component_status`, lazy,
   only while the calc is on), build-time game data present and its age,
   overlay and keepalive alive (`procs.status`, no window scan), item
   check hotkey registered (read from AshLight's own overlay log, never
   "pressed"), dashboard address. Each check is pass / fail / unknown /
   off (and "note" for a non-English client: nothing to fix). Each fail
   carries one fix line naming an existing step (the consent button,
   `scripts\run.ps1`, `scripts\setup.ps1 -TcCalc`, `scripts\build.ps1
   -Snapshot`, the contact key). The dashboard "Checks" tool in the Tools
   card is folded to one summary line, opens itself when a check newly
   fails, and "Copy report" writes the core's plain-text report inside
   that click only. The report carries no path, user name, contact,
   character name, token or chat: details are written without them and
   `diag.redact` masks the repo, sidecar, home and Client.txt paths, the
   user name, contact, character name, any e-mail and any drive path. No
   network module is imported by diag.py (test).
2. LANG-GUARD (`server/al/langguard.py`). The row's signal ("You have
   entered" missing for 3 loads) cannot work: research 0002 found PoE2
   never writes that line, so every English player would see the notice.
   Replacement, ruled by the adjudicator 2026-11-17: a strike is a
   table-known `area_generated` whose next real `[SCENE]` name differs
   from the English zone name, or a system line (": " body, never chat,
   whisper or NPC text) holding a non-ASCII letter; English evidence is a
   matching scene name or an English system pattern (level-up, death,
   AFK / DND, joined / left, trade accepted / cancelled). 3 strikes in a
   row with no English evidence show the notice; evidence clears it and
   resets the count. Counter in memory only; the notice is hideable
   (browser storage, per notice start) and never says the client is
   broken; DIAG-SELF shows the same verdict; item.py's non-English item
   warning reuses its wording.

## Alternatives

- LANG-GUARD built as the row says: rejected, a false notice for every
  English player.
- Script check only: rejected, misses mostly-ASCII French, German,
  Spanish and Portuguese lines.
- Block LANG-GUARD until a localised log sample exists: rejected, the
  replacement is safe on English clients now.
- Report auto-upload or a "send report" button: floor-no (ruling J, a
  network call outside the web data opt-in).
- Probe the overlay window or the game process for the checks: floor-no
  (ruling J, passive checks only).

## Why

Every check is a local read the core already had; one place now answers
"is AshLight healthy, and what do I do if not" with no click. The
language notice turns silent half-working dashboards into one honest
sentence without guessing a translation.

## Reverses if

A localised Client.txt sample shows the LANG-GUARD signals misfire or stay
silent; the zone snapshot is dropped (decisions 0009, 0020); PoE2 starts
writing `You have entered`; decision 0003 or 0013 changes; or a report
field is found to leak a path or identifier.
