"""TEST-MARKS (research 0049 R3, R4, R9; findings F-022, F-065, F-089):
the 'calc', 'timing' and xdist_group marks select what they claim.

A real collect-only run of the whole tree (a child pytest, so this run's
modules and fixtures stay untouched) records every item with its marks and
fixtures, once with -m calc and once with -m timing:

- -m calc lists only tests of the live calc files (tc_live_util.CALC_FILES),
  every one of them, and every test that requests warm_bridge;
- -m timing lists all of test_budgets, test_soak and test_math_perf, the
  per-call bound tests of test_fuzz (those that call _run or _timed) and
  the individually marked tests of mixed files (TIMING_TESTS, e.g. the
  TC-PRESS-STAGED-LIVE first-card budget test), and nothing else;
- a calc test is in the xdist group 'calc'; every test of the three
  supervisor files is in the xdist group 'supervisor';
- the marks are registered (--strict-markers).
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tc_live_util import CALC_FILES

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.slow  # two collect-only runs of the whole tree

# The child: pytest.main with a plugin that records every collected item,
# selected (pytest_collection_finish) and deselected (pytest_deselected).
CHILD = r'''
import json, sys
import pytest

out_path = sys.argv[1]


class Rec:
    def __init__(self):
        self.rows = []

    def _row(self, item, selected):
        groups = [m.args[0] if m.args else m.kwargs.get("name")
                  for m in item.iter_markers("xdist_group")]
        return {"nodeid": item.nodeid,
                "name": getattr(item, "originalname", None) or item.name,
                "marks": sorted({m.name for m in item.iter_markers()}),
                "groups": groups,
                "warm": "warm_bridge" in getattr(item, "fixturenames", ()),
                "selected": selected}

    def pytest_deselected(self, items):
        self.rows.extend(self._row(i, False) for i in items)

    def pytest_collection_finish(self, session):
        self.rows.extend(self._row(i, True) for i in session.items)


rec = Rec()
rc = pytest.main(sys.argv[2:], plugins=[rec])
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump({"rc": int(rc), "rows": rec.rows}, fh)
'''

CALC_WHOLE = {"tests/test_math_e2e_live.py", "tests/test_math_perf.py"}
CALC_TESTS = {
    "tests/test_fullstack.py": {"test_fullstack_calc_on_leg"},
    "tests/test_math_weapon_type.py": {"test_live_bow_build_cannot_use_a_wand"},
    "tests/test_tc_bridge.py": {"test_live_minimal_build_returns_numeric_outputs",
                                "test_live_reload_does_not_leak_state",
                                "test_live_outputs_match_pob_gui_within_0_1_percent"},
    "tests/test_audit_pass7.py": {"test_live_flask_and_charm_outputs_reach_the_build_view"},
    "tests/test_tc_pob_drift_guard.py": {"test_live_launch_object_and_output_keys"},
    "tests/test_math_skill_split.py": {"test_live_calc_outputs_for_build_view"},
}
TIMING_WHOLE = {"tests/test_budgets.py", "tests/test_soak.py", "tests/test_math_perf.py"}
# mixed files: only these tests carry the timing mark, the rest of the file not
TIMING_TESTS = {
    "tests/test_tc_press_staged.py": {"test_first_card_and_reply_within_budget_with_a_slow_calc"},
    "tests/test_metrics.py": {"test_100000_updates_under_50_ms"},
}
FUZZ = "tests/test_fuzz.py"
SUPERVISOR = ("tests/test_keepalive.py", "tests/test_procs.py", "tests/test_supervisor.py")


def _collect(expr, tmp_path):
    out = tmp_path / f"collect-{expr}.json"
    proc = subprocess.run(
        [sys.executable, "-c", CHILD, str(out), "--collect-only", "-q",
         "--strict-markers", "-m", expr, "tests"],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert out.is_file(), proc.stdout[-2000:] + proc.stderr[-2000:]
    doc = json.loads(out.read_text(encoding="utf-8"))
    # 0 = collected, 5 = nothing selected; anything else is a collect error
    assert doc["rc"] in (0, 5), proc.stdout[-2000:] + proc.stderr[-2000:]
    for row in doc["rows"]:
        row["file"] = row["nodeid"].split("::", 1)[0]
    return doc["rows"]


@pytest.fixture(scope="module")
def calc_rows(tmp_path_factory):
    return _collect("calc", tmp_path_factory.mktemp("marks"))


@pytest.fixture(scope="module")
def timing_rows(tmp_path_factory):
    return _collect("timing", tmp_path_factory.mktemp("marks"))


def _fuzz_bound_tests():
    """test_fuzz test functions whose body calls _run or _timed."""
    tree = ast.parse((ROOT / FUZZ).read_text(encoding="utf-8"))
    out = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            calls = {c.func.id for c in ast.walk(node)
                     if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
            if calls & {"_run", "_timed"}:
                out.add(node.name)
    return out


def test_calc_files_list_is_the_live_calc_files():
    assert set(CALC_FILES) == CALC_WHOLE | set(CALC_TESTS)
    assert len(CALC_FILES) == 8
    for rel in CALC_FILES:
        assert (ROOT / rel).is_file(), rel


def test_marks_collection_sees_the_whole_tree(calc_rows, timing_rows):
    assert len(calc_rows) > 1000
    assert {r["nodeid"] for r in calc_rows} == {r["nodeid"] for r in timing_rows}


def test_minus_m_calc_lists_only_the_live_calc_files(calc_rows):
    picked = [r for r in calc_rows if r["selected"]]
    assert picked
    files = {r["file"] for r in picked}
    assert files <= set(CALC_FILES), sorted(files - set(CALC_FILES))
    assert files == set(CALC_FILES), sorted(set(CALC_FILES) - files)


def test_minus_m_calc_picks_exactly_the_live_tests(calc_rows):
    for rel in CALC_WHOLE:
        rows = [r for r in calc_rows if r["file"] == rel]
        assert rows and all(r["selected"] for r in rows), rel
    for rel, names in CALC_TESTS.items():
        got = {r["name"] for r in calc_rows if r["file"] == rel and r["selected"]}
        assert got == names, rel


def test_every_warm_bridge_user_is_a_calc_test(calc_rows):
    users = [r for r in calc_rows if r["warm"]]
    assert users, "conftest's warm_bridge has no user"
    unmarked = [r["nodeid"] for r in users if not r["selected"]]
    assert not unmarked, f"warm_bridge users without the calc mark: {unmarked}"


def test_calc_tests_share_the_calc_worker_group(calc_rows):
    for r in calc_rows:
        if r["selected"]:
            assert "calc" in r["groups"], r["nodeid"]
        else:
            assert "calc" not in r["groups"], r["nodeid"]


def test_minus_m_timing_lists_the_timing_files_and_fuzz_bounds(timing_rows):
    picked = [r for r in timing_rows if r["selected"]]
    files = {r["file"] for r in picked}
    assert files == TIMING_WHOLE | {FUZZ} | set(TIMING_TESTS), sorted(files)
    for rel in TIMING_WHOLE:
        rows = [r for r in timing_rows if r["file"] == rel]
        assert rows and all(r["selected"] for r in rows), rel
    for rel, names in TIMING_TESTS.items():
        got = {r["name"] for r in picked if r["file"] == rel}
        assert got == names, (rel, sorted(got ^ names))
        # the file's other tests are not wall-clock sensitive
        assert any(r["file"] == rel and not r["selected"] for r in timing_rows), rel
    bound = _fuzz_bound_tests()
    assert len(bound) >= 12
    got = {r["name"] for r in picked if r["file"] == FUZZ}
    assert got == bound, (sorted(got - bound), sorted(bound - got))
    # the rest of test_fuzz is not wall-clock sensitive
    assert any(r["file"] == FUZZ and not r["selected"] for r in timing_rows)


def test_supervisor_files_share_one_worker_group(calc_rows):
    for rel in SUPERVISOR:
        rows = [r for r in calc_rows if r["file"] == rel]
        assert rows, rel
        for r in rows:
            assert r["groups"] == ["supervisor"], r["nodeid"]
