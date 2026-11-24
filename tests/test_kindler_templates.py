"""KINDLER-TEMPLATES (decision 0081 points 2, 15, 16 and 18): the first
authored Kindler templates in server/al/data/archetypes.json.

The table is AshLight's own work. These tests check it with the
KINDLER-DATA loader and validator: the structure, one template per
archetype toggle (melee, spell, minion, bow), stages from the first zone to
early maps, gem timing that only uses gems already picked up, the
ascendancy trials in order, the point budget at each stage's level, and,
when the sidecar caches are present, the real GGG tree export (node ids,
routes from the class and ascendancy starts), the world_areas zone ids and
the gem names of the cached base_items snapshot. A missing cache skips its
test; nothing is fetched.
"""

import json
from pathlib import Path

import pytest

from server.al import acts
from server.al.theorycraft import archetypes, datacredit, treedata

TABLE_PATH = archetypes.PATH
REQUIRED_TOGGLES = ("melee", "spell", "minion", "bow")


@pytest.fixture(scope="module")
def table():
    return archetypes.load(TABLE_PATH)


def _cache(name):
    path = datacredit.cache_dir() / name
    if not path.is_file():
        pytest.skip(f"no cached {name}")
    return path


@pytest.fixture(scope="module")
def tree():
    path = treedata.default_path()
    if not Path(path).is_file():
        pytest.skip("no cached tree export")
    return archetypes.tree_graph(json.loads(Path(path).read_bytes()))


@pytest.fixture(scope="module")
def area_ids():
    ids = acts.load_ids(_cache(acts.FILE_NAME))
    if not ids:
        pytest.skip("cached world_areas is unreadable")
    return ids


def _gem_names(stage):
    names = [s["name"] for s in stage["skills"]]
    names += [n for s in stage["skills"] for n in s["supports"]]
    return names


# --- the file -----------------------------------------------------------

def test_file_is_ascii_lf_and_ends_with_newline():
    raw = TABLE_PATH.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert len(raw) <= archetypes.MAX_BYTES


def test_tracked_table_validates(table):
    assert table["schema"] == archetypes.SCHEMA
    assert table["templates"]
    assert archetypes.table()["templates"] == table["templates"]


def test_one_template_per_archetype_toggle(table):
    covered = {x for t in table["templates"] for x in t["toggles"]}
    for toggle in REQUIRED_TOGGLES:
        assert toggle in covered, toggle


def test_every_template_has_a_class_ascendancy_and_defence(table):
    for t in table["templates"]:
        assert t["class"] and t["ascendancy"], t["id"]
        assert t["defence"] in archetypes.DEFENCES, t["id"]


# --- stages ---------------------------------------------------------------

def test_stages_run_from_the_first_zone_to_maps(table):
    for t in table["templates"]:
        stages = t["stages"]
        assert len(stages) >= 5, t["id"]
        first, last = stages[0]["trigger"], stages[-1]["trigger"]
        assert first == {"kind": "zone", "zone": acts.FIRST_AREA}, t["id"]
        assert last["kind"] == "area_level" and last["max"] == archetypes.MAX_LEVEL
        acts_seen = [s["trigger"]["act"] for s in stages if s["trigger"]["kind"] == "act"]
        assert acts_seen == sorted(acts_seen) and len(set(acts_seen)) == len(acts_seen)
        assert acts_seen[:4] == [1, 2, 3, 4], t["id"]


def test_stage_levels_rise(table):
    for t in table["templates"]:
        levels = [s["level"] for s in t["stages"]]
        assert levels == sorted(levels) and len(set(levels)) == len(levels), t["id"]


def test_area_level_bands_do_not_overlap(table):
    for t in table["templates"]:
        bands = [s["trigger"] for s in t["stages"] if s["trigger"]["kind"] == "area_level"]
        for a, b in zip(bands, bands[1:]):
            assert a["max"] < b["min"], t["id"]


def test_every_stage_has_skills_focus_and_provenance(table):
    for t in table["templates"]:
        for st in t["stages"]:
            where = f"{t['id']} {st['id']}"
            assert st["skills"], where
            assert st["focus"], where
            assert st["src"].startswith("AshLight-authored"), where
            assert st["checked"] == t["checked"], where
            for sk in st["skills"]:
                assert sk["sockets"] == len(sk["supports"]), where


def test_main_skill_has_links_after_the_first_zone(table):
    for t in table["templates"]:
        for st in t["stages"][1:]:
            assert st["skills"][0]["supports"], f"{t['id']} {st['id']}"


def test_no_support_repeats_within_a_stage(table):
    for t in table["templates"]:
        for st in t["stages"]:
            sups = [n for s in st["skills"] for n in s["supports"]]
            assert len(sups) == len(set(sups)), f"{t['id']} {st['id']}"


# --- gem timing ---------------------------------------------------------

def test_gem_steps_follow_the_skills_in_use(table):
    """Each stage's steps move the gems in use from the previous stage to
    this one: a pick or swap brings a gem in, a swap's `for` and a drop
    take one out, and nothing else changes."""
    for t in table["templates"]:
        held = set()
        for st in t["stages"]:
            where = f"{t['id']} {st['id']}"
            now = set(_gem_names(st))
            after = set(held)
            for g in st["gems"]:
                if g["action"] == "pick":
                    assert g["name"] not in held, where
                    after.add(g["name"])
                elif g["action"] == "swap":
                    assert g["for"] in held, where
                    after.discard(g["for"])
                    after.add(g["name"])
                else:
                    assert g["name"] in held, where
                    after.discard(g["name"])
            assert after == now, where
            held = now


def test_gem_levels_are_left_out(table):
    """Point 16: no gem level is authored (the gems snapshot gives it)."""
    for t in table["templates"]:
        for st in t["stages"]:
            assert all(g["level"] is None for g in st["gems"]), f"{t['id']} {st['id']}"


# --- ascendancy and passives -------------------------------------------

def test_ascendancy_trials_one_to_four_in_order(table):
    for t in table["templates"]:
        trials = [s["ascendancy"]["trial"] for s in t["stages"] if s["ascendancy"]]
        assert trials == [1, 2, 3, 4], t["id"]
        for s in t["stages"]:
            if s["ascendancy"]:
                assert s["ascendancy"]["nodes"], f"{t['id']} {s['id']}"


def test_point_budget_and_order_without_caches(table):
    report = archetypes.check(table)
    assert report["ok"], report["problems"]


def test_every_stage_adds_passives_within_budget(table):
    for t in table["templates"]:
        total = 0
        for st in t["stages"]:
            assert st["passives"], f"{t['id']} {st['id']}"
            total += len(st["passives"])
            assert total <= archetypes.point_budget(st["level"], st["bonus_points"])


def test_no_bonus_points_are_claimed(table):
    """Quest passive points are left out (no permitted source names them)."""
    for t in table["templates"]:
        assert all(st["bonus_points"] == 0 for st in t["stages"]), t["id"]


# --- the real caches --------------------------------------------------

def test_check_passes_against_the_cached_tree_and_world_areas(table, tree, area_ids):
    report = archetypes.check(table, tree=tree, gems=None, area_ids=area_ids)
    assert report["ok"], report["problems"]
    assert not [n for n in report["notes"] if "dropped" in n]


def test_resolve_keeps_every_node_on_the_cached_tree(table, tree):
    view = archetypes.resolve(table, tree=tree, gems=None)
    assert not [n for n in view["notes"] if "dropped" in n]
    for t in view["templates"]:
        for st in t["stages"]:
            assert all(g["checked"] is False for g in st["gems"])


def test_class_and_ascendancy_match_the_tree(table, tree):
    for t in table["templates"]:
        assert tree.class_start(t["class"]) is not None, t["id"]
        assert tree.asc_start(t["ascendancy"]) is not None, t["id"]
        assert (tree.asc_class(t["ascendancy"]) or "").lower() == t["class"].lower()


def test_gem_names_are_released_gems_in_base_items(table):
    doc = json.loads(_cache("base_items.json").read_bytes())
    gems = {v.get("name") for v in doc.values()
            if isinstance(v, dict) and v.get("release_state") == "released"
            and "Gem" in str(v.get("item_class"))}
    for t in table["templates"]:
        for st in t["stages"]:
            names = _gem_names(st) + [g["name"] for g in st["gems"]]
            names += [g["for"] for g in st["gems"] if g["for"]]
            for name in names:
                assert name in gems, f"{t['id']} {st['id']}: {name}"
