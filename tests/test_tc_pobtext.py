"""ITEM-INFO-POB-TEXT (decision 0083 point 3, amends the decision 0037
amendment): where-found rows for the item info popover from the
hash-pinned PoB-PoE2 checkout's Uniques Source lines and WorldAreas.lua,
read as text (never run as Lua), only while the checkout marker names the
pinned archive and each file matches its pob2_files sha256.

Every checkout here is synthetic, written into tmp_path for this test
(shape only, not PoB's text); the real pinned checkout is guarded by
tests/test_tc_pob_drift_guard.py. No network, no process.
"""

import hashlib
import json

import pytest

from server.al import iteminfo
from server.al.theorycraft import pobtext

ARCHIVE = "a" * 64
TOP = "PoB-Top-1"

BELT = """-- Item data (c) Grinding Gear Games

return {
-- Belt
[[
Clasp One
Plate Belt
Source: No longer obtainable
Variant: Pre 0.1.1
Implicits: 1
+(100-140) to Armour
]],[[
Clasp Two
Utility Belt
Source: Drops from unique{The Mist King} in normal{Crux Zone}
Implicits: 1
Has (1-3) Charm Slot
]],[[
Clasp Three
Heavy Belt
Implicits: 1
+(40-60) to maximum Life
]],[[
Clasp Four
Wide Belt
Source: Drops from unique{Lone Boss}
Source: Drops from unique{Lone Boss}
Source: Found in a strange way
]],
}
"""

RING = """return {
[[
Clasp Two
Ruby Ring
Source: Drops from unique{Second Boss} in normal{Domain Zone}
]],[[
Odd {Name}
Ruby Ring
Source: Drops from unique{Bad Boss
]],
}
"""

AREAS = """local worldAreas, _ = ...

worldAreas["CruxA"] = {
\tname = "Crux Zone (Map)",
\tbaseName = "Crux Zone",
\tact = 10,
\tisMap = true,
}

worldAreas["DomainA"] = {
\tname = "Domain Zone",
\tbaseName = "Domain Zone",
\tact = 10,
\tisMap = false,
}

worldAreas["MixedA"] = {
\tname = "Mixed Zone (Act 1)",
\tbaseName = "Mixed Zone",
\tisMap = false,
}

worldAreas["MixedB"] = {
\tname = "Mixed Zone (Map)",
\tbaseName = "Mixed Zone",
\tisMap = true,
}
"""

FILES = {
    "src/Data/Uniques/belt.lua": BELT,
    "src/Data/Uniques/ring.lua": RING,
    "src/Data/WorldAreas.lua": AREAS,
}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_checkout(tmp_path, files=FILES, archive=ARCHIVE, pin_over=None):
    """(pins path, checkout root) of a synthetic pinned checkout."""
    root = tmp_path / "cache" / TOP
    for rel, text in files.items():
        p = root.joinpath(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
    (root / pobtext.MARKER).write_text(json.dumps({"archive_sha256": archive}),
                                       encoding="ascii")
    pins = {"pob2": {"top_dir": TOP, "archive_sha256": ARCHIVE},
            "pob2_files": {"_doc": "x"}}
    for rel, text in files.items():
        pins["pob2_files"][rel] = {"sha256": sha(text), "size": len(text), "commit": "c"}
    pins["pob2_files"].update(pin_over or {})
    pins_path = tmp_path / "tc_pins.json"
    pins_path.write_text(json.dumps(pins), encoding="ascii")
    return pins_path, root


def test_parse_uniques_reads_only_source_lines():
    out = pobtext.parse_uniques(BELT)
    assert set(out) == {"clasp one", "clasp two", "clasp four"}
    assert out["clasp one"] == {"name": "Clasp One", "drops": [],
                                "no_longer_obtainable": True}
    assert out["clasp two"]["drops"] == [{"boss": "The Mist King", "zone": "Crux Zone"}]
    # a repeated line is one row; unknown Source wording is skipped, not guessed
    assert out["clasp four"] == {"name": "Clasp Four", "drops": [{"boss": "Lone Boss"}]}


def test_parse_uniques_skips_bad_names_and_lines():
    out = pobtext.parse_uniques(RING)
    assert set(out) == {"clasp two"}
    assert pobtext.parse_uniques(None) == {}
    assert pobtext.parse_uniques("[[\n" + "x\n" * (pobtext.MAX_LINES + 2) + "]]") == {}
    crlf = BELT.replace("\n", "\r\n")
    assert pobtext.parse_uniques(crlf) == pobtext.parse_uniques(BELT)


def test_parse_world_areas_map_flag():
    areas = pobtext.parse_world_areas(AREAS)
    assert areas["crux zone"] is True
    assert areas["crux zone (map)"] is True
    assert areas["domain zone"] is False
    assert areas["mixed zone"] is None   # areas disagree: no flag
    assert pobtext.parse_world_areas(42) == {}


def test_load_and_lookup_merge_files(tmp_path):
    pins_path, root = make_checkout(tmp_path)
    wf = pobtext.WhereFound(pins_path=pins_path, root=root)
    idx = wf.get()
    assert idx["files"] == sorted(FILES)
    assert wf.lookup("clasp two") == {"drops": [
        {"boss": "The Mist King", "zone": "Crux Zone", "map": True},
        {"boss": "Second Boss", "zone": "Domain Zone", "map": False}]}
    assert wf.lookup("clasp one") == {"drops": [], "no_longer_obtainable": True}
    assert wf.lookup("clasp three") is None
    assert wf.lookup("nothing") is None


def test_hash_mismatch_omits_only_that_file(tmp_path):
    pins_path, root = make_checkout(tmp_path, pin_over={
        "src/Data/Uniques/ring.lua": {"sha256": "b" * 64}})
    wf = pobtext.WhereFound(pins_path=pins_path, root=root)
    assert wf.get()["files"] == ["src/Data/Uniques/belt.lua", "src/Data/WorldAreas.lua"]
    assert wf.lookup("clasp two") == {"drops": [
        {"boss": "The Mist King", "zone": "Crux Zone", "map": True}]}


def test_world_areas_mismatch_drops_only_the_map_flag(tmp_path):
    pins_path, root = make_checkout(tmp_path, pin_over={
        "src/Data/WorldAreas.lua": {"sha256": "c" * 64}})
    wf = pobtext.WhereFound(pins_path=pins_path, root=root)
    assert wf.lookup("clasp two")["drops"][0] == {"boss": "The Mist King",
                                                  "zone": "Crux Zone"}


def test_unpinned_file_is_never_read(tmp_path):
    files = dict(FILES)
    pins_path, root = make_checkout(tmp_path, files=files)
    pins = json.loads(pins_path.read_text(encoding="ascii"))
    del pins["pob2_files"]["src/Data/Uniques/belt.lua"]
    pins["pob2_files"]["../escape.lua"] = {"sha256": "d" * 64}
    pins["pob2_files"]["src/Data/Uniques/Special/Generated.lua"] = {"sha256": "d" * 64}
    pins_path.write_text(json.dumps(pins), encoding="ascii")
    assert [r for r, _ in pobtext.pinned_files(pins)] == [
        "src/Data/Uniques/ring.lua", "src/Data/WorldAreas.lua"]
    wf = pobtext.WhereFound(pins_path=pins_path, root=root)
    assert wf.lookup("clasp one") is None


def test_wrong_marker_reads_nothing(tmp_path):
    pins_path, root = make_checkout(tmp_path, archive="e" * 64)
    wf = pobtext.WhereFound(pins_path=pins_path, root=root)
    assert wf.get() == {"uniques": {}, "areas": {}, "files": []}
    (root / pobtext.MARKER).unlink()
    assert pobtext.load(root, json.loads(pins_path.read_text("ascii")))["files"] == []


def test_missing_checkout_or_pins_reads_nothing(tmp_path):
    wf = pobtext.WhereFound(pins_path=tmp_path / "none.json", root=tmp_path / "none")
    assert wf.lookup("clasp one") is None
    pins_path, _ = make_checkout(tmp_path)
    wf = pobtext.WhereFound(pins_path=pins_path, root=tmp_path / "gone")
    assert wf.lookup("clasp one") is None


def test_parsed_once_per_pin(tmp_path, monkeypatch):
    pins_path, root = make_checkout(tmp_path)
    calls = []
    real = pobtext.load
    monkeypatch.setattr(pobtext, "load", lambda r, p: calls.append(1) or real(r, p))
    wf = pobtext.WhereFound(pins_path=pins_path, root=root)
    for _ in range(5):
        wf.lookup("clasp two")
    assert len(calls) == 1
    # a rewrite with the same pin values re-reads the pin file, not the checkout
    pins_path.write_text(pins_path.read_text("ascii") + " ", encoding="ascii")
    import os
    st = pins_path.stat()
    os.utime(pins_path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    wf.lookup("clasp two")
    assert len(calls) == 1
    # a moved pin is parsed again
    pins = json.loads(pins_path.read_text("ascii"))
    pins["pob2_files"]["src/Data/Uniques/ring.lua"]["sha256"] = "f" * 64
    pins_path.write_text(json.dumps(pins), encoding="ascii")
    os.utime(pins_path, ns=(st.st_atime_ns, st.st_mtime_ns + 20_000_000))
    assert wf.lookup("clasp two")["drops"] == [
        {"boss": "The Mist King", "zone": "Crux Zone", "map": True}]
    assert len(calls) == 2


def test_checkout_root_refuses_odd_top_dir(tmp_path):
    env = {"AL_SIDECAR_ROOT": str(tmp_path)}
    assert pobtext.checkout_root({"pob2": {"top_dir": "../x"}}, env) is None
    assert pobtext.checkout_root({"pob2": {"top_dir": "a/b"}}, env) is None
    assert pobtext.checkout_root({}, env) is None
    assert pobtext.checkout_root({"pob2": {"top_dir": TOP}}, env).name == TOP


def test_never_runs_lua_or_opens_a_process():
    src = (pobtext.__file__)
    text = open(src, encoding="utf-8").read()
    for word in ("subprocess", "luajit", "socket", "urllib", "os.system", "eval(", "exec("):
        assert word not in text, word


# --- the popover lookup ---------------------------------------------------

def _info(tmp_path, pob):
    bases = tmp_path / "gamedata" / "base_items.json"
    bases.parent.mkdir(parents=True, exist_ok=True)
    bases.write_text(json.dumps({}), encoding="utf-8")
    uniques = bases.with_name(iteminfo.UNIQUES_NAME)
    uniques.write_text(json.dumps({"x": {"name": "Clasp Two", "item_class": "Belt"}}),
                       encoding="utf-8")
    return iteminfo.ItemInfo(bases, uniques, pob=pob)


def test_lookup_adds_where_found_and_credits_pob(tmp_path):
    pins_path, root = make_checkout(tmp_path)
    info = _info(tmp_path, pobtext.WhereFound(pins_path=pins_path, root=root))
    reply = info.lookup("clasp  two")
    assert reply["name"] == "Clasp Two"
    assert reply["fields"]["rarity"] == "Unique"
    assert reply["fields"]["where_found"]["drops"][0]["boss"] == "The Mist King"
    assert reply["sources"] == [iteminfo.REPOE, pobtext.SOURCE_ID]
    # PoB alone gives where_found only: no rarity, no class, the asked name
    only = info.lookup("Clasp One")
    assert only == {"name": "Clasp One",
                    "fields": {"where_found": {"drops": [], "no_longer_obtainable": True}},
                    "sources": [pobtext.SOURCE_ID]}


def test_lookup_without_checkout_has_no_where_found(tmp_path):
    info = _info(tmp_path, None)
    reply = info.lookup("Clasp Two")
    assert "where_found" not in reply["fields"]
    assert reply["sources"] == [iteminfo.REPOE]


class _Boom:
    def lookup(self, k):
        raise RuntimeError("bad")


def test_failing_reader_omits_the_field(tmp_path):
    assert "where_found" not in _info(tmp_path, _Boom()).lookup("Clasp Two")["fields"]


def test_auto_reads_checkout_only_for_the_default_base_path(tmp_path, monkeypatch):
    # a test runtime's base list: no reader at all
    assert iteminfo.auto_pob(tmp_path / "gamedata" / "base_items.json") is None
    info = iteminfo.ItemInfo(tmp_path / "b.json", tmp_path / "u.json")
    assert info.pob is None
    # the core's default path: a WhereFound over the tracked pins
    monkeypatch.setattr(iteminfo, "_default_bases_path", lambda: tmp_path / "b.json")
    wf = iteminfo.auto_pob(tmp_path / "b.json")
    assert isinstance(wf, pobtext.WhereFound)


@pytest.mark.parametrize("rel", ["src/Data/WorldAreas.lua", "src/Data/Uniques/belt.lua"])
def test_tracked_pins_carry_the_parsed_files(rel):
    from server.al import paths
    pins = json.loads(paths.tc_pins_file().read_text(encoding="ascii"))
    rels = [r for r, _ in pobtext.pinned_files(pins)]
    assert rel in rels
    assert pins["pob2_files"][rel]["commit"] == pins["pob2"]["commit"]


# --- DATA-AUGMENT-POB-TEXT (decision 0091): ModRunes.lua augment rows -----
# A synthetic file of the same line shape (own words, not PoB's text).

T = "\t"
RUNES = "\n".join([
    "-- This file is automatically generated, do not edit!",
    "-- Item data (c) Grinding Gear Games",
    "",
    "return {",
    T + '["Test Rune of Sparks"] = {',
    T * 2 + '["helmet"] = {',
    T * 4 + 'type = "Rune",',
    T * 4 + '"+10 to Test Stat",',
    T * 4 + "statOrder = { 101 },",
    T * 4 + 'tradeHashes = { [111] = { "+10 to Test Stat" },  },',
    T * 4 + "isSocketBound = false,",
    T * 4 + "rank = { 50 },",
    T * 2 + "},",
    T * 2 + '["one hand mace"] = {',
    T * 4 + 'type = "Rune",',
    T * 4 + '"Test line one of",',
    T * 4 + '" a two line stat",',
    T * 4 + "statOrder = { 202, 202.1 },",
    T * 4 + 'tradeHashes = { [222] = { "Test line one of", " a two line stat" }, '
             '[333] = { "" },  },',
    T * 4 + "isSocketBound = true,",
    T * 4 + "rank = { 0 },",
    T * 2 + "},",
    T * 2 + '["gloves"] = {',            # tradeHashes missing: this slot drops
    T * 4 + 'type = "Rune",',
    T * 4 + '"+1 to Gloves Stat",',
    T * 4 + "statOrder = { 7 },",
    T * 4 + "isSocketBound = false,",
    T * 4 + "rank = { 50 },",
    T * 2 + "},",
    T + "},",
    T + '["Odd Core"] = {',               # an unknown line: its one slot drops
    T * 2 + '["boots"] = {',
    T * 4 + 'type = "SoulCore",',
    T * 4 + '"5% test speed",',
    T * 4 + "statOrder = { 9 },",
    T * 4 + 'tradeHashes = { [9] = { "5% test speed" },  },',
    T * 4 + "isSocketBound = false,",
    T * 4 + "rank = { 50 },",
    T * 4 + "value = function() return 1 end,",
    T * 2 + "},",
    T + "},",
    T + '["Twice Idol"] = {',
    T * 2 + '["armour"] = {',
    T * 4 + 'type = "Idol",',
    T * 4 + '"1% test",',
    T * 4 + "statOrder = { 1 },",
    T * 4 + 'tradeHashes = { [1] = { "1% test" },  },',
    T * 4 + "isSocketBound = false,",
    T * 4 + "rank = { 1 },",
    T * 2 + "},",
    T + "},",
    T + '["Twice Idol"] = {',               # a name given twice: both drop
    T * 2 + '["armour"] = {',
    T * 4 + 'type = "Idol",',
    T * 4 + '"2% test",',
    T * 4 + "statOrder = { 2 },",
    T * 4 + 'tradeHashes = { [2] = { "2% test" },  },',
    T * 4 + "isSocketBound = false,",
    T * 4 + "rank = { 2 },",
    T * 2 + "},",
    T + "},",
    "}",
    ""])


def test_parse_augments_fixture_shape():
    idx = pobtext.parse_augments(RUNES)
    assert sorted(idx) == ["test rune of sparks"]
    entry = idx["test rune of sparks"]
    assert entry["name"] == "Test Rune of Sparks"
    assert list(entry["slots"]) == ["helmet", "one hand mace"]
    assert entry["slots"]["helmet"] == {
        "type": "Rune", "lines": ["+10 to Test Stat"], "statOrder": [101],
        "tradeHashes": [{"hash": 111, "lines": ["+10 to Test Stat"]}],
        "isSocketBound": False, "rank": [50]}
    mace = entry["slots"]["one hand mace"]
    assert mace["lines"] == ["Test line one of", " a two line stat"]
    assert mace["statOrder"] == [202, 202.1]
    assert mace["tradeHashes"] == [
        {"hash": 222, "lines": ["Test line one of", " a two line stat"]},
        {"hash": 333, "lines": []}]
    assert mace["isSocketBound"] is True and mace["rank"] == [0]
    assert pobtext.parse_augments(None) == {}
    assert pobtext.parse_augments("\n" * (pobtext.MAX_LINES + 1)) == {}


def test_parse_augments_drops_an_unclosed_block():
    cut = RUNES.replace(T * 2 + "},\n" + T + "},\n" + T + '["Odd Core"]',
                        T + '["Odd Core"]', 1)
    assert cut != RUNES
    assert "test rune of sparks" not in pobtext.parse_augments(cut)


def _aug_checkout(tmp_path, archive=ARCHIVE):
    return make_checkout(tmp_path, files={pobtext.AUGMENTS: RUNES}, archive=archive)


def test_load_augments_reads_the_pinned_file(tmp_path):
    pins_path, root = _aug_checkout(tmp_path)
    pins = json.loads(pins_path.read_text("ascii"))
    assert list(pobtext.load_augments(root, pins)) == ["test rune of sparks"]
    assert pobtext.Augments(pins_path=pins_path, root=root).get() == \
        pobtext.parse_augments(RUNES)
    # the where-found reader never reads it
    assert pobtext.AUGMENTS not in [r for r, _ in pobtext.pinned_files(pins)]


def test_load_augments_sha_mismatch_gives_empty(tmp_path):
    pins_path, root = _aug_checkout(tmp_path)
    pins = json.loads(pins_path.read_text("ascii"))
    pins["pob2_files"][pobtext.AUGMENTS]["sha256"] = "f" * 64
    assert pobtext.load_augments(root, pins) == {}
    pins["pob2_files"][pobtext.AUGMENTS]["sha256"] = "not hex"
    assert pobtext.load_augments(root, pins) == {}
    del pins["pob2_files"][pobtext.AUGMENTS]
    assert pobtext.load_augments(root, pins) == {}
    assert pobtext.load_augments(root, None) == {}


def test_load_augments_wrong_marker_gives_empty(tmp_path):
    pins_path, root = _aug_checkout(tmp_path, archive="e" * 64)
    assert pobtext.load_augments(root, json.loads(pins_path.read_text("ascii"))) == {}


def test_load_augments_missing_file_gives_empty(tmp_path):
    pins_path, root = _aug_checkout(tmp_path)
    pins = json.loads(pins_path.read_text("ascii"))
    root.joinpath(*pobtext.AUGMENTS.split("/")).unlink()
    assert pobtext.load_augments(root, pins) == {}
    assert pobtext.load_augments(tmp_path / "none", pins) == {}
    assert pobtext.Augments(pins_path=tmp_path / "none.json", root=root).get() == {}


def test_load_augments_caps_the_file(tmp_path, monkeypatch):
    pins_path, root = _aug_checkout(tmp_path)
    pins = json.loads(pins_path.read_text("ascii"))
    assert pobtext.AUGMENTS_MAX_BYTES == 1024 * 1024
    monkeypatch.setattr(pobtext, "AUGMENTS_MAX_BYTES", len(RUNES) - 1)
    assert pobtext.load_augments(root, pins) == {}


def test_augments_parsed_once_per_pin(tmp_path, monkeypatch):
    import os
    pins_path, root = _aug_checkout(tmp_path)
    calls = []
    real = pobtext.load_augments
    monkeypatch.setattr(pobtext.Augments, "LOAD",
                        staticmethod(lambda r, p: calls.append(1) or real(r, p)))
    a = pobtext.Augments(pins_path=pins_path, root=root)
    for _ in range(4):
        assert a.get()
    assert len(calls) == 1
    st = pins_path.stat()
    pins_path.write_text(pins_path.read_text("ascii") + " ", encoding="ascii")
    os.utime(pins_path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    a.get()
    assert len(calls) == 1
    pins = json.loads(pins_path.read_text("ascii"))
    pins["pob2_files"][pobtext.AUGMENTS]["sha256"] = "f" * 64
    pins_path.write_text(json.dumps(pins), encoding="ascii")
    os.utime(pins_path, ns=(st.st_atime_ns, st.st_mtime_ns + 20_000_000))
    assert a.get() == {}
    assert len(calls) == 2


def test_augments_parse_runs_nothing(monkeypatch):
    import builtins
    import subprocess

    def boom(*a, **k):
        raise AssertionError("ran something")

    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(builtins, "exec", boom)
    monkeypatch.setattr(builtins, "eval", boom)
    monkeypatch.setattr(builtins, "compile", boom)
    assert pobtext.parse_augments(RUNES)
    src = open(pobtext.__file__, encoding="utf-8").read()
    for word in ("subprocess", "luajit", "loadstring", "eval(", "exec("):
        assert word not in src, word


def test_real_pinned_mod_runes_gives_287_augments():
    from server.al import paths
    pins = json.loads(paths.tc_pins_file().read_text(encoding="ascii"))
    root = pobtext.checkout_root(pins)
    if root is None or not root.joinpath(*pobtext.AUGMENTS.split("/")).is_file():
        pytest.skip("pinned PoB checkout absent (setup.ps1 -TcCalc)")
    idx = pobtext.load_augments(root, pins)
    assert len(idx) == 287, "ModRunes.lua misses its pob2_files sha256 or the marker"
    assert sum(len(e["slots"]) for e in idx.values()) == 570
