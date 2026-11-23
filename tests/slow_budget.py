"""TEST-SLOW-BUDGET (F-168, research 0049 R5): the slow-test budget.

Installed from tests/conftest.py with install(globals()). Every run:

- A test whose call phase passes its ceiling fails with the budget message.
  The ceiling is UNMARKED_S (1.5 s), or SLOW_S (15 s) for a test marked
  @pytest.mark.slow or listed in SLOW_TABLE (which may name more), times
  the kit load factor (fleet_test_guard.budget(), the live suite-gate slot
  holders, 1..4) and times PARALLEL_FACTOR (2) on a pytest-xdist worker. The load factor is read only for a call that is
  already over its unscaled ceiling.
- A full run (no file, directory or node id named beyond the testpaths, and
  no -k) fails when its wall time passes SUITE_S, scaled by the same load
  factor. SUITE_S starts at 260 s; later rows ratchet it to 215 s, then
  200 s. When SUITE_T0_ENV holds an epoch time (a runner that starts its
  phases as separate pytest processes sets it once), the suite clock starts
  there, so the phases count as one run. A subset run never applies it.
- The WORST_N (five) worst call times are printed at the end.
- Under AL_CI=1 (decision 0080: shared runners make timing unstable) the
  ceilings are reported, never applied.

The hang guard is core pytest: faulthandler_timeout and
faulthandler_exit_on_timeout in pytest.ini (pytest 9.0 or newer).
Standard library plus pytest only."""

import os
import time
from pathlib import Path

import pytest

UNMARKED_S = 1.5
SLOW_S = 15.0
PARALLEL_FACTOR = 2
SUITE_S = 260.0  # research 0049 R5: ratchet to 215 s, then 200 s
WORST_N = 5
SUITE_T0_ENV = "AL_SUITE_T0"
CI_ENV = "AL_CI"
WORKER_ENV = "PYTEST_XDIST_WORKER"
TAG = "slow-test budget"


# Tests marked slow here instead of in their own file (this package may edit
# only its own files): every test over its ceiling in the gated survey of
# 2026-11-21 (12 workers: phase 1 wall 104 s, phase 2 55 s; and a serial
# run of 5,168 tests in 529 s), plus unmarked ones over 75 percent of their
# ceiling in either run (2.25 s parallel, 1.1 s serial), so a loaded box
# does not flap them. Key: a node id, a node id without its [params], or a test
# file (every test in it). Value: (unscaled ceiling in seconds, reason).
# A test that gets faster leaves the table; tests/test_slow_budget.py checks
# that every key still names a live test.
HEAVY_S = 30.0  # live PoB calc or a real browser render end to end
SLOW_TABLE = {
    "tests/test_shots.py::test_real_render_from_a_real_demo_core":
        (HEAVY_S, "renders real pages from a real demo core"),
    "tests/test_math_e2e_live.py":
        (HEAVY_S, "live PoB calc end to end through a real core"),
    "tests/test_fullstack.py::test_fullstack_calc_on_leg":
        (HEAVY_S, "live PoB calc through a real core"),
    "tests/test_dash_perf.py::test_dashboard_elements_task_time_and_heap":
        (HEAVY_S, "drives a real browser page and measures its heap"),
    "tests/test_logshapes.py::test_file_text_under_64_kb_after_1000000_lines":
        (SLOW_S, "feeds one million log lines"),
    "tests/test_test_select.py::test_the_last_20_merge_commits_select_every_test_file_they_changed":
        (SLOW_S, "walks 20 real merge commits with git"),
    "tests/test_test_select.py::test_the_command_line_prints_the_lines_against_a_base":
        (SLOW_S, "real git diff plus an ast pass over tests/"),
    "tests/test_http_ceilings.py":
        (SLOW_S, "waits out real connection ceilings on a real server"),
    "tests/test_floor_static.py::test_floor_holds_on_the_tree":
        (SLOW_S, "scans the whole tree"),
    "tests/test_play_states.py::test_recipe_builds_pinned_and_yields_its_fields":
        (SLOW_S, "builds a real test core per recipe"),
    "tests/test_dependabot_reapply.py":
        (SLOW_S, "real git repositories and a lockfile rebuild"),
    "tests/test_uninstall.py":
        (SLOW_S, "runs uninstall.ps1 under Windows PowerShell"),
    "tests/test_release_stage.py":
        (SLOW_S, "stages a release with real git and zip steps"),
    "tests/test_pre_push_hook.py":
        (SLOW_S, "runs the real pre-push hook against git repositories"),
    "tests/test_math_skill_split.py::test_live_calc_outputs_for_build_view":
        (SLOW_S, "live PoB calc"),
    "tests/test_http_security.py":
        (SLOW_S, "real cores, cross-site probes and SSE streams"),
    "tests/test_loop_wave_hold.py::test_two_holders_of_the_merge_lock_run_one_after_the_other":
        (SLOW_S, "two real processes take the merge lock in turn"),
    "tests/test_tc_press_staged.py::test_first_card_and_reply_within_budget_with_a_slow_calc":
        (SLOW_S, "waits on a planted slow calc"),
    "tests/test_dash_console.py":
        (SLOW_S, "loads the dashboard in a real browser"),
    "tests/test_suite_run.py::test_real_phases_keep_timing_tests_out_of_the_parallel_pass":
        (SLOW_S, "runs real pytest children"),
    "tests/test_leak_sweep.py::test_tracked_tree_is_clean_structurally":
        (SLOW_S, "sweeps every tracked file"),
    "tests/test_capture_helper.py":
        (SLOW_S, "captures pages of a demo core in a real browser"),
    "tests/test_probe.py":
        (SLOW_S, "starts and stops a real core"),
    "tests/test_structure.py::test_planted_text_module_outside_the_gate_fails":
        (SLOW_S, "copies the server tree before planting a module"),
    "tests/test_loop_flip.py":
        (SLOW_S, "real git merges"),
    "tests/test_cover_gaps.py::test_transport_one_hop_size_cap_and_errors":
        (SLOW_S, "real socket transport with size caps"),
    "tests/test_http_backlog.py::test_the_old_backlog_of_5_refuses_the_same_burst":
        (SLOW_S, "a real connection burst"),
    "tests/test_tc_code_api.py::test_rejected_body_drain_is_bounded":
        (SLOW_S, "waits out a bounded body drain on a real server"),
    "tests/test_http_robust.py::test_slow_sse_reader_is_dropped_and_does_not_stall_others":
        (SLOW_S, "waits until a real slow SSE reader is dropped"),
    "tests/test_run_health_ps.py::test_fake_listener_gets_no_token_from_run_ps1":
        (SLOW_S, "runs run.ps1 under Windows PowerShell"),
    "tests/test_fullstack.py::test_fullstack_session_through_http_and_sse":
        (SLOW_S, "a real core through HTTP and SSE"),
    "tests/test_install_selftest.py::test_wrong_version_answer_fails_moves_and_reports":
        (SLOW_S, "a real self-test start that fails and moves"),
    "tests/test_oauthlisten.py::test_closes_after_the_timeout_with_no_request":
        (SLOW_S, "waits out the listener timeout"),
    "tests/test_soak.py::test_dropped_sse_clients_free_their_slots_promptly":
        (SLOW_S, "waits for real SSE slots to free"),
    # GATE-HOLD (wave 31, same basis as the wave 30 ruling of db60425:
    # wall-clock-sensitive tests are marked, no number moves): unmarked
    # tests that went over UNMARKED_S under parallel load in 13 loop gates
    # on 2026-11-22 (0.6 to 1.2 s alone; slow keeps them in phase 1)
    "tests/test_price_cadence.py::test_pressed_type_refreshes_hourly_for_24_h":
        (SLOW_S, "a day of hourly price refreshes on a fake clock"),
    "tests/test_price_cadence.py::test_unpressed_day_makes_at_most_200_overview_gets":
        (SLOW_S, "a day of overview refreshes on a fake clock"),
    "tests/test_price_shape_guard.py::"
    "test_renamed_value_key_keeps_yesterdays_entries_and_sets_a_shape_error":
        (SLOW_S, "two days of price book refreshes"),
    "tests/test_price_shape_guard.py::test_checks_row_fails_and_names_poe_ninja_and_the_worst_type":
        (SLOW_S, "price book refreshes through the Checks row"),
    "tests/test_price_book.py::test_type_failing_three_times_waits_a_day":
        (SLOW_S, "a day of failing refreshes on a fake clock"),
    "tests/test_util_multichar.py::test_storage_caps_characters_and_runs":
        (SLOW_S, "fills the character and run caps through real files"),
    "tests/test_watch_file.py":
        (SLOW_S, "real git commits of row files"),
    "tests/test_supervisor.py::test_hung_core_that_cannot_be_terminated_is_never_duplicated":
        (SLOW_S, "waits out a hung core's health checks"),
    "tests/test_util_10_ready.py::test_id_goes_to_poe_ninja_and_name_to_the_trade_link":
        (SLOW_S, "a real core prices one item end to end"),
    "tests/test_ovl_check.py::test_answer_from_the_tried_in_game_card":
        (SLOW_S, "a full check over real loopback HTTP on a fake clock"),
    "tests/test_test_layout.py::test_no_new_test_to_test_imports":
        (SLOW_S, "an ast pass over every test file"),
}


def table_entry(nodeid):
    """(ceiling, reason) for a node id in SLOW_TABLE, else None."""
    base = nodeid.split("[", 1)[0]
    for key in (nodeid, base, base.split("::", 1)[0]):
        if key in SLOW_TABLE:
            return SLOW_TABLE[key]
    return None


def kit_budget(seconds):
    """fleet_test_guard.budget(): seconds times the live load factor; 1x
    when the kit is not importable (a budget helper never breaks a test)."""
    try:
        import fleet_test_guard
        return float(fleet_test_guard.budget(seconds))
    except Exception:  # noqa: BLE001
        return float(seconds)


def ceiling(slow, parallel, base=None):
    """The call ceiling in seconds before the load factor: base (a
    SLOW_TABLE value), else SLOW_S or UNMARKED_S, doubled on a worker."""
    if base is None:
        base = SLOW_S if slow else UNMARKED_S
    return base * (PARALLEL_FACTOR if parallel else 1)


def item_ceiling(nodeid, marked_slow):
    """(slow, base seconds) for a test: the slow mark, else its table entry."""
    entry = table_entry(nodeid)
    if entry is None:
        return marked_slow, (SLOW_S if marked_slow else UNMARKED_S)
    return True, max(entry[0], SLOW_S if marked_slow else 0.0)


def is_worker(environ=None):
    return bool((os.environ if environ is None else environ).get(WORKER_ENV))


def report_only(environ=None):
    return (os.environ if environ is None else environ).get(CI_ENV) == "1"


def full_run(config):
    """True when the run names nothing beyond the testpaths and has no -k."""
    if config.getoption("keyword", default=""):
        return False
    src = getattr(config, "args_source", None)
    if src is not None and src != pytest.Config.ArgsSource.ARGS:
        return True
    root = Path(config.rootpath).resolve()
    whole = {root} | {(root / p).resolve() for p in config.getini("testpaths")}
    here = Path(config.invocation_params.dir)
    for arg in config.args:
        if "::" in arg:
            return False
        if (here / arg).resolve() not in whole:
            return False
    return True


def budget_message(took, limit, slow, parallel, scaled):
    kind = "a slow-marked test" if slow else "an unmarked test"
    how = []
    if parallel:
        how.append(f"x{PARALLEL_FACTOR} parallel")
    if scaled:
        how.append("load scaled")
    extra = f" ({', '.join(how)})" if how else ""
    fix = ("make it faster" if slow else
           "make it faster or mark it @pytest.mark.slow with a reason")
    return (f"{TAG}: the call took {took:.2f} s, over the {limit:.2f} s ceiling "
            f"for {kind}{extra}; {fix} (TEST-SLOW-BUDGET)")


def suite_message(took, limit):
    return (f"{TAG}: this full run took {took:.1f} s, over the {limit:.1f} s "
            f"suite ceiling; find the slow tests below (TEST-SLOW-BUDGET)")


def install(ns, budget=None, suite_s=None):
    """Add the budget hooks to a conftest's globals(). budget(seconds) scales
    a ceiling by load (default kit_budget); suite_s overrides SUITE_S."""
    scale = budget or kit_budget
    suite_limit = SUITE_S if suite_s is None else float(suite_s)
    state = {"t0": time.time(), "calls": [], "suite": None}

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_makereport(item, call):
        rep = yield
        if rep.when != "call" or not rep.passed or report_only():
            return rep
        slow, base = item_ceiling(item.nodeid,
                                  item.get_closest_marker("slow") is not None)
        parallel = is_worker()
        limit = ceiling(slow, parallel, base)
        if rep.duration <= limit:
            return rep
        scaled = scale(limit)
        if rep.duration <= scaled:
            return rep
        rep.outcome = "failed"
        rep.longrepr = budget_message(rep.duration, scaled, slow, parallel,
                                      scaled > limit)
        return rep

    def pytest_sessionstart(session):
        t0 = time.time()
        try:
            t0 = float(os.environ.get(SUITE_T0_ENV) or t0)
        except ValueError:
            pass
        state["t0"] = t0

    def pytest_runtest_logreport(report):
        if report.when == "call" and not is_worker():
            state["calls"].append((report.duration, report.nodeid))

    def pytest_sessionfinish(session, exitstatus):
        if is_worker() or not full_run(session.config):
            return
        took = time.time() - state["t0"]
        if took <= suite_limit:
            return
        limit = scale(suite_limit)
        if took <= limit:
            return
        state["suite"] = (took, limit)
        if not report_only() and session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def pytest_terminal_summary(terminalreporter):
        if is_worker() or not state["calls"]:
            return
        tr = terminalreporter
        worst = sorted(state["calls"], key=lambda c: (-c[0], c[1]))[:WORST_N]
        note = " (AL_CI: report only)" if report_only() else ""
        tr.write_line(f"{TAG}: {len(worst)} worst call times{note}")
        for took, nodeid in worst:
            tr.write_line(f"  {took:7.2f} s  {nodeid}")
        if state["suite"]:
            tr.write_line(suite_message(*state["suite"]) + note)

    for fn in (pytest_runtest_makereport, pytest_sessionstart,
               pytest_runtest_logreport, pytest_sessionfinish,
               pytest_terminal_summary):
        if fn.__name__ in ns:
            raise RuntimeError(f"slow_budget: {fn.__name__} is already defined")
        ns[fn.__name__] = fn
    return state
