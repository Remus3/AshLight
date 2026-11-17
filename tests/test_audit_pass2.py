"""AREA-AUDIT pass 2 (session diff, docs/audit/2026-11-17-audit.md):
regression tests for the findings fixed in that pass."""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tc_pin  # noqa: E402

from server.al.theorycraft import bridge  # noqa: E402

DECISIONS = ROOT / "docs" / "decisions"


def test_decision_numbers_are_unique():
    """P2-D1: two decisions were both numbered 0022 (tc-bridge, tc-delta)."""
    nums = [m.group(1) for p in DECISIONS.glob("*.md")
            if (m := re.match(r"(\d{4})-", p.name))]
    dup = sorted(n for n, c in Counter(nums).items() if c > 1)
    assert not dup, f"duplicate decision numbers: {dup}"


def test_tc_delta_code_cites_its_own_decision():
    """P2-D1: TC-DELTA code and tests name decision 0024, not the bridge's."""
    for rel in ("server/al/theorycraft/delta.py", "server/al/theorycraft/evaluate.py",
                "server/al/theorycraft/live.py", "server/al/upgrade.py",
                "server/al/state.py", "server/al/core.py", "tests/test_tc_delta.py"):
        text = (ROOT / rel).read_text(encoding="ascii")
        assert "TC-DELTA (decision 0022)" not in text, rel
        assert "decision 0024" in text, rel


def _bare_bridge(monkeypatch):
    b = bridge.Bridge(["unused"])
    monkeypatch.setattr(b, "request", lambda cmd, timeout=None, **a: {})
    return b


def test_bridge_replay_keeps_the_last_item_per_slot(monkeypatch):
    """P2-B1: every hotkey item check appended to the crash-replay list, so
    it grew without bound (memory, and a replay of every item ever checked)."""
    b = _bare_bridge(monkeypatch)
    b.load_build("<PathOfBuilding2/>")
    for i in range(500):
        b.set_item(f"helmet {i}", slot="Helmet")
    assert b._items == [{"text": "helmet 499", "slot": "Helmet"}]


def test_bridge_replay_list_is_capped(monkeypatch):
    b = _bare_bridge(monkeypatch)
    b.load_build("<PathOfBuilding2/>")
    for i in range(500):
        b.set_item(f"item {i}")  # no slot: each text is its own entry
    assert len(b._items) <= bridge.MAX_REPLAY_ITEMS
    assert b._items[-1] == {"text": "item 499"}  # newest kept
    b.set_item("item 499")  # the same text again is not a second entry
    assert sum(1 for a in b._items if a["text"] == "item 499") == 1
    assert b._items[-1] == {"text": "item 499"}


def test_luajit_builds_static_so_its_hash_covers_the_vm():
    """P2-B2: msvcbuild.bat / make default to a dynamic build (luajit.exe +
    lua51.dll); exepin hashes luajit.exe only, so the unhashed lua51.dll
    (the whole VM) was loaded unverified. A static build is one file."""
    msvc = tc_pin.build_plan(lambda n: "cl" if n == "cl" else None)
    assert msvc[-2:] == ["msvcbuild.bat", "static"]
    both = {"mingw32-make": "m", "gcc": "g"}
    assert tc_pin.build_plan(both.get) == ["m", "BUILDMODE=static"]
