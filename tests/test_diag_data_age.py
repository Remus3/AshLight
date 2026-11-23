"""RUN-DIAG-DATA-AGE (finding F-114): Checks shows "Game data is older
than your game" while the log names a campaign or map area id the cached
world_areas.json lacks (server/al/plug/dataage.py, acts.area_kind).

Synthetic events and tmp files only; no network, no live log."""

import json
import os

import pytest

from server.al import acts, diag
from server.al.core import Core
from server.al.plug import dataage


def gen(area_id, at=1000.0):
    return {"type": "area_generated", "area_id": area_id, "area_level": 1,
            "seed": "1", "recv_ts": at}


def write_areas(path, ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {i: {"name": f"Zone {i}", "area_level": 1, "is_town": False} for i in ids}
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    try:
        yield c
    finally:
        c.close()


def areas_path(core):
    return core.zone_table.path


def checks_row(core):
    rows = diag.checks(core.diag_facts(now=2000.0), 2000.0)
    return next((r for r in rows if r["id"] == "data_age"), None)


def test_area_kind_classes_ids():
    known = frozenset({"G1_1", "MapCrypt"})
    assert acts.area_kind("G1_1", known) == {"kind": "campaign", "known": True}
    assert acts.area_kind("G6_3", known) == {"kind": "campaign", "known": False}
    assert acts.area_kind("C_G2_4")["kind"] == "cruel"
    assert acts.area_kind("P1_2")["kind"] == "interlude"
    assert acts.area_kind("MapNewOne", known) == {"kind": "map", "known": False}
    assert acts.area_kind("HideoutFelled", known)["kind"] == "hideout"
    assert acts.area_kind("MapHideoutX")["kind"] == "hideout"
    assert acts.area_kind("SomethingElse")["kind"] == "other"
    assert acts.area_kind(None) == {"kind": "other", "known": None}
    assert acts.area_kind("G1_1") == {"kind": "campaign", "known": None}
    assert acts.area_kind("G1_1", frozenset())["known"] is None


def test_load_ids(tmp_path):
    p = tmp_path / "world_areas.json"
    assert acts.load_ids(p) == frozenset()
    write_areas(p, ["G1_1", "MapCrypt", "HideoutFelled"])
    assert acts.load_ids(p) == frozenset({"G1_1", "MapCrypt", "HideoutFelled"})
    p.write_text("[1, 2]", encoding="utf-8")
    assert acts.load_ids(p) == frozenset()
    p.write_text("{bad", encoding="utf-8")
    assert acts.load_ids(p) == frozenset()


def test_unknown_campaign_id_raises_the_row(core):
    write_areas(areas_path(core), ["G1_1", "G1_2", "MapCrypt"])
    core.bus.publish(gen("G1_1"))
    assert checks_row(core) is None
    core._next_diag = 99.0
    core.bus.publish(gen("G6_1"))
    assert core._next_diag == 0.0  # Checks refreshes on the next pass
    row = checks_row(core)
    assert row == {"id": "data_age", "label": "Game data", "status": "fail",
                   "detail": ("Game data is older than your game: it doesn't list "
                              "an area you entered, so zone levels can be missing "
                              "there."),
                   "fix": ('Keep "Use web data" ticked under Settings, Reading and '
                           "web data. AshLight fetches newer game data by itself, "
                           "at most once a day.")}
    core.bus.publish(gen("MapBrandNew"))
    assert "2 areas" in checks_row(core)["detail"]


def test_hideout_id_does_not(core):
    write_areas(areas_path(core), ["G1_1"])
    for area_id in ("HideoutFelled", "MapHideoutCanal", "SomethingElse", "G1_1"):
        core.bus.publish(gen(area_id))
    assert checks_row(core) is None
    assert core.diag_facts(now=2000.0)["data_age_unknown"] == []


def test_no_row_without_a_snapshot_file(core):
    assert not areas_path(core).exists()
    core.bus.publish(gen("G6_1"))
    core.bus.publish(gen("MapBrandNew"))
    assert core.diag_facts(now=2000.0)["data_age_unknown"] == []
    assert checks_row(core) is None


def test_row_clears_after_a_refresh(core):
    write_areas(areas_path(core), ["G1_1"])
    core.bus.publish(gen("G6_1"))
    assert checks_row(core) is not None
    write_areas(areas_path(core), ["G1_1", "G6_1", "G6_2"])
    assert checks_row(core) is None
    assert core.diag_facts(now=2000.0)["data_age_unknown"] == []


def test_resumed_zone_counts(core):
    write_areas(areas_path(core), ["G1_1"])
    core.state.area_id = "G5_2"
    assert core.diag_facts(now=2000.0)["data_age_unknown"] == ["G5_2"]


def test_area_ids_share_the_zone_table_parse(tmp_path):
    """RUN-DATAAGE-SHARED-PARSE: the area id list rides the zone table's one
    parse of world_areas (acts.TableCache, RUN-PERF-PARSE-ONCE); start reads
    it once and a later Checks pass parses nothing more."""
    rt = tmp_path / "rt"
    areas = rt / "gamedata" / acts.FILE_NAME
    write_areas(areas, ["G1_1", "G1_2"])
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=rt, log_path=str(log), tail=False)
    try:
        share = c.zone_table._share
        assert share is not None and c.data_age.ids._share is share
        assert share.parses == 1
        assert c.data_age.ids.loads == 1  # filled at start from the kept parse
        c.bus.publish(gen("G6_1"))
        assert c.diag_facts(now=2000.0)["data_age_unknown"] == ["G6_1"]
        assert share.parses == 1
        write_areas(areas, ["G1_1", "G6_1"])
        st = os.stat(areas)
        os.utime(areas, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 9))
        assert c.diag_facts(now=2000.0)["data_age_unknown"] == []
        assert share.parses == 2  # one parse per change for every table
        assert c.zone_table.get()
    finally:
        c.close()


def test_ids_from_doc():
    assert acts.ids_from_doc({"G1_1": {}, "": {}, "MapX": 1}) == frozenset({"G1_1", "MapX"})
    assert acts.ids_from_doc([1, 2]) == frozenset()
    assert acts.ids_from_doc(None) == frozenset()


def test_seen_ids_are_bounded(tmp_path):
    p = tmp_path / "world_areas.json"
    write_areas(p, ["G1_1"])
    t = dataage.Tracker(p)
    for i in range(dataage.MAX_SEEN + 5):
        assert t.note(f"Map{i}") is True
    assert not t.note("Map20")
    got = t.unknown()
    assert len(got) == dataage.MAX_SEEN
    assert got[0] == "Map5"


def test_row_shape_and_view():
    assert dataage.rows({}, 0.0) is None
    assert dataage.rows({"data_age_unknown": [1, None]}, 0.0) is None
    row = dataage.rows({"data_age_unknown": ["G6_1"]}, 0.0)
    assert row["status"] == "fail" and row["fix"]
    for text in (dataage.detail_text(1), dataage.detail_text(3), dataage.FIX):
        assert text.isascii()
