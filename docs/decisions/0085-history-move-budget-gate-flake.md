# 0085 - PLAY-TD-21C-HISTORY-MOVE: budget gate failures are load flakes

Date: 2026-11-22. Row: PLAY-TD-21C-HISTORY-MOVE (refute round 2/3).

## Finding

The gated run reported two failures in tests/test_budgets.py:
test_core_idle_cpu_under_1_percent_with_dashboard_and_overlay_streams and
test_tailer_idle_cpu_under_2_percent (17 passed, phase timing exit 0).

## Decision

No code change. The two failures stand as load flakes, not regressions of this
row.

## Why

- The diff touches only web/history.js, web/summary.js, web/index.html,
  web/app.css, app/test/rail.test.js, app/test/summary.test.js and
  docs/design/reviews.log. No server/ or tools/ file changed.
- Both tests measure the CPU share of the test process: a Tailer thread on a
  1000-line file, and a Core with the HTTP server and two SSE streams. Neither
  loads a web/ asset, so a static page move cannot change their numbers.
- Both assert against 0.01 / 0.02 times fleet_test_guard.load_factor(); a
  machine running other lanes' suites at the same time moves the measured
  share over the line. The failure times (3.57 s and 3.30 s) match the 3 s
  sampling windows, not a hang.

## Alternatives

- Loosen the budgets: refused, decision 0002 and decision 0080 say not to move
  a budget number to hide a flake.
- Skip the tests for this row: refused, they stay structural gates.

## Reverses if

The same two tests fail on a quiet machine with only this diff applied, or a
later change adds a web/ asset read to either test.
