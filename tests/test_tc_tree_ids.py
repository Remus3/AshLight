"""DATA-TREE-IDS: PoB2 spec node ids are GGG tree export `skill` ids
(research 0015), so resolve() maps them 1:1; id_match() guards against a
spec from another id space.

Real-shaped synthetic data: the export below has the real key layout
(nodes keyed by the skill id as a string, `skill` int, `ascendancyId`,
classes[].ascendancies, a `root` pseudo node, 16-bit range ids) and the
PoB2 XML has the real Spec layout (treeVersion 0_5, comma-separated nodes).
Every id, name and stat is invented; no game or PoB2 data is copied
(decision 0009).
"""

import random

from server.al.theorycraft import model, treedata

EXPORT = {
    "tree": "Default",
    "classes": [
        {"name": "Synth Warrior", "ascendancies": [
            {"id": "SynthWarrior1", "name": "Synth Ascent One"},
            {"id": "SynthWarrior2", "name": "Synth Ascent Two"}]},
        {"name": "Synth Witch", "ascendancies": []},
    ],
    "nodes": {
        "root": {"group": 0, "orbit": 0, "out": ["47175"], "in": []},
        "47175": {"skill": 47175, "id": "synth_start_warrior",
                  "name": "SYNTH WARRIOR", "classStartIndex": [0], "stats": []},
        "4739": {"skill": 4739, "id": None, "name": "Synth Strength",
                 "stats": ["+8 to [Strength|Strength]"]},
        "29358": {"skill": 29358, "id": "synth_notable", "name": "Synth Notable",
                  "isNotable": True, "stats": ["12% increased Synth Damage"]},
        "61834": {"skill": 61834, "name": "Synth Keystone", "isKeystone": True,
                  "stats": ["Synth keystone effect"]},
        "50986": {"skill": 50986, "name": "Synth Ascent Start",
                  "ascendancyId": "SynthWarrior2", "isAscendancyStart": True,
                  "stats": []},
        "8045": {"skill": 8045, "name": "Synth Ascent Notable",
                 "ascendancyId": "SynthWarrior2", "isNotable": True,
                 "stats": ["Synth ascendancy effect"]},
        "65120": {"skill": 65120, "name": "", "stats": []},
    },
}

SPEC_IDS = (47175, 4739, 29358, 61834, 50986, 8045)


def _xml(nodes):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<PathOfBuilding2>\n'
            '\t<Build level="70" targetVersion="0_5" className="Synth Warrior"'
            ' ascendClassName="Synth Ascent Two"/>\n'
            '\t<Tree activeSpec="1">\n'
            '\t\t<Spec title="Synth" treeVersion="0_5" classId="1"'
            ' ascendClassId="2" nodes="' + ",".join(str(n) for n in nodes) + '">\n'
            '\t\t\t<URL>https://example.org/tree/synth</URL>\n'
            '\t\t</Spec>\n'
            '\t</Tree>\n'
            '</PathOfBuilding2>\n')


def test_spec_ids_resolve_to_export_skill_ids_one_to_one():
    tree = treedata.parse(EXPORT)
    spec = model.parse(_xml(SPEC_IDS)).active_spec
    assert spec.nodes == SPEC_IDS and spec.tree_version == "0_5"
    out = tree.resolve(spec.nodes)
    assert [r["id"] for r in out] == list(SPEC_IDS)  # no remap, order kept
    by_id = {r["id"]: r for r in out}
    assert by_id[4739]["name"] == "Synth Strength"
    assert by_id[29358]["notable"] and by_id[61834]["keystone"]
    assert by_id[8045]["ascendancy"] == "Synth Ascent Two"
    assert by_id[47175]["name"] == "SYNTH WARRIOR"
    # every resolved id is the export node's own `skill` value
    for nid in SPEC_IDS:
        assert EXPORT["nodes"][str(nid)]["skill"] == nid == tree.node(nid).id


def test_build_view_carries_match_and_names_for_same_id_space():
    tree = treedata.parse(EXPORT)
    view = model.parse(_xml(SPEC_IDS)).to_dict(tree)["tree"]
    assert view["tree_match"] == {"known": 6, "total": 6, "ok": True}
    assert [r["name"] for r in view["named_nodes"]][:3] == [
        "SYNTH WARRIOR", "Synth Strength", "Synth Notable"]


def test_version_drift_still_ok_and_unknown_reads_none():
    tree = treedata.parse(EXPORT)
    ids = SPEC_IDS + (12345,)  # one node removed in a newer tree
    view = model.parse(_xml(ids)).to_dict(tree)["tree"]
    assert view["tree_match"] == {"known": 6, "total": 7, "ok": True}
    assert view["named_nodes"][-1] == {"id": 12345, "name": None,
                                       "ascendancy": None, "notable": False,
                                       "keystone": False}


def test_guard_trips_on_a_different_id_space():
    tree = treedata.parse(EXPORT)
    # dense row indexes, as a tool keyed by table row would emit
    foreign = tuple(range(1, 41))
    m = tree.id_match(foreign)
    assert m == {"known": 0, "total": 40, "ok": False}
    view = model.parse(_xml(foreign)).to_dict(tree)["tree"]
    assert view["tree_match"]["ok"] is False and "named_nodes" not in view
    assert view["nodes"] == list(foreign)  # raw ids still shown


def test_random_ids_in_a_large_tree_fall_below_threshold():
    rng = random.Random(15)
    nodes = {str(i): {"skill": i, "name": f"Synth {i}"}
             for i in rng.sample(range(1, 65536), 5000)}
    tree = treedata.parse({"nodes": nodes})
    real = [int(k) for k in list(nodes)[:100]]
    assert tree.id_match(real)["ok"]
    foreign = [i for i in rng.sample(range(1, 65536), 100)]
    m = tree.id_match(foreign)
    assert not m["ok"] and m["known"] < 25


def test_id_match_edges():
    tree = treedata.parse(EXPORT)
    assert tree.id_match([]) == {"known": 0, "total": 0, "ok": True}
    assert tree.id_match(None)["ok"]
    assert tree.id_match(["4739", "bad", True]) == {"known": 1, "total": 1,
                                                    "ok": True}
    assert tree.id_match([4739, 1]) == {"known": 1, "total": 2, "ok": True}
    assert treedata.MIN_ID_MATCH == 0.5
