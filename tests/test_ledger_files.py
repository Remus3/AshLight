"""LOOP-LEDGERS: union merge for one-line ledgers, and ledger shape checks."""
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGERS = ("docs/design/reviews.log", "docs/decisions/README.md",
           "docs/research/README.md")
LINE = re.compile(
    r"^\d{4}-\d\d-\d\d \| scope=\S.* \| verdict=(PASS WITH FINDINGS|PASS|FAIL) "
    r"S1=\d+ S2=\d+ S3=\d+ S4=\d+ \| \S.* \| audit=\S.*$")


def _git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="scratch",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="scratch")
    return subprocess.run(["git", *args], cwd=str(cwd), env=env, text=True,
                          capture_output=True)


def _repo(tmp):
    """Scratch repo with the real .gitattributes and base ledger files."""
    tmp = Path(tmp)
    _git(tmp, "init", "-q", "-b", "main")
    (tmp / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    for rel in LEDGERS:
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"# header\nbase line\n")
    _git(tmp, "add", "-A")
    assert _git(tmp, "commit", "-q", "-m", "base").returncode == 0
    return tmp


def _branch_append(repo, branch, rel, line):
    assert _git(repo, "checkout", "-q", "-b", branch, "main").returncode == 0
    with open(repo / rel, "a", newline="\n") as f:
        f.write(line + "\n")
    _git(repo, "commit", "-q", "-am", branch)


def test_union_merge_keeps_both_review_lines():
    rel = LEDGERS[0]
    with tempfile.TemporaryDirectory() as t:
        repo = _repo(t)
        _branch_append(repo, "a", rel, "line from a")
        _branch_append(repo, "b", rel, "line from b")
        r = _git(repo, "merge", "--no-edit", "a")
        assert r.returncode == 0, r.stderr + r.stdout
        text = (repo / rel).read_text()
        assert "line from a" in text and "line from b" in text
    # the two README indexes carry the attribute too
    attrs = (ROOT / ".gitattributes").read_text().splitlines()
    for p in LEDGERS:
        assert f"{p} merge=union" in attrs
    assert not any(a.startswith("ROADMAP.md") for a in attrs)


def test_union_under_cherry_pick_and_rebase_is_recorded():
    """Assert what git does: record whether union holds under cherry-pick/rebase."""
    rel = LEDGERS[0]
    with tempfile.TemporaryDirectory() as t:
        repo = _repo(t)
        _branch_append(repo, "a", rel, "line from a")
        _git(repo, "checkout", "-q", "main")
        _branch_append(repo, "b", rel, "line from b")
        # Cherry-pick a's commit onto b, and rebase a onto b.
        cp = _git(repo, "cherry-pick", "a")
        cherry_ok = cp.returncode == 0
        if not cherry_ok:
            _git(repo, "cherry-pick", "--abort")
        _git(repo, "checkout", "-q", "a")
        rb = _git(repo, "rebase", "b")
        rebase_ok = rb.returncode == 0
        if not rebase_ok:
            _git(repo, "rebase", "--abort")
        # Recorded behaviour of git (merge=union is a merge driver choice that
        # the three-way content merge honours in all three paths).
        assert cherry_ok, cp.stderr
        assert rebase_ok, rb.stderr
        text = (repo / rel).read_text()
        assert "line from a" in text and "line from b" in text


def _numbers(folder):
    nums = []
    for p in (ROOT / folder).iterdir():
        m = re.match(r"^(\d{4})-.+\.md$", p.name)
        if m:
            nums.append(m.group(1))
    return nums


def test_decision_and_research_numbers_are_unique():
    for folder in ("docs/decisions", "docs/research"):
        dup = [n for n, c in Counter(_numbers(folder)).items() if c > 1]
        assert not dup, f"duplicate numbers in {folder}: {dup}"


def test_reviews_log_lines_are_wellformed():
    text = (ROOT / "docs/design/reviews.log").read_bytes().decode("utf-8")
    bad = [ln[:100] for ln in text.split("\n")
           if ln and not ln.startswith("#") and not LINE.match(ln)]
    assert not bad, f"malformed reviews.log lines: {bad}"
