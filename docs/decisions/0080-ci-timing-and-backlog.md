# 0080 - CI timing tolerance and the core's listen backlog

Date: 2026-11-19. Source: adjudicator ruling 2026-11-19 (Option D,
fix-forward under GP-09 while the repository is private) on the red `ci`
runs of package GP-09 (docs/plan/04-go-public.md gate 12); decision 0002
(budgets); decision 0079 (gate 6, same package).

## Finding

The first two `ci` runs on GitHub's shared `windows-2025` runners were
red with failures that are green on the player's PC:

- tests/test_budgets.py: the resume scan of the 32 MB cap took 531.8 ms
  against the 500 ms budget (test-newest).
- tests/test_dash_console.py: the browser logged ERR_CONNECTION_REFUSED
  for /events and /api/overlay-layout; tests/test_play_fit.py: a state
  page "never came live".
- tests/test_e2e_replay.py::test_partial_line_waits_for_its_newline timed
  out; tests/test_procs.py::test_stop_script_leaves_no_ashlight_process
  saw "still running: overlay" right after "overlay stopped".

## Decision

1. Backlog (a code fix): `ALServer.request_queue_size = 128` (socketserver's
   default is 5). Reproduced first: a server bound and listening but not
   accepting gets 50 parallel connects; with a backlog of 5 Windows refused
   36 to 45 of 50 over three runs, with 128 none. tests/test_http_backlog.py
   keeps both halves (ephemeral port, 127.0.0.1). Port, bind address,
   token, Host / Origin checks and CSP are unchanged.
2. AL_CI=1 is set only in the job env of .github/workflows/ci.yml
   (tests/test_ci_workflow.py checks it). Under it, every timing budget of
   tests/test_budgets.py (parse, tail burst, resume scan, tailer and core
   idle CPU) skips with the measured value printed, after the test's
   structural checks ran (`skip_if_ci_timing`, tests/ci_timing.py). The
   memory bound and every structural assert stay hard. Locally nothing
   changes.
3. Under AL_CI=1 test waits widen 3x (`ci_scale`): the CDP scripts
   (app/test/cdp/dash_console.mjs, play_fit.mjs) get one bounded retry of
   the page-live wait at 3x and a 3x watchdog, their Python drivers a 3x
   answer timeout; test_e2e_replay's waits and test_procs' stop-script
   timeouts are 3x. No assertion changes, no rerun plugin. Only if a CDP
   test still fails on a runner after this does it skip in CI only (hard
   locally); that step was not needed when this was written.
4. Two causes found on the way are fixed where they live:
   test_partial_line_waits_for_its_newline now waits for the tailer's
   first look before it writes the partial line (a start_at_end tailer
   that looks after the write skips those bytes, so no timeout could
   help); `procs.stop` waits for a terminated overlay as long as for the
   supervisor (`max(5.0, wait_s)`, stop.ps1 -TimeoutSec), not a fixed 5 s,
   and its final "left running" check counts only overlay pids that are
   still alive (the full rerun of the first green run still saw "still
   running: overlay" with the 3x wait on windows-2025, so the process scan
   there can list an exited process; the stop test now prints what the
   scan sees when it fails). test_hot_reload's SSE wait is 3x under AL_CI.
5. Gate 12 of docs/plan/04 is two consecutive green `ci` runs (same or
   consecutive main commits) with fleet-identity-guard green; a red run
   resets the count.

## Alternatives

- Skip everything timing- or browser-related in CI. Rejected: it hides the
  connection-refused defect, which was real and is fixed in code, and
  drops the CDP checks that catch console and CSP errors.
- Scale the budgets on CI (for example 2x). Rejected: a shared runner's
  noise has no stable bound, so any factor flakes again; decision 0002's
  numbers stay the player-PC contract and stay hard locally.
- A retry plugin (pytest-rerunfailures or similar). Rejected: a new
  dependency, and a blanket rerun hides real failures; the one bounded
  retry lives in the two CDP scripts only.

## Why

Decision 0002's budgets describe the player's PC; shared runners are
slower and noisier, so a wall-clock assert there measures the runner, not
AshLight. The budgets stay enforced where they mean something (the
local gate before every commit). A connection refused, by contrast, can be
a real bug, and it was: a stalled accept loop with a backlog of 5 drops a
page load's parallel connects on Windows.

## Reverses if

Dedicated or otherwise stable runners make timing reliable (then the
AL_CI skips go), an AL_CI skip hides a regression later seen locally, or
the backlog fix shows no effect and connection failures persist on the
runners (then the browser tests get a local-only marker).
