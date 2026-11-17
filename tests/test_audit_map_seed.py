"""AUDIT-MAP-SEED (audit pass 2 findings P2-M1, P2-M2, P2-M3).

M1: a portal back into the same map instance logs a new "Generating level"
line with the same area id and seed; it is a re-entry, not a second map.
M2: DeathLog's "most deaths" comes from the capped rows, never an uncapped
counter. M3: after a restart the recap never says "No deaths this session"
while the deaths tile shows restored deaths. Synthetic events only."""

from server.al import parser, resume, runs
from server.al.state import SessionState


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def gen(area_id, at, seed="7", level=65):
    return {"type": "area_generated", "area_id": area_id, "area_level": level,
            "seed": seed, "recv_ts": at}


def scene(name, at, hideout=False):
    return {"type": "scene_changed", "scene": name, "is_null": False,
            "is_transient": False, "is_hideout": hideout, "recv_ts": at}


def death(at, who="Ash"):
    return {"type": "death", "character": who, "suicide": False, "recv_ts": at}


# -- M1


def test_same_id_and_seed_is_a_reentry_one_map_one_clock():
    st = SessionState(clock=Clock(2000.0))
    for ev in (gen("HideoutFelled", 90.0, seed="3", level=1),
               gen("MapCrypt", 100.0), scene("Crypt", 110.0),
               gen("HideoutFelled", 200.0, seed="3", level=1),
               scene("Felled Hideout", 210.0, hideout=True),
               gen("MapCrypt", 300.0), scene("Crypt", 310.0),
               death(400.0)):
        st.apply(ev)
    v = st.maps.view(500.0)
    assert v["count"] == 1
    assert v["done"] == 0
    assert v["recent"] == []
    # 100 s before the hideout trip + 190 s after the portal back.
    assert v["current"] == {"name": "Crypt", "area_level": 65, "time_s": 290.0,
                            "deaths": 1, "inside": True}


def test_same_id_new_seed_is_a_new_map():
    m = runs.MapRuns()
    assert m.on_generated("MapCrypt", 100.0, 65, seed="7") is True
    assert m.on_scene("Crypt", 110.0, False) is True
    assert m.on_generated("MapCrypt", 300.0, 65, seed="8") is True
    v = m.view(400.0)
    assert v["count"] == 2
    assert v["done"] == 1


def test_no_seed_keeps_the_old_rule():
    m = runs.MapRuns()
    assert m.on_generated("MapCrypt", 100.0, 65) is True
    assert m.on_generated("MapCrypt", 200.0, 65) is True
    assert m.view(300.0)["count"] == 2


def test_reentry_after_campaign_close_is_a_new_map():
    m = runs.MapRuns()
    m.on_generated("MapCrypt", 100.0, 65, seed="7")
    m.on_generated("G1_town", 200.0, 1, seed="9")  # campaign closes the map
    assert m.on_generated("MapCrypt", 300.0, 65, seed="7") is True
    assert m.view(400.0)["count"] == 2


def test_replay_keeps_the_seed_through_resume_fields():
    lines = [
        '2026/11/17 10:00:00 1 abc [DEBUG Client 1] Generating level 65 area '
        '"MapCrypt" with seed 7',
        '2026/11/17 10:01:00 1 abc [DEBUG Client 1] Generating level 1 area '
        '"HideoutFelled" with seed 3',
        '2026/11/17 10:02:00 1 abc [DEBUG Client 1] Generating level 65 area '
        '"MapCrypt" with seed 7',
    ]
    evs = [parser.parse_line(x) for x in lines]
    assert all(e and e["type"] == "area_generated" for e in evs)
    compact = resume._run_events(list(reversed(evs)))
    assert [e.get("seed") for e in compact] == ["7", "3", "7"]
    for i, e in enumerate(compact):
        e["at"] = 100.0 + 60 * i
    maps, _ = runs.replay(compact)
    assert maps.view(400.0)["count"] == 1


# -- M2


def test_most_deaths_derives_from_capped_rows():
    log = runs.DeathLog()
    for i in range(10000):
        log.add(at=float(i), zone=f"Zone {i}", area_level=1, level=1, zone_s=1.0)
    assert len(log.rows) == runs.MAX_DEATHS
    assert len(log.by_zone()) <= runs.MAX_DEATHS
    for i in range(3):
        log.add(at=20000.0 + i, zone="Crypt", area_level=65, level=70, zone_s=5.0)
    assert log.view()["worst_text"] == "Most deaths: Crypt (3)."


def test_most_deaths_forgets_rows_that_fell_off_the_cap():
    log = runs.DeathLog()
    for i in range(2):
        log.add(at=float(i), zone="Old Zone", area_level=1, level=1, zone_s=1.0)
    for i in range(runs.MAX_DEATHS):
        log.add(at=10.0 + i, zone=f"Zone {i}", area_level=1, level=1, zone_s=1.0)
    assert log.view()["worst_text"] == ""


# -- M3


def test_restored_deaths_without_rows_never_say_no_deaths():
    st = SessionState(clock=Clock(2000.0))
    st.restore({"character": "Ash", "deaths": 3, "run_events": []})
    snap = st.snapshot()
    assert snap["deaths"] == 3
    rec = snap["death_recap"]
    assert rec["recent"] == []
    assert "No deaths" not in rec["empty_text"]
    # merged with UX-NEW-CARDS: its wording (earlier deaths) is kept
    assert rec["empty_text"] == ("3 deaths came before AshLight started reading, so "
                                 "their zones aren't known. New deaths show here "
                                 "with their zone and level.")


def test_recap_text_unchanged_with_no_deaths():
    st = SessionState(clock=Clock(2000.0))
    assert st.snapshot()["death_recap"]["empty_text"] == runs.DEATHS_EMPTY_TEXT
