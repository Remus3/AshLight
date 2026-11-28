"""LOOP-ADJUDICATE-MERGE: `tools/loop_merge.py adjudicate <ID> --ruling TEXT`
merges a ruled adjudicate record's kept commit through the gates and the
merge lock and records the ruling; a record with no ruling is refused. Every
side effect is injected; the git world is a throwaway repo under tmp_path."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402
import loop_merge  # noqa: E402

from al_loopkit import (  # noqa: E402
    FakeSpawn, deps, git, git_world, isolate_git, real_git, stub_git)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)
    stub_git(monkeypatch)


def _lanes_running():
    return [{"index": i, "state": "RUNNING", "lane": n}
            for i, n in enumerate(("build", "data", "review"))]


def adjudicate_world(tmp_path, clear_cache=True):
    """An item parked in adjudicate by a final verifier non-PASS (plan 129),
    its commit kept under refs/al/keep/<id>."""
    root, wt = git_world(tmp_path)
    items = al_loop.Items(root)
    rec = items.get("012")
    rec.update(rounds=3, round_log=[{"round": 3, "source": "verifier",
                                     "findings": ["VERDICT: FAIL\n1. nit"]}])
    items.put(rec)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: FAIL\n1. still off"}])
    al_loop.tick(deps=deps(root, spawn=sp, git=real_git, lane_state=_lanes_running),
                 no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "adjudicate" and rec.get("commit")
    assert not (root / "feature.txt").exists()
    if clear_cache:  # the review gated this tree green; start from no verdict
        (root / al_loop.GATE_CACHE_REL).unlink()
    return root


def _deps(root, **kw):
    kw.setdefault("gates", lambda cwd: (True, "gates green (1, test)"))
    return deps(root, git=real_git, lane_state=_lanes_running, **kw)


def _merge(iid, ruling, deps, gate_dir):
    return loop_merge.adjudicate_merge(al_loop.Tick(deps), iid, ruling, gate_dir=gate_dir)


@pytest.mark.git
def test_ruled_adjudicate_record_merges_and_reads_back_merged(tmp_path):
    root = adjudicate_world(tmp_path)
    seen = []

    def gates(cwd):
        seen.append(Path(cwd))
        assert (Path(cwd) / "feature.txt").read_text() == "work\n"  # the kept commit
        return True, "gates green (1, test)"

    rc, msg = _merge("012", "the nit is cosmetic; merge as is",
                     deps=_deps(root, gates=gates), gate_dir=tmp_path / "gate-012")
    assert rc == 0, msg
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged" and rec["verdict"] == "RULED"
    assert rec["ruling"]["text"] == "the nit is cosmetic; merge as is"
    assert rec["ruling"]["gates"].startswith("green")
    assert "keep_ref" not in rec
    assert git(root, "for-each-ref", "refs/al/keep/") == ""
    assert (root / "feature.txt").read_text() == "work\n"
    body = git(root, "log", "-1", "--format=%B", "main")
    assert body.startswith("merge: ") and "ruling: the nit is cosmetic" in body
    assert len(seen) == 1 and not seen[0].exists()  # the gate worktree is removed
    assert git(root, "status", "--porcelain") == ""


@pytest.mark.git
def test_a_cached_green_verdict_of_the_kept_tree_is_not_gated_again(tmp_path):
    root = adjudicate_world(tmp_path, clear_cache=False)
    ran = []
    rc, msg = _merge("012", "ok",
                     deps=_deps(root, gates=lambda cwd: ran.append(cwd) or (False, "x")),
                     gate_dir=tmp_path / "gate")
    assert rc == 0, msg
    assert ran == [] and al_loop.Items(root).get("012")["state"] == "merged"


@pytest.mark.git
def test_record_with_no_ruling_is_refused(tmp_path):
    root = adjudicate_world(tmp_path)
    head = git(root, "rev-parse", "main")
    gated = []
    d = _deps(root, gates=lambda cwd: gated.append(cwd) or (True, "green"))
    for ruling in ("", "   ", None):
        rc, msg = _merge("012", ruling, deps=d, gate_dir=tmp_path / "gate")
        assert rc == 2 and "ruling" in msg
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "adjudicate" and "ruling" not in rec
    assert git(root, "rev-parse", "main") == head and gated == []


@pytest.mark.git
def test_red_gates_keep_the_record_parked_with_the_ruling(tmp_path):
    root = adjudicate_world(tmp_path)
    head = git(root, "rev-parse", "main")
    rc, msg = _merge("012", "merge it",
                     deps=_deps(root, gates=lambda cwd: (False, "1 failed")),
                     gate_dir=tmp_path / "gate")
    assert rc == 1 and "gates red" in msg
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "adjudicate" and rec["ruling"]["text"] == "merge it"
    assert rec["ruling"]["gates"].startswith("red") and "1 failed" in rec["ruling"]["gates"]
    assert git(root, "rev-parse", "main") == head
    assert rec.get("keep_ref") and git(root, "for-each-ref", "refs/al/keep/")
    assert not (tmp_path / "gate").exists()


@pytest.mark.git
def test_only_adjudicate_records_are_merged(tmp_path):
    root, _wt = git_world(tmp_path)  # state "ran", no commit
    rc, msg = _merge("012", "x", deps=_deps(root), gate_dir=tmp_path / "gate")
    assert rc == 2 and "not adjudicate" in msg
    rc, msg = _merge("999", "x", deps=_deps(root), gate_dir=tmp_path / "gate")
    assert rc == 2 and "no loop record" in msg


def test_cli_usage_and_dispatch(monkeypatch, capsys):
    calls = []
    tick = object()
    monkeypatch.setattr(loop_merge, "adjudicate_merge",
                        lambda t, iid, ruling, gate_dir=None:
                        calls.append((t, iid, ruling)) or (0, f"{iid}: merged"))
    monkeypatch.setattr(loop_merge, "_cli_tick", lambda root: tick)
    assert loop_merge.main(["adjudicate", "Hc25fb4", "--ruling", "ok to merge"]) == 0
    assert calls == [(tick, "Hc25fb4", "ok to merge")]
    assert "Hc25fb4: merged" in capsys.readouterr().out
    assert loop_merge.main(["adjudicate", "Hc25fb4"]) == 2  # no --ruling
    assert loop_merge.main(["adjudicate"]) == 2
    assert loop_merge.main(["adjudicate", "X", "--bogus", "y"]) == 2
    assert loop_merge.main(["bogus"]) == 2
    assert len(calls) == 1
