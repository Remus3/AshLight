"""TEST-SLOW-BUDGET (F-168, research 0049 R5): the slow-test budget hook and
the faulthandler hang guard, each proven in a throwaway pytest project
under tmp_path that installs tests/slow_budget.py the way tests/conftest.py
does. The planted tests sleep for real, so this file is marked slow."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import slow_budget

pytestmark = pytest.mark.slow  # planted 2 s sleeps in child pytest runs

TESTS = Path(__file__).resolve().parent

CONFTEST = f"""
import os, sys
sys.path.insert(0, {str(TESTS)!r})
import slow_budget
_load = float(os.environ.get("SB_LOAD") or 1)
_suite = os.environ.get("SB_SUITE")
slow_budget.install(globals(), budget=lambda s: s * _load,
                    suite_s=float(_suite) if _suite else None)
"""

INI = """[pytest]
testpaths = tests
addopts = -p no:cacheprovider -p no:xdist -p no:anyio -p no:asyncio -p no:timeout
markers =
    slow: planted slow test
faulthandler_exit_on_timeout = true
"""

# Variables a parent run may carry that would change the child's verdict.
SCRUB = ("PYTEST_XDIST_WORKER", "PYTEST_XDIST_WORKER_COUNT",
         "PYTEST_XDIST_TESTRUNUID", "PYTEST_ADDOPTS", "PYTEST_CURRENT_TEST",
         "AL_CI", "AL_SUITE_T0", "SB_LOAD", "SB_SUITE")


def _project(tmp_path, files):
    (tmp_path / "pytest.ini").write_text(INI, encoding="utf-8", newline="\n")
    (tmp_path / "conftest.py").write_text(CONFTEST, encoding="utf-8", newline="\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    for name, body in files.items():
        (tests / name).write_text(body, encoding="utf-8", newline="\n")
    return tmp_path


def _run(project, *args, env=None, timeout=60):
    environ = {k: v for k, v in os.environ.items() if k not in SCRUB}
    environ.update(env or {})
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, "-m", "pytest", "-rA", *args],
                          cwd=str(project), env=environ, capture_output=True,
                          text=True, timeout=timeout)
    return proc.returncode, proc.stdout + proc.stderr, time.monotonic() - t0


SLEEPS = """
import time
import pytest

def test_unmarked_two_seconds():
    time.sleep(2)

@pytest.mark.slow
def test_slow_two_seconds():
    time.sleep(2)
"""


def test_unmarked_two_second_test_fails_and_slow_marked_passes(tmp_path):
    project = _project(tmp_path, {"test_sleeps.py": SLEEPS})
    rc, out, _ = _run(project)
    assert rc == 1, out
    assert "FAILED tests/test_sleeps.py::test_unmarked_two_seconds" in out, out
    assert "PASSED tests/test_sleeps.py::test_slow_two_seconds" in out, out
    assert "slow-test budget: the call took 2." in out, out
    assert "over the 1.50 s ceiling for an unmarked test" in out, out
    assert "mark it @pytest.mark.slow with a reason" in out, out


def test_load_factor_widens_the_ceiling(tmp_path):
    project = _project(tmp_path, {"test_sleeps.py": SLEEPS})
    rc, out, _ = _run(project, "-k", "unmarked", env={"SB_LOAD": "2"})
    assert rc == 0, out
    assert "PASSED tests/test_sleeps.py::test_unmarked_two_seconds" in out, out


def test_parallel_worker_doubles_the_ceiling(tmp_path):
    project = _project(tmp_path, {"test_sleeps.py": SLEEPS})
    rc, out, _ = _run(project, "-k", "unmarked", env={"PYTEST_XDIST_WORKER": "gw0"})
    assert rc == 0, out
    assert "PASSED tests/test_sleeps.py::test_unmarked_two_seconds" in out, out


def test_ci_reports_but_never_fails(tmp_path):
    project = _project(tmp_path, {"test_sleeps.py": SLEEPS})
    rc, out, _ = _run(project, "-k", "unmarked", env={"AL_CI": "1"})
    assert rc == 0, out
    assert "worst call times (AL_CI: report only)" in out, out


FAST = """
def test_a():
    pass

def test_b():
    pass
"""


def test_suite_ceiling_applies_to_a_full_run_only(tmp_path):
    project = _project(tmp_path, {"test_fast.py": FAST})
    env = {"SB_SUITE": "0.000001"}
    for args in (("tests/test_fast.py",), ("tests/test_fast.py::test_a",),
                 ("-k", "test_a")):
        rc, out, _ = _run(project, *args, env=env)
        assert rc == 0, (args, out)
        assert "suite ceiling" not in out, (args, out)
    for args in ((), ("tests",), ("-m", "not timing")):
        rc, out, _ = _run(project, *args, env=env)
        assert rc == 1, (args, out)
        assert "over the 0.0 s suite ceiling" in out, (args, out)
    rc, out, _ = _run(project, env={"SB_SUITE": "600"})
    assert rc == 0 and "suite ceiling" not in out, out


def test_suite_clock_starts_at_the_runner_mark(tmp_path):
    project = _project(tmp_path, {"test_fast.py": FAST})
    rc, out, _ = _run(project, env={"SB_SUITE": "100",
                                    "AL_SUITE_T0": str(time.time() - 200)})
    assert rc == 1, out
    assert "suite ceiling" in out, out


def test_five_worst_call_times_are_printed_in_order(tmp_path):
    body = "import time\n" + "".join(
        f"\ndef test_t{i}():\n    time.sleep({i * 0.06:.2f})\n" for i in range(1, 7))
    project = _project(tmp_path, {"test_worst.py": body})
    rc, out, _ = _run(project)
    assert rc == 0, out
    lines = out.splitlines()
    head = next(i for i, ln in enumerate(lines)
                if ln.startswith("slow-test budget: 5 worst call times"))
    listed = [ln.split()[-1] for ln in lines[head + 1:head + 6]]
    assert listed == [f"tests/test_worst.py::test_t{i}" for i in (6, 5, 4, 3, 2)], out
    assert not lines[head + 6].lstrip()[:1].isdigit(), out  # five rows, no sixth


def test_hung_test_ends_near_the_faulthandler_timeout_with_a_traceback(tmp_path):
    hang = "import time\n\ndef test_hangs():\n    time.sleep(10)\n"
    project = _project(tmp_path, {"test_hang.py": hang})
    rc, out, took = _run(project, "-o", "faulthandler_timeout=2")
    assert rc != 0, out
    assert took < 8, (took, out)
    assert "Timeout" in out, out
    assert "test_hang.py" in out and "test_hangs" in out, out


def test_ceiling_values():
    assert slow_budget.ceiling(False, False) == 1.5
    assert slow_budget.ceiling(True, False) == 15.0
    assert slow_budget.ceiling(False, True) == 3.0
    assert slow_budget.ceiling(True, True) == 30.0
    assert slow_budget.SUITE_S == 260.0
    assert slow_budget.WORST_N == 5


def test_table_entries_widen_the_ceiling():
    file_key = "tests/test_uninstall.py::test_anything[p]"
    assert slow_budget.item_ceiling(file_key, False) == (True, slow_budget.SLOW_S)
    heavy = "tests/test_math_e2e_live.py::test_x"
    assert slow_budget.item_ceiling(heavy, True) == (True, slow_budget.HEAVY_S)
    param = ("tests/test_play_states.py::"
             "test_recipe_builds_pinned_and_yields_its_fields[map]")
    assert slow_budget.item_ceiling(param, False)[0] is True
    assert slow_budget.item_ceiling("tests/test_x.py::test_y", False) == (
        False, slow_budget.UNMARKED_S)
    assert slow_budget.ceiling(True, True, slow_budget.HEAVY_S) == 60.0


def test_every_slow_table_entry_names_a_live_test():
    root = TESTS.parent
    for key, (seconds, reason) in slow_budget.SLOW_TABLE.items():
        assert seconds >= slow_budget.SLOW_S and reason, key
        path, _, func = key.partition("::")
        assert (root / path).is_file(), f"{key}: file gone, remove it"
        if func:
            text = (root / path).read_text(encoding="utf-8")
            assert f"def {func}(" in text, f"{key}: test gone, remove it"


def test_kit_budget_scales_by_the_load_factor(monkeypatch):
    import fleet_test_guard
    monkeypatch.setattr(fleet_test_guard, "load_factor", lambda gate=None: 3)
    assert slow_budget.kit_budget(1.5) == 4.5


def test_install_refuses_a_hook_name_already_defined():
    with pytest.raises(RuntimeError, match="pytest_sessionstart"):
        slow_budget.install({"pytest_sessionstart": object()})
