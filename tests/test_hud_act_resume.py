"""HUD-ACT-RESUME: act splits survive a core restart. LIVE-RESUME (decision
0008) also returns the current game run's area generations with their line
times, and the state rebuilds the splits from them (decision 0023).

Every line here is synthetic (invented names); no real log line is copied."""

import time
from pathlib import Path

from server.al import resume
from server.al.core import Core
from server.al.state import SessionState

_N = [0]


def L(body, ts="2026/11/16 21:00:00", tag="INFO"):
    _N[0] += 1
    return f"{ts} {_N[0]} 1a2b3c4d [{tag} Client 4242] {body}"


def G(area_id, ts, level=5):
    return L(f'Generating level {level} area "{area_id}" with seed 77',
             ts=ts, tag="DEBUG")


OPEN = "2026/11/16 20:00:00 ***** LOG FILE OPENING *****"


def _write(path, lines):
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    return path


def _epoch(ts_local):
    return time.mktime(time.strptime(ts_local, "%Y-%m-%dT%H:%M:%S"))


# One game run: Act 1 from its first zone, Act 2, a hideout, a waypoint back
# to Act 1, then Act 3 (open). An earlier run's zones must not count.
RUN = [OPEN,
       G("G2_1", "2026/11/15 10:00:00"),
       OPEN,
       G("G1_1", "2026/11/16 21:00:00", 1),
       L(": Quill (Monk) is now level 2", ts="2026/11/16 21:05:00"),
       G("G1_town", "2026/11/16 21:10:00", 15),
       G("G2_1", "2026/11/16 21:30:00", 16),
       G("HideoutFelled", "2026/11/16 21:40:00", 1),
       G("G2_town", "2026/11/16 21:45:00", 22),
       G("G1_town", "2026/11/16 21:50:00", 15),
       L("[SCENE] Set Source [Clearfell Encampment]", ts="2026/11/16 21:50:01"),
       G("G3_1", "2026/11/16 22:00:00", 30),
       L(": Quill (Monk) is now level 3", ts="2026/11/16 22:05:00"),
       G("G3_2", "2026/11/16 22:10:00", 31),
       L("[SCENE] Set Source [Jungle Ruins]", ts="2026/11/16 22:10:01")]


def test_scan_returns_the_runs_act_areas_oldest_first(tmp_path):
    r = resume.scan(_write(tmp_path / "Client.txt", RUN))
    # Only campaign / endgame ids; a streak in one act keeps its first entry.
    assert r["act_areas"] == [
        {"area_id": "G1_1", "ts_local": "2026-11-16T21:00:00", "level": 1},
        {"area_id": "G2_1", "ts_local": "2026-11-16T21:30:00", "level": 2},
        {"area_id": "G1_town", "ts_local": "2026-11-16T21:50:00", "level": 2},
        {"area_id": "G3_1", "ts_local": "2026-11-16T22:00:00", "level": 2},
    ]
    # The rest of LIVE-RESUME is unchanged.
    assert r["zone"] == "Jungle Ruins" and (r["area_id"], r["area_level"]) == ("G3_2", 31)
    assert r["character"] == "Quill" and r["level"] == 3 and r["level_ups"] == 2


def test_state_fields_carry_epoch_times(tmp_path):
    r = resume.scan(_write(tmp_path / "Client.txt", RUN))
    now = _epoch("2026-11-16T23:00:00")
    f = resume.state_fields(r, now=now)
    assert f["act_areas"] == [
        {"area_id": "G1_1", "at": _epoch("2026-11-16T21:00:00"), "level": 1},
        {"area_id": "G2_1", "at": _epoch("2026-11-16T21:30:00"), "level": 2},
        {"area_id": "G1_town", "at": _epoch("2026-11-16T21:50:00"), "level": 2},
        {"area_id": "G3_1", "at": _epoch("2026-11-16T22:00:00"), "level": 2},
    ]


def test_restore_rebuilds_splits_exact(tmp_path):
    r = resume.scan(_write(tmp_path / "Client.txt", RUN))
    t0 = _epoch("2026-11-16T21:00:00")
    now = t0 + 4200.0  # 22:10:00
    st = SessionState(character="", clock=lambda: now)
    st.restore(resume.state_fields(r, now=now))
    rows = st.snapshot()["acts"]["splits"]
    assert [(x["key"], x["time_s"], x["cumulative_s"], x["current"], x["partial"])
            for x in rows] == [("G1", 1800.0, 1800.0, False, False),
                               ("G2", 1800.0, 3600.0, False, False),
                               ("G3", 600.0, 4200.0, True, False)]
    assert rows[0]["started_at"] == t0 and rows[2]["ended_at"] is None
    assert st.snapshot()["acts"]["current"] == "G3"
    # A live area generation after the restore keeps folding on top.
    st.apply({"type": "area_generated", "area_id": "G4_1", "area_level": 40,
              "seed": "1", "recv_ts": now + 60.0})
    rows = st.snapshot()["acts"]["splits"]
    assert [(x["key"], x["ended_at"]) for x in rows] == [
        ("G1", t0 + 1800.0), ("G2", t0 + 3600.0), ("G3", now + 60.0), ("G4", None)]


def test_run_started_mid_campaign_is_partial_from_the_log(tmp_path):
    lines = [OPEN, G("G1_1", "2026/11/15 09:00:00", 1),
             OPEN, G("G3_4", "2026/11/16 21:00:00", 33),
             G("G4_1", "2026/11/16 21:20:00", 40)]
    r = resume.scan(_write(tmp_path / "Client.txt", lines))
    now = _epoch("2026-11-16T21:30:00")
    st = SessionState(character="", clock=lambda: now)
    st.restore(resume.state_fields(r, now=now))
    rows = st.snapshot()["acts"]["splits"]
    assert [(x["key"], x["time_s"], x["partial"]) for x in rows] == [
        ("G3", 1200.0, True), ("G4", 600.0, False)]


def test_endgame_maps_close_the_run_and_compress(tmp_path):
    lines = [OPEN, G("G1_1", "2026/11/16 21:00:00", 1),
             G("G2_1", "2026/11/16 21:30:00"),
             G("MapCrypt", "2026/11/16 22:00:00", 65),
             G("HideoutFelled", "2026/11/16 22:05:00", 1),
             G("MapMire", "2026/11/16 22:10:00", 65),
             G("G1_town", "2026/11/16 22:20:00"),
             G("MapCrypt", "2026/11/16 22:30:00", 66)]
    r = resume.scan(_write(tmp_path / "Client.txt", lines))
    assert [a["area_id"] for a in r["act_areas"]] == [
        "G1_1", "G2_1", "MapCrypt", "G1_town", "MapCrypt"]
    now = _epoch("2026-11-16T23:00:00")
    st = SessionState(character="", clock=lambda: now)
    st.restore(resume.state_fields(r, now=now))
    a = st.snapshot()["acts"]
    assert a["finished"] is True
    assert [(x["key"], x["time_s"]) for x in a["splits"]] == [("G1", 1800.0), ("G2", 1800.0)]


def test_new_character_in_the_log_starts_a_new_run(tmp_path):
    lines = [OPEN, L(": Old (Monk) is now level 30", ts="2026/11/16 20:30:00"),
             G("G2_1", "2026/11/16 21:00:00", 30),
             G("G1_1", "2026/11/16 21:30:00", 1),
             L(": Fresh (Witch) is now level 2", ts="2026/11/16 21:35:00"),
             G("G1_2", "2026/11/16 21:40:00", 2)]
    r = resume.scan(_write(tmp_path / "Client.txt", lines))
    assert r["character"] == "Fresh"
    now = _epoch("2026-11-16T22:00:00")
    st = SessionState(character="", clock=lambda: now)
    st.restore(resume.state_fields(r, now=now))
    rows = st.snapshot()["acts"]["splits"]
    assert [(x["key"], x["time_s"], x["partial"]) for x in rows] == [("G1", 1800.0, False)]


def test_no_area_generations_keep_existing_splits():
    st = SessionState(character="", clock=lambda: 500.0)
    st.apply({"type": "area_generated", "area_id": "G1_1", "area_level": 1,
              "seed": "1", "recv_ts": 100.0})
    st.restore({"zone": "Shore", "act_areas": []})
    st.restore({"zone": "Shore"})
    rows = st.snapshot()["acts"]["splits"]
    assert [(x["key"], x["started_at"]) for x in rows] == [("G1", 100.0)]


def _wait(pred, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_core_restart_mid_act_keeps_earlier_act_times(tmp_path):
    log = _write(tmp_path / "Client.txt", RUN)
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.02,
                character="")
    try:
        core.record_consent(True)
        assert _wait(lambda: core.state.snapshot()["tailer"]["reading"])
        s = core.state.snapshot()
        rows = s["acts"]["splits"]
        assert [(x["key"], x["current"], x["partial"]) for x in rows] == [
            ("G1", False, False), ("G2", False, False), ("G3", True, False)]
        assert [x["time_s"] for x in rows[:2]] == [1800.0, 1800.0]
        assert rows[2]["started_at"] == _epoch("2026-11-16T22:00:00")
        assert "acts" in s["tailer"]["resume"]["recovered"]
        assert [r["type"] for r in s["recent_events"]] == ["tailer_started"]
    finally:
        core.close()


def test_scan_cost_stays_bounded_for_a_long_run(tmp_path):
    # Thousands of map generations compress to one entry per streak.
    lines = [OPEN, G("G1_1", "2026/11/16 10:00:00", 1)]
    lines += [G(f"Map{i % 7}", "2026/11/16 12:00:00", 70) for i in range(3000)]
    r = resume.scan(_write(tmp_path / "Client.txt", lines))
    assert [a["area_id"] for a in r["act_areas"]] == ["G1_1", "Map0"]
    assert Path(tmp_path / "Client.txt").stat().st_size == r["bytes_scanned"]
