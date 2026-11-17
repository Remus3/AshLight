"""AUDIT-LOOP-COMMIT-MSG (audit finding C2, docs/audit/2026-11-17-audit.md).

A loop commit carried only the row text cut at 300 chars plus refute /
verifier lines, so an ACCEPT like "root cause named in the commit"
(FLAKY-EVAL-API) was never met by the commit. The lane's own result line
(its "RESULT:" line, else the last paragraph of its reply) now goes into the
lane commit and the main merge commit as a `result:` paragraph.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import al_loop  # noqa: E402
import loop_prompts  # noqa: E402
import loop_roadmap  # noqa: E402

from al_loopkit import FakeSpawn, deps, git, git_world, isolate_git, real_git  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)


def test_result_line_prefers_the_result_marker():
    text = ("Worked on it.\n\nRESULT: root cause: an early 401 closed the socket with "
            "the body unread; fixed by a bounded drain.\n\nVERDICT: n/a\n")
    assert loop_roadmap.result_line(text) == (
        "root cause: an early 401 closed the socket with the body unread; fixed by a "
        "bounded drain.")


def test_result_line_falls_back_to_the_last_paragraph():
    text = "step one\n\nstep two\n\nAdded the guard and a regression test.\n  \n"
    assert loop_roadmap.result_line(text) == "Added the guard and a regression test."


def test_result_line_is_ascii_bounded_and_empty_safe():
    assert loop_roadmap.result_line(None) == ""
    assert loop_roadmap.result_line("   ") == ""
    long = "RESULT: " + "x" * 2000 + " " + chr(0x2014) + " end"
    out = loop_roadmap.result_line(long)
    assert len(out) <= loop_roadmap.RESULT_MAX and out.isascii()


def test_commit_body_carries_result_paragraph():
    rec = {"label": "row X: " + "y" * 400, "result": "root cause: Z"}
    body = loop_roadmap.commit_body(rec)
    assert "\n\nresult: root cause: Z\n" in body
    assert loop_roadmap.commit_body({"label": "row X"}).count("result:") == 0


def test_plan_prompt_asks_for_the_result_line():
    p = loop_prompts.plan_prompt({"id": "X1", "title": "t"})
    assert "RESULT:" in p and "root cause" in p


@pytest.mark.git
def test_lane_and_merge_commits_name_the_result(tmp_path):
    root, wt = git_world(tmp_path)
    rec = al_loop.Items(root).get("012")
    rec["result"] = "root cause: the reply raced the unread body; fixed by a drain"
    al_loop.Items(root).put(rec)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "fine\nVERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged"
    lane_msg = git(root, "log", "-1", "--format=%B", rec["commit"])
    merge_msg = git(root, "log", "-1", "--format=%B", "main")
    for msg in (lane_msg, merge_msg):
        assert "result: root cause: the reply raced the unread body" in msg, msg


def test_lane_worker_records_the_result_line(tmp_path):
    src = (ROOT / "tools" / "al_loop.py").read_text(encoding="ascii")
    worker = src.split("def lane_worker(", 1)[1].split("\ndef ", 1)[0]
    assert 'result=result_line(line.get("result"))' in worker
