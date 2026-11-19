"""TEST-SELECT (F-065, F-104; research 0049 F6, R1, R9, R11): the test files a
package must run for its diff.

The rules run on a small planted tree under tmp_path (no git needed); the
merge-history check and the command line run read-only on this checkout.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "test_select.py"

_spec = importlib.util.spec_from_file_location("al_test_select", TOOL)
ts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ts)

HEAD = "import pytest\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"

TREE = {
    "server/al/__init__.py": "",
    "server/al/alpha.py": "A = 1\n",
    "server/al/beta.py": "B = 1\n",
    "server/al/theorycraft/__init__.py": "",
    "server/al/theorycraft/calc.py": "C = 1\n",
    "config/thing.json": "{}\n",
    "config/heavy.json": "{}\n",
    "config/tc_pins.json": "{}\n",
    "web/page.js": "x;\n",
    "app/main.js": "y;\n",
    "docs/notes/a.md": "a\n",
    "tools/tool_x.py": "X = 1\n",
    "README.md": "r\n",
    "tests/conftest.py": "",
    "tests/helper_mod.py": "from server.al import alpha\n",
    "tests/calc_helper.py": "import pytest\nCALC = pytest.mark.calc\n",
    "tests/test_alpha.py": HEAD + "from server.al import alpha\ndef test_a():\n    pass\n",
    "tests/test_beta.py": HEAD + "import helper_mod\n"
                          "PAGE = ROOT / 'web' / 'page.js'\ndef test_b():\n    pass\n",
    "tests/test_gamma.py": HEAD + "CFG = 'config/thing.json'\ndef test_g():\n    pass\n",
    "tests/test_walk.py": HEAD + "def test_w():\n"
                          "    assert list((ROOT / 'docs' / 'notes').rglob('*.md'))\n",
    "tests/test_readme.py": HEAD + "def test_r():\n    (ROOT / 'README.md').read_text()\n",
    "tests/test_tc.py": HEAD + "from server.al.theorycraft import calc\n"
                        "import calc_helper\n"
                        "pytestmark = [pytest.mark.calc]\ndef test_t():\n    pass\n",
    "tests/test_tcmix.py": HEAD + "from server.al import alpha\n"
                           "@pytest.mark.calc\ndef test_live():\n    pass\n"
                           "def test_plain():\n    pass\n",
    "tests/test_slowtime.py": HEAD + "from server.al import alpha\n"
                              "pytestmark = pytest.mark.timing\ndef test_s():\n    pass\n",
    "tests/test_heavy.py": HEAD + "CFG = 'config/heavy.json'\n" + "".join(
        f"@pytest.mark.slow\ndef test_h{i}():\n    pass\n" for i in range(61)),
    "tests/test_floor_static.py": HEAD + "def test_f():\n    pass\n",
    "tests/test_overlay_smoke.py": HEAD + "def test_o():\n    pass\n",
    "tests/test_ascii_lf.py": HEAD + "def test_l():\n    pass\n",
    "tests/test_leak_sweep.py": HEAD + "def test_k():\n    pass\n",
    "tests/test_budgets.py": HEAD + "pytestmark = pytest.mark.timing\n"
                             "def test_budget():\n    pass\n",
}
ALWAYS_UNGATED = {"tests/test_floor_static.py", "tests/test_overlay_smoke.py",
                  "tests/test_ascii_lf.py", "tests/test_leak_sweep.py"}


@pytest.fixture
def tree(tmp_path):
    for rel, text in TREE.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="ascii", newline="\n")
    return tmp_path


def _sel(root, changed):
    return ts.select(changed, ts.DirectMap(root))


def _all(sel):
    return set(sel.ungated) | set(sel.gated)


def test_direct_map_names_importers_helpers_and_path_literals(tree):
    tmap = ts.DirectMap(tree)
    assert tmap.tests_for("server/al/alpha.py") >= {
        "tests/test_alpha.py", "tests/test_beta.py", "tests/test_tcmix.py",
        "tests/test_slowtime.py"}  # test_beta through helper_mod (one hop)
    assert "tests/test_gamma.py" not in tmap.tests_for("server/al/alpha.py")
    assert tmap.tests_for("web/page.js") == {"tests/test_beta.py"}
    assert tmap.tests_for("config/thing.json") == {"tests/test_gamma.py"}
    assert tmap.tests_for("docs/notes/new.md") == {"tests/test_walk.py"}  # walked folder
    sel = _sel(tree, ["server/al/alpha.py"])
    assert {"tests/test_alpha.py", "tests/test_beta.py"} <= set(sel.ungated)
    assert "tests/test_gamma.py" not in _all(sel)


def test_a_changed_or_new_test_file_is_always_selected(tree):
    assert "tests/test_gamma.py" in _sel(tree, ["tests/test_gamma.py"]).ungated
    (tree / "tests" / "test_fresh.py").write_text("def test_n():\n    pass\n")
    assert "tests/test_fresh.py" in _sel(tree, ["tests/test_fresh.py"]).ungated
    gone = _sel(tree, ["tests/test_deleted.py"])
    assert "tests/test_deleted.py" not in _all(gone)  # a deleted file cannot run


def test_a_changed_helper_selects_its_importers(tree):
    sel = _sel(tree, ["tests/helper_mod.py"])
    assert "tests/test_beta.py" in sel.ungated
    assert "tests/test_alpha.py" not in _all(sel)
    every = _sel(tree, ["tests/conftest.py"])
    assert _all(every) >= set(ts.DirectMap(tree).tests) - {"tests/test_tc.py"}


def test_an_unknown_path_selects_its_whole_area(tree):
    sel = _sel(tree, ["server/al/beta.py"])  # no test names it
    assert {"tests/test_alpha.py", "tests/test_beta.py", "tests/test_tcmix.py",
            "tests/test_slowtime.py"} <= _all(sel)
    assert "tests/test_gamma.py" not in _all(sel)
    named = _sel(tree, ["README.md"])
    assert "tests/test_readme.py" in named.ungated and "tests/test_gamma.py" not in _all(named)
    root_sel = _sel(tree, ["NEWS.txt"])  # a root file: the root-file tests
    assert "tests/test_readme.py" in _all(root_sel)
    assert "tests/test_gamma.py" not in _all(root_sel)
    (tree / "tests" / "test_readme.py").unlink()
    bare = _sel(tree, ["NEWS.txt"])  # no test names a root file: every test
    assert "tests/test_gamma.py" in _all(bare) and "tests/test_alpha.py" in _all(bare)


@pytest.mark.parametrize("changed", [[], ["config/thing.json"], ["web/page.js"],
                                     ["server/al/theorycraft/calc.py"], ["NEWS.txt"]])
def test_the_always_run_list_is_present_for_every_diff(tree, changed):
    sel = _sel(tree, changed)
    assert ALWAYS_UNGATED <= _all(sel)
    assert "tests/test_budgets.py" in sel.gated


def test_calc_tests_join_only_for_theorycraft_pins_or_their_tests(tree):
    off = _sel(tree, ["server/al/alpha.py", "server/al/beta.py"])
    assert "tests/test_tc.py" not in _all(off)  # calc-only file dropped
    assert "tests/test_tcmix.py" in off.ungated and off.args == '-m "not calc"'
    for trigger in (["server/al/theorycraft/calc.py"], ["config/tc_pins.json"],
                    ["tests/test_tc.py"], ["tests/calc_helper.py"]):
        on = _sel(tree, trigger)
        assert on.calc_on and on.args == "", trigger
        assert "tests/test_tc.py" in _all(on), trigger


def test_a_timing_test_lands_in_the_gated_list(tree):
    sel = _sel(tree, ["server/al/alpha.py"])
    assert "tests/test_slowtime.py" in sel.gated
    assert "tests/test_slowtime.py" not in sel.ungated
    assert "tests/test_budgets.py" not in sel.ungated


def test_an_ungated_list_over_90_s_moves_to_the_gated_list(tree):
    small = _sel(tree, ["config/thing.json"])
    assert small.ungated and not small.moved and small.est_ungated < 90
    big = _sel(tree, ["config/heavy.json"])  # 61 slow tests: over 90 s
    assert big.moved and big.ungated == []
    assert {"tests/test_heavy.py"} | ALWAYS_UNGATED <= set(big.gated)
    lines = ts.render("b", ["config/heavy.json"], big)
    assert "ungated: none" in lines and "run-ungated: none" in lines


def test_render_prints_the_lines_and_npm_only_for_app_or_web(tree):
    web = _sel(tree, ["web/page.js"])
    lines = ts.render("abc", ["web/page.js"], web)
    heads = [line.split(":", 1)[0] for line in lines]
    for key in ("ungated", "gated", "env", "args", "npm", "run-ungated", "run-gated"):
        assert key in heads
    assert "env: AL_FUZZ_S=0.1" in lines
    assert "npm: npm test --prefix app" in lines
    assert _sel(tree, ["app/main.js"]).npm
    plain = ts.render("abc", ["config/thing.json"], _sel(tree, ["config/thing.json"]))
    assert "npm: none" in plain
    gated = [line for line in plain if line.startswith("run-gated: ")][0]
    assert "fleet_suite_gate.py run --owner <OWNER> -- python -m pytest -q" in gated


def _git(*args):
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60, check=False)


def _history_or_skip():
    probe = _git("rev-parse", "--is-shallow-repository")
    if probe.returncode != 0:
        pytest.skip("not a git checkout")
    if probe.stdout.strip() == "true":
        pytest.skip("shallow history")


@pytest.mark.git
def test_the_last_20_merge_commits_select_every_test_file_they_changed():
    _history_or_skip()
    merges = _git("log", "--merges", "-20", "--format=%H").stdout.split()
    if not merges:
        pytest.skip("no merge commits in this history")
    tmap = ts.DirectMap(ROOT)
    for sha in merges:
        changed = ts.changed_paths(ROOT, f"{sha}^1", sha)
        sel = ts.select(changed, tmap)
        want = {p for p in changed if ts.TEST_RE.match(p) and p in tmap.modules}
        assert want <= _all(sel), (sha, sorted(want - _all(sel)))


@pytest.mark.git
def test_the_command_line_prints_the_lines_against_a_base():
    _history_or_skip()
    proc = subprocess.run([sys.executable, str(TOOL), "--base", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=120, check=False)
    assert proc.returncode == 0, proc.stderr
    heads = [line.split(":", 1)[0] for line in proc.stdout.splitlines()]
    assert {"ungated", "gated", "env"} <= set(heads)
    assert "tests/test_budgets.py" in proc.stdout
