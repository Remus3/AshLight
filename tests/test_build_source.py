"""ACTIVE-BUILD-PICK (decision 0096): one active build source per
character, the pasted build or a Kindler plan, picked by the player's
click and kept across a restart. A real build store, Kindler tabs store
and engine over the invented fixtures of tests/kindler_fixtures.py; a fake
calc counts calls (a restore must make none)."""

import json
import os

import pytest

import kindler_fixtures as fx
from server.al import playview
from server.al import state as state_mod
from server.al.plug import buildsource as plug
from server.al.plug import progression as prog_plug
from server.al.theorycraft import (archetypes, buildsource, codec, genstore, kindler,
                                   kindlerplan, store as build_store, treedata)

PIN = "a" * 40
NAME = "Hero"
PASTED_XML = ('<PathOfBuilding2><Build level="90" className="Witch" '
              'ascendClassName="Infernalist" mainSocketGroup="1"/>'
              '<Tree activeSpec="1"><Spec title="End" nodes="1,2,3"/></Tree>'
              '<Skills/><Items/></PathOfBuilding2>')


def _inputs():
    doc = fx.tree_doc()
    table = archetypes.validate(fx.table_doc(fx.template()))
    return {"view": archetypes.resolve(table, tree=archetypes.tree_graph(doc)),
            "table_sha": "t" * 64, "tree": treedata.parse(doc),
            "tree_version": "v" * 64, "pin": PIN}


class FixedSources:
    def __init__(self, inputs):
        self._inputs = inputs

    def inputs(self):
        return self._inputs

    def gems(self):
        return None


class CountCalc:
    def __init__(self):
        self.calls = 0

    def __call__(self, build, swaps):
        self.calls += 1
        return {"dps": 100.0, "ehp": 1000.0}


class _Core:
    def __init__(self, runtime, calc):
        self.runtime = runtime
        self.state = state_mod.SessionState()
        self.state.character = NAME
        self.state.level = 3
        self.builds = build_store.BuildStore(build_store.default_path(runtime),
                                             per_character=True)
        self.builds.character_of = lambda: self.state.character
        self.tc_calc = calc
        self.ticks = []

    def add_tick(self, name, fn=None):
        self.ticks.append((name, fn))


def _core(tmp_path, calc=None, generate=True, paste=True):
    """A core with the plugs attached; a pasted build for NAME and one
    generated Kindler tab, unless told otherwise."""
    core = _Core(tmp_path, calc or CountCalc())
    plug.attach(core)
    core.kindler.sources = FixedSources(_inputs())
    core.kindler_plan.sources = core.kindler.sources
    prog_plug.attach(core)
    core.builds.sync()
    if paste:
        core.builds.load_code(codec.encode(PASTED_XML))
    tab = core.gen_builds.add(cls="Warrior")
    if generate:
        core.kindler.generate(tab, wait=True)
    return core, tab


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


def _post(core, body):
    req = _Req(core, body)
    plug.post_build_source(req, {}, None)
    return req.sent


def _pasted_bytes(core):
    return core.builds.active_path().read_bytes()


# --- the store -------------------------------------------------------------------

def test_the_store_keeps_twelve_choices_and_drops_bad_entries(tmp_path):
    path = buildsource.default_path(tmp_path)
    s = buildsource.SourceStore(path)
    for i in range(14):
        s.set(f"c{i}", "k1", 1000 + i)
    again = buildsource.SourceStore(path)
    assert again.get("c0") is None and again.get("c1") is None
    assert again.get("c13") == {"tab": "k1", "at": 1013}
    doc = json.loads(path.read_text(encoding="ascii"))
    assert doc["schema"] == 1 and len(doc["chars"]) == buildsource.MAX_CHARS
    path.write_text(json.dumps({"schema": 1, "chars": {
        "ok": {"tab": "k2", "at": 5}, "bad tab": {"tab": "x", "at": 5},
        "bad at": {"tab": "k1", "at": True}, "": {"tab": "k1", "at": 1}}}),
        encoding="ascii")
    got = buildsource.SourceStore(path)
    assert got.get("ok") == {"tab": "k2", "at": 5}
    assert got.get("bad tab") is None and got.get("bad at") is None
    with pytest.raises(ValueError):
        got.set("x", "nope", 1)
    assert got.drop("ok") is True and got.drop("ok") is False


def test_the_summary_keeps_the_best_stage_and_variant():
    res = genstore.clean_result({"template": "t1", "at": 5, "scored": True,
                                 "key": "", "stage": "mid", "variant": 1}, strict=True)
    assert res["stage"] == "mid" and res["variant"] == 1
    old = genstore.clean_result({"template": "t1", "at": 5}, strict=True)
    assert "stage" not in old and "variant" not in old
    with pytest.raises(genstore.GenError):
        genstore.clean_result({"template": "t1", "at": 5, "variant": 9}, strict=True)


# --- the choice ------------------------------------------------------------------

def test_the_pasted_build_is_in_use_by_default(tmp_path):
    core, tab = _core(tmp_path)
    core.build_source.tick(force=True)
    view = core.state.snapshot()["build_source"]
    assert view["use"] == "pasted" and view["pasted"] is True
    assert view["offer"]["id"] == tab
    assert core.builds.build.class_name == "Witch"


def test_using_the_kindler_plan_keeps_the_pasted_file(tmp_path):
    core, tab = _core(tmp_path)
    before = _pasted_bytes(core)
    code, doc = _post(core, {"use": "kindler", "id": tab})
    assert code == 200 and doc["use"] == "kindler" and doc["saved"] is True
    assert doc["tab"] == tab and doc["label"] and doc["offer"] is None
    b = core.builds.build
    assert b.class_name == "Warrior" and b.level == 6  # the stage of level 3
    assert core.builds.source == "kindler"
    assert core.builds.snapshot()["source_label"] == doc["label"]
    assert _pasted_bytes(core) == before
    # one click back: the pasted build, read again from its file
    code, doc = _post(core, {"use": "pasted"})
    assert code == 200 and doc["use"] == "pasted"
    assert core.builds.build.class_name == "Witch" and core.builds.override is None
    assert buildsource.SourceStore(buildsource.default_path(tmp_path)).get(NAME) is None


def test_the_plan_stage_follows_play(tmp_path):
    core, tab = _core(tmp_path)
    _post(core, {"use": "kindler", "id": tab})
    assert core.builds.build.level == 6
    core.state.level = 12
    core.state.area_id = "G2_1"
    core.build_source.tick(force=True)
    assert core.builds.build.level == 12
    # follow off: the result's best stage
    core.gen_builds.update(tab, {"follow": False})
    core.build_source.tick(force=True)
    best = core.kindler.last(tab)["best"]["stage"]
    want = next(st["level"] for st in fx.template()["stages"] if st["id"] == best)
    assert core.builds.build.level == want


def test_a_restart_restores_the_plan_with_no_calc_and_no_generate(tmp_path):
    core, tab = _core(tmp_path)
    _post(core, {"use": "kindler", "id": tab})
    calc = CountCalc()
    again = _Core(tmp_path, calc)
    plug.attach(again)
    again.kindler.sources = FixedSources(_inputs())
    again.builds.sync()
    assert again.builds.build.class_name == "Witch"  # before the tick
    again.build_source.tick()
    assert again.builds.build.class_name == "Warrior"
    assert again.kindler.last(tab)["restored"] is True
    assert again.kindler.running() is None and calc.calls == 0
    assert again.state.snapshot()["build_source"]["use"] == "kindler"


def test_a_new_paste_makes_the_pasted_build_the_one_in_use(tmp_path):
    core, tab = _core(tmp_path)
    _post(core, {"use": "kindler", "id": tab})
    core.builds.load_code(codec.encode(PASTED_XML.replace('level="90"', 'level="91"')))
    assert core.builds.build.level == 91 and core.builds.override is None
    core.build_source.tick(force=True)
    assert core.builds.build.level == 91
    assert core.state.snapshot()["build_source"]["use"] == "pasted"


def test_a_changed_file_wins_only_when_newer_than_the_choice(tmp_path):
    core, tab = _core(tmp_path)
    _post(core, {"use": "kindler", "id": tab})
    path = core.builds.active_path()
    at = core.build_source.store.get(NAME)["at"]
    path.write_bytes((codec.encode(PASTED_XML.replace('level="90"', 'level="92"'))
                      + "\n").encode("ascii"))
    os.utime(path, (at - 100, at - 100))
    core.builds.sync()
    assert core.builds.build.class_name == "Warrior"
    path.write_bytes((codec.encode(PASTED_XML.replace('level="90"', 'level="93"'))
                      + "\n").encode("ascii"))
    os.utime(path, (at + 100, at + 100))
    core.builds.sync()
    assert core.builds.build.level == 93 and core.builds.override is None
    assert core.build_source.store.get(NAME) is None


def test_a_closed_tab_reads_as_the_pasted_build(tmp_path):
    core, tab = _core(tmp_path)
    _post(core, {"use": "kindler", "id": tab})
    core.gen_builds.close(tab)
    core.build_source.tick(force=True)
    assert core.builds.build.class_name == "Witch"
    assert core.state.snapshot()["build_source"]["use"] == "pasted"


# --- the route -------------------------------------------------------------------

@pytest.mark.parametrize("body", [{}, {"use": "x"}, {"use": "kindler"},
                                  {"use": "kindler", "id": 5},
                                  {"use": "kindler", "id": "zz"},
                                  {"use": "pasted", "id": "k1"},
                                  {"use": "pasted", "extra": 1}])
def test_the_route_refuses_bad_bodies(tmp_path, body):
    core, _tab = _core(tmp_path, generate=False)
    assert _post(core, body) == (400, {"error": plug.BAD})


def test_the_route_needs_a_result_and_a_character(tmp_path):
    core, tab = _core(tmp_path, generate=False)
    assert _post(core, {"use": "kindler", "id": tab}) == (400, {"error": plug.NO_RESULT})
    assert _post(core, {"use": "kindler", "id": "k99"}) == (400, {"error": plug.NO_RESULT})
    core.state.character = None
    core.builds.character = None
    assert _post(core, {"use": "pasted"}) == (400, {"error": plug.NO_CHARACTER})


def test_the_routes_are_get_and_post():
    assert plug.ROUTES == {("GET", "/api/build-source"): plug.get_build_source,
                           ("POST", "/api/build-source"): plug.post_build_source}
    assert plug.ORDER > 110 and plug.ORDER < prog_plug.ORDER


# --- Play and Progression follow it --------------------------------------------------

def _snap(state="fits", use="pasted", offer=None, pasted=True, label="Plan"):
    return {"build": {"loaded": state != "none", "class_name": "Warrior", "level": 6},
            "sources": {"calc_on": True},
            "build_source": {"use": use, "tab": "k1" if use == "kindler" else None,
                             "label": label if use == "kindler" else "",
                             "offer": offer, "pasted": pasted}}


def test_the_play_build_line_names_the_source_and_one_switch():
    v = playview.build_view(_snap(use="kindler"))
    assert v["row1"] == "Kindler: Plan, level 6"
    assert v["row2"] == playview.BUILD_SRC_KINDLER
    assert v["switch"] == {"label": "Use pasted build", "use": "pasted", "id": None}
    v = playview.build_view(_snap(offer={"id": "k1", "label": "Plan"}))
    assert v["row1"] == "Warrior, level 6" and v["row2"] == playview.BUILD_SRC_PASTED
    assert v["switch"] == {"label": "Use Kindler plan", "use": "kindler", "id": "k1"}
    v = playview.build_view(_snap())
    assert v["switch"] is None and v["row2"] == playview.BUILD_CALC_ON
    # no pasted build and no result: nothing to switch to, the paste button
    v = playview.build_view(_snap(state="none", pasted=False))
    assert v["switch"] is None and v["can_paste"] is True
    # no pasted build but a result: the one button is the switch
    v = playview.build_view(_snap(state="none", pasted=False, offer={"id": "k1", "label": ""}))
    assert v["switch"]["use"] == "kindler" and v["can_paste"] is False
    assert v["row2"] == "Or paste a PoB code on Build."
    assert len(playview.BUILD_SRC_KINDLER) <= playview.CAP_BUILD_ROW


def test_progression_uses_the_chosen_plan_over_the_pasted_build(tmp_path):
    core, tab = _core(tmp_path)
    core.progression.tick()
    assert core.progression.get()["source"] == "pob"
    _post(core, {"use": "kindler", "id": tab})
    core.progression._next_full = 0.0
    core.progression.tick()
    assert core.progression.get()["source"] == "kindler"


def test_from_summary_falls_back_to_the_last_stage():
    templates = _inputs()["view"]["templates"]
    doc = kindler.from_summary({"template": "warrior_hammer", "at": 1, "key": ""}, templates)
    hit = kindlerplan.best_of(doc, templates)
    assert hit[1] == len(templates[0]["stages"]) - 1 and hit[2] == 0
    assert kindler.from_summary({"template": "gone", "at": 1}, templates) is None
    assert kindler.from_summary(None, templates) is None


# --- the page (web/kindler.js, web/index.html, web/panels/build.js) ------------------

def test_the_page_has_the_two_use_for_play_chips():
    import srcpaths
    js, html = srcpaths.read("kindler.js"), srcpaths.read("index.html")
    assert 'id: "kindler-use", type: "button", "class": "chip"' in js
    assert 'var SOURCE_PATH = "/api/build-source";' in js
    assert ('<button id="build-use" type="button" class="chip" aria-pressed="true" '
            'data-label="Use pasted build for Play" hidden>Use pasted build for Play</button>'
            ) in html
    assert 'kindler: "Kindler plan (generated)"' in srcpaths.read("panels/build.js")
    for bad in ("innerHTML", "setInterval", "clipboard"):
        assert bad not in js


def test_source_of_reads_the_snapshot_view():
    import shutil
    import subprocess

    import srcpaths
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = (
        "const K = require('./web/kindler.js');"
        "const out = [K.sourceOf({build_source: {use: 'kindler', tab: 'k1', offer: null}}),"
        "K.sourceOf({build_source: {use: 'x', offer: {id: 'k2'}}}), K.sourceOf({}),"
        "K.USE_WORDS.use];"
        "process.stdout.write(JSON.stringify(out));")
    got = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True,
                                    check=True, cwd=str(srcpaths.ROOT)).stdout)
    assert got[0] == {"use": "kindler", "tab": "k1", "offer": None}
    assert got[1] == {"use": "pasted", "tab": "", "offer": {"id": "k2"}}
    assert got[2] is None and got[3] == "Use this plan for Play"
