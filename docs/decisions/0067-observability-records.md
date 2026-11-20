# 0067 - Observability records: AshLight records only its own behaviour

Date: 2026-11-19. Source: package RUN-METRICS-CORE (wave 13); finding
F-032 (docs/plan/02-findings.md, OBS-COUNTERS and BUDGET-LOG); decision
0006 method 3 (AshLight's own process counters); decision 0029 (no
process-list check for the game); decision 0040 (DIAG-SELF, the Checks
class of self-diagnostics); decision 0056 (RUN-SEAMS, the plug folder).
This one file covers the four observability records of the plan: the
counters (this package), the budget log (RUN-BUDGET-LOG-CORE /
-CLIENT), the typed event log (RUN-OPLOG, folded into
RUN-START-REASON-CORE) and the report (RUN-REPORT-FIELDS). Each later
package adds its own detail here as a dated amendment.

## Decision

1. Scope. AshLight records only its own behaviour: its own counters,
   its own processes' footprint, its own typed events and a report the
   player asks for. Never the game process or window (nothing listed,
   opened or measured), no Client.txt text, no path, character or
   account name, chat or item text, no pid, nothing uploaded. The
   records are a Checks-class self-diagnostic (decision 0040), not the
   on / off FPS measurement of decision 0006 item 4.
2. Counters (`server/al/metrics.py`). In-memory only: counters, gauges
   and timing rings (the last 64 values of a name). Names are short code
   constants (a lower-case word with `. _ - : / * |` and digits); another
   shape raises, and past 512 names per kind a new name is refused and
   counted in `metrics.dropped`, so the store stays bounded. One process
   registry (`metrics.REGISTRY`) with module-level shortcuts (`inc`,
   `set_gauge`, `add_gauge`, `timing`, `emit`, `subscribe`). Nothing is
   written to a file or put in the state snapshot.
3. Typed events. `metrics.emit(kind, **fields)` counts `emit|<kind>` and
   hands `{"kind", "t", **fields}` to each subscriber (the later event
   log subscribes). A field is a bool, int, float, None or a WORD: a
   lower-case token with no space, slash or backslash, at most 64
   characters (a host from the allow-list, a status class). No free-text
   field type exists, so no path, name, chat or item text can travel
   through it. A subscriber that raises is counted and skipped.
4. GET /api/debug (`server/al/plug/debug.py`, a plug route of decision
   0056). Token-gated like every `/api/` path (the hello proof and
   `?token=` open it not), GET only, pull only: never in the snapshot,
   never in an SSE frame. The body is JSON under 4096 bytes: version,
   own uptime, own process (working set MB, CPU seconds, thread count,
   read through its own process handle only), the tailer's lines, bytes,
   resets, dropped lines and running flag (read at request time), lines
   fed / ignored / failed, bus events by type plus those parsed from
   Client.txt, SSE subscribers / frames / bytes, HTTP replies by route
   key and status class plus the 401 count, the core loop's age and
   each tick's last ms, the timing rings (n, last, p50, max) and other
   counters. Every key is a code constant and every value a number,
   bool or null. When the body would reach 4096 bytes the detail parts
   are dropped in a fixed order (other counters, timings, tick ms, HTTP
   replies, events) and `trimmed` names them.
5. Where counting happens. `http.Handler._send` counts each reply as
   `http|<route>|<class>` (the route a table key, a plug route path or
   `other`, never request text) and the 401s; `_sse_write` counts frames
   and bytes; the debug plug's attach adds a bus listener (events by
   type) and wraps `core.feed_line` (lines fed, ignored, failed), and a
   `tick_metrics` core tick adds each loop pass's total tick ms to the
   `loop_ms` ring. The invariant: tailer lines = Client.txt events +
   ignored + failed.
6. Later records (detail lands with their packages, as amendments):
   the budget log is one row a minute of AshLight's own processes in a
   1 MB capped file under the sidecar Logs dir; the event log writes
   typed events only (no free-text field), bounded; the report is built
   on the player's click from an allow-list of fields, log tails only as
   an explicit second choice through the redactor.

## Choices the package text left open (ruled by the builder)

- One process registry, not one per core. Alternatives: a registry per
  Core instance passed to http.py. Why: emit call sites (fetch, calc
  bridge, press) have no core handle, and production runs one core per
  process; tests reset the registry. Reverses if: one process runs two
  cores outside tests.
- Lines fed / ignored are counted by wrapping `core.feed_line` from the
  plug's attach (an instance attribute the tailer takes when it starts),
  not by editing core.py. Alternatives: derive ignored as lines minus
  events (then the invariant proves nothing); edit core.py (outside the
  package files, and RUN-LEDGER-WIRE edits feed_line later). Why: an
  independent count makes `lines = events + ignored + failed` a real
  check. Reverses if: RUN-LEDGER-WIRE moves the counting into feed_line.
- A WORD field type in emit. Alternatives: numbers and bools only. Why:
  RUN-METRICS-SITES needs a host from the allow-list and a status class;
  a WORD cannot hold a path (no slash or backslash), a sentence (no
  space) or a mixed-case name. Reverses if: a WORD field is found to
  carry a name or other player text.
- Thread count is the live Python thread count, not the OS thread
  count. Alternatives: a toolhelp thread snapshot. Why: a toolhelp
  snapshot enumerates every process's threads, which is more than the
  own-handle rule allows. Reverses if: an own-handle OS thread count
  is needed and found.
- Size cap by shedding detail parts in a fixed order, plus top-N lists
  (24 event types, 16 routes, 16 other counters, the rest summed as
  `other`). Alternatives: truncating the JSON text; paging. Why: a
  pull-only probe wants one valid document every time. Reverses if:
  a consumer needs a part that is shed in normal use.
- The working set read is the own process only: `GetProcessMemoryInfo`
  on the `GetCurrentProcess` pseudo handle on Windows, `/proc/self/statm`
  elsewhere, else null.

## Alternatives

- Counters in the state snapshot: rejected, the snapshot reaches the
  overlay and dashboard on every push and must stay small (decision 0002
  budgets); the debug view is a pull for a probe or a developer.
- A metrics file written on a timer: rejected for the counters; the
  bounded budget log (point 6) is the one timed record.
- An OS-wide process view (process list, performance counters of other
  processes): rejected by decisions 0006 and 0029.

## Why

The plan closes OVL-BUDGET and the reader / feed checks with no operator
session (F-032): AshLight's own numbers are enough, and keeping them to
code constants and numbers means the debug view, the event log and the
report cannot leak a path, name or text even when copied into an issue.
Checked by tests/test_metrics.py, tests/test_security_surface.py and
tests/test_http_security.py.

## Reverses if

A record is found to hold a path, name, chat or item text, the sampler
costs overlay budget, or GGG restricts derived local records.
