"""BUILD-LIVE (decision 0045): one build per character, swapped live with
the character the player's own Client.txt names; stale-build alert;
upgrade notices for items checked earlier; pluggable build sources (the
ggg_api stub never makes a request); hot reload of the build files.

Synthetic names and items only; tmp runtimes only."""

import ast
import os
import time
from pathlib import Path

import pytest

from server.al import state as state_mod
from server.al.core import Core
from server.al.theorycraft import buildlive, codec, providers, store
from server.al.theorycraft import weights as weights_mod
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML
from tc_fixtures import FULL_XML, MINIMAL_XML

ROOT = Path(__file__).resolve().parents[1]
RANGER = codec.encode(EVAL_BUILD_XML)   # Ranger, level 80
WARRIOR = codec.encode(MINIMAL_XML)     # Warrior
MONK = codec.encode(FULL_XML)           # Monk


def lvl(name, cls, n, at=1.0):
    return {"type": "level_up", "character": name, "class": cls, "level": n,
            "recv_ts": at}


def opened(at):
    return {"type": "log_opened", "recv_ts": at}


# -- file names

@pytest.mark.parametrize("name", ["Sable", "sable", "Quill_2", "\u00c9lise", "a-b c"])
def test_slug_round_trip(name):
    s = store.slug(name)
    assert s.isascii() and "/" not in s and "\\" not in s
    assert store.name_of(s) == name


def test_slug_keeps_case_apart_and_rejects_foreign_stems():
    assert store.slug("Sable").lower() != store.slug("sable").lower()
    assert store.name_of("c-Sable-00000000") is None
    assert store.name_of("x-zz") is None
    assert store.name_of("last-code") is None


# -- per-character store

def test_store_migrates_legacy_code_to_first_character(tmp_path):
    legacy = tmp_path / "build" / "last-code.txt"
    legacy.parent.mkdir()
    legacy.write_text(RANGER + "\n", encoding="ascii")
    s = store.BuildStore(legacy, per_character=True)
    assert s.build.class_name == "Ranger" and s.character is None
    assert s.sync("Sable") == "switch"
    assert s.character == "Sable" and s.build.class_name == "Ranger"
    assert not legacy.exists()
    assert (legacy.parent / "last-code.txt.migrated").exists()
    assert s.active_path().read_text(encoding="ascii").strip() == RANGER
    # a second character has no build of its own
    assert s.sync("Quill") == "switch"
    assert s.build is None and s.load_error is None
    assert s.characters_with_builds() == ["Sable"]


def test_store_swaps_builds_and_fires_listeners(tmp_path):
    s = store.BuildStore(tmp_path / "build" / "last-code.txt", per_character=True)
    seen = []
    s.add_listener(lambda b: seen.append(b.class_name if b else None))
    s.sync("Sable")
    s.load_code(RANGER)
    s.sync("Quill")
    s.load_code(MONK)
    assert s.sync("Sable") == "switch" and s.build.class_name == "Ranger"
    assert s.sync("Sable") is None  # nothing changed
    assert s.sync(None) is None     # an unknown character keeps the build
    assert seen == [None, "Ranger", None, "Monk", "Ranger"]
    assert sorted(s.characters_with_builds()) == ["Quill", "Sable"]
    snap = s.snapshot()
    assert snap["character"] == "Sable" and snap["source"] == "paste"
    # a new store comes back with the character played last
    again = store.BuildStore(tmp_path / "build" / "last-code.txt", per_character=True)
    assert again.character == "Sable" and again.build.class_name == "Ranger"


def test_store_without_per_character_ignores_names(tmp_path):
    s = store.BuildStore(tmp_path / "last-code.txt")
    s.load_code(RANGER)
    assert s.sync("Sable") is None
    assert s.active_path() == tmp_path / "last-code.txt"


def test_hot_reload_applies_a_new_file_and_keeps_a_good_build(tmp_path):
    s = store.BuildStore(tmp_path / "build" / "last-code.txt", per_character=True)
    s.sync("Sable")
    s.load_code(RANGER)
    seen = []
    s.add_listener(lambda b: seen.append(b.class_name))
    path = s.active_path()
    assert s.sync() is None  # its own write is not a change
    path.write_text(WARRIOR + "\n", encoding="ascii")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert s.sync() == "reload" and s.build.class_name == "Warrior"
    # a broken file never replaces the good build
    path.write_text("garbage !!\n", encoding="ascii")
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 9_000_000_000))
    assert s.sync() is None
    assert s.build.class_name == "Warrior" and s.load_error
    assert seen == ["Warrior"]
    # a dropped character JSON or code for the legacy file works the same
    legacy = store.BuildStore(tmp_path / "other" / "last-code.txt")
    legacy.path.parent.mkdir()
    legacy.path.write_text(MONK, encoding="ascii")
    assert legacy.sync() == "reload" and legacy.build.class_name == "Monk"


def test_core_tick_follows_the_log_character(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    try:
        core.state.apply(lvl("Sable", "Ranger", 30))
        assert core.tick_build() == "switch"
        alert = core.state.snapshot()["build_alert"]
        assert alert["kind"] == "missing"
        assert alert["text"] == ("No build saved for Sable yet. Paste a PoB code on the "
                                 "Build tab, or copy the code in Path of Building and "
                                 "press the item key.")
        assert alert["short"] == "No build for Sable"
        core.builds.load_code(RANGER)
        snap = core.state.snapshot()
        assert snap["build"]["character"] == "Sable" and snap["build_alert"] is None
        core.eval_press(ADVANCED_RING)
        assert core.state.snapshot()["eval"]["verdict"] == "upgrade"
        # a game restart and another character's first level-up
        core.state.apply(opened(10.0))
        core.state.apply(lvl("Quill", "Monk", 12, 11.0))
        assert core.tick_build() == "switch"
        snap = core.state.snapshot()
        assert snap["build"]["loaded"] is False and snap["build"]["character"] == "Quill"
        assert snap["eval"]["error"] == "no build loaded"  # the card follows
        assert snap["upgrades"]["items"] == [] and snap["upgrades"]["checked"] == 0
        # back to Sable: her build and her checked items come back
        core.state.apply(opened(20.0))
        core.state.apply(lvl("Sable", "Ranger", 31, 21.0))
        assert core.tick_build() == "switch"
        snap = core.state.snapshot()
        assert snap["build"]["class_name"] == "Ranger"
        assert snap["upgrades"]["checked"] == 1
        assert snap["upgrades"]["items"][0]["slot"] in ("Ring 1", "Ring 2")
    finally:
        core.close()


# -- stale build alert

def info(cls="Ranger", asc=None, level=40, character="Sable", loaded=True):
    return {"loaded": loaded, "class_name": cls, "ascendancy": asc, "level": level,
            "character": character}


def test_class_fit_rules():
    assert buildlive.class_fits("Ranger", "Ranger", None) is True
    assert buildlive.class_fits("Deadeye", "Ranger", None) is True
    assert buildlive.class_fits("Deadeye", "Ranger", "Deadeye") is True
    assert buildlive.class_fits("Pathfinder", "Ranger", "Deadeye") is False
    assert buildlive.class_fits("Witch", "Ranger", None) is False
    assert buildlive.class_fits("Ranger", "Ranger", "Deadeye") is True  # not ascended yet
    assert buildlive.class_fits(None, "Ranger", None) is None
    assert buildlive.class_fits("NewClass", "NewClass", None) is True


def test_class_fit_follows_the_tree(tmp_path):
    """TC-ASC-FROM-TREE: a synthetic tree naming a new ascendancy makes
    class_fits (and the character JSON import) know its class with no code
    change; the built-in table stays the fallback and gains no name."""
    import json as json_mod
    from server.al.theorycraft import charjson, treedata
    doc = {"nodes": {}, "classes": [
        {"name": "Ranger", "ascendancies": [
            {"id": "Ranger9", "name": "Synthetic Skyrunner"}]},
        {"name": "Witch", "ascendancies": [
            {"id": "Witch9", "name": "Synthetic Hexer"}]}]}
    path = tmp_path / "skilltree.json"
    path.write_text(json_mod.dumps(doc), encoding="ascii")
    treedata.publish(None)
    try:
        assert buildlive.class_fits("Synthetic Skyrunner", "Ranger", None) is False
        assert treedata.TreeCache(path).get() is not None
        assert buildlive.class_fits("Synthetic Skyrunner", "Ranger", None) is True
        assert buildlive.class_fits("Synthetic Skyrunner", "Ranger",
                                    "Synthetic Skyrunner") is True
        assert buildlive.class_fits("Synthetic Skyrunner", "Ranger", "Deadeye") is False
        assert buildlive.class_fits("Synthetic Hexer", "Ranger", None) is False
        assert buildlive.class_fits("Deadeye", "Ranger", None) is True  # table fallback
        assert buildlive.class_fits("Pathfinder", "Ranger", "Deadeye") is False
        assert charjson._classes("Synthetic Hexer") == ("Witch", "Synthetic Hexer")
        assert charjson._classes("Lich") == ("Witch", "Lich")
        assert charjson._classes("Witch") == ("Witch", "None")
        assert "Synthetic Hexer" not in charjson.ASCENDANCY_CLASS
    finally:
        treedata.publish(None)


def test_alert_kinds_and_words():
    assert buildlive.alert(info(), "Sable", "Ranger", 44) is None
    assert buildlive.alert(info(level=90), "Sable", "Ranger", 51) is None  # planned ahead
    lv = buildlive.alert(info(level=42), "Sable", "Ranger", 51)
    assert lv == {"kind": "level", "character": "Sable", "build_level": 42, "level": 51}
    # TC-VERDICT-CAVEAT (F-042): every sentence names the item-key build load
    assert state_mod.build_alert_text(lv) == {
        "kind": "level", "head": "Build is from level 42",
        "short": "Build is from level 42",
        "text": ("Build is from level 42; you are level 51. Paste a fresh PoB code on "
                 "the Build tab, or copy the code in Path of Building and press the "
                 "item key.")}
    cl = buildlive.alert(info(), "Sable", "Witch", 40)
    assert cl["kind"] == "class"
    assert state_mod.build_alert_text(cl) == {
        "kind": "class", "head": "Build is for a Ranger", "short": "Build is for a Ranger",
        "text": ("Build is for a Ranger, but Sable is a Witch. Paste Sable's own PoB code "
                 "on the Build tab, or copy the code in Path of Building and press the "
                 "item key.")}
    inv = buildlive.alert(info(cls="Witch", asc="Infernalist"), "Sable", "Monk", 40)
    assert state_mod.build_alert_text(inv)["text"].startswith(
        "Build is for an Infernalist, but Sable is a Monk. ")
    assert state_mod.build_alert_text({"kind": "missing", "character": "Sable"}) == {
        "kind": "missing", "head": "No build saved for Sable yet",
        "short": "No build for Sable",
        "text": ("No build saved for Sable yet. Paste a PoB code on the Build tab, or "
                 "copy the code in Path of Building and press the item key.")}
    for words in (state_mod.build_alert_text(a) for a in (lv, cl, inv)):
        assert words["text"].endswith(
            "or copy the code in Path of Building and press the item key.")
    assert buildlive.alert(info(loaded=False), None, None, None) is None
    assert buildlive.alert(info(character="Quill"), "Sable", "Witch", 60) is None
    assert state_mod.build_alert_text(None) is None


def test_snapshot_publishes_the_alert():
    st = state_mod.SessionState()
    st.set_build_info(info(level=42, character="Sable"))
    st.apply(lvl("Sable", "Ranger", 51))
    a = st.snapshot()["build_alert"]
    assert a["kind"] == "level" and a["head"] == "Build is from level 42"


def test_snapshot_card_carries_alert_head():
    """TC-VERDICT-CAVEAT (F-043): a fresh item check under a build alert
    has the short head in card.line3 and the sentence in eval.text.notes;
    a fixed build clears both by itself, with no click."""
    now = [1000.0]
    st = state_mod.SessionState(clock=lambda: now[0])
    st.set_build_info(info(level=42, character="Sable"))
    st.apply(lvl("Sable", "Ranger", 51))
    ev = {"ok": True, "error": None, "verdict": "upgrade", "slot": "Ring 1",
          "score_delta": 12, "item": {"name": "Storm Loop"},
          "comparisons": [{"slot": "Ring 1", "verdict": "upgrade", "score_delta": 12,
                           "empty": False, "equipped": {"name": "Weak Loop"},
                           "stats": [{"key": "+# to maximum Life", "delta": 12,
                                      "score_delta": 12, "weighted": True}]}]}
    st.set_eval(ev)
    snap = st.snapshot()
    sentence = snap["build_alert"]["text"]
    assert snap["card"]["kind"] == "eval"
    assert (snap["card"]["head"], snap["card"]["line2"], snap["card"]["line3"]) == (
        "Upgrade +12 vs Ring 1", "Storm Loop", "Build is from level 42")
    assert snap["eval"]["text"]["line"] == "Build is from level 42"
    assert snap["eval"]["text"]["notes"] == [sentence]
    # a fresh build for this level clears the alert, the head and the note
    st.set_build_info(info(level=51, character="Sable"))
    snap = st.snapshot()
    assert snap["build_alert"] is None
    assert snap["card"]["line3"] == "+12 to maximum Life"
    assert snap["eval"]["text"]["line"] == "+12 to maximum Life"
    assert snap["eval"]["text"]["notes"] == []


# -- upgrade notices

def test_rescore_raises_new_upgrade_after_weights_change(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    try:
        core.state.apply(lvl("Sable", "Ranger", 30))
        core.tick_build()
        core.builds.load_code(RANGER)
        core.weights.put({"weights": {}})
        core.eval_press(ADVANCED_RING)
        snap = core.state.snapshot()
        assert snap["eval"]["verdict"] != "upgrade"
        assert snap["upgrades"]["items"] == []
        assert snap["upgrades"]["text"] == ""
        core.weights.put({"weights": dict(weights_mod.DEFAULT_WEIGHTS)})
        core.last_eval.rerun()
        up = core.state.snapshot()["upgrades"]
        assert up["new"] == 1 and up["text"] == "1 item you checked is an upgrade now."
        n = up["items"][0]
        assert n["new"] is True and n["slot"] in ("Ring 1", "Ring 2")
        assert n["replaces"] in ("Weak Loop", "Strong Loop")
        assert n["head"] == f"New upgrade for {n['slot']}: Storm Loop"
        assert n["line"].startswith(f"Replaces {n['replaces']}, +")
        # Sable is level 30; the ring needs level 40
        assert n["fit"] == "Needs level 40; you are level 30."
        # another re-score with nothing new: still an upgrade, no longer new
        core.last_eval.rerun()
        up = core.state.snapshot()["upgrades"]
        assert up["new"] == 0 and up["items"][0]["head"].startswith("Upgrade for ")
    finally:
        core.close()


def test_candidates_are_bounded_and_deduplicated():
    c = buildlive.Candidates()
    for i in range(buildlive.MAX_ITEMS + 5):
        c.add("Sable", f"item {i}", None, "upgrade", float(i))
    c.add("Sable", "item 14", None, "downgrade", 99.0)
    rows = c.rows("Sable")
    assert len(rows) == buildlive.MAX_ITEMS
    assert rows[-1]["text"] == "item 14" and rows[-1]["verdict"] == "downgrade"
    for i in range(buildlive.MAX_CHARACTERS + 3):
        c.add(f"C{i}", "x", None, None, 0.0)
    assert c.count("Sable") == 0  # the least recently used character dropped
    early = buildlive.Candidates()
    early.add(None, "before any name", None, "upgrade", 1.0)
    assert [r["text"] for r in early.rows("Sable")] == ["before any name"]


def test_notice_words():
    n = {"name": None, "base": "Example Ring", "slot": "Ring 1", "empty": True,
         "replaces": None, "score_delta": 2.5, "source": "pob_cached", "new": False,
         "fit": {"ok": True, "kind": "build", "build_class": "Deadeye"}}
    t = state_mod.upgrade_notice_text(n)
    assert t == {"head": "Upgrade for Ring 1: Example Ring",
                 "line": "Goes in your empty Ring 1 slot, +2.5%.",
                 "fit": "Fits your Deadeye build."}
    assert state_mod.upgrades_text({"items": [n, n]}) == (
        "2 items you checked are upgrades now.")


# -- providers

def test_ggg_api_provider_is_a_stub():
    p = providers.GggApiProvider()
    st = p.status()
    assert st["configured"] is False and st["scope"] == "account:characters"
    assert st["note"] == "Not set up. Paste a PoB code instead."
    with pytest.raises(providers.NotConfigured):
        p.fetch("Sable")
    assert providers.PasteProvider().status()["configured"] is True


def test_import_from_unset_provider_keeps_build(tmp_path):
    s = store.BuildStore(tmp_path / "last-code.txt", per_character=True)
    s.sync("Sable")
    s.load_code(RANGER)
    for name in ("ggg_api", "nope"):
        with pytest.raises(providers.NotConfigured):
            s.import_from(name)
    assert s.build.class_name == "Ranger"
    names = [p["name"] for p in s.snapshot()["providers"]]
    assert names == ["paste", "ggg_api"]


def test_provider_module_makes_no_request():
    """ToS floor / decision 0045: no network code in the build sources."""
    src = (ROOT / "server" / "al" / "theorycraft" / "providers.py").read_text(encoding="ascii")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {"urllib", "http", "socket", "ssl", "webfetch", "requests"}
    assert "http://" not in src and "https://" not in src


def test_snapshot_time_is_not_slowed_by_many_checks(tmp_path):
    st = state_mod.SessionState()
    st.set_upgrades({"character": "Sable", "checked": 10, "build_loaded": True,
                     "items": [{"name": "R", "slot": "Ring 1", "replaces": "Old",
                                "score_delta": 3, "source": "weights", "new": True,
                                "fit": {"ok": True, "build_class": "Ranger"}}] * 10})
    t0 = time.perf_counter()
    for _ in range(200):
        st.snapshot()
    assert time.perf_counter() - t0 < 2.0
