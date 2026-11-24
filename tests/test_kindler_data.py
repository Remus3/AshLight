"""KINDLER-DATA (decision 0081 points 2, 6 and 11 to 16): the archetype
template schema, the structural loader (hot reloaded), the runtime resolve
against the cached tree export and gems snapshot, and the validator-only
breadth-first route check."""

import ast
import copy
import json
import os
from pathlib import Path

import pytest

from server.al import hotreload
from server.al.theorycraft import archetypes as ar

import kindler_fixtures as kf

ROOT = Path(__file__).resolve().parent.parent


def _tree():
    return ar.tree_graph(kf.tree_doc())


def _gems():
    return ar.gem_index(kf.gems_doc())


def _bad(doc, needle):
    with pytest.raises(ValueError) as e:
        ar.validate(doc)
    assert needle in str(e.value), str(e.value)


# --- schema -------------------------------------------------------------

def test_fixture_table_validates_and_is_cleaned():
    table = ar.validate(kf.table_doc())
    assert table["schema"] == 1
    t = table["templates"][0]
    assert t["id"] == "warrior_hammer" and t["class"] == "Warrior"
    assert [s["id"] for s in t["stages"]] == ["early", "mid", "maps"]
    assert t["stages"][0]["passives"] == [101, 102, 103]
    assert t["stages"][1]["ascendancy"] == {"trial": 1, "nodes": [301, 302]}
    assert t["stages"][2]["ascendancy"] is None
    # slot names fold to the model's canonical spelling, order kept
    assert list(t["stages"][0]["focus"]) == ["Weapon 1", "Boots"]
    assert t["stages"][0]["focus"]["Weapon 1"] == ["physical damage", "attack speed"]


def test_schema_and_template_list():
    _bad({"schema": 2, "templates": []}, "schema")
    _bad({"schema": 1, "templates": []}, "templates")
    _bad([], "schema")
    two = kf.table_doc(kf.template(), kf.template())
    _bad(two, "repeats template id")


@pytest.mark.parametrize("field", ["src", "checked"])
def test_every_template_and_stage_has_src_and_checked(field):
    t = kf.template()
    del t[field]
    _bad(kf.table_doc(t), field)
    t = kf.template()
    del t["stages"][1][field]
    _bad(kf.table_doc(t), field)
    t = kf.template(checked="yesterday")
    _bad(kf.table_doc(t), "checked")


def test_conditions_are_json_data_only():
    # unknown keys are refused, so no field can carry code to run
    t = kf.template(expr="lambda: 1")
    _bad(kf.table_doc(t), "unknown field")
    t = kf.template()
    t["stages"][0]["trigger"] = {"kind": "eval", "code": "level > 3"}
    _bad(kf.table_doc(t), "trigger")
    t = kf.template()
    t["stages"][0]["trigger"]["when"] = "level > 3"
    _bad(kf.table_doc(t), "trigger")
    # the module never evaluates text as code
    tree = ast.parse((ROOT / "server/al/theorycraft/archetypes.py").read_text(encoding="ascii"))
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"eval", "exec", "compile", "__import__"}


@pytest.mark.parametrize("trigger, ok", [
    ({"kind": "level", "min": 1, "max": 10}, True),
    ({"kind": "level", "min": 10, "max": 2}, False),
    ({"kind": "level", "min": 0, "max": 2}, False),
    ({"kind": "act", "act": 3}, True),
    ({"kind": "act", "act": 0}, False),
    ({"kind": "zone", "zone": "G1_town"}, True),
    ({"kind": "zone", "zone": "../x"}, False),
    ({"kind": "area_level", "min": 65, "max": 82}, True),
    ({"kind": "area_level", "min": 65, "max": True}, False),
])
def test_triggers(trigger, ok):
    t = kf.template()
    t["stages"][0]["trigger"] = trigger
    if ok:
        assert ar.validate(kf.table_doc(t))["templates"][0]["stages"][0]["trigger"] == trigger
    else:
        _bad(kf.table_doc(t), "trigger")


def test_supports_bounded_by_sockets():
    t = kf.template()
    t["stages"][0]["skills"][0]["sockets"] = 0
    _bad(kf.table_doc(t), "supports")
    t = kf.template()
    t["stages"][0]["skills"][0]["sockets"] = ar.MAX_SOCKETS + 1
    _bad(kf.table_doc(t), "sockets")
    t = kf.template()
    t["stages"][0]["skills"][0]["supports"] = ["Brute Force", "Brute Force"]
    t["stages"][0]["skills"][0]["sockets"] = 3
    _bad(kf.table_doc(t), "repeats")


def test_gem_timing_entries():
    t = kf.template()
    t["stages"][0]["gems"] = [{"name": "Ground Crack", "action": "keep"}]
    _bad(kf.table_doc(t), "action")
    t = kf.template()
    t["stages"][0]["gems"] = [{"name": "Ground Crack", "action": "swap"}]
    _bad(kf.table_doc(t), "for")
    t = kf.template()
    t["stages"][0]["gems"] = [{"name": "Ground Crack", "action": "pick", "level": 101}]
    _bad(kf.table_doc(t), "level")


def test_passive_prefix_is_an_ordered_id_list():
    t = kf.template()
    t["stages"][0]["passives"] = [101, "102"]
    _bad(kf.table_doc(t), "passives")
    t = kf.template()
    t["stages"][1]["passives"] = [104, 101]
    _bad(kf.table_doc(t), "repeats passive")
    t = kf.template()
    t["stages"][1]["ascendancy"] = {"trial": 5, "nodes": [301]}
    _bad(kf.table_doc(t), "trial")
    t = kf.template()
    t["stages"][2]["ascendancy"] = {"trial": 0, "nodes": []}
    _bad(kf.table_doc(t), "trial")


def test_ascendancy_trials_do_not_go_back():
    t = kf.template()
    t["stages"][1]["ascendancy"] = {"trial": 2, "nodes": [301]}
    t["stages"][2]["ascendancy"] = {"trial": 1, "nodes": [302]}
    _bad(kf.table_doc(t), "trial")


def test_focus_slots_and_stats():
    t = kf.template()
    t["stages"][0]["focus"] = {"Hat": ["life"]}
    _bad(kf.table_doc(t), "slot")
    t = kf.template()
    t["stages"][0]["focus"] = {"boots": ["movement speed"]}
    assert list(ar.validate(kf.table_doc(t))["templates"][0]["stages"][0]["focus"]) == ["Boots"]
    t = kf.template()
    t["stages"][0]["focus"] = {"Boots": []}
    _bad(kf.table_doc(t), "focus")


def test_toggles_and_defence():
    _bad(kf.table_doc(kf.template(toggles=["melee", "fast"])), "toggles")
    _bad(kf.table_doc(kf.template(defence="armour")), "defence")
    ok = ar.validate(kf.table_doc(kf.template(toggles=["melee", "crit"], defence="hybrid")))
    assert ok["templates"][0]["toggles"] == ["melee", "crit"]


def test_ascii_text_only():
    _bad(kf.table_doc(kf.template(label="Hammer w" + chr(0xe4) + "rrior")), "label")


# --- loader and hot reload ----------------------------------------------

def _write(path, doc):
    path.write_text(json.dumps(doc), encoding="ascii")


def test_load_refuses_large_and_non_ascii(tmp_path):
    p = tmp_path / "archetypes.json"
    p.write_bytes(b"{" + b" " * ar.MAX_BYTES + b"}")
    with pytest.raises(ValueError):
        ar.load(p)
    p.write_bytes(('{"schema": 1, "x": "' + chr(0xe4) + '"}').encode("utf-8"))
    with pytest.raises(ValueError):
        ar.load(p)


def test_file_hot_reloads(tmp_path):
    p = tmp_path / "archetypes.json"
    w = ar.watch(p, registry=False)
    assert w.get() == {}                      # missing file: no table
    _write(p, kf.table_doc())
    first = w.get()
    assert first["templates"][0]["label"] == "Hammer warrior"
    second = kf.table_doc(kf.template(label="Hammer warrior two"))
    _write(p, second)
    os.utime(p, ns=(1, 10 ** 18))
    assert w.get()["templates"][0]["label"] == "Hammer warrior two"
    # a bad edit keeps the last good copy and shows a note
    p.write_text('{"schema": 1, "templates": [{"id": "x"}]}', encoding="ascii")
    os.utime(p, ns=(1, 2 * 10 ** 18))
    assert w.get()["templates"][0]["label"] == "Hammer warrior two"
    assert w.error and "last good copy" in w.error
    p.unlink()
    assert w.get() == {}


def test_module_watch_is_registered():
    assert ar._watch in hotreload.REGISTRY.watches()
    assert ar.PATH == ROOT / "server" / "al" / "data" / "archetypes.json"


# --- tree graph and gems index -------------------------------------------

def test_tree_graph_reads_edges_starts_and_ascendancies():
    g = _tree()
    assert g.class_start("warrior") == 100 and g.class_start("Witch") == 200
    assert g.class_start("Monk") is None
    assert g.asc_start("Titan") == 300
    assert g.asc_class("Titan") == "Warrior"
    assert 101 in g.adj[100] and 100 in g.adj[101]
    assert g.asc_of(301) == "Titan" and g.asc_of(101) is None
    assert 110 in g.nodes and not g.adj.get(110)


def test_gem_index_names_and_levels():
    gi = _gems()
    assert gi["hammer swing"] == {"name": "Hammer Swing", "level": 1}
    assert gi["ground crack"]["level"] == 4      # lowest per_level requirement
    assert gi["echo strike"] == {"name": "Echo Strike", "level": None}
    assert ar.gem_index([]) == {}
    assert ar.gem_index({"x": 3, "y": {"display_name": 7}}) == {}


def test_load_gems_missing_file_is_none(tmp_path):
    assert ar.load_gems(tmp_path / "gems.json") is None
    p = tmp_path / "gems.json"
    p.write_text(json.dumps(kf.gems_doc()), encoding="utf-8")
    assert "war cry" in ar.load_gems(p)


# --- runtime resolve: drop unknown ids with a note, gem checked flags ------

def test_resolve_drops_unknown_node_ids_with_a_note():
    t = kf.template()
    t["stages"][0]["passives"] = [101, 9999, 102, 103]
    view = ar.resolve(ar.validate(kf.table_doc(t)), tree=_tree(), gems=_gems())
    st = view["templates"][0]["stages"][0]
    assert st["passives"] == [101, 102, 103]
    assert any("9999" in n for n in view["notes"])
    assert view["tree"] is True


def test_resolve_marks_gems_checked_from_snapshot():
    t = kf.template()
    t["stages"][0]["skills"][0]["supports"] = ["Brute Force", "Made Up Support"]
    t["stages"][0]["skills"][0]["sockets"] = 3
    view = ar.resolve(ar.validate(kf.table_doc(t)), tree=_tree(), gems=_gems())
    sk = view["templates"][0]["stages"][0]["skills"][0]
    assert sk["gem"] == {"name": "Hammer Swing", "level": 1, "checked": True}
    assert sk["supports"][0] == {"name": "Brute Force", "level": 3, "checked": True}
    assert sk["supports"][1] == {"name": "Made Up Support", "level": None, "checked": False}
    pick = view["templates"][0]["stages"][0]["gems"][0]
    # snapshot level wins over the authored one
    assert pick["level"] == 4 and pick["checked"] is True
    assert any("Made Up Support" in n for n in view["notes"])


def test_resolve_without_snapshots_is_unchecked():
    view = ar.resolve(ar.validate(kf.table_doc()), tree=None, gems=None)
    st = view["templates"][0]["stages"][0]
    assert st["passives"] == [101, 102, 103]       # nothing dropped blind
    assert st["skills"][0]["gem"]["checked"] is False
    pick = st["gems"][0]
    assert pick == {"name": "Ground Crack", "action": "pick", "level": 4,
                    "for": None, "checked": False}  # authored level kept
    assert view["tree"] is False and view["gems"] is False


def test_resolve_does_not_run_the_route_search(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("breadth-first check at run time")
    monkeypatch.setattr(ar, "_reach", boom)
    ar.resolve(ar.validate(kf.table_doc()), tree=_tree(), gems=_gems())


# --- validator: breadth-first route and point budget ---------------------

def test_check_passes_the_fixture():
    rep = ar.check(ar.validate(kf.table_doc()), _tree(), _gems())
    assert rep["problems"] == [] and rep["ok"] is True


def test_check_finds_a_disconnected_prefix():
    t = kf.template()
    t["stages"][0]["passives"] = [101, 103]          # 102 missing
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert not rep["ok"]
    assert any("not connected" in p and "103" in p for p in rep["problems"])


def test_check_finds_an_island_and_unknown_ids():
    t = kf.template()
    t["stages"][0]["passives"] = [101, 110, 4242]
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert any("110" in p and "not connected" in p for p in rep["problems"])
    assert any("4242" in n for n in rep["notes"])
    assert not any("4242" in p for p in rep["problems"])


def test_check_route_follows_its_order():
    t = kf.template()
    t["stages"][0]["passives"] = [102, 101, 103]     # 102 before its link
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert any("order" in p and "102" in p for p in rep["problems"])


def test_check_prefix_is_cumulative_across_stages():
    t = kf.template()
    t["stages"][0]["passives"] = [101]
    t["stages"][1]["passives"] = [102, 103, 104]     # continues from 101
    assert ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())["ok"]


def test_check_point_budget_at_the_stage_level():
    t = kf.template()
    t["stages"][0]["level"] = 3                      # 2 points, 3 nodes
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert any("point budget" in p for p in rep["problems"])
    t["stages"][0]["bonus_points"] = 1
    assert ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())["ok"]
    assert ar.point_budget(1) == 0 and ar.point_budget(10, 2) == 11


def test_check_class_start_and_wrong_class():
    rep = ar.check(ar.validate(kf.table_doc(kf.template(**{"class": "Monk"}))),
                   _tree(), _gems())
    assert any("class start" in p for p in rep["problems"])
    t = kf.template(**{"class": "Witch"}, ascendancy=None)
    t["stages"][1]["ascendancy"] = None
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert any("not connected" in p for p in rep["problems"])


def test_check_ascendancy_nodes_and_order():
    t = kf.template()
    t["stages"][1]["ascendancy"] = {"trial": 1, "nodes": [302, 301]}
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert any("ascendancy" in p and "302" in p for p in rep["problems"])
    t = kf.template()
    t["stages"][1]["ascendancy"] = {"trial": 1, "nodes": [301, 201]}
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert any("201" in p and "ascendancy" in p for p in rep["problems"])
    t = kf.template()
    t["stages"][1]["passives"] = [104, 301]
    t["stages"][1]["ascendancy"] = None
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert any("301" in p and "ascendancy" in p for p in rep["problems"])
    rep = ar.check(ar.validate(kf.table_doc(kf.template(ascendancy="Pyromancer"))),
                   _tree(), _gems())
    assert any("Pyromancer" in p for p in rep["problems"])


def test_check_unknown_gem_with_snapshot_and_without():
    t = kf.template()
    t["stages"][0]["gems"] = [{"name": "Not A Gem", "action": "pick"}]
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems())
    assert any("Not A Gem" in p for p in rep["problems"])
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), None)
    assert rep["ok"] and any("gems snapshot" in n for n in rep["notes"])


def test_check_without_tree_says_so():
    rep = ar.check(ar.validate(kf.table_doc()), None, _gems())
    assert rep["ok"] and any("tree export" in n for n in rep["notes"])


def test_check_zone_ids_against_world_areas():
    t = kf.template()
    t["stages"][0]["trigger"] = {"kind": "zone", "zone": "G1_9"}
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems(), area_ids={"G1_1"})
    assert any("G1_9" in p for p in rep["problems"])
    rep = ar.check(ar.validate(kf.table_doc(t)), _tree(), _gems(), area_ids={"G1_9"})
    assert rep["ok"]


def test_check_is_deterministic():
    table = ar.validate(kf.table_doc())
    a = json.dumps(ar.check(table, _tree(), _gems()), sort_keys=True)
    b = json.dumps(ar.check(copy.deepcopy(table), _tree(), _gems()), sort_keys=True)
    assert a == b


def test_view_reads_caches_and_tracked_table(tmp_path, monkeypatch):
    cache = tmp_path / "gamedata"
    cache.mkdir()
    (cache / "skilltree.json").write_text(json.dumps(kf.tree_doc()), encoding="utf-8")
    (cache / "gems.json").write_text(json.dumps(kf.gems_doc()), encoding="utf-8")
    p = tmp_path / "archetypes.json"
    _write(p, kf.table_doc())
    src = ar.Sources(p, cache / "skilltree.json", cache / "gems.json")
    view = src.view()
    assert view["tree"] is True and view["gems"] is True
    assert view["templates"][0]["stages"][0]["skills"][0]["gem"]["checked"] is True
    empty = ar.Sources(tmp_path / "none.json", cache / "x.json", cache / "y.json").view()
    assert empty == {"schema": 1, "templates": [], "notes": [], "tree": False,
                     "gems": False, "bases": False}


# --- DATA-GEMS-SNAP: the snapshot tool fills the gems file ----------------

def test_snapshot_fetches_the_gems_file_resolve_checks(tmp_path):
    """The snapshot tool's gems source lands as the file gems_path names,
    passes its probe in the fixture shape, and resolve then reads the
    authored gems checked with the snapshot level."""
    from server.al.theorycraft import snapprobe, snapshot
    url = snapshot.SOURCES["gems"]
    assert url.endswith("/" + ar.GEMS_FILE)
    assert ar.gems_path({"AL_SIDECAR_ROOT": str(tmp_path)}).name == ar.GEMS_FILE
    table = {"gems": dict(snapprobe.PROBES["gems"], min=1, names=1)}
    body = json.dumps(kf.gems_doc()).encode("ascii")
    out = snapshot.run(tmp_path, fetch=lambda u, h: (200, {}, body),
                       sources={"gems": url}, now=1_800_000_000, probes=table)
    assert out == {"gems": "fetched"}
    gems = ar.load_gems(tmp_path / ar.GEMS_FILE)
    assert gems == _gems()
    view = ar.resolve(ar.validate(kf.table_doc()), tree=_tree(), gems=gems)
    assert view["gems"] is True
    pick = view["templates"][0]["stages"][0]["gems"][0]
    assert pick["checked"] is True


# --- KINDLER-WEAPON-BASE: one authored weapon base per attack template ------

def _bases():
    return ar.base_index(kf.bases_doc())


def test_weapon_field_is_an_optional_base_name():
    table = ar.validate(kf.table_doc())
    assert table["templates"][0]["weapon"] == "Oak Mallet"
    t = kf.template()
    del t["weapon"]
    assert ar.validate(kf.table_doc(t))["templates"][0]["weapon"] is None
    assert ar.validate(kf.table_doc(kf.template(weapon="  Oak   Mallet ")))[
        "templates"][0]["weapon"] == "Oak Mallet"
    for bad in ("", 7, ["Oak Mallet"], {"base": "Oak Mallet"}, "Oak\u00e9", "x" * 61):
        _bad(kf.table_doc(kf.template(weapon=bad)), "weapon is not a base name")


def test_base_index_keeps_released_weapon_bases_only():
    idx = _bases()
    assert sorted(idx) == ["iron maul", "oak mallet", "twig bow"]
    assert idx["oak mallet"] == {"name": "Oak Mallet", "item_class": "Two Hand Mace",
                                 "level": 1}
    assert idx["twig bow"]["item_class"] == "Bow"
    # an unreleased base, an amulet and a caster wand are no attack weapon
    assert not {"glass mallet", "bead amulet", "ash wand"} & set(idx)
    assert ar.base_index([]) == {} and ar.base_index({"x": 1}) == {}


def test_base_index_repeat_name_keeps_lowest_level():
    doc = kf.bases_doc()
    doc["Metadata/Items/Weapons/Again"] = dict(
        doc["Metadata/Items/Weapons/TwoHandMaceB"], requirements={"level": 12})
    doc["Metadata/Items/Weapons/NoReq"] = {"name": "Bare Maul", "release_state": "released",
                                           "item_class": "Two Hand Mace"}
    idx = ar.base_index(doc)
    assert idx["iron maul"]["level"] == 12
    assert idx["bare maul"]["level"] is None


def test_load_bases_missing_or_broken_is_none(tmp_path):
    assert ar.load_bases(tmp_path / "none.json") is None
    bad = tmp_path / "base_items.json"
    bad.write_text("{not json", encoding="ascii")
    assert ar.load_bases(bad) is None
    bad.write_text(json.dumps(kf.bases_doc()), encoding="ascii")
    assert ar.load_bases(bad) == _bases()
    assert ar.bases_path({"AL_SIDECAR_ROOT": str(tmp_path)}).name == ar.BASES_FILE
    assert ar.default_bases(tmp_path / "c" / "gems.json") == tmp_path / "c" / ar.BASES_FILE


def test_resolve_checks_the_weapon_against_the_snapshot():
    table = ar.validate(kf.table_doc())
    view = ar.resolve(table, bases=_bases())
    assert view["bases"] is True
    assert view["templates"][0]["weapon"] == {
        "name": "Oak Mallet", "item_class": "Two Hand Mace", "level": 1, "checked": True}
    assert not [n for n in view["notes"] if "weapon" in n]


def test_resolve_never_guesses_a_weapon():
    unknown = ar.validate(kf.table_doc(kf.template(weapon="Glass Mallet")))
    view = ar.resolve(unknown, bases=_bases())
    assert view["templates"][0]["weapon"] == {
        "name": "Glass Mallet", "item_class": None, "level": None, "checked": False}
    assert any("weapon Glass Mallet" in n and "not composed" in n for n in view["notes"])
    plain = ar.resolve(ar.validate(kf.table_doc()))
    assert plain["bases"] is False
    assert plain["templates"][0]["weapon"]["checked"] is False
    assert not [n for n in plain["notes"] if "weapon" in n]
    t = kf.template()
    del t["weapon"]
    assert ar.resolve(ar.validate(kf.table_doc(t)), bases=_bases())[
        "templates"][0]["weapon"] is None


def test_check_attack_template_needs_a_weapon():
    t = kf.template()
    del t["weapon"]
    report = ar.check(ar.validate(kf.table_doc(t)))
    assert "warrior_hammer: attack template has no weapon base" in report["problems"]
    spell = dict(kf.template(id="witch_spell", toggles=["spell"]))
    del spell["weapon"]
    assert ar.check(ar.validate(kf.table_doc(spell)))["ok"]
    assert any("weapon bases not checked" in n
               for n in ar.check(ar.validate(kf.table_doc()))["notes"])


@pytest.mark.parametrize("over, needle", [
    ({"weapon": "Glass Mallet"}, "is not a weapon base in base_items"),
    ({"weapon": "Ash Wand"}, "is not a weapon base in base_items"),
    ({"weapon": "Twig Bow"}, "(Bow) does not fit toggle melee"),
    ({"weapon": "Oak Mallet", "toggles": ["bow"]}, "(Two Hand Mace) does not fit toggle bow"),
    ({"weapon": "Iron Maul"}, "needs level 30, past the first stage's level 6"),
])
def test_check_weapon_against_the_snapshot(over, needle):
    report = ar.check(ar.validate(kf.table_doc(kf.template(**over))), bases=_bases())
    assert any(needle in p for p in report["problems"]), report["problems"]


def test_check_weapon_passes_the_fixture_with_the_snapshot():
    report = ar.check(ar.validate(kf.table_doc()), tree=_tree(), gems=_gems(),
                      bases=_bases())
    assert report["ok"], report["problems"]
    bow = kf.template(id="ranger_bow", toggles=["bow"], weapon="Twig Bow")
    assert ar.check(ar.validate(kf.table_doc(bow)), bases=_bases())["ok"]


def test_view_reads_the_bases_beside_the_gems_file(tmp_path):
    cache = tmp_path / "gamedata"
    cache.mkdir()
    (cache / "gems.json").write_text(json.dumps(kf.gems_doc()), encoding="utf-8")
    (cache / ar.BASES_FILE).write_text(json.dumps(kf.bases_doc()), encoding="utf-8")
    p = tmp_path / "archetypes.json"
    _write(p, kf.table_doc())
    view = ar.Sources(p, cache / "none.json", cache / "gems.json").view()
    assert view["bases"] is True
    assert view["templates"][0]["weapon"]["checked"] is True
    other = tmp_path / "elsewhere.json"
    other.write_text(json.dumps({}), encoding="utf-8")
    view = ar.Sources(p, cache / "none.json", cache / "gems.json",
                      bases_file=other).view()
    assert view["templates"][0]["weapon"]["checked"] is False


def test_server_words_are_pinned_exactly():
    """KINDLER-WEAPON-BASE: the server words live in server/al/text/kindler.py
    (docs/design/copy/kindler.md, Server words) and both modules use them."""
    from server.al.text import kindler as words
    from server.al.theorycraft import kindler as engine
    assert (words.TABLE_NAME, words.TREE_NAME, words.GEMS_NAME, words.BASES_NAME) == (
        "Kindler templates", "Passive tree (Kindler)", "Gems snapshot",
        "Weapon bases (Kindler)")
    assert (words.ENGINE_TABLE_NAME, words.ENGINE_TREE_NAME, words.ENGINE_GEMS_NAME,
            words.ENGINE_BASES_NAME) == (
        "Kindler templates (engine)", "Passive tree (Kindler engine)",
        "Gems snapshot (Kindler engine)", "Weapon bases (Kindler engine)")
    assert words.MELEE_CLASSES == (
        "One Hand Mace", "Two Hand Mace", "One Hand Sword", "Two Hand Sword",
        "One Hand Axe", "Two Hand Axe", "Dagger", "Claw", "Spear", "Flail", "Warstaff")
    assert words.RANGED_CLASSES == ("Bow", "Crossbow") and words.BOW_CLASS == "Bow"
    assert words.weapon_unknown("t1", "Glass Mallet") == (
        "t1: weapon Glass Mallet is not a weapon base in the base_items snapshot; "
        "not composed")
    assert ar.MELEE_CLASSES is words.MELEE_CLASSES
    assert ar.TOGGLE_CLASSES["bow"] == (words.BOW_CLASS,)
    sheet = (ROOT / "docs" / "design" / "copy" / "kindler.md").read_text(encoding="ascii")
    flat = " ".join(sheet.split())
    for word in (words.TABLE_NAME, words.TREE_NAME, words.GEMS_NAME, words.BASES_NAME,
                 words.ENGINE_TABLE_NAME, words.ENGINE_TREE_NAME, words.ENGINE_GEMS_NAME,
                 words.ENGINE_BASES_NAME) + words.MELEE_CLASSES + words.RANGED_CLASSES:
        assert f"`{word}`" in flat, word
    for path in ("server/al/theorycraft/archetypes.py", "server/al/theorycraft/kindler.py"):
        src = (ROOT / path).read_text(encoding="ascii")
        assert "from ..text import kindler as words" in src, path
    assert engine.words is words


def test_weapon_note_never_reaches_a_player():
    """KW-1 (design review): resolve()'s weapon note is author and test
    output only. The engine's result and the plan of a template whose base
    the snapshot lacks carry no note, the Generate route and the planner
    never read the view's notes, and no web file holds the words."""
    from server.al.theorycraft import kindler as engine, kindlerplan, treedata
    table = ar.validate(kf.table_doc(kf.template(weapon="Glass Mallet")))
    view = ar.resolve(table, tree=_tree(), bases=_bases())
    assert any("not composed" in n for n in view["notes"])
    inputs = {"view": view, "table_sha": "t" * 64, "tree": treedata.parse(kf.tree_doc()),
              "tree_version": "v" * 64, "pin": "a" * 40}
    tab = {"class": "Warrior", "toggles": {}}
    calc = lambda build, swaps: {"dps": 1.0, "ehp": 2.0}  # noqa: E731
    for doc in (engine.generate(inputs, tab, 5, calc), engine.generate(inputs, tab, 5, None),
                kindlerplan.build_plan(view["templates"][0])):
        raw = json.dumps(doc)
        assert "not composed" not in raw and "base_items" not in raw
    for path in ("server/al/plug/kindler.py", "server/al/theorycraft/kindlerplan.py",
                 "server/al/theorycraft/kindler.py"):
        assert '["notes"]' not in (ROOT / path).read_text(encoding="ascii"), path
    for path in (ROOT / "web").rglob("*"):
        if path.suffix in (".js", ".html"):
            text = path.read_text(encoding="utf-8")
            assert "not composed" not in text and "weapon_unknown" not in text, path
