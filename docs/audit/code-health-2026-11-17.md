# Code health pass (AREA-TEST batch 6, 2026-11-17)

Behaviour-preserving pass after the ~40 feature branches that landed on
2026-11-17. Base: main at 40955c3. Method: `wc -l`, an AST scan for long
and unreferenced functions, an AST-hash scan for identical test bodies and
test helpers, grep for repeated file / number helpers, and the stdlib trace
coverage of `tools/cover.py`.

## 1. Measurements

### Largest modules (lines, before)

- server/al/state.py: 1550
- web/app.js: 1146
- server/al/http.py: 790
- server/al/core.py: 671
- server/al/theorycraft/item.py: 456
- server/al/ninja.py: 445
- server/al/keepalive.py: 422
- server/al/theorycraft/bridge.py: 399
- server/al/theorycraft/evaluate.py: 350
- server/al/logfile.py: 346
- Total server/ + web/: 17773

### Functions over 80 lines

- server/al/state.py:1145 SessionState._apply_locked: 144 (the event
  dispatcher; one if / elif arm per event type)
- server/al/core.py:61 Core.__init__: 119 (wiring of every sub-service)
- server/al/__main__.py:116 main: 108
- server/al/resume.py:106 scan: 99
- server/al/state.py:747 SessionState.__init__: 89 (field defaults)
- server/al/http.py:219 Handler.do_GET: 82 (route table)

None was split: each is a flat dispatcher or wiring list whose length is
its number of cases, and a split would move code without removing any.

### Duplicated helpers

- Atomic JSON / text write (mkdir, `<name>.tmp`, ASCII + LF, os.replace):
  11 copies, in pricebook, ninja, pricewatch, runhistory, summary, layout,
  theorycraft/weights, theorycraft/store, theorycraft/snapshot, core
  (write_private, 0600 mode), procs / keepalive / __main__ (pid, state,
  heartbeat files).
- Tolerant JSON read (missing / corrupt / wrong type / oversized reads as a
  default): 14 copies, in the modules above plus procs, zonenotes, acts,
  basetypes, datacredit, tradestats, keepalive.
- Finite-number sanitizer: ninja._num and pricebook._num identical
  (overflow-safe); runhistory._num and theorycraft/calcwire._num not
  overflow-safe (see section 3); summary, waystone, health, searchstr,
  potential keep their own variants because they return a different type
  (the original int, or a bool).
- web/: `pad` in 5 files, `duration` in 4, `clock` in 3 (acts, app,
  history, runs, summary). Not changed here: each script is a separate
  classic `<script defer>` IIFE with no shared module yet, and web/ changes
  need a design review; filed as a follow-up.

### Dead code

- server/al/webfetch.py `require_contact` and its only user
  `ContactMissing`: no caller in server/, tools/, tests/ or app/ since
  PRICE-TRADE-LINK. Removed.
- Used only by tests (kept, they are a tested public surface):
  bus.subscriber_count, parser.parse_lines, codec.looks_like_build_code,
  item.display_name, treedata.is_ascendancy, treedata.class_starts.

### Tests that duplicate each other

- No two test functions have an identical body except
  tests/test_overlay_layout.py test_normalize_strict_rejects and
  test_strict_rejects_below_floor, which share a body but run different
  parameter sets (kept).
- Copied test helpers: `srv` (4 files), `scene` (4), `gen` (3 + 3),
  `death` (3), `up` (3), `_isolated_git` (3), `_build` (3), `L` / `_write`
  (3). Candidates for tests/conftest.py fixtures; not moved here because
  conftest also installs the fleet test guard and the copies are short.

## 2. Changes

- New server/al/jsonfile.py: `read_json` (never raises; size cap, encoding,
  kind check, default), `write_json` / `write_text` / `write_bytes`
  (atomic temp + os.replace, ASCII + LF, parents made), `dumps`.
  Moved to it, byte-for-byte the same output: pricebook, ninja, pricewatch,
  runhistory, summary, layout (load, save's write, read_displays), procs
  `_read_json`, zonenotes, theorycraft/weights, theorycraft/store,
  theorycraft/snapshot. -184 / +51 lines in callers.
- New server/al/num.py `finite`: ninja and pricebook `_num` alias it;
  runhistory and calcwire use it (bug fix, section 3).
- Removed webfetch `require_contact` / `ContactMissing`.
- tests/test_jsonfile.py: 19 tests for the helper, the sanitizer and both
  regressions.

Not moved (would change bytes or behaviour): core.write_private (0600
mode), procs.record_overlay, keepalive._write_state and
__main__.write_heartbeat (they write with Path.write_text and no newline
argument, so CRLF on Windows; stop.ps1 / run.ps1 parse them, so a switch
to LF is left to a change that re-tests those scripts), layout.save's read
(it must raise on a hand-broken config, not default), weights' load (it
records load_error), and acts / basetypes / datacredit / tradestats reads
(build-time data with their own error shapes).

state.py split: a clean seam exists (lines 74-745 are pure card / event
text functions, the class below is the state machine), but
tools/design_gate.py, the design-reviewer agent, loop_prompts and design
docs 0001 / 0002 key the UI-copy review on the path server/al/state.py.
Moving the text out needs those updated together; filed as a follow-up
rather than done in a behaviour-preserving pass.

## 3. Bugs found

- runhistory._num: `float()` of a 400-digit JSON int raised OverflowError
  out of `runhistory.load()` (a hand-edited run_history.json would break
  the run history view). Now read as None (that run is dropped).
- theorycraft/calcwire._num: `math.isfinite()` of a huge int raised
  OverflowError out of `map_outputs`. Now None (the next DPS key is used).
- Noted, not changed: ninja `in_div` calls math.isfinite on cached values
  that were already sanitized by `_num` at parse time, so it cannot see a
  huge int today.

Regression tests: tests/test_jsonfile.py
test_runhistory_huge_int_is_dropped_not_raised,
test_calcwire_huge_int_is_not_a_number.

## 4. Coverage (tools/cover.py)

- before (main 40955c3): 90.8% of 14850 lines (server/ 94.3% of 9791)
- after (77314ec): 90.9% of 14772 lines (server/ 94.4% of 9713); 78
  fewer executable server lines; jsonfile.py and num.py 100%; runhistory
  94.0 -> 95.8, summary 96.9 -> 97.4, pricewatch 96.8 -> 97.3, ninja
  91.3 -> 91.5

Both runs: the only failure under the tracer is the timing budget
test_budgets (expected: the line tracer slows the 50 ms / 500 ms budgets);
the untraced suite is green.

## 5. Equivalence check

A synthetic replay (tools/synth_client.py seeds 1-6, 600 minutes each,
through parser + SessionState with a fixed clock, a snapshot every 25
lines) plus a round trip of every moved runtime-file module (written
bytes hashed, loads of missing / corrupt / wrong-kind / oversized files)
gives byte-identical JSON on main and on this branch.
