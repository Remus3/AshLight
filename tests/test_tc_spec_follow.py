"""TC-SPEC-FOLLOW (research 0064 G1, decision 0088): the loaded build's tree
spec follows the character level.

Synthetic PoB2 build XML only (element and attribute names as in
tests/tc_fixtures.py; every title, node and value is invented). The pinned
PoB checkout is read as text only, never run (static check skips when the
optional calc component is absent).
"""

import re

import pytest

from server.al.core import Core
from server.al.theorycraft import bridge, calcwire, codec, model, specfollow, store


def spec_xml(titles, active, level=60):
    specs = []
    for i, title in enumerate(titles):
        attr = "" if title is None else f' title="{title}"'
        nodes = ",".join(str(100 * (i + 1) + n) for n in range(i + 2))
        specs.append(f'\t\t<Spec{attr} treeVersion="0_3" classId="1" ascendClassId="0" '
                     f'nodes="{nodes}">\n'
                     f'\t\t\t<URL>https://example.org/tree/spec{i + 1}</URL>\n'
                     f'\t\t</Spec>\n')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<PathOfBuilding2>\n'
            f'\t<Build level="{level}" className="Monk" ascendClassName="None"/>\n'
            f'\t<Tree activeSpec="{active}">\n' + "".join(specs) + "\t</Tree>\n"
            '\t<Notes>A &lt;Tree activeSpec="9"&gt; line in the notes</Notes>\n'
            "</PathOfBuilding2>\n")


BANDS = ["Level 1-30", "Level 31-69", "lvl 70+"]
THREE = spec_xml(BANDS, active=3)
NO_MATCH = spec_xml(["Act 1", "Endgame", None], active=2)


def lvl(name, n, at=1.0):
    return {"type": "level_up", "character": name, "class": "Monk", "level": n,
            "recv_ts": at}


# -- the title rule

@pytest.mark.parametrize("title,band", [
    ("Level 30", (30, None)), ("lvl 30", (30, None)), ("30", (30, None)),
    ("Level 1-30", (1, 30)), ("LVL 31 - 69", (31, 69)), ("Lv. 40 to 60", (40, 60)),
    ("lvl 70+", (70, None)), ("70+", (70, None)), ("1-30", (1, 30)),
    ("Act 2 (lvl 15)", (15, None)), ("level 1 - level 30", (1, 30)),
])
def test_title_band_reads_a_level(title, band):
    assert specfollow.title_band(title) == band


@pytest.mark.parametrize("title", [
    None, "", "Act 4", "Endgame", "Level 30 and lvl 60", "Level 0", "Level 101",
    "Level 60-30", "Tier 3 maps", "Leveling", "130", "Level", "level30x",
])
def test_title_band_never_guesses(title):
    assert specfollow.title_band(title) is None


# -- the pick

def test_pick_follows_the_bands():
    specs = model.parse(THREE).specs
    assert specfollow.pick(specs, 2, 1) == (0, True)
    assert specfollow.pick(specs, 2, 30) == (0, True)
    assert specfollow.pick(specs, 2, 31) == (1, True)
    assert specfollow.pick(specs, 2, 69) == (1, True)
    assert specfollow.pick(specs, 2, 70) == (2, True)
    assert specfollow.pick(specs, 2, 100) == (2, True)


@pytest.mark.parametrize("level", [None, 0, 101, "45", True, 45.0])
def test_pick_without_a_level_keeps_pob_active(level):
    specs = model.parse(THREE).specs
    assert specfollow.pick(specs, 2, level) == (2, False)


def test_pick_no_match_falls_back_to_active():
    assert specfollow.pick(model.parse(NO_MATCH).specs, 1, 45) == (1, False)
    # a band that ends below the level does not hold it
    specs = model.parse(spec_xml(["Level 1-30", "Endgame"], active=2)).specs
    assert specfollow.pick(specs, 1, 50) == (1, False)


def test_pick_tie_is_no_guess():
    specs = model.parse(spec_xml(["Level 30", "lvl 30", "Endgame"], active=3)).specs
    assert specfollow.pick(specs, 2, 40) == (2, False)
    assert specfollow.pick(specs, 1, 40) == (1, True)  # the tie holds PoB's own


def test_highest_start_at_or_below_wins():
    specs = model.parse(spec_xml(["Level 10", "Level 40", "Level 25"], active=1)).specs
    assert specfollow.pick(specs, 0, 30) == (2, True)
    assert specfollow.pick(specs, 0, 5) == (0, False)


# -- the followed build

def test_follow_points_the_xml_at_the_spec_and_keeps_the_code():
    b = model.parse(THREE)
    f = specfollow.follow(b, 45)
    assert f.active_spec.title == "Level 31-69" and f.spec_by_level
    assert 'activeSpec="2"' in f.raw_xml and 'activeSpec="3"' not in f.raw_xml
    # only the Tree tag changed; the notes text is untouched
    assert f.raw_xml.replace('<Tree activeSpec="2">', '<Tree activeSpec="3">') == THREE
    assert model.parse(f.raw_xml).active_spec_index == 1
    assert codec.decode(f.to_code()) == THREE  # the player's own code
    assert f.pob_spec_index == 2
    view = f.to_dict()
    assert view["tree"]["title"] == "Level 31-69"
    assert view["spec_follow"] == {"index": 2, "title": "Level 31-69", "by_level": True,
                                   "level": 45, "pob_index": 3}
    # following again from the followed build
    g = specfollow.follow(f, 12)
    assert g.active_spec.title == "Level 1-30" and 'activeSpec="1"' in g.raw_xml
    h = specfollow.follow(g, 80)
    assert h.raw_xml == THREE and h.pasted_xml is None and h.spec_by_level
    assert h.to_dict()["spec_follow"]["index"] == 3


def test_follow_no_match_is_the_active_spec():
    b = model.parse(NO_MATCH)
    f = specfollow.follow(b, 45)
    assert f.raw_xml == NO_MATCH and f.active_spec.title == "Endgame"
    assert f.to_dict()["spec_follow"]["by_level"] is False


def test_follow_inserts_a_missing_active_attribute():
    xml = THREE.replace('<Tree activeSpec="3">', "<Tree>")
    b = model.parse(xml)
    assert b.active_spec_index == 0
    f = specfollow.follow(b, 80)
    assert f.active_spec.title == "lvl 70+" and '<Tree activeSpec="3">' in f.raw_xml


def test_follow_refuses_an_unclear_tree_tag():
    assert specfollow.set_active_spec(THREE + "<Tree/>", 1) is None
    assert specfollow.set_active_spec("<x/>", 1) is None


def test_single_spec_and_no_tree_are_unchanged():
    one = spec_xml(["Level 1-30"], active=1)
    assert specfollow.follow(model.parse(one), 80).raw_xml == one
    bare = model.parse('<PathOfBuilding2><Build level="3"/></PathOfBuilding2>')
    assert specfollow.follow(bare, 10).active_spec is None


# -- the store: tree view, .build download, calc and the level-up switch

def test_store_switches_the_spec_on_a_level_up(tmp_path):
    level = {"n": 12}
    s = store.BuildStore(tmp_path / "build" / "last-code.txt")
    s.level_of = lambda: level["n"]
    s.load_code(codec.encode(THREE))
    assert s.build.active_spec.title == "Level 1-30"
    assert s.sync() is None
    level["n"] = 31  # the player's own level-up line
    fired = []
    s.add_listener(fired.append)
    assert s.sync() == "spec"
    assert fired and fired[0].active_spec.title == "Level 31-69"
    snap = s.snapshot()
    assert snap["build"]["tree"]["title"] == "Level 31-69"
    assert snap["build"]["spec_follow"]["by_level"] is True
    assert codec.decode(snap["code"]) == THREE
    level["n"] = 32
    assert s.sync() is None  # same spec: nothing fires
    level["n"] = None
    assert s.sync() == "spec" and s.build.active_spec.title == "lvl 70+"


def test_store_restart_follows_at_once(tmp_path):
    path = tmp_path / "build" / "last-code.txt"
    store.BuildStore(path).load_code(codec.encode(THREE))
    s = store.BuildStore(path)
    s.level_of = lambda: 75
    assert s.build.active_spec.title == "lvl 70+"  # PoB's active, level not read yet
    assert s.sync() is None  # level 75 picks the same spec
    s.level_of = lambda: 5
    assert s.sync() == "spec" and s.build.active_spec.title == "Level 1-30"


def test_calc_loads_the_followed_spec():
    loaded = []

    class Bridge:
        def load_build(self, xml):
            loaded.append(xml)

        def set_item(self, text, slot=None):
            pass

        def outputs(self, keys=None):
            return {"TotalDPS": 1.0, "TotalEHP": 2.0}

    calc = calcwire.make_calc(lambda: Bridge())
    calc(specfollow.follow(model.parse(THREE), 45), {})
    calc(specfollow.follow(model.parse(THREE), 80), {})
    assert re.search(r'<Tree activeSpec="2">', loaded[0])
    assert re.search(r'<Tree activeSpec="3">', loaded[1])


def test_core_tick_follows_the_level_up(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    try:
        core.state.apply(lvl("Sable", 29))
        assert core.tick_build() == "switch"
        core.builds.load_code(codec.encode(THREE))
        assert core.builds.snapshot()["build"]["tree"]["title"] == "Level 1-30"
        assert core.tick_build() is None
        core.state.apply(lvl("Sable", 31, 2.0))
        assert core.tick_build() == "spec"
        assert core.builds.snapshot()["build"]["tree"]["title"] == "Level 31-69"
    finally:
        core.close()


# -- PoB's own load selects the spec named by activeSpec (text only)

try:
    _SRC = bridge.component_paths()["pob_src"]
except (OSError, ValueError, KeyError):
    _SRC = None


@pytest.mark.skipif(_SRC is None or not (_SRC / "Classes" / "TreeTab.lua").is_file(),
                    reason="pinned PoB checkout absent (setup.ps1 -TcCalc)")
def test_pinned_pob_loads_the_active_spec_attribute():
    text = (_SRC / "Classes" / "TreeTab.lua").read_text(encoding="utf-8", errors="replace")
    assert re.search(r"SetActiveSpec\(\s*tonumber\(\s*xml\.attrib\.activeSpec\s*\)", text), (
        "PoB drift: TreeTab:Load no longer selects the spec named by <Tree activeSpec>; "
        "TC-SPEC-FOLLOW (decision 0088) relies on it for the calc")
