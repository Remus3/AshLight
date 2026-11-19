"""REL-SUBJECT-CHECK (F-101, DEP-04): the commit-msg hook refuses a subject
without a known type, so the changelog generator can group by type."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import commit_subject as cs  # noqa: E402
import loop_roadmap  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "commit_subjects_untyped.txt"


def _passes(subject):
    return cs.parse(subject) is not None and cs.check(subject + "\n") is None


def test_types_are_the_planned_list():
    assert cs.TYPES == ("feat", "fix", "perf", "refactor", "data", "docs", "test",
                        "chore", "ops", "security", "deps", "merge", "release",
                        "audit", "design", "verify", "revert", "done", "kit",
                        "tools", "loop")


@pytest.mark.parametrize("ctype", cs.TYPES)
def test_each_type_passes_with_and_without_a_scope(ctype):
    assert cs.parse(f"{ctype}: do the thing") == (ctype, None, "do the thing")
    assert cs.parse(f"{ctype}(REL-SUBJECT-CHECK): do it") == (
        ctype, "REL-SUBJECT-CHECK", "do it")
    assert cs.parse(f"{ctype}(plan-ovl-client-zoom)!: breaking") == (
        ctype, "plan-ovl-client-zoom", "breaking")


@pytest.mark.parametrize("subject", [
    "merge: SEC-XML-NUL Strict build XML intake (wave 1)",
    "merge: idle deep-dive 20261119 (research)",
    "Merge branch 'main' into worktree-w7-TEST-MARKS",
    "Merge remote-tracking branch 'origin/main'",
    "Merge branches 'a' and 'b'",
    "Merge commit 'abc123'",
    "Merge tag 'v0.1.0'",
    'Revert "merge: PLAY-TD-14-NOTICE Notice N: one notice at a time (wave 6)"',
    'Reapply "merge: SEC-SSE-TAP OBS-SSE-EVENTS (wave 6)"',
])
def test_merge_and_git_own_subjects_pass(subject):
    assert _passes(subject), subject


@pytest.mark.parametrize("subject", [
    "Add a feature",
    "wip: half done",
    "Feat: capital type",
    "feat:no space",
    "feat: ",
    "feat(): empty scope",
    "feature: not a known type",
    "merge branch 'main'",
    "Revert half",
])
def test_untyped_subject_is_refused_with_one_line_naming_the_types(subject, tmp_path):
    assert cs.parse(subject) is None
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(subject + "\n\nbody\n", encoding="ascii", newline="\n")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "commit_subject.py"), str(msg)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1
    lines = r.stderr.strip().splitlines()
    assert len(lines) == 1 and r.stdout == ""
    for ctype in cs.TYPES:
        assert ctype in lines[0]


def test_only_the_subject_line_is_read(tmp_path):
    # comment and blank lines ahead of the subject are skipped; the body and
    # trailers are never judged
    assert cs.check("# Please enter the commit message\n\nfeat: x\n\nWhatever body\n"
                    "Signed-off-by: someone\n") is None
    assert cs.check("untyped subject\n\nfeat: in the body\n") == cs.REFUSAL
    assert cs.check("") is None and cs.check("# only comments\n\n") is None
    msg = tmp_path / "msg"
    msg.write_text("fix(x): y\n", encoding="ascii", newline="\n")
    assert cs.main([str(msg)]) == 0
    assert cs.main([str(tmp_path / "missing")]) == 2
    assert cs.main([]) == 2


def test_watcher_subjects_pass():
    for verb in ("file", "done"):
        subject = f"chore(roadmap): {verb} GGG-DOCS-12 (watch ggg-docs)"
        assert _passes(subject), subject
        assert cs.parse(subject)[:2] == ("chore", "roadmap")


@pytest.mark.parametrize("rec", [
    {"id": "PLAN-12", "kind": "plan", "title": "Add a thing (plan doc 0001)"},
    {"id": "PLAN-13", "kind": "plan", "title": "Fix the broken thing"},
    {"id": "o-7", "kind": "order", "label": "order 7: do the order"},
    {"id": "h-3", "kind": "handoff", "text": "LOOP: tidy the ledger"},
    {"id": "dd", "kind": "deep-dive", "date": "20261119"},
    {"id": "x", "kind": "resolve", "base_kind": "plan", "title": "resolve it"},
    {"id": "", "kind": "other"},
])
def test_loop_subjects_pass(rec):
    assert _passes(loop_roadmap.commit_subject(rec))
    assert _passes(loop_roadmap.commit_subject(rec, wip="gates failed, not merged"))
    assert _passes(loop_roadmap.merge_subject(rec))


def _commit_message_literals(path):
    """Message heads a source file hands to `git commit -m` / `-F` as a
    literal: [(head, is_prefix)]; an f-string yields its literal head."""
    out = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        elts = node.elts
        consts = [e.value if isinstance(e, ast.Constant) else None for e in elts]
        if "commit" not in consts:
            continue
        for i, val in enumerate(consts[:-1]):
            if val not in ("-m", "--message"):
                continue
            nxt = elts[i + 1]
            if isinstance(nxt, ast.Constant) and isinstance(nxt.value, str):
                out.append((nxt.value, False))
            elif isinstance(nxt, ast.JoinedStr) and nxt.values and isinstance(
                    nxt.values[0], ast.Constant):
                out.append((nxt.values[0].value, True))
    return out


def test_kit_and_tool_written_subjects_pass():
    # FLEET item 11: the kit is never edited here, so the hook must never
    # block a commit a vendored kit helper makes.
    files = sorted((ROOT / "ops" / "fleet_kit").glob("*.py")) + sorted(
        (ROOT / "tools").glob("*.py"))
    assert files
    for path in files:
        for head, is_prefix in _commit_message_literals(path):
            subject = cs.subject_of(head + ("x" if is_prefix else ""))
            assert _passes(subject), f"{path.name}: {subject!r}"
    # the loop's -F messages come from loop_roadmap (test_loop_subjects_pass)


def _fixture_subjects():
    return {ln for ln in FIXTURE.read_text(encoding="ascii").splitlines()
            if ln.strip() and not ln.startswith("#")}


@pytest.mark.git
def test_history_subjects_pass_except_the_fixture():
    r = subprocess.run(["git", "log", "-400", "--format=%s", "HEAD"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    if r.returncode != 0:
        pytest.skip("no git history here")
    allowed = _fixture_subjects()
    bad = [s for s in r.stdout.splitlines()
           if s and cs.parse(s) is None and s not in allowed]
    assert not bad, bad


def test_fixture_is_ascii_lf_and_every_entry_is_untyped():
    raw = FIXTURE.read_bytes()
    assert raw.isascii() and b"\r" not in raw
    for subject in _fixture_subjects():
        assert cs.parse(subject) is None, subject


def test_hook_runs_the_check_after_the_strip_and_the_sweep():
    cm = (ROOT / ".githooks" / "commit-msg").read_text("ascii")
    line = 'python "$ROOT/tools/commit_subject.py" "$1" || exit $?'
    assert cm.count(line) == 1
    order = [cm.index('fleet_identity.py" commit-msg "$1"'),
             cm.index('leak_sweep.py" --message "$1"'),
             cm.index(line),
             cm.rstrip().rindex("exit 0")]
    assert order == sorted(order), order
    assert "\r" not in cm and cm.startswith("#!/bin/sh")
