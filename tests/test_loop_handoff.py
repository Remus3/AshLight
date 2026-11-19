"""LOOP-TESTS-CARVE: the tools/al_loop.py tests of hand-off work items,
moved unchanged from tests/test_al_loop.py. Owner later: LOOP-HANDOFF-PREFIX,
which edits this file and never tests/test_al_loop.py."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

from al_loopkit import (  # noqa: E402
    HANDOFF, deps, isolate_git, make_root)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


def test_handoff_items_tags():
    items = al_loop.handoff_items(HANDOFF)
    assert [i["skip"] for i in items] == ["operator", "operator", "other-tree", "info", "info", None]
    assert items[-1]["text"].endswith("rewrite is re-read.")
    assert re.fullmatch(r"H[0-9a-f]{6}", items[-1]["id"])
    # the id is stable across whitespace re-wraps
    again = al_loop.handoff_items(HANDOFF.replace("is\n  re-read", "is re-read"))
    assert again[-1]["id"] == items[-1]["id"]


@pytest.mark.git
def test_dispatch_open_rows_then_handoff_to_free_lanes(tmp_path):
    root = make_root(tmp_path)
    d = deps(root, lane_state=lambda: [
        {"index": 0, "state": "RUNNING", "lane": "build"},
        {"index": 1, "state": "FREE", "lane": None},
        {"index": 2, "state": "FREE", "lane": None}])
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["012", "013"]
    items = al_loop.Items(root)
    r12 = items.get("012")
    assert r12["state"] == "dispatched" and r12["lane"] == "data" and r12["pid"] == 4242
    assert "ROADMAP.md row 012 - Grind spot recommender" in r12["prompt"]
    assert "v7 checklist" in r12["prompt"] and "decision, alternatives, why" in r12["prompt"]
    assert items.get("013")["lane"] == "review"
    al_loop.tick(deps=d, no_push=True)  # all lanes taken: nothing new
    assert d.seen["launch"] == ["012", "013"]


def test_handoff_password_oauth_per_host_items_are_operator_only():
    text = ("Carried forward:\n- Enter the account password in the launcher.\n"
            "- Grant the OAuth scope for the API.\n- Set the per-host OCR path.\n"
            "- Fix the OCR cache key.\n")
    assert [i["skip"] for i in al_loop.handoff_items(text)] == ["operator"] * 3 + [None]
