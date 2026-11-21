# 0071 - Parse ledger: masked log shapes under their own consent line

Date: 2026-11-20. Source: package RUN-METRICS-SITES (wave 15), which folds
RUN-LEDGER-CONSENT; finding F-061 (docs/plan/02-findings.md, 0051-R1 and
0051-Q1); research 0051 section "Design: the parse ledger"; the module
`server/al/logshapes.py` (RUN-LEDGER-CORE); decision 0003 (the Client.txt
opt-in); decision 0067 (AshLight records only its own behaviour). The
ledger's file writer at `Core.feed_line` lands with RUN-LEDGER-WIRE and
adds its detail here as a dated amendment.

## Decision

1. What the ledger is. Per-pattern hit counts (the event type and its
   sub-kind, the class of an area id and its act key, with first and last
   sighting) and masked shapes of lines no pattern understood, in one
   bounded file `ops/runtime/logshapes.json`. The mask is an allow-list,
   never a scrubber: a token survives only when it is one of about 80
   function and system words; every other token becomes a placeholder by
   form (`<n>`, `<addr>`, `<path>`, `<host>`, `<hex>`, `<w>`), and the
   name slots of the known templates become `<name>` first. Chat-like,
   speech-like, long and unprefixed lines are only counted, tag lines
   count their tag only. No raw line, character or account name, chat or
   item text is ever stored or sent.
2. Bounds. At most 200 shapes (least recently seen goes first, counted),
   64 tags and 100 verbatim area ids; the JSON text under 64 KB; times
   kept to the UTC hour; a shape may enter a report only after two
   sightings at least 60 s apart.
3. Its own consent line. The ledger is persisted only while the "ledger"
   key of `ops/runtime/consent.json` holds `{"consented": true, ...}`
   (with the time, the file name and what it keeps). The Client.txt
   opt-in never implies it: both persisted parts (hit counts and shapes)
   wait for this line (the stricter reading of 0051-Q1). The in-memory
   class counters and the drift counter need no extra consent: they run
   under the Client.txt opt-in and are never written.
4. The API. `POST /api/consent` takes `{"ledger": true|false}`, alone or
   after `"consent"` in one body, behind the same token, Host and Origin
   checks as every `/api/` route; a non-bool is a 400 and nothing
   changes. The snapshot's `tailer` block carries `ledger` (a bool), so
   the dashboard paints the line from the state it already receives.
5. The dashboard line. One line in the footer, beside the Client.txt
   opt-out, shown only while Client.txt is read: "Log record: off. When
   on, AshLight counts the kinds of log lines it reads and keeps their
   shapes on this computer. Names, chat and item words are blanked out.
   Nothing is sent." with its own button "Allow the log record"; when on,
   "Log record: on. ..." with "Stop the log record" and "Stopping it
   deletes the file." One click, once, outside play; nothing in play.
6. Revoking. Revoking the ledger line deletes `ops/runtime/logshapes.json`
   (and a `.bak` of it). Revoking the Client.txt opt-in also turns the
   ledger off and deletes the file; allowing Client.txt again does not
   bring the ledger back.

## Choices the package text left open (ruled by the builder)

- The ledger can be allowed only while the Client.txt opt-in is on
  (otherwise a 400 and nothing is recorded). Alternatives: record the
  flag at any time and let it wait for the Client.txt opt-in. Why: a
  flag given before any reading is a consent to something the player
  cannot see yet; the line is shown only while reading, so the click
  path never meets the refusal. Reverses if: players are seen to want
  the record armed before the first read.
- Revoking the Client.txt opt-in revokes the ledger too. Alternatives:
  keep the ledger key and resume it with the next Client.txt opt-in.
  Why: the ledger is derived from the log; withdrawing the log consent
  withdraws what was derived from it, and a later opt-in asks again.
  Reverses if: the operator rules the two opt-ins fully independent.
- The player-facing name is "log record", not "parse ledger".
  Alternatives: "parse ledger", "log notes". Why: design 0001 section 8
  (the player's words, no internal names). Reverses if: the design
  review asks for another name.
- The line lives in the footer next to the Client.txt opt-out, not in
  the setup card's opt-in row. Alternatives: a second button on region
  C's setup card (web/setupcard.js). Why: the setup card is gone once
  reading starts and is outside this package's files; the footer holds
  the Client.txt consent control on every tab. Reverses if:
  PLAY-TD-21A-SETTINGS-RAIL moves the Client.txt controls (then this
  line moves with them).
- The deletion is a direct unlink, not the Recycle Bin. Alternatives: a
  Recycle Bin move. Why: the player asked for the record to be gone; a
  copy in the Recycle Bin keeps what they withdrew, and the file is
  AshLight's own replaceable derived data. Reverses if: the operator
  rules otherwise.

## Alternatives

- Fold the ledger into the Client.txt opt-in (its `derives` list):
  rejected by 0051-Q1's stricter reading; GGG's user-aware rule and the
  privacy classes of research 0051 want an explicit, separate yes.
- A scrubber that removes known name shapes: rejected; an allow-list
  cannot leak a token it does not know, a scrubber can.
- No persisted ledger, in-memory counters only: rejected; the drift
  check across sessions and the live-1 report need the hit history.

## Why

The ledger closes the "which log lines does AshLight not understand"
gap (F-061) without ever storing what a player wrote: only allow-list
words and placeholders reach the disk, only after the player allows it
on its own line, and the file goes when they stop it. Checked by
tests/test_ledger_consent.py, tests/test_logshapes.py and
app/test/dashboard.test.js.

## Reverses if

A mask gap stores a name or a chat word, GGG restricts derived local
records, or the operator rules the ledger unwanted.

## Amendment 2026-11-20 (RUN-LEDGER-WIRE, recorded by the wave 16 integrator)

The writer landed as server/al/plug/ledger.py (decision 0056 seam).
Core.feed_line feeds every tailed line; class and drift counters run under
the Client.txt opt-in, in memory only, never written. Hit counts, masked
shapes, five read-back booleans (zone, character, level, act, session
timer) and up to 4 masked waystone property-block shapes from item presses
(known property keys kept in lower case, every other key and every value
through the allow-list mask; at most 12 lines each, LRU) are kept only
while the ledger consent is on. ops/runtime/logshapes.json is written at
most once a minute and only when something changed; a write and the
revoke-delete share core.ledger_lock, and a revoke also empties the
in-memory ledger. Two "Game log" Checks notes: 3 anchored misses in one
game run (kept for the life of the core), and a resume scan stopped at its
32 MB cap before the session start. Reverses if: the once-a-minute write
costs overlay budget, the sticky drift note misfires in normal play, or a
waystone key outside the known list proves to hold player text.
