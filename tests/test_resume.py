"""LIVE-RESUME: a bounded backward scan of Client.txt recovers zone, character,
class, level and deaths after a core restart, without re-listing old events.

Every line here is synthetic (invented names, documentation IPs); no real log
line is copied (FLEET item / CLAUDE.md fixture rule)."""

import time
from pathlib import Path

from server.al import resume
from server.al.core import Core
from server.al.state import SessionState

LIVE = Path(__file__).parent / "fixtures" / "client_live_shapes.txt"

_N = [0]


def L(body, ts="2026/11/16 21:00:00", hexid="1a2b3c4d", tag="INFO"):
    _N[0] += 1
    return f"{ts} {_N[0]} {hexid} [{tag} Client 4242] {body}"


OPEN = "2026/11/16 20:00:00 ***** LOG FILE OPENING *****"


def _write(path, lines, crlf=True, tail=b""):
    eol = "\r\n" if crlf else "\n"
    path.write_bytes((eol.join(lines) + eol).encode("utf-8") + tail)
    return path


def test_live_shapes_fixture_recovers_everything(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(LIVE.read_bytes())
    r = resume.scan(p)
    assert r["zone"] == "Clearfell Encampment"  # not "(unknown)" or "Act 1"
    assert r["in_hideout"] is False
    assert (r["area_id"], r["area_level"]) == ("G1_town", 15)
    assert r["character"] == "Cinderwisp" and r["class"] == "Sorceress"
    assert r["level"] == 2 and r["level_ups"] == 1
    assert r["deaths"] == 0
    assert r["hit_marker"] is True
    assert r["zone_ts_local"] == "2026-11-16T21:08:10"


def test_deaths_count_only_the_current_run(tmp_path):
    lines = [OPEN,
             L(": Quillfeather (Mercenary) is now level 7"),
             L(": Quillfeather has been slain."),
             L(": Quillfeather has been slain."),
             L("[SCENE] Set Source [Old Mire]"),
             OPEN,
             L("[SCENE] Set Source [(unknown)]"),
             L('Generating level 9 area "G2_3" with seed 77', tag="DEBUG"),
             L("[SCENE] Set Source [Dusty Gulch]", ts="2026/11/16 22:10:05"),
             L(": Quillfeather has been slain."),
             L(": Otherhero has been slain."),
             L(": Quillfeather has committed suicide."),
             L("[SCENE] Set Source [Act 2]"),
             L("[SCENE] Set Source [(null)]")]
    r = resume.scan(_write(tmp_path / "Client.txt", lines))
    # Level and character persist across game runs; deaths do not.
    assert r["character"] == "Quillfeather" and r["level"] == 7
    assert r["class"] == "Mercenary"
    assert r["level_ups"] == 0
    assert r["deaths"] == 2
    assert r["zone"] == "Dusty Gulch" and r["zone_ts_local"] == "2026-11-16T22:10:05"
    assert (r["area_id"], r["area_level"]) == ("G2_3", 9)


def test_zone_of_a_previous_run_is_not_current(tmp_path):
    lines = [OPEN, L("[SCENE] Set Source [Old Mire]"),
             OPEN, L("[SCENE] Set Source [(unknown)]")]
    r = resume.scan(_write(tmp_path / "Client.txt", lines))
    assert r["zone"] is None and r["area_id"] is None


def test_newest_level_up_names_the_character(tmp_path):
    lines = [OPEN,
             L(": Quillfeather (Mercenary) is now level 3"),
             L(": Quillfeather (Mercenary) is now level 4"),
             L("#Spammer: Fake (Witch) is now level 99"),  # chat cannot spoof
             L("%Partyguy: : Fake2 (Witch) is now level 98")]
    r = resume.scan(_write(tmp_path / "Client.txt", lines))
    assert r["character"] == "Quillfeather" and r["level"] == 4
    assert r["level_ups"] == 2


def test_configured_character_filters_others(tmp_path):
    lines = [OPEN,
             L(": Mine (Ranger) is now level 12"),
             L(": Mine has been slain."),
             L(": Buddy (Warrior) is now level 30"),
             L(": Buddy has been slain.")]
    r = resume.scan(_write(tmp_path / "Client.txt", lines), character="Mine")
    assert r["character"] == "Mine" and r["level"] == 12 and r["class"] == "Ranger"
    assert r["deaths"] == 1 and r["level_ups"] == 1


def test_hideout_afk_dnd_and_seven_hex_lines(tmp_path):
    lines = [OPEN,
             L("[SCENE] Set Source [Riverside Hideout]", hexid="a2b3c4d"),
             L(": AFK mode is now ON. Back soon"),
             L(": DND mode is now ON"),
             L(": DND mode is now OFF")]
    r = resume.scan(_write(tmp_path / "Client.txt", lines, crlf=False))
    assert r["zone"] == "Riverside Hideout" and r["in_hideout"] is True
    assert r["afk"] is True and r["dnd"] is False


def test_scan_stops_at_end_offset_and_ignores_partial_line(tmp_path):
    lines = [OPEN, L(": Quillfeather (Mercenary) is now level 3")]
    p = _write(tmp_path / "Client.txt", lines)
    size = p.stat().st_size
    with open(p, "ab") as fh:
        fh.write((L(": Quillfeather (Mercenary) is now level 4") + "\r\n").encode())
        fh.write(L(": Quillfeather (Mercenary) is now level 5").encode())  # no EOL
    assert resume.scan(p, end=size)["level"] == 3
    assert resume.scan(p)["level"] == 4  # the unterminated line waits


def test_byte_cap_bounds_the_scan(tmp_path):
    filler = [L("[WINDOW] Gained focus") for _ in range(4000)]
    lines = [OPEN, L(": Faraway (Monk) is now level 40")] + filler + [
        L("[SCENE] Set Source [Near Field]")]
    p = _write(tmp_path / "Client.txt", lines)
    r = resume.scan(p, max_bytes=64 * 1024)
    assert r["bytes_scanned"] <= 64 * 1024
    assert r["zone"] == "Near Field"
    assert r["level"] is None and r["character"] is None  # beyond the cap
    assert r["hit_marker"] is False
    assert resume.scan(p)["level"] == 40  # default cap reaches it


def test_bom_empty_and_missing(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"\xef\xbb\xbf" + (L("[SCENE] Set Source [Shore]") + "\n").encode())
    assert resume.scan(p)["zone"] == "Shore"
    p.write_bytes(b"")
    assert resume.scan(p)["zone"] is None
    assert resume.scan(tmp_path / "nope.txt") is None


def test_scan_stops_early_when_everything_is_known(tmp_path):
    old = [L("[WINDOW] Gained focus") for _ in range(60000)]
    lines = old + [OPEN, L(": Quillfeather (Mercenary) is now level 3"),
                   L("[SCENE] Set Source [Shore]")]
    p = _write(tmp_path / "Client.txt", lines)
    r = resume.scan(p)
    assert r["level"] == 3 and r["hit_marker"] is True
    assert p.stat().st_size > 3 * resume.CHUNK
    assert r["bytes_scanned"] <= resume.CHUNK


def test_state_restore_sets_fields_without_listing():
    st = SessionState(character="", clock=lambda: 1000.0)
    v = st.version
    st.restore({"zone": "Shore", "in_hideout": False, "area_id": "G1_2",
                "area_level": 4, "zone_entered_at": 900.0, "character": "Quill",
                "class": "Monk", "level": 9, "deaths": 2, "level_ups": 1,
                "afk": True, "dnd": False})
    s = st.snapshot()
    assert st.version > v
    assert (s["zone"], s["character"], s["class"], s["level"], s["deaths"]) == (
        "Shore", "Quill", "Monk", 9, 2)
    assert s["zone_s"] == 100.0 and s["afk"] is True
    assert s["recent_events"] == []
    # A live level-up of the restored character keeps counting.
    st.apply({"type": "level_up", "character": "Quill", "class": "Monk", "level": 10})
    s = st.snapshot()
    assert s["level"] == 10 and s["level_ups"] == 2
    st.apply({"type": "level_up", "character": "Stranger", "class": "Monk", "level": 50})
    assert st.snapshot()["level"] == 10


def test_state_restore_keeps_a_configured_character():
    st = SessionState(character="Fixed", clock=lambda: 1.0)
    st.restore({"character": "Other", "level": 3})
    s = st.snapshot()
    assert s["character"] == "Fixed" and s["level"] is None


def _wait(pred, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_core_restart_recovers_state_straight_away(tmp_path):
    lines = [OPEN,
             L(": Quillfeather (Mercenary) is now level 6"),
             L("[SCENE] Set Source [Dusty Gulch]"),
             L(": Quillfeather has been slain."),
             L("@From Seller: hi there")]
    log = _write(tmp_path / "Client.txt", lines)
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.02,
                character="")
    try:
        core.record_consent(True)
        assert _wait(lambda: core.state.snapshot()["tailer"]["reading"])
        s = core.state.snapshot()
        assert s["zone"] == "Dusty Gulch" and s["character"] == "Quillfeather"
        assert s["class"] == "Mercenary" and s["level"] == 6 and s["deaths"] == 1
        # Old events are not re-listed and old whispers do not come back.
        assert [r["type"] for r in s["recent_events"]] == ["tailer_started"]
        assert s["recent_whispers"] == [] and s["trade_requests"] == []
        assert "deaths" in s["tailer"]["resume"]["recovered"]
        assert s["tailer"]["resume"]["bytes"] == log.stat().st_size
        # New lines still flow live on top of the restored state.
        with open(log, "ab") as fh:
            fh.write((L(": Quillfeather (Mercenary) is now level 7") + "\r\n").encode())
            fh.write((L("[SCENE] Set Source [Rocky Pass]") + "\r\n").encode())
        assert _wait(lambda: core.state.snapshot()["zone"] == "Rocky Pass")
        s = core.state.snapshot()
        assert s["level"] == 7 and s["level_ups"] == 2
    finally:
        core.close()


def test_core_start_at_beginning_does_not_double_count(tmp_path):
    lines = [OPEN, L(": Quillfeather (Mercenary) is now level 6"),
             L(": Quillfeather has been slain.")]
    log = _write(tmp_path / "Client.txt", lines)
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.02,
                character="", start_at_end=False)
    try:
        core.record_consent(True)
        assert _wait(lambda: core.state.snapshot()["deaths"] == 1)
        time.sleep(0.1)
        s = core.state.snapshot()
        assert s["deaths"] == 1 and s["level_ups"] == 1
        assert "resume" not in s["tailer"]
    finally:
        core.close()


def test_session_starts_at_the_log_opening(tmp_path):
    """UX-NEW-CARDS: the Session tile counts from the run's LOG FILE OPENING
    line, so it never reads shorter than the resumed zone or act timer."""
    p = _write(tmp_path / "Client.txt", [
        OPEN,
        L(": Quillfeather (Mercenary) is now level 7", ts="2026/11/16 20:30:00"),
        L("[SCENE] Set Source [Clearfell]", ts="2026/11/16 20:40:00")])
    r = resume.scan(p)
    assert r["run_ts_local"] == "2026-11-16T20:00:00"
    now = time.mktime(time.strptime("2026-11-16T21:00:00", "%Y-%m-%dT%H:%M:%S"))
    f = resume.state_fields(r, now=now)
    assert f["session_started_at"] == now - 3600
    st = SessionState(clock=lambda: now)
    st.restore(f)
    snap = st.snapshot()
    assert snap["session_s"] >= snap["zone_s"]
    assert round(snap["session_s"]) == 3600


def test_no_marker_keeps_the_core_start(tmp_path):
    p = _write(tmp_path / "Client.txt", [L("[SCENE] Set Source [Clearfell]")])
    r = resume.scan(p)
    assert r["run_ts_local"] is None
    assert "session_started_at" not in resume.state_fields(r)
