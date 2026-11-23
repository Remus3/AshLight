# 0084 - LP-B refute round 2: the two timing-gate findings stand as unrelated

Date: 2026-11-22. Row: LP-B (focus returns after the Client.txt path form hides).

## Decision

The round-2 findings are two failures in the loop's gated phase:
`tests/test_math_perf.py::test_luajit_memory_stays_under_ceiling` and
`tests/test_budgets.py::test_core_idle_cpu_under_1_percent_with_dashboard_and_overlay_streams`.
Both stand as not caused by LP-B and need no code change in this row.

- The LP-B diff touches only `web/logpath.js`, `app/test/logpath.test.js` and
  `docs/design/reviews.log`. Neither failing test imports or serves those files
  in a way the change can reach: one measures the LuaJIT calc child's memory,
  the other measures core idle CPU with streams open.
- Both are timing / budget tests (decision 0002, decision 0060): they read
  machine load and fail under contention. The same run shows 17 passed and the
  phase-timing exit 0, so the failures were load-dependent.
- Targeted evidence: `node --test app/test/logpath.test.js` 17 of 17 green;
  `python tools/leak_sweep.py --staged` clean.

## Alternatives

- Loosen the two ceilings: rejected, budgets are settled (decision 0002) and
  this row has no standing to move them.
- Add a retry: rejected, decision 0080 forbids a rerun plugin.

## Reverses if

The two tests fail again on a tree with no load and with this diff reverted
(then they are a separate regression row), or a later run shows `web/logpath.js`
affects either measurement.
