"""UTIL-MAPS-RESUME: the map runs and the death recap survive a core
restart. The backward scan (decision 0008) returns the current game run's
scenes, area generations, deaths and level-ups, and the state replays them
through runs.replay, as HUD-ACT-RESUME does for the act splits (decision
0023 pattern, nothing persisted).

Every line here is synthetic (invented names); no real log line is copied."""

import time

from server.al import resume, runs
from server.al.core import Core
from server.al.state import SessionState

_N = [0]


def L(body, ts, tag="INFO"):
    _N[0] += 1
    return f"{ts} {_N[0]} 1a2b3c4d [{tag} Client 4242] {body}"


def G(area_id, ts, level=65):
    return L(f'Generating level {level} area "{area_id}" with seed 77',
             ts=ts, tag="DEBUG")


def S(name, ts):
    return L(f"[SCENE] Set Source [{name}]", ts=ts)


OPEN = "2026/11/16 20:00:00 ***** LOG FILE OPENING *****"


def _write(path, lines):
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    return path


def _epoch(ts):
    return time.mktime(time.strptime(ts, "%Y/%m/%d %H:%M:%S"))


# An earlier run died in a map; it must not come back. The current run:
# a finished map with a hideout trip and one death, then an open map.
RUN = [OPEN,
       G("MapCrypt", "2026/11/15 10:00:00"),
       S("Crypt", "2026/11/15 10:00:01"),
       L(": Quill has been slain.", "2026/11/15 10:01:00"),
       OPEN,
       L(": Quill (Witch) is now level 71", "2026/11/16 20:30:00"),
       G("HideoutFelled", "2026/11/16 20:59:00", 1),
       S("Felled Hideout", "2026/11/16 20:59:01"),
       G("MapCrypt", "2026/11/16 21:00:00", 65),
       S("Crypt", "2026/11/16 21:00:00"),
       S("Felled Hideout", "2026/11/16 21:02:00"),
       S("Crypt", "2026/11/16 21:03:00"),
       L(": Quill (Witch) is now level 72", "2026/11/16 21:04:00"),
       L(": Quill has been slain.", "2026/11/16 21:05:00"),
       L(": Other has been slain.", "2026/11/16 21:05:30"),
       S("Felled Hideout", "2026/11/16 21:06:00"),
       G("MapSavannah", "2026/11/16 21:10:00", 66),
       S("Savannah", "2026/11/16 21:10:00")]


def test_scan_returns_only_the_current_runs_events_oldest_first(tmp_path):
    r = resume.scan(_write(tmp_path / "Client.txt", RUN))
    types = [e["type"] for e in r["run_events"]]
    assert types[0] == "level_up" and types[-1] == "scene_changed"
    assert types.count("death") == 2  # Quill and Other, this run only
    assert [e["area_id"] for e in r["run_events"]
            if e["type"] == "area_generated"] == ["HideoutFelled", "MapCrypt",
                                                  "MapSavannah"]


def test_replay_rebuilds_maps_and_deaths_exact(tmp_path):
    r = resume.scan(_write(tmp_path / "Client.txt", RUN))
    now = _epoch("2026/11/16 21:12:30")
    f = resume.state_fields(r, now=now)
    maps, log = runs.replay(f["run_events"], "Quill")
    v = maps.view(now)
    assert v["count"] == 2 and v["done"] == 1
    # Crypt: 2:00 in, 1:00 in the hideout (paused), 3:00 in again; the
    # hideout trip at 21:06 paused it until the next map closed it.
    assert v["recent"] == [{"name": "Crypt", "area_level": 65,
                            "time_s": 300.0, "deaths": 1}]
    assert v["current"] == {"name": "Savannah", "area_level": 66,
                            "time_s": 150.0, "deaths": 0, "inside": True}
    assert v["deaths_text"] == "1 death in maps."
    d = log.view()
    assert [x["text"] for x in d["recent"]] == [
        "Died in Crypt (area level 65) at level 72, 2:00 into the zone."]


def test_replay_without_a_known_player_counts_every_death():
    at = 1000.0
    ev = [{"type": "death", "character": "A", "at": at},
          {"type": "death", "character": "B", "at": at + 1}]
    maps, log = runs.replay(ev, None)
    assert len(log.view()["recent"]) == 2 and maps.view(at)["count"] == 0


def test_replay_skips_events_without_a_time_and_null_scenes():
    ev = [{"type": "area_generated", "area_id": "MapCrypt", "area_level": 65,
           "at": 10.0},
          {"type": "scene_changed", "scene": "(null)", "is_null": True,
           "at": 11.0},
          {"type": "scene_changed", "scene": "Crypt", "at": None},
          {"type": "scene_changed", "scene": "Crypt", "at": 20.0}]
    maps, _ = runs.replay(ev, "Quill")
    assert maps.view(30.0)["current"]["time_s"] == 10.0


def test_restore_replays_and_keeps_current_without_events():
    st = SessionState(clock=lambda: 5000.0)
    ev = [{"type": "area_generated", "area_id": "MapCrypt", "area_level": 65,
           "at": 4000.0},
          {"type": "scene_changed", "scene": "Crypt", "at": 4000.0},
          {"type": "death", "character": "Quill", "at": 4100.0}]
    st.restore({"character": "Quill", "run_events": ev})
    s = st.snapshot()
    assert s["maps"]["current"]["time_s"] == 1000.0
    assert s["maps"]["current"]["deaths"] == 1
    assert s["death_recap"]["recent"][0]["text"] == (
        "Died in Crypt (area level 65), 1:40 into the zone.")
    st.restore({"character": "Quill"})
    assert st.snapshot()["maps"]["count"] == 1


def test_restore_with_a_configured_character_drops_other_deaths():
    st = SessionState(clock=lambda: 5000.0, character="Quill")
    ev = [{"type": "death", "character": "Other", "at": 4100.0},
          {"type": "death", "character": "Quill", "at": 4200.0}]
    st.restore({"character": "Quill", "run_events": ev})
    assert len(st.snapshot()["death_recap"]["recent"]) == 1


def test_run_events_are_bounded(tmp_path):
    lines = [OPEN] + [S(f"Zone{i % 2}", "2026/11/16 21:00:00")
                      for i in range(resume.MAX_RUN_EVENTS + 50)]
    r = resume.scan(_write(tmp_path / "Client.txt", lines))
    assert len(r["run_events"]) == resume.MAX_RUN_EVENTS


def _wait(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_core_restart_mid_map_keeps_the_map_and_the_deaths(tmp_path):
    log = _write(tmp_path / "Client.txt", RUN)
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.02,
                character="")
    try:
        core.record_consent(True)
        assert _wait(lambda: core.state.snapshot()["tailer"]["reading"])
        s = core.state.snapshot()
        assert s["maps"]["count"] == 2
        assert s["maps"]["current"]["name"] == "Savannah"
        assert s["maps"]["recent"][0]["time_s"] == 300.0
        assert len(s["death_recap"]["recent"]) == 1
        assert "maps" in s["tailer"]["resume"]["recovered"]
        # Live lines keep folding on top of the replayed runs.
        with open(log, "ab") as fh:
            fh.write((L(": Quill has been slain.", "2026/11/16 21:11:00")
                      + "\r\n").encode())
        assert _wait(lambda: len(
            core.state.snapshot()["death_recap"]["recent"]) == 2)
        assert core.state.snapshot()["maps"]["current"]["deaths"] == 1
    finally:
        core.close()
