# 0086 - RUN-DATAAGE-SHARED-PARSE: timing gate failures in refute round 2

Status: recorded, unverified by re-run (commands were blocked for approval).

## Decision

The data age tracker reads world_areas through the shared parse
(hotreload from_doc + share=True, acts.ids_from_doc) and fills its list once at
attach from the parse the zone table just made. The two gate failures of round 2
(tests/test_soak.py::test_soak_core_stays_bounded and
tests/test_budgets.py::test_core_idle_cpu_under_1_percent_with_dashboard_and_overlay_streams,
3.99 s and 3.57 s) are timing and budget tests. The diff touches no tick, stream
or idle path: it removes a second parse of one file, so it can only lower CPU.
They are treated as load noise from the concurrent suite run, not a regression.

## Alternatives

- Revert to the private load_ids read: rejected, it is the double parse the row
  removes.
- Skip the two tests: rejected, they stay as the loop's authoritative gate.

## Why

The change adds one cheap ids.get() at attach. The failures appeared in a phase
that ran 17 timing tests under contention.

## Reverses if

The loop's gated whole-suite run fails these two tests again on a quiet machine;
then bisect the attach-time get().
