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


# --- correctness sweep (pass 2) ---------------------------------------------

def test_tiny_note_price_never_puts_infinity_in_the_snapshot():
    """P2-V1 (medium): a seller's "~price 0.<309 zeros>1 divine" gave
    score_per_primary inf; json.dumps wrote Infinity and the snapshot / SSE
    frame was no longer valid JSON for the dashboard and overlay."""
    import json
    from server.al.theorycraft import value
    snap = {"primary": "divine", "rates": {"divine": {"value": 1.0},
                                           "exalted": {"value": 1e-300}}}
    for note in ("~price 0." + "0" * 309 + "1 divine",
                 "~b/o 0." + "0" * 20 + "1 exalted"):
        doc = value.value_of(note, 100.0, snap)
        json.dumps(doc, allow_nan=False)  # raises on inf / nan
    assert value.per_unit(1e308, 1e-308) is None
    assert value.convert(1e9, "divine", "exalted", snap) is None


def test_resolve_range_never_raises_on_long_decimals():
    """P2-I1: quantize past the 28-digit context raised InvalidOperation,
    so the item check published no card."""
    from server.al.theorycraft import item
    assert item.resolve_range("1." + "0" * 40, "2") is not None
    text = ("Item Class: Body Armours\nRarity: Rare\nX\nY\n--------\n"
            "+(1." + "0" * 40 + "-2) to maximum Life\n")
    item.parse(text)


def test_flask_property_line_is_linear_time():
    """P2-I2: _FLASK_PROP_RE backtracked quadratically on a long line."""
    import time
    from server.al.theorycraft import item
    text = ("Item Class: Life Flasks\nRarity: Normal\nLife Flask\n--------\n"
            "Recovers" + " " * 60000 + "x\n")
    t0 = time.perf_counter()
    item.parse(text)
    assert time.perf_counter() - t0 < 0.5
    ok = item.parse("Item Class: Life Flasks\nRarity: Normal\nLife Flask\n"
                    "--------\nRecovers 120 Life over 3 Seconds\n")
    assert ok.properties.get("Recovers") == "120 Life over 3 Seconds"


def test_pace_counts_skipped_levels():
    """P2-P1: a skipped level (3 -> 5) counted as one level gained."""
    from server.al.pace import Pace
    p = Pace()
    for level, at in ((3, 600.0), (5, 900.0), (6, 1200.0)):
        p.on_level(level, at)
    v = p.view(1200.0, 0.0)
    assert p.gained == 4
    assert abs(v["per_hour"] - 12.0) < 1e-9


def test_tailer_drops_overlong_terminated_lines(tmp_path):
    """P2-L1: MAX_PARTIAL capped only unterminated lines; a terminated line
    up to MAX_READ still reached the parser regexes (quadratic on some)."""
    from server.al import logfile
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    got = []
    t = logfile.Tailer(log, got.append, start_at_end=False)
    t.poll_once()
    with open(log, "ab") as fh:
        fh.write(b"a (" * (logfile.MAX_PARTIAL // 3 + 10) + b"\n")
        fh.write(b"2026/11/17 10:00:00 1 2 [INFO Client 3] : Hero is now level 5\n")
    t.poll_once()
    assert len(got) == 1 and got[0].endswith("level 5")
    assert t.dropped_lines == 1
