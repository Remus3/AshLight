"""RUN-LEDGER-WIRE (finding F-061, research 0051 R1, research 0050 R11 /
C26, decision 0071): the parse ledger wired at Core.feed_line and
Core.eval_press, its write tick, the drift note, the read-back booleans
and the waystone property-block shape.

No socket, process or network: the core never tails (tail=False); lines
go through Core.replay / Core.feed_line and the write tick is called
with an explicit monotonic time.
"""

import json
from pathlib import Path

import pytest

from server.al import logshapes, parser, resume
from server.al.core import LEDGER_FILE, Core
from server.al.plug import ledger as ledger_plug

FIXTURES = Path(__file__).parent / "fixtures"
LIVE = FIXTURES / "client_live_shapes.txt"
RESTART = FIXTURES / "client_live_restart.txt"
P = "2026/11/17 10:00:00 1 abc [INFO Client 1] "

WAYSTONE = """Item Class: Waystones
Rarity: Rare
Doom Trail
Waystone (Tier 15)
--------
Waystone Tier: 15
Revives Available: 0
Monster Pack Size: +12% (augmented)
Item Rarity: +38% (augmented)
--------
Item Level: 79
--------
Monsters deal 28(20-30)% of Damage as Extra Fire
Players have 40% less Recovery Rate of Life and Energy Shield
--------
Can be used in a Map Device, allowing you to enter a Map. Waystones can only be used once.
"""

RING = """Item Class: Rings
Rarity: Rare
Grim Coil
Ruby Ring
--------
Item Level: 70
--------
+25% to Fire Resistance (implicit)
--------
+40 to maximum Life
"""


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    yield c
    c.close()


def allow_all(core):
    core.record_consent(True)
    core.record_ledger_consent(True)


def live_lines():
    return LIVE.read_text(encoding="ascii").splitlines()


def ledger_file(core):
    return core.runtime / LEDGER_FILE


def doc_of(core):
    return json.loads(ledger_file(core).read_text(encoding="ascii"))


def rows(core):
    core.tick_diag(force=True)
    return [r for r in core.state.snapshot()["diag"]["checks"]
            if r["id"] in (ledger_plug.ROW_DRIFT, ledger_plug.ROW_CAP)]


# -- the named tests ----------------------------------------------------------

def test_no_file_with_ledger_consent_off(core):
    wire = core.ledger_wire
    assert wire is not None and "tick_ledger" in [n for n, _ in core.ticks]
    core.record_consent(True)  # the Client.txt opt-in alone
    core.replay(live_lines())
    assert wire.tick(now=0.0) is False
    core.tick_all()
    assert not ledger_file(core).exists()
    # the in-memory class counters run under the Client.txt opt-in
    assert sum(wire.counters.snapshot().values()) == len(live_lines())
    assert not wire.ledger.hits and not wire.ledger.shapes
    # allowed, written, then revoked: the file goes and is never written again
    core.record_ledger_consent(True)
    core.replay(live_lines())
    assert wire.tick(now=100.0) is True and ledger_file(core).exists()
    core.record_ledger_consent(False)
    assert not ledger_file(core).exists()
    assert not wire.ledger.hits
    core.replay(live_lines())
    assert wire.tick(now=1000.0) is False
    assert not ledger_file(core).exists()
    # revoking the Client.txt opt-in also stops it
    core.record_ledger_consent(True)
    core.replay(live_lines())
    core.record_consent(False)
    assert wire.tick(now=2000.0) is False and not ledger_file(core).exists()
    # a consent flag that disagrees with consent.json never writes
    core.state.set_tailer(ledger=True)
    core.replay(live_lines())
    assert wire.tick(now=3000.0) is False and not ledger_file(core).exists()


def test_written_at_most_once_a_minute_and_only_on_change(core):
    allow_all(core)
    wire = core.ledger_wire
    core.replay(live_lines())
    assert wire.tick(now=0.0) is True
    first = doc_of(core)
    assert first["schema"] == logshapes.SCHEMA and first["hits"]
    assert "area.campaign" in first["hits"]
    # a new pattern inside the minute waits
    core.feed_line(P + 'Generating level 70 area "MapAzmerianRanges" with seed 9')
    assert wire.tick(now=30.0) is False
    assert "area.map" not in doc_of(core)["hits"]
    assert wire.tick(now=61.0) is True
    assert "area.map" in doc_of(core)["hits"]
    # nothing new: no write, however long it waits
    mtime = ledger_file(core).stat().st_mtime_ns
    assert wire.tick(now=500.0) is False
    core.tick_all()
    assert ledger_file(core).stat().st_mtime_ns == mtime
    assert wire.writes == 2
    # the file is ASCII JSON under the byte bound and reads back
    text = ledger_file(core).read_text(encoding="ascii")
    assert len(text) < logshapes.MAX_BYTES
    again = ledger_plug.Wire(core)
    assert again.load_file() and again.ledger.hits == wire.ledger.hits


def test_three_changed_anchor_lines_add_one_note(core):
    core.record_consent(True)  # the drift counter needs no ledger consent
    changed = ["Generating level 3 area G1_2 seed 5",
               "[SCENE] Set Zone [The Riverbank]",
               ": Emberwright is now level 3",
               ": Emberwright has been slain by a Zombie."]
    for body in changed[:2]:
        core.feed_line(P + body)
    core.tick_all()
    assert rows(core) == []
    for body in changed[2:]:
        core.feed_line(P + body)
    core.tick_all()
    got = rows(core)
    assert [r["id"] for r in got] == [ledger_plug.ROW_DRIFT]
    assert got[0]["status"] == "note" and got[0]["detail"] == ledger_plug.DRIFT_TEXT
    assert "Emberwright" not in json.dumps(got)
    # more misses still give one note
    for body in changed:
        core.feed_line(P + body)
    core.tick_all()
    assert len(rows(core)) == 1
    assert not ledger_file(core).exists()


def test_live_shapes_fixture_adds_no_note(core):
    allow_all(core)
    core.replay(live_lines())
    core.replay(RESTART.read_text(encoding="ascii").splitlines())
    core.tick_all()
    assert core.ledger_wire.drift.total == 0
    assert rows(core) == []


def test_readback_flags_hold_booleans_only(core):
    allow_all(core)
    wire = core.ledger_wire
    lines = live_lines()
    core.replay(lines)
    assert wire.tick(now=0.0) is True
    doc = doc_of(core)
    rb = doc["readback"]
    assert set(rb) == set(ledger_plug.READBACK)
    assert all(v is True or v is False for v in rb.values())
    assert all(rb.values()), rb  # the live fixture reaches town as a character
    text = ledger_file(core).read_text(encoding="ascii")
    for word in ("Cinderwisp", "Sorceress", "Riverbank", "Clearfell"):
        assert word not in text, word
    # a tampered file brings back booleans only
    doc["readback"] = {"zone": "The Riverbank", "character": 1, "level": True,
                       "act": None, "session_timer": "yes", "extra": True}
    wire.load(doc)
    assert wire.readback == {"zone": False, "character": False, "level": True,
                             "act": False, "session_timer": False}
    # no tailed line: nothing is claimed
    fresh = ledger_plug.Wire(core)
    core.state.set_tailer(ledger=True)
    fresh.tick(now=0.0)
    assert not any(fresh.readback.values())


def test_waystone_press_stores_a_masked_block_shape(core):
    wire = core.ledger_wire
    core.record_consent(True)
    core.eval_press(WAYSTONE)  # ledger consent off: nothing kept
    assert wire.waystones == {}
    core.record_ledger_consent(True)
    core.eval_press(RING)  # not a waystone
    assert wire.waystones == {}
    core.eval_press(WAYSTONE)
    core.eval_press(WAYSTONE)
    assert wire.tick(now=0.0) is True
    rows_ = doc_of(core)["waystone"]
    assert len(rows_) == 1
    lines, n = rows_[0][0], rows_[0][1]
    assert lines == ["waystone tier: <n>", "revives available: <n>",
                     "monster pack size: <n> (augmented)",
                     "item rarity: <n> (augmented)"]
    assert n == 2
    text = ledger_file(core).read_text(encoding="ascii")
    for word in ("Doom", "Trail", "Extra Fire", "Recovery", "Map Device"):
        assert word not in text, word
    assert all(ledger_plug.is_safe_line(x) for x in lines)
    # an unknown key is masked (equal neighbours collapse), never kept
    odd = WAYSTONE.replace("Revives Available: 0", "Secret Owner Name: Bob")
    shape = ledger_plug.waystone_shape(odd)
    assert "<w>: <w>" in shape and "Bob" not in " ".join(shape)
    # a tampered waystone row with raw text is dropped on load
    doc = doc_of(core)
    doc["waystone"].append([["Doom Trail: Bob"], 1, "2026-11-20T10", "2026-11-20T10"])
    wire.load(doc)
    assert list(wire.waystones) == [tuple(lines)]


def test_resume_cap_note(core):
    core.state.set_tailer(resume={"bytes": resume.DEFAULT_MAX_BYTES, "hit_marker": False,
                                  "ms": 1.0, "recovered": []})
    got = rows(core)
    assert [r["id"] for r in got] == [ledger_plug.ROW_CAP]
    assert got[0]["detail"] == ledger_plug.CAP_TEXT
    core.state.set_tailer(resume={"bytes": resume.DEFAULT_MAX_BYTES, "hit_marker": True,
                                  "ms": 1.0, "recovered": []})
    assert rows(core) == []


def test_feed_error_never_stops_the_line(core, monkeypatch):
    def boom(line, ev):
        raise RuntimeError("x")
    monkeypatch.setattr(core.ledger_wire, "feed", boom)
    ev = core.feed_line(P + ": Emberwright (Witch) is now level 3")
    assert ev is not None and ev["type"] == "level_up"
    assert parser.parse_line(P + "x") is None
