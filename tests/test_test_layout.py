"""Layout guard for the test tree.

Rule 1 (naming): a test file is named after its subject, never after a
batch, pass, plan, wave or kit number (test_audit_pass9.py, test_ux_b6.py,
test_kit_v25_x.py, test_loop_inbox_p161.py). Subject names that carry a
number as part of the subject (test_util_10_ready.py, test_math_e2e_live.py)
pass.
Rule 2 (imports): one test file never imports another test file; shared
helpers live in a non-test module (tests/al_loopkit.py, tests/play_states.py).

Both rules have exact, shrink-only allow-lists of today's offenders. A listed
file or import that no longer exists fails with 'remove it'; a new offender
fails with the rule text. tests/ stays flat (prepend import mode needs unique
names).
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Tokens (split on '_' and '.') that mark a batch name.
_NUMBERED = re.compile(r"^(batch|pass|plan|wave|kit|session|pkg|p|b|v|util)\d+$")
_LABEL = {"batch", "pass", "plan", "wave", "kit"}
# Bare tokens that only ever name a sweep of fixes, never a subject.
_BARE = {"sweep"}

NAME_RULE = (
    "test files are named after their subject, not after a batch, pass, "
    "plan, wave or kit number: rename it by what it tests"
)
IMPORT_RULE = (
    "a test file must not import another test file: move the shared helper "
    "to a non-test module under tests/ and import that"
)

NAME_ALLOW = frozenset("""
tests/test_al_loop_kit_v13.py
tests/test_audit_batch4.py
tests/test_audit_pass2.py
tests/test_audit_pass3.py
tests/test_audit_pass4.py
tests/test_audit_pass5.py
tests/test_audit_pass5_low.py
tests/test_audit_pass6.py
tests/test_audit_pass7.py
tests/test_audit_pass7_low.py
tests/test_audit_pass8.py
tests/test_kit_v25_lane_cap.py
tests/test_loop_checklist_overflow_p168.py
tests/test_loop_inbox_p161.py
tests/test_loop_inbox_p164.py
tests/test_p163_lane_tools.py
tests/test_ux_b6.py
tests/test_ux_b8.py
app/test/util9.test.js
app/test/util13.test.js
app/test/ux_sweep.test.js
""".split())

IMPORT_ALLOW = frozenset({
    ("tests/test_audit_hygiene.py", "test_ascii_lf"),
    ("tests/test_audit_hygiene.py", "test_sidecar_paths"),
    ("tests/test_audit_pass3.py", "test_live_exit"),
    ("tests/test_audit_pass4.py", "test_math_compare"),
    ("tests/test_dash_console.py", "test_fullstack"),
    ("tests/test_lootfilter_tiers.py", "test_lootfilter"),
    ("tests/test_lootfilter_tiers.py", "test_price_book"),
    ("tests/test_math_compare.py", "test_tc_delta"),
    ("tests/test_math_dps_sanity.py", "test_tc_delta"),
    ("tests/test_math_weights.py", "test_tc_delta"),
    ("tests/test_math_weapon_type.py", "test_math_compare"),
    ("tests/test_sse_idle_push.py", "test_fullstack"),
    ("tests/test_tc_json.py", "test_tc_code_api"),
    ("tests/test_ux_review.py", "test_design_contrast"),
})


def batch_named(filename):
    """True when the file name carries a batch / pass / plan / kit number."""
    stem = filename.split(".")[0]
    toks = [t for t in stem.split("_") if t]
    for i, t in enumerate(toks):
        if t in _BARE or _NUMBERED.match(t):
            return True
        if t in _LABEL and i + 1 < len(toks) and toks[i + 1].isdigit():
            return True
    return False


def _rel(root, p):
    return p.relative_to(root).as_posix()


def name_offenders(root):
    found = set()
    for p in sorted((root / "tests").glob("test_*.py")):
        if batch_named(p.name):
            found.add(_rel(root, p))
    js = root / "app" / "test"
    if js.is_dir():
        for p in sorted(js.glob("*.test.js")):
            if batch_named(p.name):
                found.add(_rel(root, p))
    return found


def imported_test_modules(path):
    """Top-level module names starting with test_ that the file imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        for n in names:
            top = n.split(".")[0]
            if top.startswith("test_"):
                mods.add(top)
    return mods


def import_offenders(root):
    found = set()
    for p in sorted((root / "tests").glob("*.py")):
        for m in imported_test_modules(p):
            found.add((_rel(root, p), m))
    return found


def check_names(root, allow):
    found = name_offenders(root)
    out = [f"{f}: {NAME_RULE}" for f in sorted(found - allow)]
    out += [f"{f}: no longer a batch-named file, remove it from NAME_ALLOW"
            for f in sorted(allow - found)]
    return out


def check_imports(root, allow):
    found = import_offenders(root)
    out = [f"{f} imports {m}: {IMPORT_RULE}" for f, m in sorted(found - allow)]
    out += [f"{f} no longer imports {m}, remove it from IMPORT_ALLOW"
            for f, m in sorted(allow - found)]
    return out


def test_names_follow_the_rule():
    bad = check_names(ROOT, NAME_ALLOW)
    assert not bad, "\n".join(bad)


def test_no_new_test_to_test_imports():
    bad = check_imports(ROOT, IMPORT_ALLOW)
    assert not bad, "\n".join(bad)


def test_allow_list_sizes_only_shrink():
    assert len(NAME_ALLOW) <= 21
    assert len(IMPORT_ALLOW) <= 14


def test_subject_names_pass():
    for name in (
        "test_demo_entry.py", "test_pytest_config.py", "test_loop_failed_park.py",
        "test_loop_rowfiles.py", "test_roadmap_fold_e2e.py", "test_leagues.py",
        "test_play_states.py", "test_tc_press_build.py", "test_util_10_ready.py",
        "test_util_10_fixtures.py", "test_math_e2e_live.py",
        "tc_view.test.js", "eval.test.js",
    ):
        assert not batch_named(name), name


def test_batch_names_fail():
    for name in (
        "test_audit_pass9.py", "test_audit_batch10.py", "test_ux_b9.py",
        "test_kit_v30_x.py", "test_loop_inbox_p170.py", "test_plan_4_x.py",
        "util14.test.js",
    ):
        assert batch_named(name), name


def _mini_tree(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "app" / "test").mkdir(parents=True)
    (tmp_path / "tests" / "test_good_subject.py").write_text("x = 1\n")
    return tmp_path


def test_self_check_planted_batch_name_fails(tmp_path):
    root = _mini_tree(tmp_path)
    assert check_names(root, frozenset()) == []
    (root / "tests" / "test_audit_pass9.py").write_text("x = 1\n")
    bad = check_names(root, frozenset())
    assert len(bad) == 1 and "test_audit_pass9.py" in bad[0] and NAME_RULE in bad[0]
    (root / "app" / "test" / "util99.test.js").write_text("//\n")
    assert len(check_names(root, frozenset())) == 2


def test_self_check_planted_import_fails(tmp_path):
    root = _mini_tree(tmp_path)
    assert check_imports(root, frozenset()) == []
    (root / "tests" / "test_a.py").write_text("from test_x import y\n")
    bad = check_imports(root, frozenset())
    assert len(bad) == 1 and "test_x" in bad[0] and IMPORT_RULE in bad[0]
    (root / "tests" / "test_b.py").write_text("def f():\n    import test_z\n")
    assert len(check_imports(root, frozenset())) == 2
    (root / "tests" / "al_helper.py").write_text("import json\nfrom al import x\n")
    assert len(check_imports(root, frozenset())) == 2


def test_self_check_stale_allow_entries_fail(tmp_path):
    root = _mini_tree(tmp_path)
    bad = check_names(root, frozenset({"tests/test_gone_pass1.py"}))
    assert len(bad) == 1 and "remove it" in bad[0]
    bad = check_imports(root, frozenset({("tests/test_a.py", "test_x")}))
    assert len(bad) == 1 and "remove it" in bad[0]
