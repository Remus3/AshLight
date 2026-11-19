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
    # LIVE-1: a null scene is neither a zone nor a listed event.
    assert st.apply({"type": "scene_changed", "scene": None, "is_null": True,
                     "is_hideout": False}) is False
    s = st.snapshot()
    assert s["zone"] == "Felled Hideout" and s["in_hideout"] is True
    assert st.version == v


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


def test_zone_change_is_one_recent_row():
    """UX-COPY: the server connect line before each zone is not listed."""
    st = SessionState(clock=lambda: 1.0)
    st.apply({"type": "session_connect", "host": "192.0.2.1", "port": 6112})
    st.apply({"type": "scene_changed", "scene": "Clearfell", "is_hideout": False})
    rows = st.snapshot()["recent_events"]
    assert [r["text"] for r in rows] == ["Entered Clearfell"]


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


# --- LIVE-1 (2026-11-16): state from the anonymised real-shaped fixture.
LIVE = Path(__file__).parent / "fixtures" / "client_live_shapes.txt"


def test_live_state_with_empty_configured_character():
    # config/local.json ships "character": "" - it must mean "learn it".
    clock = [1000.0]
    st = SessionState(character="", clock=lambda: clock[0])
    for ev in parser.parse_lines(LIVE.read_text(encoding="ascii").splitlines()):
        clock[0] += 1
        ev["recv_ts"] = clock[0]
        st.apply(ev)
    s = st.snapshot()
    assert s["character"] == "Cinderwisp" and s["class"] == "Sorceress"
    assert s["level"] == 2 and s["level_ups"] == 1
    assert s["zone"] == "Clearfell Encampment"  # not "(unknown)" or "Act 1"
    assert (s["area_id"], s["area_level"]) == ("G1_town", 15)
    assert s["deaths"] == 0
    zones = [r["text"] for r in s["recent_events"] if r["type"] == "scene_changed"]
    assert zones == ["Entered The Riverbank", "Entered Clearfell Encampment"]


def test_empty_character_counts_deaths():
    st = SessionState(character="", clock=lambda: 1.0)
    st.apply({"type": "level_up", "character": "Me", "class": "Monk", "level": 2})
    st.apply({"type": "death", "character": "Me", "suicide": False})
    st.apply({"type": "death", "character": "Other", "suicide": False})
    assert st.snapshot()["deaths"] == 1


def test_transient_scene_keeps_zone_and_timer():
    st = SessionState(clock=lambda: 5.0)
    st.apply({"type": "scene_changed", "scene": "The Riverbank", "is_null": False,
              "is_hideout": False, "is_transient": False, "recv_ts": 5.0})
    v = st.version
    assert st.apply({"type": "scene_changed", "scene": "Act 1", "is_null": False,
                     "is_hideout": False, "is_transient": True, "recv_ts": 9.0}) is False
    s = st.snapshot()
    assert s["zone"] == "The Riverbank" and s["zone_entered_at"] == 5.0
    assert st.version == v


# --- TEST-LIVE-RESTART (live check 2026-11-17): the game was restarted while
# the core ran. The new run's marker must clear the old run's zone, area and
# zone timer (the player is at the login screen), keep the character, level
# and counts, and pause an open map clock.
RESTART = Path(__file__).parent / "fixtures" / "client_live_restart.txt"


def test_live_restart_clears_previous_run_zone():
    clock = [1000.0]
    st = SessionState(character="", clock=lambda: clock[0])
    for ev in parser.parse_lines(RESTART.read_text(encoding="ascii").splitlines()):
        clock[0] += 1
        ev["recv_ts"] = clock[0]
        st.apply(ev)
    s = st.snapshot()
    assert s["zone"] is None and s["zone_s"] is None
    assert s["area_id"] is None and s["area_level"] is None
    assert not s["in_hideout"] and not s["afk"] and not s["dnd"]
    assert s["character"] == "Cinderwisp" and s["level"] == 2
    assert s["level_ups"] == 1


def test_log_opened_pauses_open_map_clock():
    st = SessionState(character="Me", clock=lambda: 10.0)
    st.apply({"type": "area_generated", "area_id": "MapBluff", "area_level": 65,
              "recv_ts": 10.0})
    st.apply({"type": "scene_changed", "scene": "Bluff", "is_null": False,
              "is_hideout": False, "is_transient": False, "recv_ts": 11.0})
    assert st.maps.cur["entered_at"] == 11.0
    assert st.apply({"type": "log_opened", "recv_ts": 20.0}) is True
    assert st.maps.cur["entered_at"] is None and st.maps.cur["in_s"] == 9.0


def test_log_opened_on_fresh_state_is_quiet():
    st = SessionState(clock=lambda: 1.0)
    v = st.version
    assert st.apply({"type": "log_opened", "recv_ts": 1.0}) is False
    assert st.version == v and st.snapshot()["recent_events"] == []


def _scene(name, ts):
    return {"type": "scene_changed", "scene": name, "is_null": False,
            "is_hideout": parser.is_hideout(name), "is_transient": False,
            "recv_ts": ts}


def test_in_hideout_follows_the_area_id():
    """OVL-HIDEOUT-AREA (F-118): the area id decides, in any language."""
    st = SessionState(character="Me", clock=lambda: 10.0)
    # no generation line yet: the English scene word is the fallback
    st.apply(_scene("Felled Hideout", 1.0))
    assert st.snapshot()["in_hideout"] is True
    # a translated hideout name: the area id says hideout
    st.apply({"type": "area_generated", "area_id": "HideoutFelled",
              "area_level": 2, "recv_ts": 2.0})
    st.apply(_scene("Versteck der Gefallenen", 3.0))
    s = st.snapshot()
    assert s["in_hideout"] is True and s["in_town"] is False
    # a null scene keeps it
    assert st.apply({"type": "scene_changed", "scene": None, "is_null": True,
                     "is_hideout": False, "recv_ts": 4.0}) is False
    assert st.snapshot()["in_hideout"] is True
    # a zone whose name holds the word but whose id is no hideout
    st.apply({"type": "area_generated", "area_id": "G1_2", "area_level": 3,
              "recv_ts": 5.0})
    st.apply(_scene("Hideout Road", 6.0))
    s = st.snapshot()
    assert s["in_hideout"] is False and s["in_town"] is False
    # a translated town: in_town from the id, not a hideout
    st.apply({"type": "area_generated", "area_id": "G1_town", "area_level": 15,
              "recv_ts": 7.0})
    st.apply(_scene("Lager von Lehmfeld", 8.0))
    s = st.snapshot()
    assert s["in_town"] is True and s["in_hideout"] is False
    # area_entered takes the flag from the area id too
    st.apply({"type": "area_generated", "area_id": "HideoutCanal",
              "area_level": 2, "recv_ts": 9.0})
    st.apply({"type": "area_entered", "name": "Kanalversteck", "recv_ts": 10.0})
    assert st.snapshot()["in_hideout"] is True
    # a scene with no generation line before it: the old id is stale,
    # the scene word decides
    st.apply(_scene("Verfallene Strasse", 10.5))
    s = st.snapshot()
    assert s["in_hideout"] is False and s["in_town"] is False
    # a game start clears the area id: the scene word decides again
    st.apply({"type": "log_opened", "recv_ts": 11.0})
    s = st.snapshot()
    assert s["in_hideout"] is False and s["in_town"] is False
    st.apply(_scene("Versteck der Gefallenen", 12.0))
    assert st.snapshot()["in_hideout"] is False


def test_restore_takes_hideout_from_area_id():
    st = SessionState(character="", clock=lambda: 1000.0)
    st.restore({"zone": "Versteck der Gefallenen", "in_hideout": False,
                "area_id": "HideoutFelled", "area_level": 2})
    s = st.snapshot()
    assert s["in_hideout"] is True and s["in_town"] is False
    st = SessionState(character="", clock=lambda: 1000.0)
    st.restore({"zone": "Riverside Hideout", "in_hideout": True,
                "area_id": None})
    assert st.snapshot()["in_hideout"] is True
    st = SessionState(character="", clock=lambda: 1000.0)
    st.restore({"zone": "Lager", "in_hideout": False, "area_id": "G2_town"})
    s = st.snapshot()
    assert s["in_town"] is True and s["in_hideout"] is False
