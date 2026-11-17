"""UTIL-MAPS and UTIL-DEATHS: the map run tracker and the death recap,
folded from Client.txt events the core already parses (area generation,
scene change, death). Exact-output tests on replayed event sequences; no
network, no game."""

from server.al import mapladder, runs
from server.al.state import SessionState


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def gen(area_id, at, level=65):
    return {"type": "area_generated", "area_id": area_id, "area_level": level,
            "seed": "1", "recv_ts": at}


def scene(name, at, hideout=False):
    return {"type": "scene_changed", "scene": name, "is_null": False,
            "is_transient": False, "is_hideout": hideout, "recv_ts": at}


def death(at, who="Ash"):
    return {"type": "death", "character": who, "suicide": False, "recv_ts": at}


def up(level, at, who="Ash"):
    return {"type": "level_up", "character": who, "class": "Witch",
            "level": level, "recv_ts": at}


# -- formatting


def test_clock_text():
    assert runs.clock_text(0) == "0:00"
    assert runs.clock_text(59.9) == "0:59"
    assert runs.clock_text(192) == "3:12"
    assert runs.clock_text(3725) == "1:02:05"
    assert runs.clock_text(None) == "--:--"
    assert runs.clock_text(-5) == "0:00"


def test_map_name():
    assert runs.map_name("MapCrypt", None) == "Crypt"
    assert runs.map_name("MapCrypt", "Crypt of Ash") == "Crypt of Ash"
    assert runs.map_name("Map", None) == "Map"
    assert runs.map_name("MapUberBoss_Arbiter", None) == "Uber Boss Arbiter"
    assert runs.map_name("MapSunTemple", None) == "Sun Temple"


# -- UTIL-MAPS


def test_map_runs_exact():
    m = runs.MapRuns()
    assert m.on_generated("HideoutFelled", 100.0, 1) is False
    assert m.on_generated("MapCrypt", 200.0, 65) is True
    assert m.on_scene("Crypt", 210.0, False) is True       # names the map
    assert m.on_death(300.0) is True
    assert m.on_scene("Felled Hideout", 500.0, True) is True  # left: 290 s in map
    assert m.on_scene("Crypt", 600.0, False) is True       # back in via portal
    assert m.on_generated("HideoutFelled", 700.0, 1) is False  # generation alone changes nothing
    assert m.on_scene("Felled Hideout", 700.0, True) is True   # 100 s more
    assert m.on_generated("MapSavannah", 800.0, 66) is True    # closes Crypt
    assert m.on_scene("Savannah", 805.0, False) is True
    v = m.view(1105.0)
    assert v["count"] == 2
    assert v["done"] == 1
    assert v["current"] == {"name": "Savannah", "area_level": 66,
                            "time_s": 300.0, "deaths": 0, "inside": True}
    assert v["recent"] == [{"name": "Crypt", "area_level": 65, "time_s": 390.0,
                            "deaths": 1}]
    assert v["avg_s"] == 390.0
    assert v["avg_text"] == "Average map: 6:30 over 1 finished map."
    assert v["deaths_text"] == "1 death in maps."


def test_campaign_zone_closes_open_map_and_hideout_pauses_clock():
    m = runs.MapRuns()
    m.on_generated("MapCrypt", 0.0, 65)
    m.on_scene("Crypt", 0.0, False)
    m.on_scene("Felled Hideout", 60.0, True)
    v = m.view(1000.0)
    assert v["current"]["time_s"] == 60.0       # the clock is paused outside
    assert v["current"]["inside"] is False
    m.on_generated("G1_town", 1000.0, 15)
    v = m.view(2000.0)
    assert v["current"] is None
    assert v["recent"][0]["time_s"] == 60.0


def test_death_outside_a_map_is_not_counted_in_it():
    m = runs.MapRuns()
    m.on_generated("MapCrypt", 0.0, 65)
    m.on_scene("Crypt", 0.0, False)
    m.on_scene("Felled Hideout", 10.0, True)
    assert m.on_death(20.0) is False
    assert m.view(30.0)["current"]["deaths"] == 0


def test_map_view_empty_and_plural_text():
    v = runs.MapRuns().view(0.0)
    assert v == {"count": 0, "done": 0, "current": None, "recent": [],
                 "avg_s": None, "avg_text": "", "per_hour": None,
                 "rate_text": "", "deaths_text": "",
                 "empty_text": runs.MAPS_EMPTY_TEXT,
                 "ladder": mapladder.ladder([])}  # UTIL-MAP-LADDER
    m = runs.MapRuns()
    for i, at in enumerate((0.0, 100.0, 300.0)):
        m.on_generated("MapCrypt", at, 65)
        m.on_scene("Crypt", at, False)
        m.on_death(at + 1)
        m.on_death(at + 2)
    v = m.view(400.0)
    assert v["done"] == 2
    assert v["avg_s"] == 150.0
    assert v["avg_text"] == "Average map: 2:30 over 2 finished maps."
    assert v["deaths_text"] == "6 deaths in maps."


def test_map_history_is_capped():
    m = runs.MapRuns()
    for i in range(runs.MAX_MAPS + 10):
        m.on_generated("MapCrypt", float(i), 65)
    v = m.view(1000.0)
    assert v["count"] == runs.MAX_MAPS + 10
    assert len(v["recent"]) == runs.RECENT_MAPS


# -- UTIL-DEATHS


def test_death_recap_exact():
    d = runs.DeathLog()
    assert d.view() == {"recent": [], "worst_text": "", "earlier_text": "",
                        "empty_text": runs.DEATHS_EMPTY_TEXT}
    d.add(at=100.0, zone="Crypt", area_level=65, level=72, zone_s=192.0)
    d.add(at=200.0, zone="Savannah", area_level=66, level=72, zone_s=None)
    d.add(at=300.0, zone="Crypt", area_level=65, level=None, zone_s=5.0)
    v = d.view()
    assert [r["text"] for r in v["recent"]] == [
        "Died in Crypt (area level 65), 0:05 into the zone.",
        "Died in Savannah (area level 66) at level 72.",
        "Died in Crypt (area level 65) at level 72, 3:12 into the zone.",
    ]
    assert v["recent"][0]["at"] == 300.0
    assert v["worst_text"] == "Most deaths: Crypt (2)."


def test_death_recap_unknown_zone_and_cap():
    d = runs.DeathLog()
    d.add(at=1.0, zone=None, area_level=None, level=3, zone_s=None)
    assert d.view()["recent"][0]["text"] == "Died at level 3."
    assert d.view()["worst_text"] == ""   # one death names no worst zone
    for i in range(runs.RECENT_DEATHS + 3):
        d.add(at=float(i + 2), zone="Crypt", area_level=65, level=None, zone_s=None)
    assert len(d.view()["recent"]) == runs.RECENT_DEATHS


# -- wired into the session state snapshot


def test_snapshot_maps_and_death_recap():
    clock = Clock(0.0)
    st = SessionState(character="Ash", clock=clock)
    st.apply(up(72, 1.0))
    st.apply(gen("MapCrypt", 10.0, 65))
    st.apply(scene("Crypt", 12.0))
    st.apply(death(204.0))
    st.apply(death(250.0, who="Other"))      # another player's death: ignored
    st.apply(scene("Felled Hideout", 300.0, hideout=True))
    clock.t = 400.0
    snap = st.snapshot()
    assert snap["maps"]["current"] == {"name": "Crypt", "area_level": 65,
                                       "time_s": 288.0, "deaths": 1,
                                       "inside": False}
    assert snap["death_recap"]["recent"][0]["text"] == (
        "Died in Crypt (area level 65) at level 72, 3:12 into the zone.")
    assert snap["deaths"] == 1


def test_replayed_client_lines_exact():
    """Client.txt-shaped lines through the real parser into the state."""
    import datetime

    from server.al import parser
    lines = [
        '2026/11/17 20:00:00 1 a [INFO Client 5150] : Ash (Witch) is now level 72',
        '2026/11/17 20:00:10 2 a [DEBUG Client 5150] Generating level 65 area '
        '"MapCrypt" with seed 7',
        '2026/11/17 20:00:12 3 a [INFO Client 5150] [SCENE] Set Source [Crypt]',
        '2026/11/17 20:03:24 4 a [INFO Client 5150] : Ash has been slain.',
        '2026/11/17 20:04:00 5 a [INFO Client 5150] [SCENE] Set Source '
        '[Felled Hideout]',
        '2026/11/17 20:05:00 6 a [DEBUG Client 5150] Generating level 66 area '
        '"MapSavannah" with seed 8',
        '2026/11/17 20:05:02 7 a [INFO Client 5150] [SCENE] Set Source [Savannah]',
    ]
    clock = Clock(0.0)
    st = SessionState(clock=clock)
    base = datetime.datetime(2026, 11, 17, 20)
    for line in lines:
        ev = parser.parse_line(line)
        assert ev is not None, line
        t = datetime.datetime.fromisoformat(ev["ts_local"])
        ev["recv_ts"] = (t - base).total_seconds()
        st.apply(ev)
    clock.t = 362.0
    snap = st.snapshot()
    assert snap["maps"]["recent"] == [{"name": "Crypt", "area_level": 65,
                                       "time_s": 228.0, "deaths": 1}]
    assert snap["maps"]["current"]["name"] == "Savannah"
    assert snap["maps"]["current"]["time_s"] == 60.0
    assert [r["text"] for r in snap["death_recap"]["recent"]] == [
        "Died in Crypt (area level 65) at level 72, 3:12 into the zone."]


def test_death_recap_names_deaths_from_before_reading():
    """UX-NEW-CARDS: LIVE-RESUME restores the death count, not the details;
    the recap says so instead of "No deaths this session"."""
    d = runs.DeathLog()
    v = d.view(2)
    assert v["empty_text"] == ("2 deaths came before AshLight started reading, so "
                               "their zones aren't known. New deaths show here "
                               "with their zone and level.")
    assert v["earlier_text"] == ""
    assert d.view(1)["empty_text"].startswith("1 death came before")
    assert d.view(0)["empty_text"] == runs.DEATHS_EMPTY_TEXT
    d.add(100.0, "Crypt", 65, 70, 30.0)
    v = d.view(3)
    assert v["earlier_text"] == "2 deaths came before AshLight started reading."
    assert v["empty_text"].startswith("2 deaths came before")
    assert d.view(1)["earlier_text"] == ""


def test_snapshot_recap_counts_restored_deaths():
    st = SessionState(clock=Clock())
    st.restore({"deaths": 2, "character": "Ash"})
    assert st.snapshot()["death_recap"]["empty_text"].startswith("2 deaths came before")
