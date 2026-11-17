"""UTIL-MAPRUN acceptance, closed as a duplicate of UTIL-MAPS (area-util
batch 8): every acceptance point of the row checked against
server/al/runs.py through Client.txt-shaped lines and the real parser.
Enter a map, a town scene pauses it, a portal back (same id + seed) keeps
one map, a new seed ends it, deaths per map, area level, session totals and
maps per hour (the one missing point, added per adjudicator ruling
2026-11-17). The `Map` area-id prefix is still a guess until a live map is
logged (moved into LIVE-1). Synthetic lines only; no network, no game."""

import datetime

from server.al import parser, runs
from server.al.state import SessionState

BASE = datetime.datetime(2026, 11, 17, 20)


class Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def _line(n, hms, body):
    return f"2026/11/17 {hms} {n} a [INFO Client 5150] {body}"


def gen(n, hms, area, seed, level=65):
    return (f"2026/11/17 {hms} {n} a [DEBUG Client 5150] Generating level "
            f'{level} area "{area}" with seed {seed}')


def scene(n, hms, name):
    return _line(n, hms, f"[SCENE] Set Source [{name}]")


def slain(n, hms, who="Ash"):
    return _line(n, hms, f": {who} has been slain.")


def feed(lines, now_s):
    clock = Clock(0.0)
    st = SessionState(clock=clock)
    for line in lines:
        ev = parser.parse_line(line)
        assert ev is not None, line
        t = datetime.datetime.fromisoformat(ev["ts_local"])
        ev["recv_ts"] = (t - BASE).total_seconds()
        st.apply(ev)
    clock.t = now_s
    return st.snapshot()


SESSION = [
    _line(1, "20:00:00", ": Ash (Witch) is now level 80"),
    gen(2, "20:00:00", "HideoutFelled", 1, level=1),
    scene(3, "20:00:01", "Felled Hideout"),
    # enter map 1
    gen(4, "20:01:00", "MapCrypt", 7, level=70),
    scene(5, "20:01:00", "Crypt"),
    slain(6, "20:03:00"),
    # town trip pauses (a non-hideout town scene, not the map's)
    gen(7, "20:04:00", "HideoutFelled", 1, level=1),
    scene(8, "20:04:00", "Ziggurat Refuge"),
    # portal back: same id + seed -> the same map, one clock
    gen(9, "20:06:00", "MapCrypt", 7, level=70),
    scene(10, "20:06:00", "Crypt"),
    # new map (new seed) ends map 1: 3:00 + 1:00 = 4:00 in map
    gen(11, "20:07:00", "MapSavannah", 8, level=71),
    scene(12, "20:07:00", "Savannah"),
    # third map ends map 2 after 5:00
    gen(13, "20:12:00", "MapBog", 9, level=72),
    scene(14, "20:12:00", "Bog"),
]


def test_enter_pause_portal_back_new_map_and_deaths():
    snap = feed(SESSION, 14 * 60.0)
    m = snap["maps"]
    assert m["count"] == 3            # the portal back did not count a map
    assert m["done"] == 2
    assert m["recent"] == [
        {"name": "Savannah", "area_level": 71, "time_s": 300.0, "deaths": 0},
        {"name": "Crypt", "area_level": 70, "time_s": 240.0, "deaths": 1},
    ]
    assert m["current"] == {"name": "Bog", "area_level": 72, "time_s": 120.0,
                            "deaths": 0, "inside": True}
    assert m["avg_text"] == "Average map: 4:30 over 2 finished maps."
    assert m["deaths_text"] == "1 death in maps."


def test_town_scene_pauses_the_map_clock():
    snap = feed(SESSION[:8], 5 * 60.0)
    cur = snap["maps"]["current"]
    assert cur["inside"] is False
    assert cur["time_s"] == 180.0     # 20:01 -> 20:04, the town time not counted


def test_maps_per_hour_waits_for_two_maps_and_ten_minutes():
    snap = feed(SESSION[:12], 8 * 60.0)          # 1 finished map
    assert snap["maps"]["per_hour"] is None
    assert snap["maps"]["rate_text"] == ""
    # 2 finished maps, 11:00 after the first map opened at 20:01
    snap = feed(SESSION, 12 * 60.0)
    assert snap["maps"]["rate_text"] == "10.9 maps per hour since the first map."
    m = runs.MapRuns()                           # 2 maps, under 10 minutes
    for at, seed in ((0.0, "1"), (100.0, "2"), (200.0, "3")):
        m.on_generated("MapCrypt", at, 70, seed=seed)
    assert m.per_hour(599.0) is None
    assert m.per_hour(600.0) == 12.0


def test_maps_per_hour_text_exact():
    m = runs.MapRuns()
    for at, seed in ((0.0, "1"), (600.0, "2"), (1200.0, "3")):
        m.on_generated("MapCrypt", at, 70, seed=seed)
        m.on_scene("Crypt", at, False)
    v = m.view(1800.0)                 # 2 finished maps in 30 minutes
    assert v["per_hour"] == 4.0
    assert v["rate_text"] == "4.0 maps per hour since the first map."


def test_maps_per_hour_survives_replay():
    events = []
    for at, seed in ((0.0, "1"), (600.0, "2"), (1200.0, "3")):
        events.append({"type": "area_generated", "area_id": "MapCrypt",
                       "area_level": 70, "seed": seed, "at": at})
        events.append({"type": "scene_changed", "scene": "Crypt",
                       "is_hideout": False, "at": at})
    maps, _log = runs.replay(events)
    assert maps.per_hour(1800.0) == 4.0
