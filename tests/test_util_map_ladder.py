"""UTIL-MAP-LADDER: maps, deaths, median time and level-ups per map area
level, this session and (run history on) across sessions (research 0032
section 5.4, research 0031 ruling I).

Every event here is synthetic (invented names and ids)."""

import json

from server.al import mapladder, runs
from server.al.core import Core
from server.al.state import SessionState


def _ev(t, at, **kw):
    return dict(kw, type=t, recv_ts=at)


def gen(area_id, at, level, seed):
    return _ev("area_generated", at, area_id=area_id, area_level=level, seed=seed)


def scene(name, at, hideout=False):
    return _ev("scene_changed", at, scene=name, is_hideout=hideout)


def lvl(at, level, who="Quill"):
    return _ev("level_up", at, character=who, level=level, **{"class": "Witch"})


def died(at, who="Quill"):
    return _ev("death", at, character=who)


def _state(events, t0=1000.0):
    clock = [t0]
    st = SessionState(clock=lambda: clock[0])
    for e in events:
        clock[0] = e["recv_ts"]
        st.apply(e)
    return st, clock


def _map(area_id, start, level, seed, dur, deaths=0):
    out = [gen(area_id, start, level, seed), scene(area_id[3:], start + 1)]
    for i in range(deaths):
        out.append(died(start + 2 + i))
    out.append(gen("HideoutFelled", start + dur, 1, 1))
    out.append(scene("Felled Hideout", start + dur + 1, hideout=True))
    return out


def _ladder(st):
    return st.snapshot()["maps"]["ladder"]


def test_empty_ladder_has_empty_text():
    st, _ = _state([])
    lad = _ladder(st)
    assert lad["levels"] == [] and lad["highest"] is None
    assert lad["empty_text"] == mapladder.EMPTY_TEXT and lad["text"] == ""


def test_one_level_counts_maps_deaths_and_median():
    ev = [lvl(1000, 80)]
    ev += _map("MapCrypt", 1100, 65, 1, 300, deaths=1)
    ev += _map("MapBog", 1500, 65, 2, 500)
    ev += _map("MapCrypt", 2100, 65, 3, 400)
    st, _ = _state(ev)
    lad = _ladder(st)
    assert lad["highest"] == 65 and lad["maps"] == 3
    (row,) = lad["levels"]
    assert row["area_level"] == 65 and row["maps"] == 3 and row["deaths"] == 1
    # times 300, 500, 400: scene to hideout scene
    assert row["median_s"] == 400 and row["median_text"] == "6:40"
    assert lad["text"] == "Highest map level: 65, over 3 maps. " + mapladder.MEDIAN_NOTE


def test_several_levels_highest_first_with_deaths_per_level():
    ev = [lvl(1000, 80)]
    ev += _map("MapCrypt", 1100, 65, 1, 300, deaths=2)
    ev += _map("MapBog", 1500, 67, 2, 200)
    ev += _map("MapCrypt", 1800, 66, 3, 100, deaths=1)
    st, _ = _state(ev)
    lad = _ladder(st)
    assert [r["area_level"] for r in lad["levels"]] == [67, 66, 65]
    assert [r["deaths"] for r in lad["levels"]] == [0, 1, 2]
    assert lad["highest"] == 67


def test_portal_reentry_same_seed_is_one_map():
    ev = [lvl(1000, 80),
          gen("MapCrypt", 1100, 65, 9), scene("Crypt", 1101),
          gen("HideoutFelled", 1200, 1, 1), scene("Felled Hideout", 1201, True),
          gen("MapCrypt", 1300, 65, 9), scene("Crypt", 1301),
          died(1310)]
    st, _ = _state(ev)
    (row,) = _ladder(st)["levels"]
    assert row["maps"] == 1 and row["deaths"] == 1
    # the open map has no final time yet
    assert row["median_s"] is None and row["median_text"] == "--:--"


def test_level_ups_count_only_inside_a_map():
    ev = [lvl(1000, 80)]
    ev += [gen("MapCrypt", 1100, 70, 1), scene("Crypt", 1101), lvl(1150, 81),
           gen("HideoutFelled", 1200, 1, 1), scene("Felled Hideout", 1201, True),
           lvl(1250, 82),
           lvl(1260, 30, who="Other")]
    st, _ = _state(ev)
    (row,) = _ladder(st)["levels"]
    assert row["level_ups"] == 1


def test_map_without_area_level_is_left_out():
    lad = mapladder.ladder([{"area_level": None, "time_s": 5, "done": True},
                            {"area_level": True, "time_s": 5, "done": True}])
    assert lad["levels"] == [] and lad["maps"] == 0


def test_rows_capped_to_max_rows():
    rows = [{"area_level": i, "time_s": 10, "done": True} for i in range(30)]
    lad = mapladder.ladder(rows)
    assert len(lad["levels"]) == mapladder.MAX_ROWS
    assert lad["levels"][0]["area_level"] == 29 and lad["maps"] == 30


def test_resume_replay_rebuilds_the_same_ladder():
    ev = [lvl(1000, 80)]
    ev += _map("MapCrypt", 1100, 65, 1, 300, deaths=1)
    ev += [gen("MapBog", 1500, 66, 2), scene("Bog", 1501), lvl(1550, 81)]
    live, clock = _state(ev)
    replay_events = [dict(e, at=e["recv_ts"]) for e in ev]
    maps, _ = runs.replay(replay_events, me="Quill")
    assert maps.view(clock[0])["ladder"] == _ladder(live)


# -- across sessions (run history on)

def _core(tmp_path, monkeypatch=None):
    core = Core(runtime=tmp_path / "rt", config_path=tmp_path / "local.json", tail=False)
    return core


def _feed(core, events):
    for e in events:
        core.state._clock = (lambda t: (lambda: t))(e["recv_ts"])
        core.state.apply(e)


def test_store_saves_finished_maps_once_and_survives_restart(tmp_path):
    path = tmp_path / mapladder.FILE_NAME
    lad = mapladder.MapLadder(path)
    rec = {"area_id": "MapCrypt", "seed": 5, "opened_at": 100.0, "area_level": 65,
           "time_s": 200.0, "deaths": 1, "level_ups": 0, "done": True}
    assert lad.record("Quill", [rec]) is True
    # a restart rebuilds the same map with a log time a second apart
    again = dict(rec, opened_at=101.0)
    assert lad.record("Quill", [again]) is False
    lad2 = mapladder.MapLadder(path)
    view = lad2.view("Quill", [dict(again)])
    assert view["maps"] == 1 and view["title"] == mapladder.TITLE_ALL
    # another character's maps stay apart
    assert lad2.view("Other", [])["maps"] == 0
    doc = json.loads(path.read_text(encoding="ascii"))
    assert doc["schema"] == mapladder.SCHEMA


def test_store_is_bounded(tmp_path):
    lad = mapladder.MapLadder(tmp_path / mapladder.FILE_NAME)
    recs = [{"area_id": "MapCrypt", "seed": i, "opened_at": float(i * 1000),
             "area_level": 65, "time_s": 10.0} for i in range(mapladder.MAX_SAVED + 50)]
    lad.record("Quill", recs)
    assert len(mapladder.load(lad.path)["Quill"]) == mapladder.MAX_SAVED
    for i in range(mapladder.MAX_CHARACTERS + 3):
        lad.record(f"C{i}", [dict(recs[0], opened_at=1e9 + i)])
    assert len(mapladder.load(lad.path)) == mapladder.MAX_CHARACTERS


def test_bad_file_reads_empty(tmp_path):
    p = tmp_path / mapladder.FILE_NAME
    p.write_text("{not json", encoding="ascii")
    assert mapladder.load(p) == {}
    p.write_text(json.dumps({"characters": {"Q": {"maps": [
        {"area_id": "", "opened_at": 1}, {"area_id": "MapX", "opened_at": 1,
                                          "area_level": 5, "time_s": -1},
        {"area_id": "MapX", "opened_at": 1, "area_level": 5, "time_s": 3,
         "deaths": 10 ** 30}]}}}), encoding="ascii")
    (rec,) = mapladder.load(p)["Q"]
    assert rec["deaths"] == mapladder.MAX_COUNT


def test_core_publishes_all_sessions_ladder_with_history_on(tmp_path):
    core = _core(tmp_path)
    ev = [lvl(1000, 80)] + _map("MapCrypt", 1100, 65, 1, 300, deaths=1)
    ev += [gen("MapBog", 1500, 66, 2), scene("Bog", 1501)]
    _feed(core, ev)
    core.tick_history()
    snap = core.state.snapshot()["maps"]
    assert snap["ladder_all"]["maps"] == 2
    saved = mapladder.load(core.ladder.path)
    assert [r["area_id"] for r in saved["Quill"]] == ["MapCrypt"]
    # a second core (restart) with the same session replayed: no double count
    core2 = _core(tmp_path)
    _feed(core2, ev)
    core2.tick_history()
    assert core2.state.snapshot()["maps"]["ladder_all"]["maps"] == 2
    assert len(mapladder.load(core2.ladder.path)["Quill"]) == 1


def test_core_history_off_saves_nothing_and_clear_empties(tmp_path):
    core = _core(tmp_path)
    ev = [lvl(1000, 80)] + _map("MapCrypt", 1100, 65, 1, 300)
    ev += [gen("MapBog", 1500, 66, 2)]  # closes the first map
    _feed(core, ev)
    core.tick_history()
    assert mapladder.load(core.ladder.path)
    core.set_history(clear=True)
    assert mapladder.load(core.ladder.path) == {}
    # the session's maps opened before the clear are not saved again
    assert core.state.snapshot()["maps"]["ladder_all"]["maps"] == 0
    assert mapladder.load(core.ladder.path) == {}
    core.set_history(enabled=False)
    assert core.state.snapshot()["maps"]["ladder_all"] is None
