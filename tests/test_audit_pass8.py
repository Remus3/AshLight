"""AREA-AUDIT pass 8 regression tests (docs/audit/2026-11-17-audit.md).

Every event here is synthetic (invented names and ids)."""

from server.al import mapladder
from server.al.core import Core


def _ev(t, at, **kw):
    return dict(kw, type=t, recv_ts=at)


def _gen(area_id, at, level, seed):
    return _ev("area_generated", at, area_id=area_id, area_level=level, seed=seed)


def _scene(name, at, hideout=False):
    return _ev("scene_changed", at, scene=name, is_hideout=hideout)


def _lvl(at, level, who):
    return _ev("level_up", at, character=who, level=level, **{"class": "Witch"})


def _map(area_id, start, level, seed, dur):
    return [_gen(area_id, start, level, seed), _scene(area_id[3:], start + 1),
            _gen("HideoutFelled", start + dur, 1, 1),
            _scene("Felled Hideout", start + dur + 1, hideout=True)]


def _feed(core, events):
    for e in events:
        core.state._clock = (lambda t: (lambda: t))(e["recv_ts"])
        core.state.apply(e)


def test_p8_1_map_ladder_never_files_one_characters_maps_under_another(tmp_path):
    """P8-1: the session's map runs are not per character (runs.MapRuns
    stays across a UTIL-MULTICHAR switch), so after a relog to another
    character every map of the first one was saved again under the
    second's name and showed in its all-sessions ladder."""
    core = Core(runtime=tmp_path / "rt", config_path=tmp_path / "local.json", tail=False)
    _feed(core, [_lvl(1000, 80, "Quill")] + _map("MapCrypt", 1100, 65, 1, 300)
          + _map("MapBog", 1500, 66, 2, 300))
    core.tick_history()
    # MapBog is still open (a hideout trip never closes a map)
    assert [r["area_id"] for r in mapladder.load(core.ladder.path)["Quill"]] == [
        "MapCrypt"]
    # a game restart, then the player's other character (decision 0038)
    _feed(core, [_ev("log_opened", 2000), _lvl(2100, 70, "Sable")]
          + _map("MapSump", 2200, 70, 3, 300) + [_gen("MapFen", 2600, 71, 4)])
    assert core.state.snapshot()["character"] == "Sable"
    core.tick_history()
    saved = mapladder.load(core.ladder.path)
    assert [r["area_id"] for r in saved["Quill"]] == ["MapCrypt"]
    assert [r["area_id"] for r in saved["Sable"]] == ["MapSump"]
    # Sable's all-sessions ladder: its saved map and its open one only
    assert core.state.snapshot()["maps"]["ladder_all"]["maps"] == 2


def test_p8_1_a_map_opened_before_the_switch_line_stays_with_the_new_character(tmp_path):
    """The switch happens on the first level-up after a game start; a map
    generated in that game run before the level-up is the new
    character's, so the boundary is the game start, not the switch."""
    core = Core(runtime=tmp_path / "rt", config_path=tmp_path / "local.json", tail=False)
    _feed(core, [_lvl(1000, 80, "Quill")] + _map("MapCrypt", 1100, 65, 1, 300)
          + [_gen("MapAsh", 1500, 65, 9)])
    core.tick_history()
    _feed(core, [_ev("log_opened", 2000), _gen("MapSump", 2050, 70, 3),
                 _scene("Sump", 2051), _lvl(2100, 70, "Sable"),
                 _gen("MapFen", 2400, 71, 4)])
    core.tick_history()
    saved = mapladder.load(core.ladder.path)
    assert [r["area_id"] for r in saved["Sable"]] == ["MapSump"]
    assert [r["area_id"] for r in saved["Quill"]] == ["MapCrypt"]
