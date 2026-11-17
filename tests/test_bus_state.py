"""Event bus (bounded, drop-oldest) and derived session state."""

import threading
from pathlib import Path

from server.al import parser
from server.al.bus import EventBus
from server.al.core import Core
from server.al.state import SessionState

FIXTURE = Path(__file__).parent / "fixtures" / "client_sample.txt"


def test_seq_ring_and_listener():
    bus = EventBus(ring_size=5)
    seen = []
    bus.add_listener(seen.append)
    for i in range(12):
        bus.publish({"type": "x", "i": i})
    assert [e["seq"] for e in bus.recent()] == [8, 9, 10, 11, 12]
    assert len(seen) == 12 and bus.published == 12
    assert bus.recent(2)[-1]["i"] == 11


def test_slow_subscriber_drops_oldest():
    bus = EventBus(queue_size=4)
    sub = bus.subscribe()
    for i in range(10):
        bus.publish({"type": "x", "i": i})
    got = sub.get(timeout=0)
    assert [e["i"] for e in got] == [6, 7, 8, 9]
    assert sub.dropped == 6
    sub.close()
    assert bus.subscriber_count == 0


def test_subscriber_wakes_on_publish():
    bus = EventBus()
    sub = bus.subscribe()
    out = []
    t = threading.Thread(target=lambda: out.extend(sub.get(timeout=5)))
    t.start()
    bus.publish({"type": "x"})
    t.join(5)
    assert out and out[0]["type"] == "x"


def test_thread_safe_publish():
    bus = EventBus(ring_size=10000)
    def worker():
        for _ in range(500):
            bus.publish({"type": "x"})
    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    seqs = [e["seq"] for e in bus.recent()]
    assert len(seqs) == 4000 and len(set(seqs)) == 4000


def _state_from_fixture():
    clock = [1000.0]
    st = SessionState(clock=lambda: clock[0])
    bus = EventBus()
    bus.add_listener(st.apply)
    for ev in parser.parse_lines(FIXTURE.read_text(encoding="ascii").splitlines()):
        clock[0] += 1
        ev["recv_ts"] = clock[0]
        bus.publish(ev)
    return st, clock


def test_state_from_fixture():
    st, clock = _state_from_fixture()
    s = st.snapshot()
    assert s["character"] == "Emberwright" and s["class"] == "Witch"
    assert s["level"] == 3 and s["level_ups"] == 2  # party chat "level 99" ignored
    assert s["deaths"] == 1  # Otherguy's suicide is not ours
    assert s["zone"] == "Clearfell" and s["in_hideout"] is False
    assert s["area_level"] == 2
    assert s["afk"] is False and s["dnd"] is False
    assert len(s["recent_whispers"]) == 5
    assert any(w["trade"] for w in s["recent_whispers"])
    assert s["zone_s"] == clock[0] - s["zone_entered_at"]
    assert s["session_s"] > 0


def test_null_scene_keeps_zone_and_hideout_flag():
    st = SessionState(clock=lambda: 5.0)
    st.apply({"type": "scene_changed", "scene": "Felled Hideout", "is_null": False,
              "is_hideout": True})
    v = st.version
    assert st.apply({"type": "scene_changed", "scene": None, "is_null": True,
                     "is_hideout": False}) is True  # listed, but zone kept
    s = st.snapshot()
    assert s["zone"] == "Felled Hideout" and s["in_hideout"] is True
    assert st.version > v


def test_configured_character_filters_level_ups():
    st = SessionState(character="Me", clock=lambda: 1.0)
    st.apply({"type": "level_up", "character": "Other", "class": "Monk", "level": 50})
    assert st.snapshot()["level"] is None
    st.apply({"type": "level_up", "character": "Me", "class": "Monk", "level": 5})
    assert st.snapshot()["level"] == 5


def test_buffers_bounded():
    st = SessionState(clock=lambda: 1.0)
    for i in range(1000):
        st.apply({"type": "whisper_in", "from": "x", "text": str(i)})
    s = st.snapshot()
    assert len(s["recent_whispers"]) <= 10 and len(s["recent_events"]) <= 30


def test_core_consent_gate(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.02)
    try:
        assert core.consented() is False
        assert core.start_tailing() is False and core.tailer is None
        core.record_consent(True)
        assert core.tailer is not None and core.tailer.running
        assert (tmp_path / "rt" / "consent.json").is_file()
        core.record_consent(False)
        assert core.tailer is None
        assert core.state.snapshot()["tailer"]["consented"] is False
    finally:
        core.close()


def test_core_no_tail_never_tails(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    core.record_consent(True)
    assert core.tailer is None
    n = core.replay(FIXTURE.read_text(encoding="ascii").splitlines())
    assert n > 20 and core.state.snapshot()["level"] == 3
    core.close()
