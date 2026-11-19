"""RUN-DURABLE-STORE-FILES (finding F-014, decision 0036 amendment
2026-11-18): every player-data store saves through jsonfile with one .bak
of its last good copy, reads with the .bak restore, and every clear path
removes the .bak with the data. Synthetic data; tmp files only."""

import pytest

from server.al import (hints, jsonfile, layout, mapladder, pricewatch, runhistory,
                       summary, zoneguide)
from server.al.core import Core


RUN = {"started_at": 1000.0, "character": "Ash", "class": "Monk",
       "splits": [{"key": "act1", "label": "Act 1", "time_s": 1200.0}],
       "deaths": {"The Riverbank": 2}, "finished": False}
MAP = {"area_id": "MapAugury", "seed": 7, "opened_at": 5000.0, "area_level": 65,
       "time_s": 300.0, "deaths": 1, "level_ups": 0}
VISITS = {"schema": 1, "characters": {"Ash": {"act1": ["The Riverbank"]}}}


# -- one case per store: (file name, save(path), load(path) -> data or None)

def _run_save(p):
    runhistory.RunHistory(p).record(RUN)  # False on a repeat: nothing new


def _run_load(p):
    return runhistory.RunHistory(p).runs or None


def _ladder_save(p):
    mapladder.MapLadder(p).record("Ash", [MAP])  # False on a repeat


def _ladder_load(p):
    return mapladder.MapLadder(p).by or None


def _watch_save(p):
    item = {"name": "Mirror", "base": "Mirror", "rarity": "Currency", "corrupted": False}
    assert pricewatch.PriceWatch(p).record(item, {"value": 3.5, "unit": "divine"}, 100.0)


def _watch_load(p):
    return pricewatch.PriceWatch(p).items or None


def _summary_save(p):
    summary.save(p, {"title": "Session", "played_s": 60})


def _summary_load(p):
    return summary.load_last(p)


def _hints_save(p):
    h = hints.Hints(p)
    h.on_level("Ash", 2, 10.0)
    h._save()


def _hints_load(p):
    return dict(hints.Hints(p).chars) or None


def _visits_save(p):
    zoneguide.write_visits(p, VISITS)


def _visits_load(p):
    return zoneguide.read_visits(p) or None


def _layout_save(p):
    layout.save(p, {"corner": "top-left"})


def _layout_load(p):
    got = layout.load(p)
    return got if got["corner"] == "top-left" else None


STORES = {
    "runhistory": (runhistory.FILE_NAME, _run_save, _run_load),
    "mapladder": (mapladder.FILE_NAME, _ladder_save, _ladder_load),
    "pricewatch": (pricewatch.FILE_NAME, _watch_save, _watch_load),
    "summary": ("session_summaries.json", _summary_save, _summary_load),
    "hints": (hints.FILE_NAME, _hints_save, _hints_load),
    "visits": ("zone_visits.json", _visits_save, _visits_load),
    "layout": ("local.json", _layout_save, _layout_load),
}


@pytest.fixture(autouse=True)
def _no_restored_leftovers():
    jsonfile.pop_restored()
    yield
    jsonfile.pop_restored()


@pytest.mark.parametrize("name", sorted(STORES))
def test_each_store_save_keeps_one_bak(tmp_path, name):
    fname, save, load = STORES[name]
    path = tmp_path / fname
    save(path)
    save(path)  # a second save never adds a second .bak or a temp file
    bak = jsonfile.bak_path(path)
    assert bak.is_file()
    assert bak.read_bytes() == path.read_bytes()
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([path.name, bak.name])
    assert load(path) is not None


@pytest.mark.parametrize("name", sorted(STORES))
def test_store_restores_from_bak_when_main_is_half(tmp_path, name):
    """C9: a main file cut in half (a crash mid-write on a disk that lost the
    rename's data) reads back from its .bak, and the main file is healed."""
    fname, save, load = STORES[name]
    path = tmp_path / fname
    save(path)
    good = path.read_bytes()
    path.write_bytes(good[:len(good) // 2])
    assert load(path) is not None
    assert path.read_bytes() == good
    assert str(path) in jsonfile.pop_restored()


def test_missing_main_is_not_restored_from_bak(tmp_path):
    """A store whose main file is gone starts empty: a stray .bak alone is
    never revived (a cleared store removes both)."""
    path = tmp_path / runhistory.FILE_NAME
    _run_save(path)
    path.unlink()
    assert _run_load(path) is None and not path.exists()


def test_clear_run_history_removes_the_bak_files(tmp_path):
    """The dashboard's Clear run history (core.set_history(clear=True))
    empties the run history, map ladder and zone visits files and leaves
    none of their .bak files behind."""
    rt = tmp_path / "rt"
    core = Core(runtime=rt, config_path=tmp_path / "local.json", tail=False)
    try:
        assert core.history.record(RUN)
        assert core.ladder.record("Ash", [MAP])
        zoneguide.write_visits(core.visits_path, VISITS)
        files = [core.history.path, core.ladder.path, core.visits_path]
        for p in files:
            assert jsonfile.bak_path(p).is_file(), p
        core.set_history(clear=True)
        for p in files:
            assert p.is_file(), p
            assert not jsonfile.bak_path(p).exists(), p
        assert runhistory.load(core.history.path) == []
        assert mapladder.load(core.ladder.path) == {}
        assert not zoneguide.read_visits(core.visits_path).get("characters")
    finally:
        core.close()


def test_price_watch_clear_removes_its_bak(tmp_path):
    path = tmp_path / pricewatch.FILE_NAME
    _watch_save(path)
    w = pricewatch.PriceWatch(path)
    w.clear()
    assert w.items == [] and pricewatch.PriceWatch(path).items == []
    assert not jsonfile.bak_path(path).exists()


def test_a_cleared_store_saves_a_bak_again_on_its_next_write(tmp_path):
    path = tmp_path / runhistory.FILE_NAME
    h = runhistory.RunHistory(path)
    assert h.record(RUN)
    h.clear()
    assert not jsonfile.bak_path(path).exists()
    assert h.record(RUN)
    assert jsonfile.bak_path(path).read_bytes() == path.read_bytes()
