"""KINDLER-ENGINE (decision 0081 points 2 to 5, 12 and 13): candidates,
PoB XML, the fixed ranking, the result key, the partial cut, calc off and
the Generate route. A fake calc stands in for the bridge (the live checks
are tests/test_kindler_live.py); the tree and gems are the invented
fixtures of tests/kindler_fixtures.py."""

import json
import xml.etree.ElementTree as ET

import pytest

import kindler_fixtures as fx
from server.al.plug import kindler as plug
from server.al.theorycraft import archetypes, delta, genstore, kindler, treedata

PIN = "a" * 40


def _tree():
    doc = fx.tree_doc()
    return treedata.parse(doc), archetypes.tree_graph(doc)


def _inputs(*templates, tree=True, sha="t" * 64):
    data, graph = _tree()
    table = archetypes.validate(fx.table_doc(*templates))
    return {"view": archetypes.resolve(table, tree=graph if tree else None),
            "table_sha": sha, "tree": data if tree else None,
            "tree_version": "v" * 64 if tree else "", "pin": PIN}


def _two_skill_stage(**over):
    return fx.stage(**dict({
        "skills": [{"name": "Hammer Swing", "sockets": 1, "supports": ["Brute Force"]},
                   {"name": "Ground Crack", "sockets": 0, "supports": []}]}, **over))


def _templates():
    """Three warrior templates: a melee one with two skills, a melee crit
    one and a crit-only one."""
    a = fx.template(id="w_a", toggles=["melee"], stages=[_two_skill_stage()])
    b = fx.template(id="w_b", toggles=["melee", "crit"], stages=[fx.stage()])
    c = fx.template(id="w_c", toggles=["crit"], defence="es", stages=[fx.stage()])
    return a, b, c


class FakeCalc:
    """calc(build, swaps) -> {"dps", "ehp"} from the composed XML: DPS by
    the main skill's gem, EHP by the allocated node count."""

    def __init__(self, dps=None, ehp_per_node=10.0, fail=()):
        self.dps = dps or {"Hammer Swing": 100.0, "Ground Crack": 300.0}
        self.ehp_per_node = ehp_per_node
        self.fail = set(fail)
        self.xmls = []

    def __call__(self, build, swaps):
        assert swaps == {}
        root = ET.fromstring(build.raw_xml)
        self.xmls.append(build.raw_xml)
        main = int(root.find("Build").get("mainSocketGroup"))
        group = root.find("Skills/SkillSet").findall("Skill")[main - 1]
        gem = group.find("Gem").get("nameSpec")
        if gem in self.fail:
            raise RuntimeError("bridge failed")
        nodes = [n for n in root.find("Tree/Spec").get("nodes").split(",") if n]
        return {"dps": self.dps.get(gem, 1.0), "ehp": 1000.0 + self.ehp_per_node * len(nodes)}


def _tab(cls="Warrior", **toggles):
    return {"class": cls, "toggles": dict(genstore.default_toggles(), **toggles)}


# --- key and band -------------------------------------------------------------

def test_level_band():
    assert kindler.level_band(1) == "1-10"
    assert kindler.level_band(10) == "1-10"
    assert kindler.level_band(11) == "11-20"
    assert kindler.level_band(100) == "91-100"
    for bad in (None, 0, 101, True, "5"):
        assert kindler.level_band(bad) == kindler.BAND_ALL


def test_result_key_covers_the_six_inputs():
    tog = genstore.default_toggles()
    base = ("Warrior", tog, "t" * 64, PIN, "v" * 64, "1-10")
    key = kindler.result_key(*base)
    assert len(key) == 64 and key == kindler.result_key(*base)
    changed = [("Witch",) + base[1:],
               (base[0], dict(tog, melee="yes")) + base[2:],
               base[:2] + ("u" * 64,) + base[3:],
               base[:3] + ("b" * 40,) + base[4:],
               base[:4] + ("w" * 64, "1-10"),
               base[:5] + ("11-20",)]
    keys = {kindler.result_key(*c) for c in changed}
    assert key not in keys and len(keys) == 6


# --- candidates -----------------------------------------------------------------

def test_filters_and_order_by_match_count_then_id():
    a, b, c = (archetypes.validate(fx.table_doc(*_templates()))["templates"])
    ts = [c, a, b]
    got = [t["id"] for _n, t in kindler.ordered_templates(ts, "Warrior", _tab())]
    assert got == ["w_a", "w_b", "w_c"]  # no yes toggle: by id
    got = kindler.ordered_templates(ts, "Warrior", _tab(crit="yes", melee="yes")["toggles"])
    assert [(n, t["id"]) for n, t in got] == [(2, "w_b"), (1, "w_a"), (1, "w_c")]
    got = kindler.ordered_templates(ts, "", _tab(crit="no")["toggles"])
    assert [t["id"] for _n, t in got] == ["w_a"]  # "no" excludes a carrier
    got = kindler.ordered_templates(ts, "Warrior", _tab(defence="energy_shield")["toggles"])
    assert [t["id"] for _n, t in got] == ["w_c"]
    assert kindler.ordered_templates(ts, "Witch", _tab()["toggles"]) == []


def test_candidates_give_one_variant_per_skill_and_stop_at_twelve():
    many = [fx.template(id=f"w{i:02d}", stages=[_two_skill_stage()]) for i in range(8)]
    ts = archetypes.resolve(archetypes.validate(fx.table_doc(*many)))["templates"]
    got = kindler.candidates(ts, "Warrior", _tab()["toggles"], "1-10")
    assert len(got) == kindler.MAX_CANDIDATES == 12
    assert [(c["template"]["id"], c["variant"]) for c in got[:3]] == [
        ("w00", 0), ("w00", 1), ("w01", 0)]
    assert got[1]["skill"] == "Ground Crack"


def test_stage_by_level_band():
    t = archetypes.validate(fx.table_doc())["templates"][0]  # plan levels 6, 12, 20
    assert kindler.stage_index(t, "1-10") == 0
    assert kindler.stage_index(t, "11-20") == 2
    assert kindler.stage_index(t, kindler.BAND_ALL) == 2
    t2 = dict(t, stages=[dict(s, level=lv) for s, lv in zip(t["stages"], (15, 25, 40))])
    assert kindler.stage_index(t2, "1-10") == 0  # none fits: the first


# --- PoB XML -------------------------------------------------------------------

def test_compose_xml_uses_the_export_ids_and_cumulative_nodes():
    inputs = _inputs()
    t = inputs["view"]["templates"][0]
    ids = kindler.tree_ids(inputs["tree"], t)
    assert ids == (0, "Warrior1")
    xml = kindler.compose_xml(t, 1, 0, ids)
    assert xml.isascii() and "\r" not in xml
    root = ET.fromstring(xml)
    b = root.find("Build")
    assert (b.get("level"), b.get("className"), b.get("ascendClassName"),
            b.get("mainSocketGroup")) == ("12", "Warrior", "Titan", "1")
    spec = root.find("Tree/Spec")
    assert spec.get("classInternalId") == "0"
    assert spec.get("ascendancyInternalId") == "Warrior1"
    assert spec.get("nodes") == "101,102,103,104,105,106,301,302"
    groups = root.find("Skills/SkillSet").findall("Skill")
    assert [g.get("nameSpec") for g in groups[0].findall("Gem")] == [
        "Ground Crack", "Brute Force", "Echo Strike"]
    assert groups[0].get("includeInFullDPS") == "true"
    assert all(g.get("level") == "20" and g.get("quality") == "0"
               for g in groups[0].findall("Gem"))


def test_compose_xml_quotes_names():
    inputs = _inputs()
    t = dict(inputs["view"]["templates"][0])
    t["stages"] = [dict(t["stages"][0], skills=[
        {"gem": {"name": 'Uruk\'s "Smelting" <&>'}, "sockets": 0, "supports": []}])]
    root = ET.fromstring(kindler.compose_xml(t, 0, 0, (0, "")))
    assert root.find("Skills/SkillSet/Skill/Gem").get("nameSpec") == 'Uruk\'s "Smelting" <&>'
    assert root.find("Tree/Spec").get("ascendancyInternalId") == ""


def test_tree_ids_never_guess():
    inputs = _inputs()
    t = inputs["view"]["templates"][0]
    with pytest.raises(kindler.TreeIdsMissing):
        kindler.tree_ids(inputs["tree"], dict(t, **{"class": "Monk"}))
    with pytest.raises(kindler.TreeIdsMissing):
        kindler.tree_ids(inputs["tree"], dict(t, ascendancy="Unknown"))
    assert kindler.tree_ids(inputs["tree"], dict(t, ascendancy=None)) == (0, "")


# --- generate and rank -------------------------------------------------------------

def test_rank_by_blend_then_template_then_variant():
    rows = [{"template": "b", "variant": 0, "dps": 100, "ehp": 200},
            {"template": "a", "variant": 1, "dps": 200, "ehp": 100},
            {"template": "a", "variant": 0, "dps": 200, "ehp": 100},
            {"template": "c", "variant": 0, "dps": 50, "ehp": 50}]
    got = kindler.rank(rows)
    assert [(r["template"], r["variant"]) for r in got] == [
        ("a", 0), ("a", 1), ("b", 0), ("c", 0)]
    assert got[0]["score"] == got[2]["score"] == -25.0
    assert got[3]["score"] == -75.0
    assert got[0]["score"] == round(delta.combined({"dps": 0.0, "ehp": -50.0}), 4)


def test_generate_scores_through_the_calc_and_ranks():
    calc = FakeCalc()
    doc = kindler.generate(_inputs(*_templates()), _tab(), 5, calc)
    assert doc["scored"] and not doc["partial"] and doc["band"] == "1-10"
    assert [(c["template"], c["variant"]) for c in doc["candidates"]] == [
        ("w_a", 1), ("w_a", 0), ("w_b", 0), ("w_c", 0)]
    assert doc["best"]["skill"] == "Ground Crack" and doc["best"]["dps"] == 300
    assert len(calc.xmls) == 4


def test_two_runs_on_one_key_are_byte_identical():
    inputs = _inputs(*_templates())
    one = kindler.dumps(kindler.generate(inputs, _tab(melee="yes"), 5, FakeCalc()))
    two = kindler.dumps(kindler.generate(inputs, _tab(melee="yes"), 5, FakeCalc()))
    assert one == two and one.isascii()


def test_budget_cut_is_partial():
    ticks = iter([0.0, 0.0, 10.0, 61.0, 62.0, 63.0])
    doc = kindler.generate(_inputs(*_templates()), _tab(), 5, FakeCalc(),
                           clock=lambda: next(ticks))
    assert doc["partial"] and doc["scored"] and len(doc["candidates"]) == 2
    assert doc["note"] == "partial"


def test_failed_candidates_are_left_out():
    doc = kindler.generate(_inputs(*_templates()), _tab(), 5,
                           FakeCalc(fail={"Ground Crack"}))
    assert doc["failed"] == 1
    assert "Ground Crack" not in [c["skill"] for c in doc["candidates"]]
    allbad = kindler.generate(_inputs(*_templates()), _tab(), 5,
                              FakeCalc(fail={"Ground Crack", "Hammer Swing"}))
    assert not allbad["scored"] and allbad["note"] == kindler.NO_SCORE


def test_calc_off_shows_one_unscored_template():
    doc = kindler.generate(_inputs(*_templates()), _tab(crit="yes"), 5, None)
    assert doc["scored"] is False and doc["note"] == kindler.CALC_OFF
    assert len(doc["candidates"]) == 1
    assert doc["best"]["template"] == "w_b"
    assert "dps" not in doc["best"] and "ehp" not in doc["best"]
    assert kindler.summary(doc, 5)["dps"] is None


def test_no_tree_and_no_match():
    doc = kindler.generate(_inputs(*_templates(), tree=False), _tab(), 5, FakeCalc())
    assert not doc["scored"] and doc["note"] == kindler.NO_TREE
    none = kindler.generate(_inputs(*_templates()), _tab(cls="Witch"), 5, FakeCalc())
    assert none["note"] == kindler.NO_MATCH and none["best"] is None
    assert kindler.summary(none, 5) is None


# --- sources ---------------------------------------------------------------------

def test_sources_read_table_tree_gems_and_pin(tmp_path):
    table = tmp_path / "archetypes.json"
    table.write_text(json.dumps(fx.table_doc()), encoding="ascii")
    tree = tmp_path / "skilltree.json"
    tree.write_text(json.dumps(fx.tree_doc()), encoding="ascii")
    gems = tmp_path / "gems.json"
    gems.write_text(json.dumps(fx.gems_doc()), encoding="ascii")
    pins = tmp_path / "pins.json"
    pins.write_text(json.dumps({"pob2": {"commit": PIN}}), encoding="ascii")
    src = kindler.Sources(table, tree, gems, pins)
    got = src.inputs()
    assert got["pin"] == PIN and len(got["table_sha"]) == 64
    assert len(got["tree_version"]) == 64 and got["tree"].classes[0] == "Warrior"
    assert got["view"]["templates"][0]["id"] == "warrior_hammer"
    missing = kindler.Sources(tmp_path / "no.json", tmp_path / "no2.json",
                              tmp_path / "no3.json", tmp_path / "no4.json").inputs()
    assert missing["view"]["templates"] == [] and missing["tree"] is None
    assert missing["pin"] == "" and missing["table_sha"] == ""


# --- engine and route ------------------------------------------------------------

class FixedSources:
    def __init__(self, inputs):
        self._inputs = inputs

    def inputs(self):
        return self._inputs


def _engine(tmp_path, calc, clock=None, inputs=None):
    store = genstore.GenStore(tmp_path / "gen_builds.json")
    tab = store.add(cls="Warrior")
    eng = kindler.Engine(FixedSources(inputs or _inputs(*_templates())),
                         calc=lambda: calc, level=lambda: 5, store=store,
                         wall=lambda: 1000.0, **({"clock": clock} if clock else {}))
    return eng, store, tab


def test_engine_writes_the_summary_and_caches_a_final_result(tmp_path):
    calc = FakeCalc()
    eng, store, tab = _engine(tmp_path, calc)
    state, _ = eng.generate(tab)
    assert state == "started"
    eng.join(10)
    res = store.tab(tab)["result"]
    assert res["template"] == "w_a" and res["scored"] and not res["partial"]
    assert res["dps"] == 300 and res["at"] == 1000 and len(res["key"]) == 64
    assert store.tab(tab)["candidates"] == 4
    n = len(calc.xmls)
    state, doc = eng.generate(tab)
    assert state == "done" and doc == eng.last(tab) and len(calc.xmls) == n


def test_engine_never_caches_a_partial(tmp_path):
    ticks = iter([0.0, 0.0, 61.0] + [100.0] * 50)
    eng, store, tab = _engine(tmp_path, FakeCalc(), clock=lambda: next(ticks))
    assert eng.generate(tab, wait=True)[0] == "done"
    assert store.tab(tab)["result"]["partial"] is True
    assert eng._cache == {}
    assert eng.generate(tab)[0] == "started"
    eng.join(10)


def test_engine_one_run_at_a_time(tmp_path):
    eng, _store, tab = _engine(tmp_path, FakeCalc())
    eng._running = "k99"
    assert eng.generate(tab) == ("running", None)


def test_engine_calc_off_writes_an_unscored_summary(tmp_path):
    eng, store, tab = _engine(tmp_path, None)
    eng.generate(tab, wait=True)
    res = store.tab(tab)["result"]
    assert res["scored"] is False and res["dps"] is None and res["ehp"] is None
    assert store.tab(tab)["candidates"] == 0
    assert eng._cache == {}  # an unscored result is not cached as final


def test_engine_toggle_change_marks_stale_and_misses_the_cache(tmp_path):
    calc = FakeCalc()
    eng, store, tab = _engine(tmp_path, calc)
    eng.generate(tab, wait=True)
    store.update(tab, {"toggles": {"crit": "yes"}})
    assert store.tab(tab)["result"]["stale"] is True
    n = len(calc.xmls)
    assert eng.generate(tab, wait=True)[0] == "done"
    assert len(calc.xmls) > n and store.tab(tab)["result"]["stale"] is False


class _Req:
    def __init__(self, core, body):
        self.server = type("S", (), {"core": core})()
        self._body = body
        self.sent = None

    def _read_json(self):
        return self._body

    def _json(self, code, obj, extra=None):
        self.sent = (code, obj)
        return code


class _Core:
    def __init__(self, runtime, calc):
        self.runtime = runtime
        self.tc_calc = calc
        self.state = type("St", (), {"level": 5})()
        self.ticks = []

    def add_tick(self, name, fn):
        self.ticks.append(name)


def test_route_generate_and_read(tmp_path):
    core = _Core(tmp_path, FakeCalc())
    plug.attach(core)
    core.kindler.sources = FixedSources(_inputs(*_templates()))
    tab = core.gen_builds.add(cls="Warrior")
    req = _Req(core, {"id": tab, "op": "read"})
    plug.post_generate(req, {}, None)
    assert req.sent == (200, {"state": "none", "result": None})
    req = _Req(core, {"id": tab})
    plug.post_generate(req, {}, None)
    assert req.sent[0] == 200 and req.sent[1]["state"] == "started"
    core.kindler.join(10)
    req = _Req(core, {"id": tab, "op": "read"})
    plug.post_generate(req, {}, None)
    assert req.sent[1]["state"] == "done"
    assert req.sent[1]["result"]["best"]["template"] == "w_a"
    req = _Req(core, {"id": tab})
    plug.post_generate(req, {}, None)
    assert req.sent[1]["state"] == "done"  # same key: the cached result


@pytest.mark.parametrize("body", [{"id": 5}, {"id": "k1", "op": "x"},
                                  {"id": "k1", "extra": 1}, {}])
def test_route_refuses_bad_bodies(tmp_path, body):
    core = _Core(tmp_path, None)
    plug.attach(core)
    req = _Req(core, body)
    plug.post_generate(req, {}, None)
    assert req.sent[0] == 400 and req.sent[1]["error"] == plug.BAD


def test_route_gone_tab(tmp_path):
    core = _Core(tmp_path, None)
    plug.attach(core)
    req = _Req(core, {"id": "k42"})
    plug.post_generate(req, {}, None)
    assert req.sent == (400, {"error": genstore.GONE_TEXT})


def test_route_is_the_one_plug_route():
    assert plug.ROUTES == {("POST", "/api/kindler-generate"): plug.post_generate}
