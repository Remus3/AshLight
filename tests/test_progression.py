"""PROGRESSION-VIEW (decision 0092): the Progression view model, its plug
and its words.

Invented demo data only (tests/progression_fixtures.py). Covers: the
tree export's drawing fields, positions and kinds, the node states from a
Kindler plan and from a PoB spec, the move on a level change (and the
"new" list), the TC-SPEC-FOLLOW adapter and its fallback, the fallback
with no tree export and with the calc off, the guide's point books (never
claimed taken), the next-up hook, the size bounds, the plug's tick (a
rebuild only on a change, the published summary) and its route, and the
exact word templates.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tests", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import progression_fixtures as pf  # noqa: E402
from server.al import state as state_mod  # noqa: E402
from server.al.plug import progression as plug  # noqa: E402
from server.al.text import progression as words  # noqa: E402
from server.al.theorycraft import progression, treedata  # noqa: E402


@pytest.fixture(scope="module")
def tree():
    return pf.tree()


def kmodel(tree, level, stage=2, prev=None, **kw):
    plan = kw.pop("plan", None) or pf.plan(tree)
    return progression.build_model(tree=tree, level=level, area_id="G1_4", zone="Demo Woods",
                                   guide=pf.GUIDE, kindler={"plan": plan, "stage": stage,
                                                            "label": "Demo"}, prev=prev, **kw)


# --- the export's drawing fields ------------------------------------------------

def test_the_tree_export_keeps_positions_links_and_mastery(tree):
    n = tree.nodes[1001]
    assert n.x == pytest.approx(1950.0) and n.y == pytest.approx(0.0)
    assert 1002 in n.links and all(isinstance(i, int) for i in n.links)
    assert tree.nodes[9999].mastery is True and tree.nodes[1001].mastery is False
    # a start lists only "root" in its in list: no numeric link from it
    assert pf.START_ID not in tree.nodes[pf.START_ID].links
    # to_dict is unchanged (the drawing fields are not part of it)
    assert set(n.to_dict()) == {"id", "name", "stats", "ascendancy", "notable", "keystone",
                                "jewel_socket", "class_start"}


def test_a_node_without_numbers_has_no_position():
    t = treedata.parse({"nodes": {"7": {"skill": 7, "x": "1", "y": True, "out": ["root", "8"]},
                                  "8": {"skill": 8, "x": 1.5, "y": -2}}})
    assert t.nodes[7].x is None and t.nodes[7].y is None and t.nodes[7].links == (8,)
    assert (t.nodes[8].x, t.nodes[8].y) == (1.5, -2.0)


# --- positions, kinds and states ------------------------------------------------

def test_the_view_sends_export_positions_and_own_kinds(tree):
    m = kmodel(tree, 29)
    rows = {r[0]: r for r in m["tree"]["n"]}
    n = tree.nodes[1001]
    assert rows[1001][1:3] == [round(n.x), round(n.y)]
    kinds = {r[3] for r in m["tree"]["n"]}
    assert kinds <= set(progression.KINDS) and {"s", "n", "c"} <= kinds
    assert 9999 not in rows  # a mastery is never drawn
    assert all(not tree.nodes[i].ascendancy for i in rows)
    # every edge joins two sent nodes, by index, with a state
    for i, j, st in m["tree"]["e"]:
        assert 0 <= i < len(rows) and 0 <= j < len(rows) and st in progression.STATES
    # names only for planned and notable nodes, at most two stat lines
    for k, v in m["tree"]["names"].items():
        assert 1 <= len(v) <= 1 + progression.MAX_STATS


def test_kindler_states_follow_the_level_budget(tree):
    plan = pf.plan(tree)
    order = [p["id"] for st in plan["stages"] for p in st["passives"]]
    m = kmodel(tree, 29, plan=plan)
    states = {r[0]: r[4] for r in m["tree"]["n"]}
    assert [states[i] for i in order[:28]] == ["h"] * 28
    assert [states[i] for i in order[28:31]] == ["d"] * 3
    assert all(states[i] == "l" for i in order[31:])
    assert m["counts"] == {"have": 28, "due": 3, "later": 29, "asc_have": 0, "asc_due": 2}
    # the budget line only repeats the planned count here: left out (PG-15)
    assert not any("not counting books" in p for p in m["points"])


def test_a_level_up_moves_the_due_nodes_and_lists_the_new_ones(tree):
    plan = pf.plan(tree)
    order = [p["id"] for st in plan["stages"] for p in st["passives"]]
    before = kmodel(tree, 29, plan=plan)
    after = kmodel(tree, 30, plan=plan, prev=before)
    assert before["key"] != after["key"]
    states = {r[0]: r[4] for r in after["tree"]["n"]}
    assert states[order[28]] == "h" and states[order[31]] == "d"
    assert after["new"] == [order[31]]
    # the first model of a core lists nothing as new (nothing to compare)
    assert before["new"] == []
    # an unchanged input gives the same key (the page reads nothing new)
    assert kmodel(tree, 30, plan=plan, prev=before)["key"] == after["key"]


def test_the_ascendancy_view_has_its_own_box_and_trial_states(tree):
    m = kmodel(tree, 29, stage=2)
    asc = m["asc"]
    assert asc["name"] == pf.ASC
    st = {r[0]: r[4] for r in asc["n"]}
    assert st[5001] == st[5002] == "d" and st[5003] == "l"
    assert {r[3] for r in asc["n"]} >= {"a"}
    assert asc["box"][0] < -19000  # framed on the ascendancy, apart from the main tree
    assert any(s["kind"] == "ascendancy" and s["text"].startswith("After ascendancy trial 1: ")
               for s in m["next"])
    # with follow off (no stage) nothing is planned or due, all later
    off = kmodel(tree, 29, stage=None)
    assert {r[4] for r in off["asc"]["n"] if r[0] in (5001, 5002, 5003, 5004)} == {"l"}


def test_no_level_means_nothing_planned_and_an_honest_line(tree):
    m = kmodel(tree, None)
    assert m["counts"]["have"] == 0 and m["counts"]["due"] == 0
    assert m["points"][0] == words.PASSIVES_NO_LEVEL.format(have=0)


# --- PoB source and the TC-SPEC-FOLLOW adapter ----------------------------------------

def test_a_pob_build_shows_its_active_spec_with_no_due_nodes(tree):
    b = pf.build(tree, 30, stats={"Spirit": 100, "SpiritUnreserved": 40},
                 weapon_sets={1: [1001, 1002], 2: [1003]})
    m = progression.build_model(build=b, tree=tree, level=30, area_id="G1_4",
                                zone="Demo Farm", guide=pf.GUIDE)
    assert m["source"] == "pob" and m["source_line"] == words.SOURCE_POB
    assert m["counts"]["have"] == 30 and m["counts"]["due"] == 0
    assert m["counts"]["asc_have"] == 2
    assert words.SPIRIT.format(spirit="100", free="40") in m["points"]
    assert words.WEAPON_SETS.format(one=2, two=1) in m["points"]
    # the gem row: the active gem with its two supports
    row = m["skills"][0]
    assert row["name"] == "Demo Strike" and [s["name"] for s in row["supports"]] == [
        "Demo Support 0", "Demo Support 1"]
    assert row["meta"] == "gem level 20, unchecked"
    assert row["with"] == "with Demo Support 0 (unchecked), Demo Support 1 (unchecked)"
    # the book of this zone shows on the strip
    assert m["next"] == [{"kind": "book", "text": progression.step_text(
        "Here: A book of 2 points - bring the demo lute back.")}]


def test_pick_specs_falls_back_to_the_active_spec(tree):
    nodes = pf.path_from_start(tree, 40)
    b = pf.model.parse(pf.build_xml(tree, nodes, specs=[("Level 1-20", nodes[:15]),
                                                        ("Level 21-40", nodes[:30]),
                                                        ("Level 41-60", nodes)]))
    assert progression.pick_specs(b, 25) == (0, None)
    assert progression.pick_specs(b, 25, picker=lambda bb, lv: None) == (0, None)
    assert progression.pick_specs(b, 25, picker=lambda bb, lv: 99) == (0, None)

    def boom(bb, lv):
        raise RuntimeError("x")
    assert progression.pick_specs(b, 25, picker=boom) == (0, None)

    def band(bb, lv):
        return 0 if lv <= 20 else 1 if lv <= 40 else 2
    assert progression.pick_specs(b, 25, picker=band) == (1, 2)
    assert progression.pick_specs(b, 50, picker=band) == (2, None)
    m = progression.build_model(build=b, tree=tree, level=25, picker=band)
    assert m["counts"]["have"] == 30 and m["counts"]["due"] == 10
    assert m["source_line"] == words.SOURCE_POB_SPEC.format(title="Level 21-40")
    assert m["next"][0] == {"kind": "passive", "text": "Next tree: 10 more passives"}
    # a level-up into the next band: the next spec shows, its new nodes were due
    m2 = progression.build_model(build=b, tree=tree, level=41, picker=band, prev=m)
    assert m2["counts"]["have"] == 40 and m2["counts"]["due"] == 0


def test_a_spec_from_another_id_space_shows_no_nodes(tree):
    b = pf.model.parse(pf.build_xml(tree, [60001, 60002, 60003]))
    m = progression.build_model(build=b, tree=tree, level=10)
    assert m["note"] == words.NO_IDS and m["counts"]["have"] == 0


# --- fallbacks -------------------------------------------------------------------

def test_no_tree_export_still_gives_skills_points_and_a_note(tree):
    m = kmodel(None, 29, plan=pf.plan(tree))
    assert m["tree"] is None and m["asc"] is None and m["note"] == words.NO_TREE
    assert m["skills"] and m["points"]
    s = progression.summary(m)
    assert s["tree"] is False and s["key"] == m["key"]


def test_the_calc_off_plan_shows_applies_as_not_reported(tree):
    plan = pf.plan(tree, supports=3)
    for st in plan["stages"]:
        for sk in st["skills"]:
            for s in sk["supports"]:
                s["applies"] = None  # kindlerplan without a fit callable (calc off)
    m = kmodel(tree, 29, plan=plan)
    assert all(s["applies"] is None for r in m["skills"] for s in r["supports"])
    assert "doesn't fit" not in json.dumps(m["skills"])
    # with PoB's answer a support that does not apply says so
    m2 = kmodel(tree, 29)
    assert "Demo Support 1 (doesn't fit)" in m2["skills"][0]["with"]


def test_nothing_loaded_is_source_none_with_no_points(tree):
    m = progression.build_model(tree=tree, level=12)
    assert m["source"] == "none" and m["tree"] is None and m["points"] == []
    assert m["source_line"] == words.SOURCE_NONE


def test_gem_timing_reads_the_gems_snapshot_and_marks_the_next_one(tree):
    gems = {"demo strike": {"name": "Demo Strike", "level": 1},
            "demo support 0": {"name": "Demo Support 0", "level": 8},
            "demo support 1": {"name": "Demo Support 1", "level": 33}}
    b = pf.build(tree, 30)
    m = progression.build_model(build=b, tree=tree, level=30, gems=gems)
    row = m["skills"][0]
    assert row["ready"] and row["meta"] == "gem level 20, ready"
    assert row["with"] == "with Demo Support 0 (ready), Demo Support 1 (level 33)"
    assert {"kind": "gem", "text": "Support at level 33: Demo Support 1"} in m["next"]


def test_kindler_gem_steps_say_ready_or_the_level(tree):
    m = kmodel(tree, 31)
    gem = [s for s in m["next"] if s["kind"] == "gem"]
    assert gem == [{"kind": "gem", "text": "Support ready: Demo Support 0"}]
    m = kmodel(tree, 30)
    gem = [s for s in m["next"] if s["kind"] == "gem"]
    assert gem == [{"kind": "gem", "text": "Support at level 31: Demo Support 0"}]


# --- books -------------------------------------------------------------------------

def test_books_are_counted_from_the_guide_and_never_claimed():
    label, found, here = progression.books(pf.GUIDE, "G1_4", "Demo Farm")
    assert label == "Act 1" and found == ["Demo Woods", "Demo Farm"]
    assert here == "A book of 2 points - bring the demo lute back."
    assert progression.books(pf.GUIDE, None, "Demo Farm") == (None, [], None)
    assert progression.books(pf.GUIDE, "G2_1", "x") == ("Act 2", [], None)
    for text in (words.BOOKS_ACT, words.BOOKS_NONE, words.BOOKS_UNKNOWN, words.BOOK_HERE):
        low = text.lower()
        assert "taken" not in low and "picked" not in low and "got" not in low


# --- the next-up hook -------------------------------------------------------------

def test_a_next_up_source_adds_steps_in_its_order(tree):
    try:
        progression.add_next_source("demo-first", lambda ctx: [
            {"kind": "uncut", "text": "Demo uncut gem at level %d" % ctx["level"]}], order=5)
        progression.add_next_source("demo-bad", lambda ctx: [{"kind": "x", "text": "caf\u00e9"},
                                                             "junk", {"kind": "", "text": "y"}])

        def boom(ctx):
            raise RuntimeError("broken source")
        progression.add_next_source("demo-boom", boom)
        m = kmodel(tree, 29)
        assert m["next"][0] == {"kind": "uncut", "text": "Demo uncut gem at level 29"}
        assert len(m["next"]) == progression.NEXT_MAX
        assert all(s["text"].isascii() for s in m["next"])
    finally:
        for name in ("demo-first", "demo-bad", "demo-boom"):
            progression.remove_next_source(name)
    with pytest.raises(ValueError):
        progression.add_next_source("", lambda ctx: [])


# --- bounds -----------------------------------------------------------------------

def test_a_big_tree_stays_within_the_node_edge_and_byte_caps():
    big = pf.tree(rings=30, long_names=True)
    order = pf.path_from_start(big, 400)
    plan = {"class": "Warrior", "ascendancy": pf.ASC, "stages": [
        {"level": 1, "budget": 0, "passives": [{"id": n} for n in order], "skills": [],
         "gems": [], "ascendancy": None}]}
    m = progression.build_model(tree=big, level=90, kindler={"plan": plan, "stage": 0,
                                                            "label": "big"})
    assert len(m["tree"]["n"]) <= progression.MAX_NODES
    assert len(m["tree"]["e"]) <= progression.MAX_EDGES
    assert len(m["tree"]["names"]) <= progression.MAX_NAMED
    assert len(json.dumps(m, separators=(",", ":"))) <= progression.MAX_BYTES
    # every planned node is kept before any unplanned one
    sent = {r[0] for r in m["tree"]["n"]}
    assert set(order) <= sent
    s = progression.summary(m)
    assert len(json.dumps(s)) < 2048


def test_the_render_budget_is_ten_elements_a_tree():
    """Decision 0002 dashboard budget (tests/test_dash_perf.py, 1,500
    elements): web/panels/tree.js draws a whole tree in one fixed set of
    paths (4 link states, 1 ring, 4 node states, 1 new), whatever its
    size."""
    src = (ROOT / "web" / "panels" / "tree.js").read_text(encoding="ascii")
    assert 'var STATES = ["o", "l", "h", "d"];' in src
    assert src.count('el(doc, "path"') == 4
    assert "createElementNS(NS, name)" in src


# --- the plug -----------------------------------------------------------------------

class _Builds:
    def __init__(self, tree, build=None):
        self.build = build
        self.tree = _Cache(tree)


class _Cache:
    def __init__(self, tree):
        self.t = tree

    def best_for(self, ids):
        return self.t


class _Core:
    def __init__(self, tree, build=None):
        self.state = state_mod.SessionState()
        self.builds = _Builds(tree, build)
        self.ticks = []

    def add_tick(self, name, fn=None):
        self.ticks.append((name, fn))


def test_the_tick_publishes_only_on_a_change(tree):
    core = _Core(tree)
    plug.attach(core)
    holder = core.progression
    clock = [0.0]
    holder.clock = lambda: clock[0]
    assert [n for n, _ in core.ticks] == ["progression"]
    # nothing loaded: no snapshot key at all
    assert holder.tick() is True
    assert "progression" not in core.state.snapshot()
    v0 = core.state.version
    assert holder.tick() is False and core.state.version == v0
    # a build appears: the summary is published by itself
    core.builds.build = pf.build(tree, 30)
    assert holder.tick() is True
    snap = core.state.snapshot()
    assert snap["progression"]["source"] == "pob"
    key = snap["progression"]["key"]
    assert holder.get()["key"] == key
    # the same inputs: no rebuild, no version bump
    v1 = core.state.version
    clock[0] += plug.FULL_EVERY_S + 1
    assert holder.tick() is False and core.state.version == v1
    # a level change moves it on
    core.state.level = 31
    assert holder.tick() is True
    assert core.state.snapshot()["progression"]["level"] == 31
    # the build goes: the view is published empty
    core.builds.build = None
    assert holder.tick() is True and core.state.snapshot()["progression"] is None


def test_the_spec_picker_is_none_without_specfollow(monkeypatch):
    monkeypatch.setattr(plug, "_specfollow", lambda: None)
    assert plug.spec_picker(object()) is None
    assert plug.ROUTES == {("GET", "/api/progression"): plug.get_progression}


def test_the_spec_picker_follows_specfollow_pick(tree, monkeypatch):
    """TC-SPEC-FOLLOW (decision 0089): the chooser is specfollow.pick() with
    PoB's own active spec as the fallback; the next band's new nodes are
    due."""
    asked = []

    class SF:
        @staticmethod
        def pick(specs, active_index, level):
            asked.append((active_index, level))
            return (0 if level <= 20 else 1 if level <= 40 else 2), True
    monkeypatch.setattr(plug, "_specfollow", lambda: SF)
    nodes = pf.path_from_start(tree, 40)
    b = pf.model.parse(pf.build_xml(tree, nodes, specs=[("Level 1-20", nodes[:15]),
                                                        ("Level 21-40", nodes[:30]),
                                                        ("Level 41-60", nodes)]))
    picker = plug.spec_picker(object())
    assert picker(b, 25) == 1 and asked[0] == (0, 25)
    m = progression.build_model(build=b, tree=tree, level=25, picker=picker)
    assert m["counts"]["have"] == 30 and m["counts"]["due"] == 10
    assert m["next"][0]["text"] == "Next tree: 10 more passives"


def test_the_route_answers_the_last_model(tree):
    core = _Core(tree, pf.build(tree, 20))
    plug.attach(core)

    class Req:
        class server:
            pass

        def _json(self, code, body, extra):
            return code, body
    req = Req()
    req.server.core = core
    assert plug.get_progression(req, {}, {}) == (200, {"key": None})
    core.progression.tick()
    code, body = plug.get_progression(req, {}, {})
    assert code == 200 and body["key"] == core.progression.get()["key"]
    assert body["source"] == "pob" and body["tree"]["n"]


# --- words ---------------------------------------------------------------------------

def test_the_words_are_pinned_exactly():
    assert words.TAKE_NEXT == "Take next: {names}"
    assert words.NEXT_BAND == "Next tree: {n} more {passives}"
    assert words.GEM_NOW == "{kind} ready: {name}"
    assert words.GEM_LATER == "{kind} at level {level}: {name}"
    assert words.ASC_TRIAL == "After ascendancy trial {trial}: {names}"
    assert words.BOOK_HERE == "Here: {text}"
    assert words.NOTHING_NEXT == "Nothing new is due at this level."
    assert words.SOURCE_NONE == "No build yet. Paste one on Build and items."
    assert words.names_line(["A", "A", "B", "C"], 2, words.TAKE_NEXT_MORE,
                            words.TAKE_NEXT) == "Take next (+1): A (2), B"
    assert words.names_line(["A"], 2, words.TAKE_NEXT_MORE, words.TAKE_NEXT) == "Take next: A"
    for name in dir(words):
        v = getattr(words, name)
        if isinstance(v, str) and not name.startswith("_"):
            assert v.isascii() and "!" not in v, name


def test_the_copy_sheet_lists_every_template():
    sheet = (ROOT / "docs" / "design" / "copy" / "progression.md").read_text(encoding="ascii")
    for name in dir(words):
        v = getattr(words, name)
        if isinstance(v, str) and name.isupper():
            assert f"`{v}`" in sheet, name
    js = (ROOT / "web" / "panels" / "progression.js").read_text(encoding="ascii")
    for word in ("Next up", "Item check", "Progression", "Back to build",
                 "Skills and supports", "Hover a node to read it."):
        assert word in js and f"`{word}`" in sheet, word
