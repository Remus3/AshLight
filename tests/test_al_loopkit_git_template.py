"""TEST-LOOP-GIT-TEMPLATE: al_loopkit.git_world copies one session-scoped
template repo instead of running init / add / commit for every test."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import al_loopkit  # noqa: E402
from al_loopkit import git, git_world  # noqa: E402

pytestmark = pytest.mark.git


def test_git_worlds_share_one_template_commit(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    root_a, wt_a = git_world(a)
    built = al_loopkit.template_builds()
    root_b, wt_b = git_world(b, kind="audit")
    # the second world is a copy: no new template, the same init commit
    assert al_loopkit.template_builds() == built
    assert git(root_a, "rev-parse", "HEAD") == git(root_b, "rev-parse", "HEAD")
    assert git(root_a, "log", "--format=%s") == "init"
    # each copy is its own repo: a commit in one never shows in the other
    git(wt_a, "add", "-A")
    git(wt_a, "commit", "-q", "-m", "lane a")
    assert git(root_b, "log", "--all", "--format=%s").splitlines() == ["init"]
    assert git(root_b, "worktree", "list").count("\n") == 1
    assert (wt_b / "feature.txt").read_text() == "work\n"
    assert git(root_a, "status", "--porcelain") == ""
    assert (root_b / "AL-NEXT-SESSION.txt").read_text() == ""
