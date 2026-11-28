"""LOOP-TESTS-CARVE: the tools/al_loop.py tests of hand-off work items,
moved from tests/test_al_loop.py. LOOP-HANDOFF-PREFIX rewrote them: a
"Carried forward" bullet is loop work only when it starts with 'LOOP:'."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402
import loop_preflight  # noqa: E402

from al_loopkit import (  # noqa: E402
    HANDOFF, deps, isolate_git, make_root)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


LOOP_HANDOFF = """AL NEXT SESSION
---------------
Next action: x

Carried forward (not acted on yet):
- OPERATOR (physical): press Ctrl+Alt+E and confirm the overlay toggles.
- LOOP: OPERATOR: set profile.family in config.
- LOOP: MAIN to record AL's port block in the registry.
- LOOP: NOTE: OCR residual accepted.
- LOOP: Fix the OCR cache key so a same-second rewrite is
  re-read.
- Fix the size cap of the price cache.

Context: CLAUDE.md
"""


def test_handoff_items_tags():
    items = al_loop.handoff_items(LOOP_HANDOFF)
    assert [i["skip"] for i in items] == ["operator", "other-tree", "info", None]
    assert items[-1]["text"] == "Fix the OCR cache key so a same-second rewrite is re-read."
    assert re.fullmatch(r"H[0-9a-f]{6}", items[-1]["id"])
    # the id is stable across whitespace re-wraps
    again = al_loop.handoff_items(LOOP_HANDOFF.replace("is\n  re-read", "is re-read"))
    assert again[-1]["id"] == items[-1]["id"]


def test_only_loop_prefixed_bullets_are_work():
    # the shared fixture has no LOOP: bullet: none of its bullets is work
    assert al_loop.handoff_items(HANDOFF) == []
    items = al_loop.handoff_items(LOOP_HANDOFF)
    assert [i for i in items if i["skip"] is None] == [items[-1]]
    assert all("price cache" not in i["text"] for i in items)
    # the prefix must open the bullet; mid-text or lower-case does not count
    text = ("Carried forward:\n- Fix it, see LOOP: notes.\n- loop: fix it.\n"
            "- LOOP:fix the tick.\n")
    assert [i["text"] for i in al_loop.handoff_items(text)] == ["fix the tick."]


def test_blocked_loop_bullet_is_listed_not_dispatched(tmp_path):
    text = ("Carried forward:\n- LOOP: BLOCKED until the OCR fixture lands: re-key\n"
            "  the cache.\n- LOOP: Re-key the price cache.\n- BLOCKED plain note.\n")
    items = al_loop.handoff_items(text)
    assert [i["skip"] for i in items] == ["blocked", None]
    assert items[0]["reason"].startswith("BLOCKED")
    # lower-case "blocked" is prose, not the marker
    prose = al_loop.handoff_items("Carried forward:\n- LOOP: fix the blocked tick.\n")
    assert prose[0]["skip"] is None
    root = make_root(tmp_path, handoff=text)
    _rows, work, skipped = al_loop.Tick(deps(root)).work_list()
    hand_work = [w["id"] for w in work if w.get("kind") == "handoff"]
    assert hand_work == [items[1]["id"]]
    listed = [s for s in skipped if s["id"] == items[0]["id"]]
    assert listed and listed[0]["skip"] == "blocked"


def test_live_handoff_loop_bullets_are_counted_and_well_formed():
    # the live hand-off may carry any number of LOOP: bullets; the preflight
    # count matches the parsed work items and every item is well-formed
    live = (ROOT / "AL-NEXT-SESSION.txt").read_text(encoding="utf-8")
    assert "Carried forward" in live
    items = al_loop.handoff_items(live)
    work = [i for i in items if i["skip"] is None]
    assert loop_preflight.handoff_count(ROOT) == len(work)
    for item in items:
        assert re.fullmatch(r"H[0-9a-f]{6}", item["id"])
        assert isinstance(item["text"], str) and item["text"].strip()
        assert not item["text"].startswith("LOOP:")
        assert item["skip"] in (None, "blocked", "operator", "other-tree", "info")
        if item["skip"] == "blocked":
            assert item["reason"].startswith("BLOCKED")
    assert len({i["id"] for i in items}) == len(items)


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
    text = ("Carried forward:\n- LOOP: Enter the account password in the launcher.\n"
            "- LOOP: Grant the OAuth scope for the API.\n- LOOP: Set the per-host OCR path.\n"
            "- LOOP: Fix the OCR cache key.\n")
    assert [i["skip"] for i in al_loop.handoff_items(text)] == ["operator"] * 3 + [None]
