"""DATA-TREE-SRC: cached GGG PoE2 passive tree reader and its optional use in
the build view. Synthetic fixture only (tests/fixtures/skilltree_synthetic.json,
modelled on the documented export shape, UNVERIFIED); no network.
"""

import json
import shutil
from pathlib import Path

import pytest

from server.al import core as core_mod
from server.al.theorycraft import model, store, treedata

from tc_fixtures import FULL_XML

FIX = Path(__file__).resolve().parent / "fixtures" / "skilltree_synthetic.json"


@pytest.fixture
def tree():
    return treedata.load(FIX)


def test_reader_names_stats_and_flags(tree):
    assert tree.classes == ("Alpha Class", "Beta Class")
    assert tree.name(20) == "Test Small Node" and tree.name("30") == "Test Notable"
    n = tree.node(30)
    assert n.notable and not n.keystone and n.stats == ("10% increased Test Damage",)
    assert tree.node(40).keystone and tree.node(40).stats == ()
    asc = tree.node(50)
    assert asc.is_ascendancy and asc.ascendancy == "First Ascent"
    assert not tree.node(20).is_ascendancy
    assert tree.node(55).jewel_socket and tree.name(55) == "Keyed By Id Only"
    assert tree.node(999) is None and tree.name("x") is None
    assert set(tree.nodes) == {10, 11, 20, 30, 40, 50, 55}  # root / bad skipped
    assert json.loads(json.dumps(asc.to_dict()))["ascendancy"] == "First Ascent"


def test_class_starts_both_shapes(tree):
    assert tree.class_starts() == {"Alpha Class": 10, "Beta Class": 11}


def test_resolve_keeps_order_and_unknown_ids(tree):
    out = tree.resolve([10, 50, 77, "bad"])
    assert [r["id"] for r in out] == [10, 50, 77]
    assert out[0]["name"] == "Alpha Start" and out[1]["ascendancy"] == "First Ascent"
    assert out[2] == {"id": 77, "name": None, "ascendancy": None,
                      "notable": False, "keystone": False}


@pytest.mark.parametrize("doc", [[], {}, {"nodes": []}, "x"])
def test_parse_rejects_non_tree(doc):
    with pytest.raises(ValueError):
        treedata.parse(doc)


def test_parse_tolerates_missing_classes():
    t = treedata.parse({"nodes": {"1": {"name": "A", "classStartIndex": 4}}})
    assert t.name(1) == "A" and t.class_starts() == {}


def test_cache_missing_bad_then_present(tmp_path):
    p = tmp_path / "skilltree.json"
    c = treedata.TreeCache(p)
    assert c.get() is None and c.error is None
    p.write_text("not json", encoding="ascii")
    assert c.get() is None and c.error
    shutil.copyfile(FIX, p)
    import os
    os.utime(p, ns=(1, 2_000_000_000_000_000_000))
    t = c.get()
    assert t is not None and t.name(30) == "Test Notable"
    assert c.get() is t  # unchanged file is not re-read


def test_default_path_in_sidecar_cache(tmp_path):
    env = {"AL_SIDECAR_ROOT": str(tmp_path / "AL")}
    assert treedata.default_path(env) == (
        tmp_path / "AL" / "Cache" / "gamedata" / "skilltree.json").resolve()


def test_build_view_names_nodes_only_with_tree(tree):
    b = model.parse(FULL_XML)
    plain = b.to_dict()["tree"]
    assert "named_nodes" not in plain
    named = b.to_dict(tree)["tree"]
    assert {k: v for k, v in named.items() if k != "named_nodes"} == plain
    by_id = {r["id"]: r for r in named["named_nodes"]}
    assert by_id[30]["name"] == "Test Notable" and by_id[60]["name"] is None


def test_store_snapshot_with_and_without_cache(tmp_path):
    code = model.parse(FULL_XML).to_code()
    tp = tmp_path / "gamedata" / "skilltree.json"
    s = store.BuildStore(tmp_path / "last-code.txt", tree=treedata.TreeCache(tp))
    s.load_code(code)
    assert "named_nodes" not in s.snapshot()["build"]["tree"]
    tp.parent.mkdir(parents=True)
    shutil.copyfile(FIX, tp)
    names = [r["name"] for r in s.snapshot()["build"]["tree"]["named_nodes"]]
    assert "Test Keystone" in names
    assert store.BuildStore(tmp_path / "none.txt").snapshot()["loaded"] is False


def test_store_survives_broken_tree_holder(tmp_path):
    class Boom:
        def get(self):
            raise RuntimeError("boom")
    s = store.BuildStore(tmp_path / "c.txt", tree=Boom())
    s.load_code(model.parse(FULL_XML).to_code())
    assert s.snapshot()["build"]["tree"]["node_count"] == 6


def test_test_core_reads_tree_from_its_runtime_only(tmp_path):
    rt = tmp_path / "rt"
    core = core_mod.Core(runtime=rt, log_path=str(tmp_path / "Client.txt"), tail=False)
    assert core.builds.tree.path == rt / "gamedata" / "skilltree.json"
    assert core.builds.snapshot()["loaded"] is False
