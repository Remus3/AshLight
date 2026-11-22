"""TC-CAMPAIGN-KEEP (decision 0057): keep or vendor with no build loaded.

Fixture items at levels 10, 30 and 60 give the expected verdict and the
thresholds met, with the exact card words; a broken rule file keeps the
last good copy with a Checks note; every entry carries src and checked;
the boots band agrees with campaign.DEFAULT_BOOTS_LEVEL; a loaded build
gives no keep part; card lines fit 26 characters (CARD-LINE-LIMIT-COPY)."""

import json
import os

import pytest

from server.al import campaign, hotreload
from server.al.core import Core
from server.al.state import eval_card_text
from server.al.theorycraft import cardparts, codec, evaluate, item, levelrules, live
from server.al.theorycraft.cardparts import keep
from tc_eval_fixtures import EVAL_BUILD_XML


def gear(item_class, *mods, name="Test Piece", base="Plain Base"):
    lines = [f"Item Class: {item_class}", "Rarity: Rare", name, base, "--------",
             "Item Level: 40", "--------", *mods]
    return "\n".join(lines) + "\n"


GLOVES_10 = gear("Gloves", "+12 to maximum Life", "+9% to Fire Resistance")
RING_30 = gear("Rings", "+20 to maximum Life", "+13% to all Elemental Resistances")
HELMET_30 = gear("Helmets", "+30 to maximum Life", "10% increased Armour")
ARMOUR_60 = gear("Body Armours", "+70 to maximum Life", "+26% to Cold Resistance",
                 "+5% to Fire Resistance")
BOOTS_60 = gear("Boots", "+80 to maximum Life", "+30% to Fire Resistance")
FAST_BOOTS_60 = gear("Boots", "+80 to maximum Life", "+30% to Fire Resistance",
                     "15% increased Movement Speed")
BOOTS_10 = gear("Boots", "+8 to maximum Life", "+4% to Cold Resistance")
UNID = ("Item Class: Gloves\nRarity: Rare\nTest Piece\nPlain Base\n--------\n"
        "Item Level: 40\n--------\nUnidentified\n")


@pytest.fixture(autouse=True)
def fresh_parts():
    cardparts.reset()
    yield
    cardparts.reset()


def ctx_for(text, level, build=None):
    return {"text": text, "parsed": item.parse(text),
            "result": evaluate.evaluate(text, build, None), "build": build,
            "character": "Tester", "level": level, "area_id": None, "config": dict}


def card_for(text, level, build=None):
    ctx = ctx_for(text, level, build)
    card = live.compact(ctx["result"])
    card["parts"] = cardparts.compute(ctx)
    return card, eval_card_text(card)


# -- verdicts and exact words -------------------------------------------------

def test_level_10_gloves_keep():
    card, t = card_for(GLOVES_10, 10)
    assert card["parts"]["keep"] == {
        "status": "keep", "level": 10, "need": 1, "of": 5, "count": 2,
        "met": [{"label": "life", "min": 10, "have": 12},
                {"label": "fire res", "min": 8, "have": 9}],
        "missed": []}
    assert (t["word"], t["tone"], t["answers"]) == ("Keep", "upgrade", True)
    assert t["head"] == "Keep - 2 of 5 met, Lv 10"
    assert t["item"] == "Test Piece"
    assert t["line"] == "Load a build first"
    assert t["notes"] == [
        "Worth keeping: it meets 2 of 5 levelling thresholds for level 10.",
        "Thresholds met: life 10+, fire res 8+."]


def test_level_30_ring_keep_counts_all_elemental_for_each():
    _card, t = card_for(RING_30, 30)
    assert t["head"] == "Keep - 3 of 5 met, Lv 30"
    assert t["notes"] == [
        "Worth keeping: it meets 3 of 5 levelling thresholds for level 30.",
        "Thresholds met: fire res 12+, cold res 12+, lightning res 12+."]


def test_level_30_helmet_vendor():
    card, t = card_for(HELMET_30, 30)
    assert card["parts"]["keep"]["status"] == "vendor"
    assert (t["word"], t["tone"], t["answers"]) == ("Vendor", "note", True)
    assert t["head"] == "Vendor - 1 of 5 met, Lv 30"
    assert t["notes"] == [
        "Vendor: it meets 1 of 5 levelling thresholds for level 30, and 2 are needed.",
        "Thresholds met: life 25+."]


def test_level_60_armour_keep():
    _card, t = card_for(ARMOUR_60, 60)
    assert t["head"] == "Keep - 2 of 5 met, Lv 60"
    assert t["notes"] == [
        "Worth keeping: it meets 2 of 5 levelling thresholds for level 60.",
        "Thresholds met: life 65+, cold res 25+."]


def test_level_60_boots_without_speed_vendor():
    _card, t = card_for(BOOTS_60, 60)
    assert (t["word"], t["head"]) == ("Vendor", "Vendor - no move speed")
    assert t["notes"] == [
        "Vendor: it lacks move speed 10+, which this levelling rule needs at level 60.",
        "Thresholds met: life 65+, fire res 25+."]
    _card, t = card_for(FAST_BOOTS_60, 60)
    assert t["head"] == "Keep - 3 of 6 met, Lv 60"
    assert t["notes"][1] == "Thresholds met: life 65+, fire res 25+, move speed 10+."


def test_level_10_boots_have_no_speed_rule_and_none_met():
    _card, t = card_for(BOOTS_10, 10)
    assert t["head"] == "Vendor - 0 of 5 met, Lv 10"
    assert t["notes"] == [
        "Vendor: it meets 0 of 5 levelling thresholds for level 10, and 1 is needed."]


def test_missing_level_or_unidentified_names_the_input():
    card, t = card_for(GLOVES_10, None)
    assert card["parts"]["keep"] == {"status": "no_level"}
    assert (t["word"], t["head"], t["answers"]) == ("Not checked", "No build loaded", False)
    assert t["notes"] == ["Keep or vendor needs your character level from Client.txt."]
    card, t = card_for(UNID, 30)
    assert card["parts"]["keep"] == {"status": "unidentified"}
    assert t["notes"] == ["Keep or vendor needs the item identified first."]
    assert t["answers"] is False


def test_no_part_for_items_the_table_does_not_cover():
    flask = "Item Class: Life Flasks\nRarity: Normal\nSmall Life Flask\n--------\n"
    jewel = "Item Class: Jewels\nRarity: Rare\nX\nRuby\n--------\n+10 to maximum Life\n"
    for text in (flask, jewel, "not an item at all"):
        card, _t = card_for(text, 30)
        assert "keep" not in card["parts"]


# -- a loaded build -----------------------------------------------------------

def test_loaded_build_gives_no_keep_part():
    ctx = ctx_for(GLOVES_10, 30)
    ctx["build"] = object()
    assert keep.compute(ctx) is None
    ctx = ctx_for(GLOVES_10, 30)
    ctx["result"] = dict(ctx["result"], ok=True, error=None)
    assert keep.compute(ctx) is None


def test_press_with_and_without_build(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    try:
        core.state.level = 30
        core.last_eval.run(RING_30)
        ev = core.state.snapshot()["eval"]
        assert ev["error"] == "no build loaded"
        assert ev["parts"]["keep"]["status"] == "keep"
        assert ev["text"]["head"] == "Keep - 3 of 5 met, Lv 30"
        core.builds.load_code(codec.encode(EVAL_BUILD_XML))
        ev = core.state.snapshot()["eval"]
        assert ev["ok"] and "keep" not in ev["parts"]
        assert not ev["text"]["head"].startswith(("Keep", "Vendor"))
    finally:
        core.close()


# -- card line lengths --------------------------------------------------------

def test_card_lines_fit_26():
    """CARD-LINE-LIMIT-COPY: the head fits 26 at every level and count (HEAD_MAX
    stays 34 until CARD-LINE-LIMIT-FLIP); level 100 with a word Vendor drops
    the level, never the count."""
    assert keep.HEAD_MAX == 34 and keep.HEAD_FIT == 26
    for level in range(1, 101):
        for status in ("keep", "vendor"):
            for of in range(1, 7):
                value = {"status": status, "level": level, "need": 2, "of": of,
                         "count": of, "met": [], "missed": []}
                h = keep.head(value)
                assert len(h) <= 26 and f"{of} of {of} met" in h, h
    value = {"status": "vendor", "level": 100, "need": 2, "of": 6, "count": 0,
             "met": [], "missed": []}
    assert keep.head(value) == "Vendor - 0 of 6 met"
    value["status"], value["count"] = "keep", 6
    assert keep.head(value) == "Keep - 6 of 6 met, Lv 100"
    for text, level in ((GLOVES_10, 10), (RING_30, 30), (HELMET_30, 30),
                        (ARMOUR_60, 60), (BOOTS_60, 60), (BOOTS_10, 10)):
        _card, t = card_for(text, level)
        assert len(t["head"]) <= 26 and len(t["line"]) <= 26, t
        for note in t["notes"]:
            assert note.isascii() and "!" not in note and len(note.split()) <= 20, note


# -- the rule file ------------------------------------------------------------

def test_every_entry_has_src_and_checked():
    doc = json.loads(levelrules.PATH.read_text(encoding="ascii"))
    checks = [c for band in doc["bands"] for c in band["checks"]]
    assert checks
    for c in checks:
        assert isinstance(c.get("src"), str) and c["src"].strip(), c
        assert isinstance(c.get("checked"), str) and len(c["checked"]) == 10, c
    assert levelrules.validate(doc)["bands"]
    assert levelrules._watch.error is None and levelrules.table()["bands"]


def test_boots_band_agrees_with_campaign_default():
    doc = levelrules.table()
    speed_bands = [b for b in doc["bands"]
                   if any(c["id"] == "speed" and c["slots"] == ["Boots"] for c in b["checks"])]
    assert speed_bands
    assert min(b["min_level"] for b in speed_bands) == campaign.DEFAULT_BOOTS_LEVEL == 16
    assert all(any(c["id"] == "speed" for c in b["checks"])
               for b in doc["bands"] if b["min_level"] >= campaign.DEFAULT_BOOTS_LEVEL)
    assert levelrules.band_for(doc, 15)["max_level"] == 15


def test_rule_file_is_watched_by_the_core_registry():
    assert levelrules._watch in hotreload.REGISTRY.watches()


def _bump(path, text):
    path.write_text(text, encoding="ascii")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


def test_broken_rule_file_keeps_last_good_copy_with_a_checks_note(tmp_path):
    good = json.loads(levelrules.PATH.read_text(encoding="ascii"))
    f = tmp_path / "level_rules.json"
    reg = hotreload.Registry()
    w = levelrules.watch(f, registry=reg)
    _bump(f, json.dumps(good))
    first = w.get()
    assert first["bands"] and w.error is None
    _bump(f, "{half written")
    assert w.get() is first
    assert w.error == ("Levelling rules did not load (not valid JSON at line 1). "
                       "The last good copy stays in use.")
    assert reg.notes() == [w.error]
    bad = json.loads(json.dumps(good))
    del bad["bands"][1]["checks"][0]["src"]
    _bump(f, json.dumps(bad))
    assert w.get() is first and "has no src" in w.error
    gap = json.loads(json.dumps(good))
    gap["bands"][1]["min_level"] = 17
    _bump(f, json.dumps(gap))
    assert w.get() is first and "does not start at level 16" in w.error
    code = json.loads(json.dumps(good))
    code["bands"][0]["checks"][0]["min"] = "__import__('os')"
    _bump(f, json.dumps(code))
    assert w.get() is first and "has no positive min" in w.error
    _bump(f, json.dumps(good))
    assert w.get()["bands"] and w.error is None and reg.notes() == []


def test_no_table_gives_no_part(monkeypatch):
    monkeypatch.setattr(levelrules, "table", dict)
    assert keep.compute(ctx_for(GLOVES_10, 30)) is None


def test_missed_must_head_names_the_check_and_fits_26():
    """Design review TCK-3: a Vendor from a missed must check names the
    check, never a count that reads like a pass; every must label in the
    table fits 26 at every level (CARD-LINE-LIMIT-COPY: "move speed" is too
    long for ", Lv <n>", so the level drops; a short label keeps it)."""
    doc = levelrules.table()
    labels = {c["label"] for b in doc["bands"] for c in b["checks"] if c["must"]}
    assert labels == {"move speed"}
    for level in range(1, 101):
        for label in labels:
            value = {"status": "vendor", "level": level, "need": 2, "of": 6, "count": 5,
                     "met": [], "missed": [{"label": label, "min": 10, "have": 0}]}
            h = keep.head(value)
            assert len(h) <= 26 and h.startswith(f"Vendor - no {label}"), h
            assert "met" not in h
    value["level"] = 20
    assert keep.head(value) == "Vendor - no move speed"
    value["level"] = 100
    assert keep.head(value) == "Vendor - no move speed"
    value["missed"] = [{"label": "life", "min": 10, "have": 0}]
    assert keep.head(value) == "Vendor - no life, Lv 100"
    value["missed"] = [{"label": "lightning res", "min": 10, "have": 0}]
    value["level"] = 20
    assert keep.head(value) == "Vendor - no lightning res"
