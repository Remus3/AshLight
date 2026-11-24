"""KINDLER-PLAN (decision 0081 points 14 to 17): the plan of the top-ranked
template (stages, support links, gem timing, ordered passives, ascendancy,
per-slot item focus) and the follow-Play-guidance resolver. A fake calc
stands in for the bridge; the tree and gems are the invented fixtures of
tests/kindler_fixtures.py."""

import json
import xml.etree.ElementTree as ET

import pytest

import kindler_fixtures as fx
from server.al.plug import kindler as plug
from server.al.theorycraft import (archetypes, calcwire, delta, genstore, kindler, kindlerplan,
                                   treedata)

PIN = "b" * 40


def _inputs(*templates, tree=True, gems=True):
    doc = fx.tree_doc()
    data, graph = treedata.parse(doc), archetypes.tree_graph(doc)
    table = archetypes.validate(fx.table_doc(*templates))
    return {"view": archetypes.resolve(table, tree=graph if tree else None,
                                       gems=archetypes.gem_index(fx.gems_doc()) if gems else None),
            "table_sha": "t" * 64, "tree": data if tree else None,
            "tree_version": "v" * 64 if tree else "", "pin": PIN}


def _template(inputs=None):
    return (inputs or _inputs())["view"]["templates"][0]


class FixedSources:
    def __init__(self, inputs):
        self._inputs = inputs

    def inputs(self):
        return self._inputs


class ProbeCalc:
    """calc(build, swaps): DPS / EHP fixed, a probe line on the carrier adds
    by its stat (per point) so the weights come out in a known order."""

    PER_POINT = {"maximum Life": (0.0, 2.0), "Armour": (0.0, 0.5),
                 "Physical Damage": (3.0, 0.0), "Movement Speed": (0.0, 0.0)}

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __call__(self, build, swaps):
        ET.fromstring(build.raw_xml)  # a composed PoB XML
        self.calls.append(dict(swaps))
        if self.fail:
            raise RuntimeError("bridge failed")
        dps, ehp = 100.0, 1000.0
        for slot, text in swaps.items():
            assert slot == kindlerplan.CARRIER_SLOT
            assert "Rarity: Rare" in text and "Gold Amulet" in text
            line = text.splitlines()[-1]
            for stat, (d, e) in self.PER_POINT.items():
                if line.endswith(stat):
                    dps += d * 10
                    ehp += e * 10
        return {"dps": dps, "ehp": ehp}


class FitCalc(ProbeCalc):
    """ProbeCalc plus the calc's `fit(build)` (calcwire.make_calc): PoB's
    answer per linked support of each skill group in the composed XML; the
    supports in REJECT do not apply and the ones in UNKNOWN PoB did not
    recognise (not answered)."""

    REJECT = {"Echo Strike"}
    UNKNOWN = set()

    def __init__(self, fail_fit=False, **kw):
        super().__init__(**kw)
        self.fits = []
        self.fail_fit = fail_fit

    def fit(self, build):
        root = ET.fromstring(build.raw_xml)
        self.fits.append(root.find("Build").get("level"))
        if self.fail_fit:
            raise RuntimeError("bridge failed")
        out = {}
        for group in root.iter("Skill"):
            gems = [g.get("nameSpec") for g in group.iter("Gem")]
            out[gems[0]] = {name: name not in self.REJECT for name in gems[1:]
                            if name not in self.UNKNOWN}
        return out


def _bases_file(tmp_path, with_amulet=True):
    doc = {"Metadata/Items/Amulets/Gold": {"item_class": "Amulet", "name": "Gold Amulet",
                                           "release_state": "released"},
           "Metadata/Items/Amulets/Zinc": {"item_class": "Amulet", "name": "Zinc Amulet",
                                           "release_state": "released"},
           "Metadata/Items/Amulets/Alpha": {"item_class": "Amulet", "name": "Alpha Amulet",
                                            "release_state": "unreleased"},
           "Metadata/Items/Rings/Iron": {"item_class": "Ring", "name": "Aaa Ring",
                                         "release_state": "released"}}
    if not with_amulet:
        doc = {k: v for k, v in doc.items() if v["item_class"] != "Amulet"}
    p = tmp_path / "base_items.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _result(template_id="warrior_hammer", stage="mid", scored=True, key="k" * 64):
    best = {"template": template_id, "label": "x", "variant": 0, "skill": "Ground Crack",
            "stage": stage}
    return {"key": key, "band": "11-20", "scored": scored, "partial": False,
            "candidates": [best], "best": best, "note": ""}


# --- the plan ------------------------------------------------------------------

def test_plan_stages_skills_links_and_gem_timing():
    plan = kindlerplan.build_plan(_template())
    assert plan["template"] == "warrior_hammer" and plan["class"] == "Warrior"
    assert [s["id"] for s in plan["stages"]] == ["early", "mid", "maps"]
    early, mid, maps = plan["stages"]
    sk = early["skills"][0]
    assert sk["name"] == "Hammer Swing" and sk["sockets"] == 2 and sk["checked"] is True
    assert sk["supports"] == [{"name": "Brute Force", "level": 3, "checked": True,
                               "applies": None}]
    # gem timing: snapshot level when the snapshot names it, else authored
    assert early["gems"][0]["name"] == "Ground Crack" and early["gems"][0]["level"] == 4
    assert early["gems"][0]["checked"] is True
    assert early["gems"][0]["trigger"] == {"kind": "level", "min": 1, "max": 6}
    swap, cry = mid["gems"]
    assert swap["action"] == "swap" and swap["for"] == "Hammer Swing"
    assert cry["level"] == 10 and cry["checked"] is True
    assert mid["skills"][0]["supports"][1] == {"name": "Echo Strike", "level": None,
                                               "checked": True, "applies": None}
    assert maps["gems"][0]["action"] == "drop"


def test_unknown_gem_keeps_authored_level_unchecked():
    st = fx.stage(gems=[{"name": "Made Up Gem", "action": "pick", "level": 9}])
    plan = kindlerplan.build_plan(_template(_inputs(fx.template(stages=[st]))))
    assert plan["stages"][0]["gems"][0]["level"] == 9
    assert plan["stages"][0]["gems"][0]["checked"] is False


def test_plan_passives_in_order_with_points_budget_and_ascendancy():
    inputs = _inputs()
    plan = kindlerplan.build_plan(_template(inputs), tree=inputs["tree"])
    early, mid, maps = plan["stages"]
    assert [n["id"] for n in early["passives"]] == [101, 102, 103]
    assert early["passives"][0]["name"] == "Strength"
    assert [n["id"] for n in mid["passives"]] == [104, 105, 106]
    assert (early["points"], mid["points"], maps["points"]) == (3, 6, 6)
    assert early["budget"] == archetypes.point_budget(6)
    assert early["ascendancy"] is None
    assert mid["ascendancy"] == {"trial": 1, "nodes": [{"id": 301, "name": "Stone Skin"},
                                                       {"id": 302, "name": "Giant Blood"}]}


def test_plan_without_tree_names_nodes_none():
    plan = kindlerplan.build_plan(_template(_inputs(tree=False)))
    assert plan["stages"][0]["passives"][0] == {"id": 101, "name": None}


def test_support_applicability_comes_only_from_fit():
    seen = []

    def fit(skill, supports):
        seen.append((skill, supports))
        return {"Brute Force": True, "Echo Strike": False, "Other": "junk"}

    plan = kindlerplan.build_plan(_template(), fit=fit)
    sups = plan["stages"][1]["skills"][0]["supports"]
    assert [s["applies"] for s in sups] == [True, False]
    assert ("Ground Crack", ["Brute Force", "Echo Strike"]) in seen

    def broken(skill, supports):
        raise RuntimeError("no")

    plan = kindlerplan.build_plan(_template(), fit=broken)
    assert plan["stages"][1]["skills"][0]["supports"][0]["applies"] is None


def test_authored_focus_without_weights():
    plan = kindlerplan.build_plan(_template(), note=kindlerplan.FOCUS_CALC_OFF)
    assert plan["focus"] == "authored" and plan["focus_note"] == "calc_off"
    focus = plan["stages"][0]["focus"]
    assert [f["slot"] for f in focus] == ["Weapon 1", "Boots"]
    assert focus[1] == {"slot": "Boots", "source": "authored",
                        "stats": [{"stat": "movement speed", "weight": None},
                                  {"stat": "life", "weight": None}]}


def test_rank_stats_keeps_unweighted_places():
    w = {"+# to maximum Life": 0.2, "+# to Armour": 0.9}
    got = kindlerplan.rank_stats(["movement speed", "maximum life", "number of arrows",
                                  "armour"], w)
    assert [r["stat"] for r in got] == ["movement speed", "armour", "number of arrows",
                                        "maximum life"]
    assert got[1]["weight"] == 0.9 and got[0]["weight"] is None
    # a zero weight (no DPS / EHP change seen) keeps its place too
    zero = kindlerplan.rank_stats(["physical damage", "armour", "maximum life"],
                                  {"#% increased Physical Damage": 0.0,
                                   "+# to Armour": 0.1, "+# to maximum Life": 0.5})
    assert [r["stat"] for r in zero] == ["physical damage", "maximum life", "armour"]
    assert zero[0]["weight"] == 0.0
    # ties keep authored order
    tie = kindlerplan.rank_stats(["armour", "maximum life"],
                                 {"+# to maximum Life": 1.0, "+# to Armour": 1.0})
    assert [r["stat"] for r in tie] == ["armour", "maximum life"]


def test_weapon_slots_stay_authored_with_weights():
    w = {"#% increased Attack Speed": 5.0, "#% increased Physical Damage": 1.0}
    focus = kindlerplan.stage_focus({"Weapon 1": ["physical damage", "attack speed"],
                                     "Gloves": ["physical damage", "attack speed"]}, w)
    assert focus[0]["source"] == "authored"
    assert [r["stat"] for r in focus[0]["stats"]] == ["physical damage", "attack speed"]
    assert focus[1]["source"] == "pob"
    assert [r["stat"] for r in focus[1]["stats"]] == ["attack speed", "physical damage"]


def test_every_authored_focus_word_maps_or_is_known_unweighable():
    """Each focus word of the real table has a probe key, except the ones
    PoB's DPS / EHP cannot weigh (they keep their authored place)."""
    unweighable = {"movement speed", "number of arrows"}
    doc = json.loads(archetypes.PATH.read_text(encoding="ascii"))
    words = {w for t in doc["templates"] for st in t["stages"]
             for stats in st["focus"].values() for w in stats}
    assert words - set(kindlerplan.STAT_KEYS) <= unweighable
    for key in kindlerplan.STAT_KEYS.values():
        assert delta.probe_line(key) is not None, key


def test_focus_keys_skip_weapons_dedupe_and_cap():
    keys = kindlerplan.focus_keys(_template())
    assert keys == ["+# to maximum Life"]
    many = fx.stage(focus={"Amulet": list(kindlerplan.STAT_KEYS)[:12],
                           "Belt": list(kindlerplan.STAT_KEYS)[12:24]})
    keys = kindlerplan.focus_keys(_template(_inputs(fx.template(stages=[many]))))
    assert len(keys) == len(set(keys)) <= delta.MAX_PROBES


def test_carrier_base_is_the_first_released_amulet(tmp_path):
    doc = json.loads(_bases_file(tmp_path).read_text(encoding="utf-8"))
    assert kindlerplan.carrier_base_from_doc(doc) == "Gold Amulet"
    assert kindlerplan.carrier_base_from_doc({}) is None
    assert kindlerplan.carrier_base_from_doc([]) is None
    text = kindlerplan.carrier_text("Gold Amulet")
    assert text.isascii() and "Gold Amulet" in text


def test_focus_weights_through_pob_probes():
    inputs = _inputs()
    t = _template(inputs)
    xml = kindler.compose_xml(t, 1, 0, kindler.tree_ids(inputs["tree"], t))
    calc = ProbeCalc()
    keys = ["+# to maximum Life", "+# to Armour", "#% increased Physical Damage"]
    w = kindlerplan.focus_weights(calc, xml, "Gold Amulet", keys)
    assert set(w) == set(keys)
    assert w["+# to maximum Life"] > w["+# to Armour"] > 0
    assert kindlerplan.focus_weights(calc, xml, "Gold Amulet", []) == {}
    with pytest.raises(delta.CalcError):
        kindlerplan.focus_weights(ProbeCalc(fail=True), xml, "Gold Amulet", keys)


# --- the resolver ----------------------------------------------------------------

def _plan_of(stages):
    return {"stages": [{"id": f"s{i}", "trigger": trig, "level": lvl}
                       for i, (trig, lvl) in enumerate(stages)]}


REAL_SHAPE = _plan_of([({"kind": "zone", "zone": "G1_1"}, 3),
                       ({"kind": "act", "act": 1}, 15),
                       ({"kind": "act", "act": 2}, 31),
                       ({"kind": "area_level", "min": 54, "max": 64}, 56),
                       ({"kind": "area_level", "min": 65, "max": 100}, 70),
                       ({"kind": "level", "min": 90, "max": 100}, 95)])


@pytest.mark.parametrize("here,want", [
    ({"area_id": "G1_1", "area_level": 1, "level": 1}, ("s0", "zone")),
    ({"area_id": "G1_4", "area_level": 8, "level": 7}, ("s1", "act")),
    ({"area_id": "G1_town", "area_level": 15, "level": 12}, ("s1", "act")),
    ({"area_id": "G2_3", "area_level": 20, "level": 19}, ("s2", "act")),
    ({"area_id": "P1_2", "area_level": 55, "level": 53}, ("s3", "area_level")),
    ({"area_id": "MapHill", "area_level": 68, "level": 70}, ("s4", "area_level")),
    ({"area_id": "G3_1", "area_level": 33, "level": 30}, ("s2", "nearest_level")),
    ({"area_id": None, "area_level": None, "level": 92}, ("s5", "level")),
    ({"area_id": "HideoutX", "area_level": None, "level": 20}, ("s2", "nearest_level")),
    ({"area_id": None, "area_level": None, "level": 99}, ("s5", "level")),
])
def test_current_stage_priority(here, want):
    got = kindlerplan.current_stage(REAL_SHAPE, here)
    assert (got["id"], got["by"]) == want
    assert set(got) == {"stage", "id", "by"}  # never a done / progress claim


def test_current_stage_unknown_and_past_the_last():
    assert kindlerplan.current_stage(REAL_SHAPE, {"area_id": None, "area_level": None,
                                                  "level": None}) is None
    assert kindlerplan.current_stage({"stages": []}, {"level": 5}) is None
    tail = _plan_of([({"kind": "act", "act": 1}, 15)])
    got = kindlerplan.current_stage(tail, {"area_id": None, "area_level": None, "level": 40})
    assert got == {"stage": 0, "id": "s0", "by": "nearest_level"}


def test_here_reads_only_the_three_published_fields():
    snap = {"area_id": "G1_1", "area_level": 2, "level": True, "zone": "x", "acts": {}}
    assert kindlerplan.here_of(snap) == {"area_id": "G1_1", "area_level": 2, "level": None}
    obj = type("St", (), {"area_id": 5, "area_level": 3, "level": 9})()
    assert kindlerplan.here_of(obj) == {"area_id": None, "area_level": 3, "level": 9}
    assert kindlerplan.here_of(None) == {"area_id": None, "area_level": None, "level": None}


# --- the planner ------------------------------------------------------------------

def _planner(tmp_path, calc, inputs=None, bases=True, fit=None):
    return kindlerplan.Planner(FixedSources(inputs or _inputs()), calc=lambda: calc,
                               fit=fit, base_path=_bases_file(tmp_path, with_amulet=bases))


def _applies(plan):
    return [[[s["applies"] for s in sk["supports"]] for sk in st["skills"]]
            for st in plan["stages"]]


def test_planner_calc_off_is_authored(tmp_path):
    p = _planner(tmp_path, None)
    plan, word = p.plan(_result(scored=False))
    assert word == "calc_off" and plan["focus"] == "authored"
    assert p.plan(None) == (None, "")
    assert p.plan(_result(template_id="gone")) == (None, "")


def test_planner_pending_then_pob_and_cached(tmp_path):
    calc = ProbeCalc()
    p = _planner(tmp_path, calc)
    plan, word = p.plan(_result(), busy=True)
    assert word == "pending" and calc.calls == []  # the engine's run in flight
    plan, word = p.plan(_result(), wait=True)
    assert word == "pob" and plan["focus"] == "pob"
    boots = next(f for f in plan["stages"][0]["focus"] if f["slot"] == "Boots")
    assert boots["source"] == "pob"
    assert boots["stats"][1] == {"stat": "life", "weight": pytest.approx(0.1)}
    n = len(calc.calls)
    again, word = p.plan(_result())
    assert word == "pob" and len(calc.calls) == n and again == plan


def test_planner_background_run(tmp_path):
    calc = ProbeCalc()
    p = _planner(tmp_path, calc)
    p.plan(_result())
    p.join(10)
    assert p.plan(_result())[1] == "pob"


def test_planner_failed_and_no_base(tmp_path):
    p = _planner(tmp_path, ProbeCalc(fail=True))
    assert p.plan(_result(), wait=True)[1] == "failed"
    q = _planner(tmp_path / "n", ProbeCalc(), bases=False) if (tmp_path / "n").mkdir() is None \
        else None
    plan, word = q.plan(_result(), wait=True)
    assert word == "no_base" and plan["focus"] == "authored"


def test_planner_no_tree(tmp_path):
    p = _planner(tmp_path, ProbeCalc(), inputs=_inputs(tree=False))
    assert p.plan(_result())[1] == "no_tree"


# --- KINDLER-SUPPORT-FIT: support applicability from PoB ---------------------------

def test_stage_fits_asks_pob_once_per_stage_with_new_links():
    inputs = _inputs()
    t = _template(inputs)
    calc = FitCalc()
    fits = kindlerplan.stage_fits(calcwire.build_fit, calc, t,
                                  kindler.tree_ids(inputs["tree"], t))
    assert fits == {"Hammer Swing": {"Brute Force": True},
                    "Ground Crack": {"Brute Force": True, "Echo Strike": False}}
    # early and mid; maps repeats early's one link, so it is not loaded
    assert calc.fits == ["6", "12"]
    assert calc.calls == []  # no DPS / EHP calc for the fit


def test_stage_fits_keeps_only_asked_bool_answers():
    inputs = _inputs()
    t = _template(inputs)
    ids = kindler.tree_ids(inputs["tree"], t)

    def odd(calc, build):
        return {"Hammer Swing": {"Brute Force": "yes", "Not Linked": True},
                "Ground Crack": {"Echo Strike": True}, "Other": {"Brute Force": True},
                "Bad": ["x"]}

    assert kindlerplan.stage_fits(odd, None, t, ids) == {"Ground Crack": {"Echo Strike": True}}
    assert kindlerplan.stage_fits(lambda c, b: None, None, t, ids) == {}
    assert kindlerplan.stage_fits(calcwire.build_fit, FitCalc(fail_fit=True), t, ids) == {}
    assert kindlerplan.stage_fits(calcwire.build_fit, ProbeCalc(), t, ids) == {}


def test_planner_fills_applies_from_pob(tmp_path):
    calc = FitCalc()
    p = _planner(tmp_path, calc, fit=calcwire.build_fit)
    plan, word = p.plan(_result(), busy=True)
    assert word == "pending" and _applies(plan) == [[[None]], [[None, None]], [[None]]]
    plan, word = p.plan(_result(), wait=True)
    assert word == "pob"
    assert _applies(plan) == [[[True]], [[True, False]], [[True]]]
    n = len(calc.fits)
    assert p.plan(_result())[0] == plan and len(calc.fits) == n  # cached per key


def test_planner_unanswered_link_stays_null(tmp_path):
    class Unknown(FitCalc):
        UNKNOWN = {"Echo Strike"}

    p = _planner(tmp_path, Unknown(), fit=calcwire.build_fit)
    assert _applies(p.plan(_result(), wait=True)[0])[1] == [[True, None]]


def test_planner_fit_failure_or_no_fit_or_calc_off_is_null(tmp_path):
    p = _planner(tmp_path, FitCalc(fail_fit=True), fit=calcwire.build_fit)
    plan, word = p.plan(_result(), wait=True)
    assert word == "pob" and _applies(plan)[1] == [[None, None]]
    q = _planner(tmp_path, FitCalc())  # no fit callable
    assert _applies(q.plan(_result(), wait=True)[0])[1] == [[None, None]]
    off = _planner(tmp_path, None, fit=calcwire.build_fit)
    plan, word = off.plan(_result(scored=False))
    assert word == "calc_off" and _applies(plan)[1] == [[None, None]]


def test_planner_fits_survive_a_missing_base(tmp_path):
    """A run with no carrier base still records PoB's support answers; the
    re-run once the snapshot lands does not ask them again."""
    calc = FitCalc()
    p = _planner(tmp_path, calc, bases=False, fit=calcwire.build_fit)
    plan, word = p.plan(_result(), wait=True)
    assert word == "no_base" and _applies(plan)[1] == [[True, False]]
    n = len(calc.fits)
    p.plan(_result(), wait=True)
    assert len(calc.fits) == n


def test_plan_is_deterministic(tmp_path):
    a = _planner(tmp_path, ProbeCalc()).plan(_result(), wait=True)[0]
    b = _planner(tmp_path, ProbeCalc()).plan(_result(), wait=True)[0]
    assert kindler.dumps(a) == kindler.dumps(b)


# --- the route ---------------------------------------------------------------------

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
    def __init__(self, runtime, calc, area_id="G1_4", level=7):
        self.runtime = runtime
        self.tc_calc = calc
        self.state = type("St", (), {"level": level, "area_id": area_id,
                                     "area_level": 8})()
        self.ticks = []

    def add_tick(self, name, fn):
        self.ticks.append(name)


def _route_core(tmp_path, calc=None):
    core = _Core(tmp_path, calc)
    plug.attach(core)
    core.kindler.sources = FixedSources(_inputs())
    core.kindler_plan = kindlerplan.Planner(core.kindler.sources, calc=lambda: calc,
                                            base_path=_bases_file(tmp_path))
    return core


def _post(core, body):
    req = _Req(core, body)
    plug.post_generate(req, {}, None)
    return req.sent


def test_route_plan_none_before_a_result(tmp_path):
    core = _route_core(tmp_path)
    tab = core.gen_builds.add(cls="Warrior")
    assert _post(core, {"id": tab, "op": "plan"}) == (
        200, {"state": "none", "plan": None, "focus": "", "current": None})


def test_route_plan_follows_the_published_zone(tmp_path):
    core = _route_core(tmp_path)
    core.state.level = 5
    tab = core.gen_builds.add(cls="Warrior")
    assert _post(core, {"id": tab})[1]["state"] == "started"
    core.kindler.join(10)
    code, body = _post(core, {"id": tab, "op": "plan"})
    assert code == 200 and body["state"] == "done" and body["focus"] == "calc_off"
    assert body["plan"]["template"] == "warrior_hammer"
    assert body["current"] == {"stage": 0, "id": "early", "by": "level"}
    core.state.area_id = "G2_1"
    assert _post(core, {"id": tab, "op": "plan"})[1]["current"]["id"] == "mid"
    core.gen_builds.update(tab, {"follow": False})
    assert _post(core, {"id": tab, "op": "plan"})[1]["current"] is None


def test_route_plan_with_the_calc_gives_pob_focus(tmp_path):
    calc = ProbeCalc()
    core = _route_core(tmp_path, calc)
    tab = core.gen_builds.add(cls="Warrior")
    _post(core, {"id": tab})
    core.kindler.join(10)
    first = _post(core, {"id": tab, "op": "plan"})[1]
    assert first["focus"] in ("pending", "pob")
    core.kindler_plan.join(10)
    assert _post(core, {"id": tab, "op": "plan"})[1]["focus"] == "pob"


def test_route_planner_asks_pob_for_support_fit(tmp_path):
    core = _Core(tmp_path, None)
    plug.attach(core)
    assert core.kindler_plan.fit is calcwire.build_fit
    calc = FitCalc()
    core = _route_core(tmp_path, calc)
    core.kindler_plan.fit = calcwire.build_fit
    tab = core.gen_builds.add(cls="Warrior")
    _post(core, {"id": tab})
    core.kindler.join(10)
    _post(core, {"id": tab, "op": "plan"})
    core.kindler_plan.join(10)
    body = _post(core, {"id": tab, "op": "plan"})[1]
    assert _applies(body["plan"]) == [[[True]], [[True, False]], [[True]]]


def test_route_plan_refuses_extra_fields_and_gone_tab(tmp_path):
    core = _route_core(tmp_path)
    assert _post(core, {"id": "k1", "op": "plan", "x": 1})[0] == 400
    assert _post(core, {"id": "k42", "op": "plan"}) == (400, {"error": genstore.GONE_TEXT})


def test_route_set_is_unchanged():
    assert plug.ROUTES == {("POST", "/api/kindler-generate"): plug.post_generate}
    assert plug.OPS == ("generate", "read", "plan")
