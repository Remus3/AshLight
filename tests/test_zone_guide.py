"""ZONE-GUIDE (decision 0043): the live zone guide, the per-character quest
tracker, hot reload and the shipped guide file's shape."""

import json
import os

import pytest

from server.al import acts, zoneguide
from server.al.state import SessionState

DOC = {
    "acts": {
        "G1": {"default": "Act one default.",
               "zones": {
                   "The Riverbank": {"objective": "Beat the boss at the river's end.",
                                     "next": "Clearfell Encampment",
                                     "layout": "Follow the river."},
                   "Clearfell": {"objective": "Find the way on.", "next": "The Grelwood",
                                 "optional": [{"kind": "resist", "text": "Rare boss: resist."}]},
                   "Freythorn": {"main": False,
                                 "optional": [{"kind": "spirit", "text": "Ritual boss: spirit."}]},
                   "The Grelwood": {"objective": "Go on."}}},
        "G2": {"zones": {"Vastiri Outskirts": {"objective": "Reach the caravan."}}},
    },
    "endgame": {"objective": "Kill the map boss.", "layout": "Boss tends to sit far away."},
}

GRAPH = {
    "G1_1": {"name": "The Riverbank", "waypoint": False, "town": False, "links": ["G1_town"]},
    "G1_town": {"name": "Clearfell Encampment", "waypoint": True, "town": True,
                "links": ["G1_1", "G1_2"]},
    "G1_2": {"name": "Clearfell", "waypoint": True, "town": False, "links": ["G1_town", "G1_3"]},
    "G1_3": {"name": "Mud Burrow", "waypoint": False, "town": False, "links": ["G1_2"]},
}


def _state(level=None):
    st = SessionState(clock=lambda: 10.0)
    st.set_zone_guide(guide=DOC, graph=GRAPH)
    if level:
        st.apply({"type": "level_up", "character": "Ash", "class": "Monk", "level": level})
    return st


def _enter(st, area_id, scene, area_level=1):
    st.apply({"type": "area_generated", "area_id": area_id, "area_level": area_level})
    st.apply({"type": "scene_changed", "scene": scene, "is_hideout": False})
    return st.snapshot()["zone_guide"]


def test_guide_shows_on_zone_change_with_waypoint_and_next():
    st = _state()
    assert st.snapshot()["zone_guide"] is None
    g = _enter(st, "G1_1", "The Riverbank")
    assert g["kind"] == "campaign" and g["act"] == "Act 1"
    assert g["objective"] == "Beat the boss at the river's end."
    assert g["next"] == "Clearfell Encampment" and g["layout"] == "Follow the river."
    assert g["waypoint"] == "No waypoint here. Nearest: Clearfell Encampment."
    assert g["line"].startswith("Beat the boss")
    g = _enter(st, "G1_2", "Clearfell", 2)
    assert g["waypoint"] == zoneguide.WAYPOINT_YES
    assert g["optional"] == [{"kind": "resist", "text": "Rare boss: resist."}]


def test_unknown_zone_falls_back_to_act_default_and_hideout_hides():
    st = _state()
    g = _enter(st, "G1_9", "Somewhere New")
    assert g["objective"] == "Act one default." and g["waypoint"] is None
    st.apply({"type": "scene_changed", "scene": "Your Hideout", "is_hideout": True})
    assert st.snapshot()["zone_guide"] is None


def test_endgame_and_unknown_ids():
    st = _state()
    g = _enter(st, "MapAlpineRidge", "Alpine Ridge", 65)
    assert g["kind"] == "endgame" and g["objective"] == "Kill the map boss."
    assert g["quest"] is None
    assert _enter(st, "SomethingElse", "Odd Place") is None


def test_level_advice():
    assert zoneguide.advice(None, 10) is None
    assert zoneguide.advice(5, 10)["mode"] == "clear"
    assert "5 levels under" in zoneguide.advice(5, 10)["text"]
    assert "1 level" not in zoneguide.advice(8, 10)["text"]
    assert zoneguide.advice(8, 10)["mode"] == "fit"
    assert zoneguide.advice(14, 10)["mode"] == "push"       # over by 4 > 3
    assert zoneguide.advice(13, 10)["mode"] == "fit"        # over by 3
    assert zoneguide.advice(40, 33)["mode"] == "push"       # 7 > 3 + 2
    assert zoneguide.advice(37, 33)["mode"] == "fit"
    # DATA-GUIDE-MERGE (M3): one level-gap rule, the "underlevel_gap"
    # setting; the default is underlevel's and a bad value reads as it
    assert zoneguide.advice(7, 10)["mode"] == "clear"       # 3 under, default 3
    assert zoneguide.advice(6, 10, 5)["mode"] == "fit"      # setting 5: silent at 4
    assert zoneguide.advice(5, 10, 5)["mode"] == "clear"
    assert zoneguide.advice(9, 10, 1)["mode"] == "clear"
    for bad in (None, 0, 21, "5", True):
        assert zoneguide.advice(7, 10, bad)["mode"] == "clear", bad
    st = _state(level=6)
    assert _enter(st, "G1_1", "The Riverbank", 10)["advice"]["mode"] == "clear"
    st.set_underlevel_gap(5)
    assert st.snapshot()["zone_guide"]["advice"]["mode"] == "fit"
    assert st.snapshot()["underlevel"] is None              # the same rule: both silent
    st.set_underlevel_gap(4)
    assert st.snapshot()["zone_guide"]["advice"]["mode"] == "clear"
    assert st.snapshot()["underlevel"]["gap"] == 4


def test_one_data_file_and_no_zone_note_in_the_snapshot():
    """DATA-GUIDE-MERGE (F-122): zone_guide.json is the only authored zone
    file; the notes module, its data file, its hot reload watch and the
    snapshot key are gone."""
    import importlib.util
    from pathlib import Path
    from server.al import hotreload
    root = Path(zoneguide.__file__).resolve().parent
    assert not (root / "zonenotes.py").exists()
    assert not (root / "data" / "zone_notes.json").exists()
    assert importlib.util.find_spec("server.al.zonenotes") is None
    assert sorted(p.name for p in (root / "data").glob("zone_*.json")) == ["zone_guide.json"]
    assert not any(w.name == "Zone notes" for w in hotreload.REGISTRY.watches())
    st = _state()
    assert "zone_note" not in st.snapshot()
    _enter(st, "G1_1", "The Riverbank")
    assert "zone_note" not in st.snapshot()


def test_quest_tracker_steps_and_skipped_bonus_per_character():
    st = _state(level=2)
    _enter(st, "G1_1", "The Riverbank")
    g = _enter(st, "G1_town", "Clearfell Encampment")
    q = g["quest"]
    assert q["steps_done"] == 1 and len(q["steps"]) == 3
    assert q["bonus_total"] == 2 and q["bonus_visited"] == 0
    assert q["bonus_text"] == "Act 1 bonus zones entered: 0 of 2. AshLight can't see pickups."
    _enter(st, "G1_2", "Clearfell")
    g = _enter(st, "G2_1", "Vastiri Outskirts", 16)
    assert g["quest"]["missed"] == [{
        "act": "Act 1", "skipped": 1, "total": 2,
        "text": "Act 1: not entered yet: Freythorn (1 of 2 bonus zones)."}]
    assert "Ash" in st.visits_doc()[1]["characters"]


def test_unnamed_visits_join_the_character_once_named():
    st = _state()
    _enter(st, "G1_1", "The Riverbank")
    st.apply({"type": "level_up", "character": "Ash", "class": "Monk", "level": 2})
    _enter(st, "G1_2", "Clearfell")
    doc = st.visits_doc()[1]
    assert doc["characters"]["Ash"]["G1"] == ["The Riverbank", "Clearfell"]


def test_visit_book_bounds_and_file_round_trip(tmp_path):
    book = zoneguide.VisitBook()
    for i in range(zoneguide.MAX_CHARACTERS + 3):
        book.visit("c%d" % i, "G1_1", "The Riverbank")
    assert len(book.by_name) == zoneguide.MAX_CHARACTERS
    for i in range(zoneguide.MAX_ZONES + 5):
        book.visit("c99", "G1_1", "Zone %d" % i)
    assert len(book.of("c99").acts["G1"]) == zoneguide.MAX_ZONES
    path = tmp_path / zoneguide.FILE_NAME
    zoneguide.write_visits(path, book.to_doc())
    other = zoneguide.VisitBook()
    assert other.load_doc(zoneguide.read_visits(path))
    assert other.to_doc() == book.to_doc()
    assert zoneguide.read_visits(tmp_path / "missing.json") == {}
    assert not zoneguide.VisitBook().load_doc({"characters": "junk"})


def test_guide_file_hot_reloads_on_mtime_change(tmp_path):
    path = tmp_path / "guide.json"
    path.write_text(json.dumps({"acts": {}}), encoding="ascii")
    cache = zoneguide.guide_cache(path)
    assert cache.get() == {"acts": {}}
    path.write_text(json.dumps({"acts": {"G1": {"default": "New."}}}), encoding="ascii")
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert cache.get()["acts"]["G1"]["default"] == "New."
    path.unlink()
    assert cache.get() == {}


def test_short_cap_and_view_key(tmp_path):
    """TD-08: an optional authored short (at most 34 characters) rides the
    view as `short`; a missing one reads as ""; a 35-character short fails
    the load and a hot reload keeps the last good guide."""
    assert zoneguide.MAX_SHORT == 34
    doc = json.loads(json.dumps(DOC))
    doc["acts"]["G1"]["zones"]["The Riverbank"]["short"] = "Boss at the river's end"
    doc["endgame"]["short"] = "x" * 34
    v = zoneguide.view(doc, GRAPH, "G1_1", "The Riverbank", False, 1, 1, None)
    assert v["short"] == "Boss at the river's end"
    v = zoneguide.view(doc, GRAPH, "G1_2", "Clearfell", False, 1, 1, None)
    assert v["short"] == ""
    v = zoneguide.view(doc, GRAPH, "MapAlpineRidge", "Alpine Ridge", False, 70, 70, None)
    assert v["kind"] == "endgame" and v["short"] == "x" * 34
    assert zoneguide.short_problem(doc) is None
    path = tmp_path / "guide.json"
    path.write_text(json.dumps(doc), encoding="ascii")
    assert zoneguide.load(path) == doc
    cache = zoneguide.guide_cache(path)
    assert cache.get() == doc
    bad = json.loads(json.dumps(doc))
    bad["acts"]["G1"]["zones"]["Clearfell"]["short"] = "y" * 35
    assert "Clearfell" in zoneguide.short_problem(bad)
    path.write_text(json.dumps(bad), encoding="ascii")
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert zoneguide.load(path) == {}
    assert cache.get() == doc and "over 34" in cache.error
    bad["acts"]["G1"]["zones"]["Clearfell"]["short"] = 7
    assert zoneguide.short_problem(bad)
    bad["acts"]["G1"]["zones"]["Clearfell"]["short"] = None
    assert zoneguide.short_problem(bad) is None


def test_resume_replays_entered_zones():
    st = _state()
    st.restore({"character": "Ash", "run_events": [
        {"type": "area_generated", "area_id": "G1_2", "at": 1.0},
        {"type": "scene_changed", "scene": "Clearfell", "at": 1.5},
        {"type": "scene_changed", "scene": "(null)", "is_null": True, "at": 1.6}]})
    assert st.visits_doc()[1]["characters"]["Ash"]["G1"] == ["Clearfell"]


def test_core_saves_visits_and_clear_empties_them(tmp_path):
    from server.al.core import Core
    core = Core(runtime=tmp_path, tail=False)
    core.state.set_zone_guide(guide=DOC)
    core.state.apply({"type": "level_up", "character": "Ash", "class": "Monk", "level": 2})
    _enter(core.state, "G1_1", "The Riverbank")
    assert core.tick_guide() is True
    assert core.tick_guide() is False
    saved = json.loads((tmp_path / zoneguide.FILE_NAME).read_text(encoding="ascii"))
    assert saved["characters"]["Ash"]["G1"] == ["The Riverbank"]
    core.set_history(clear=True)
    saved = json.loads((tmp_path / zoneguide.FILE_NAME).read_text(encoding="ascii"))
    assert saved["characters"] == {}


# -- the shipped guide file ---------------------------------------------------

SHIPPED = zoneguide.load()


def test_shipped_guide_shape_and_text():
    assert SHIPPED.get("acts"), "guide file missing or malformed"
    for key, entry in SHIPPED["acts"].items():
        assert acts.label_of(key), key
        for zone, z in entry.get("zones", {}).items():
            for field in ("objective", "layout", "next"):
                v = z.get(field)
                assert v is None or (isinstance(v, str) and 3 <= len(v) <= 160), (zone, field)
            short = z.get("short")
            assert short is None or short == "" or (
                isinstance(short, str) and short.isascii()
                and len(short) <= zoneguide.MAX_SHORT), (zone, "short")
            for o in z.get("optional", []):
                assert o["kind"] in zoneguide.KINDS, (zone, o)
                assert 5 <= len(o["text"]) <= 120, (zone, o)
            nxt = z.get("next")
            if nxt:
                assert any(nxt in e.get("zones", {}) for e in SHIPPED["acts"].values()), \
                    (zone, nxt)
    assert SHIPPED["endgame"]["objective"]
    short = SHIPPED["endgame"].get("short")
    assert short is None or (isinstance(short, str) and short.isascii()
                             and len(short) <= zoneguide.MAX_SHORT)


# The campaign zones that had a zone note (zone_notes.json, decision 0030)
# before DATA-GUIDE-MERGE folded the notes into the guide.
NOTE_ZONES = {
    "G1": ["The Riverbank", "Clearfell Encampment", "Clearfell", "Mud Burrow",
           "The Grelwood", "The Red Vale", "The Grim Tangle", "Cemetery of the Eternals",
           "Mausoleum of the Praetor", "Tomb of the Consort", "Hunting Grounds",
           "Freythorn", "Ogham Farmlands", "Ogham Village", "The Manor Ramparts",
           "Ogham Manor"],
    "G2": ["Vastiri Outskirts", "The Ardura Caravan", "Traitor's Passage",
           "The Halani Gates", "Keth", "The Lost City", "Buried Shrines",
           "Mastodon Badlands", "The Bone Pits", "Valley of the Titans",
           "The Titan Grotto", "Deshar", "Path of Mourning", "The Spires of Deshar",
           "Mawdun Quarry", "Mawdun Mine", "The Dreadnought's Wake", "Dreadnought"],
    "G3": ["Sandswept Marsh", "Ziggurat Encampment", "Jungle Ruins", "The Venom Crypts",
           "Infested Barrens", "Chimeral Wetlands", "Jiquani's Machinarium",
           "Jiquani's Sanctum", "The Azak Bog", "The Matlan Waterways", "The Drowned City",
           "The Molten Vault", "Apex of Filth", "Temple of Kopec", "Utzaal", "Aggorat",
           "The Black Chambers"],
    "G4": ["Kingsmarch", "Isle of Kin", "Volcanic Warrens", "Kedge Bay", "Journey's End",
           "Whakapanu Island", "Singing Caverns", "Abandoned Prison",
           "Solitary Confinement", "Eye of Hinekora", "Halls of the Dead", "Shrike Island",
           "Arastas", "The Excavation"],
}
# Zones whose guide entry already had a layout tendency: the note was dropped.
KEPT_LAYOUT = {("G1", "Clearfell"), ("G1", "Hunting Grounds"), ("G2", "Keth"),
               ("G3", "Ziggurat Encampment"), ("G3", "Jungle Ruins"),
               ("G3", "Temple of Kopec")}


def test_every_campaign_zone_note_text_survives_in_the_guide():
    """DATA-GUIDE-MERGE: every zone that had a note still has tip text in
    its guide entry: the note itself as `layout` (with the note's own src /
    checked pair, F-097), or the guide's own layout where it had one."""
    assert sum(len(v) for v in NOTE_ZONES.values()) == 65
    for key, zones in NOTE_ZONES.items():
        table = SHIPPED["acts"][key]["zones"]
        for zone in zones:
            z = table[zone]
            layout = z.get("layout")
            assert isinstance(layout, str) and layout.endswith("."), (key, zone)
            assert layout.isascii() and "!" not in layout, (key, zone)
            if (key, zone) in KEPT_LAYOUT:
                assert "src" not in z, (key, zone)     # unchanged entry
                assert " tend" in layout, (key, zone)   # a layout tendency
            else:
                assert len(layout) <= 110, (key, zone)   # the old MAX_NOTE
                assert (z.get("src"), z.get("checked")) == ("research:0025", "2026-11-17"),                     (key, zone)
    # the moved notes show on the guide view
    v = zoneguide.view(SHIPPED, {}, "G1_1", "The Riverbank", False, 1, 1, None)
    assert v["layout"] == SHIPPED["acts"]["G1"]["zones"]["The Riverbank"]["layout"]
    assert v["layout"].startswith("First zone")


@pytest.mark.skipif(not acts.default_path().is_file(), reason="world_areas snapshot not fetched")
def test_every_guide_zone_names_a_snapshot_zone_of_its_act():
    doc = json.loads(acts.default_path().read_text(encoding="utf-8"))
    names = {}
    for area_id, a in doc.items():
        info = acts.act_of(area_id)
        if info is not None and isinstance(a, dict) and isinstance(a.get("name"), str):
            names.setdefault(info["key"], set()).add(a["name"].strip())
    for key, entry in SHIPPED["acts"].items():
        for zone in entry.get("zones", {}):
            assert zone in names.get(key, set()), (key, zone)


def test_later_main_path_zone_marks_earlier_steps_done():
    st = _state(level=5)
    q = _enter(st, "G1_4", "The Grelwood", 4)["quest"]
    assert [s["done"] for s in q["steps"]] == [True, True, False]
    assert q["steps_done"] == 2


def test_shipped_hub_and_cross_act_steps():
    st = SessionState(clock=lambda: 10.0)
    st.set_zone_guide(guide=SHIPPED)
    st.apply({"type": "level_up", "character": "Ash", "class": "Monk", "level": 50})
    _enter(st, "G1_15", "Ogham Manor", 15)
    q = _enter(st, "G2_1", "Vastiri Outskirts", 16)["quest"]
    assert q["act"] == "Act 2"
    g1 = zoneguide.quest_view(SHIPPED, "G1", st.visits.of("Ash"))
    assert g1["steps_done"] == len(g1["steps"])       # last step via the next act
    q = _enter(st, "G4_1_2", "Volcanic Warrens", 47)["quest"]
    done = {s["zone"]: s["done"] for s in q["steps"]}
    assert done["Volcanic Warrens"] is True and done["Singing Caverns"] is False
    assert q["steps_done"] == 2                       # Isle of Kin by its next; no back-fill