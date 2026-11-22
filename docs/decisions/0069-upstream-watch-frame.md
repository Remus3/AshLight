# 0069 - Upstream watcher frame

Date: 2026-11-19. Source: package AUTO-05 (WATCH-CORE, wave 13); unit
F-030 (docs/plan/02-findings.md); docs/plan/06-automation.md "The watcher
frame (F-030)" and "Decisions"; rulings Q-12 and Q-13; decisions 0009,
0013, 0025, 0044, 0050; the web-data gate of LOOP-WATCH-GATE
(tools/watch_gate.py).

## Decision

One tool and one state file run every upstream source on the dev loop.

1. Registry. `tools/upstream_watch.py` discovers one source per file of
   `tools/watch_sources/` (file-name order; a file starting with `_` is
   skipped). A source module exposes `SOURCE = {name, home, cadence_s,
   window, needs_web_data, hosts, urls, check}` (contract in
   `tools/watch_sources/__init__.py`); `check(state, now, fetch, ctx)`
   returns typed findings `{source, kind, key, tokens}`. A file that does
   not import, breaks the contract or repeats a name is skipped with one
   tick line; the rest still run.
2. Scheduling: `run_due(root, now, halted=False, fetch=None,
   directory=None, ctx=None)`, sources of home `loop` or `both` only.
   Local sources (hosts and urls empty) and the two settled sources
   (`needs_web_data` false: the docs watch, decision 0044, and the PoB
   release check, decision 0025) run whenever due, every one of them.
   Every other source is a network source: at most one runs per tick, the
   oldest due first (never run first, then the oldest `last_run`, then
   file-name order), with at most 2 requests and a 10 s timeout per
   request. A source is due when `cadence_s` (0 = every tick) has passed
   since `last_run`; inside a dated window (`{from, to, cadence_s}`, local
   dates, inclusive) the window's cadence applies.
3. Web-data gate. Every request of every source goes through
   `watch_gate.fetch` (LOOP-WATCH-GATE): the opt-in read at call time,
   repository metadata through the documented GitHub API or an exact URL
   the source lists, `webfetch.user_agent(<purpose>)`, no cookie; the
   frame also refuses a host the source does not list. While `web_data`
   is off a gated network source is not called at all (0 requests) and
   its state reads `idle: web data off`; a source whose fetch raises
   `WebDataOff` reads the same. Idle is never a failure. A local source's
   fetch refuses every URL.
4. State: `ops/runtime/watch/state.json` `{sources: {<name>: {last_run,
   last_ok, fails, etag, seen, idle, cause, data}}}`. A good run sets
   `last_ok`, clears `fails`, `cause` and `idle`, and keeps the check's
   changes to `etag` and `data`; a failed run adds one to `fails`, names
   the `cause` and keeps `last_ok`, `etag` and `data`.
5. Findings: `ops/runtime/watch/pending.json` `{findings: [{source, kind,
   key, tokens, found}]}`. A finding is queued once per (source, key) for
   all time (`seen`); a malformed finding is dropped with one tick line;
   the frame stamps the source name itself.
6. HALT (Q-13): a HALTed run still reads and queues; the frame never files
   a row (that is tools/watch_file.py, which does not file while HALT
   exists) and prints one line naming the queued count.
7. `request_dive(root, topic, urls)` writes
   `ops/runtime/watch/dive_request.json` `{topic, urls, at}` only when every
   URL passes the dive allow-list of tools/webfetch.py (decision 0050).
   docs/plan/06 named `ops/loop/control/dive_request.json`; it moved under
   `ops/runtime/watch/` so the test guard of tests/conftest.py needs no new
   ignore line.
8. CLI: `python tools/upstream_watch.py run` (one pass now, HALT read from
   the root) and `status` (one line per source). Writes are atomic
   (`loop_base.atomic_write`, ASCII) until the hardened write path of
   F-014 exists. A watcher is plain Python and costs 0 headless runs.

## Choices the package text left open (ruled)

- Failure cause. The state record carries one extra key, `cause` (one of
  network, status, shape, rate-limit, workflow), so the watch-health
  source (AUTO-08) can fill its `<cause>` token without re-running the
  source. `SourceError(cause)` lets a source name it; a fetch error or
  OSError reads `network`; any other exception reads `shape`; HTTP 429 and
  503 raise `SourceError("rate-limit")` inside the frame's fetch, so no
  source has to remember to stop. Other statuses go back to the source
  (a moved endpoint is the source's own finding). Alternatives: no cause
  (health cannot word its row); a cause per tick line only (lost on the
  next tick).
- Settled sources and the gate. `needs_web_data` false only exempts a
  source from the up-front skip and from the one-network-source count;
  its frame fetch still goes through `watch_gate.fetch` and so still
  stops while web data is off. The two settled reads keep their own
  request paths through ctx (LOOP-WATCH-SETTLED). Alternative: an
  ungated frame fetch for them (it would open a request path around the
  gate that only the two settled tools need, and they do not use it).
  Stricter reading wins.
- Local sources obey `cadence_s` too (0 by default, so they run each
  tick); a daily local check sets its cadence. Alternative: ignore
  cadence for local sources (a daily check would have to keep its own
  clock).
- Idle bookkeeping. A gated source idled by the gate keeps its
  `last_run`, so it is due at once when web data turns on; the idle line
  is printed once when the state changes, not every tick.
- `seen` is unbounded per source ("for all time"); keys are short and
  sources file at most a few a week.
- `request_dive` takes an optional `now` beside the three named
  arguments, for a fake clock in tests.
- Home `ci` sources do not run on the loop; the CI failover belongs to
  LOOP-CI-ISSUES and AUTO-19.

## Alternatives

- One tool per source: three or more state files and three silent
  failure modes; each source repeats the gate and the throttle.
- Watchers in the shipped core: decision 0044 rejected it; the core keeps
  only its own player-facing refreshes under the web-data opt-in.
- CI reading poe.ninja or a GGG host: needless traffic, outside the floor
  reading of docs/plan/06.
- Row text written by a source: upstream text could enter ROADMAP rows;
  rows come only from tracked templates (LOOP-WATCH-ROWS).

## Why

One frame makes each source about 30 lines and lets one health check
cover every source. One gate in front of every request keeps the web-data
opt-in and the metadata-only rule in one place, and the one-network-source
rule keeps the tick under its 60 s target.

## Reverses if

A source's owner asks tools not to read it automatically, the
metadata-only rule hides a break that only a data read shows, or the
operator exempts a source from the web-data gate in writing.

## Amendment 2026-11-21

Amended 2026-11-21 (LOOP-CI-ISSUES, adjudicator ruling): METADATA_TAILS gains
/issues, /actions/workflows/watch.yml and /actions/workflows/watch.yml/runs,
read-only repository metadata on api.github.com for the CI issue protocol
(decision 0076 item 6); other /actions/ and /issues/ sub-paths stay refused.
Reverses if: GitHub treats these as non-metadata, or the operator limits
watchers to the earlier tails.
