"""UTIL-SEARCHSTR (decision 0030): search strings from the loaded build."""

from server.al.theorycraft import searchstr
from server.al.theorycraft.model import Build, Item


def _build(stats, gear=None):
    return Build(raw_xml="", stats=stats, gear=gear or {})


LIFE = _build({"Life": 4000, "EnergyShield": 100, "FireResist": 75, "ColdResist": 50,
               "LightningResist": 75, "ChaosResist": -20},
              {"Weapon 1": Item(1, "", "RARE", "Grim Bite", "Expert Hunting Bow"),
               "Body Armour": Item(2, "", "UNIQUE", "Example Coat", "Ringmail Coat"),
               "Belt": Item(3, "", "MAGIC", None, "Stout Belt of the Bear"),
               "Flask 1": Item(4, "", "NORMAL", None, "Ultimate Life Flask")})


def by_id(build):
    return {s["id"]: s for s in searchstr.strings(build)}


def test_no_build_no_strings():
    assert searchstr.strings(None) == []


def test_clean_removes_search_syntax():
    assert searchstr.clean('Fire "Res"|!x (a.*b)') == "fire res x a b"
    assert searchstr.clean("  Kaom's   Heart ") == "kaom's heart"
    assert searchstr.clean(None) == ""


def test_join_or_not_and_dedupe():
    assert searchstr.join(["Fire res", "fire res", "cold res"]) == ('"fire res|cold res"', 2)
    assert searchstr.join(["extra fire"], negate=True) == ('"!extra fire"', 1)
    assert searchstr.join([]) == (None, 0)
    assert searchstr.join(["|", '"']) == (None, 0)


def test_length_cap_drops_whole_terms():
    terms = [f"term number {i:02d}" for i in range(40)]
    text, kept = searchstr.join(terms)
    assert len(text) <= searchstr.MAX_LEN and kept < 40
    assert text.endswith('"') and text.count("|") == kept - 1
    assert all(t in terms for t in text.strip('"').split("|"))
    text, kept = searchstr.join(["abcdefghij"], cap=5)
    assert (text, kept) == (None, 0)


def test_life_build_strings():
    s = by_id(LIFE)
    assert s["resists"]["text"] == '"cold res|chaos res"'
    assert s["defence"]["text"] == '"maximum life"'
    assert s["movement"]["text"] == '"movement speed"'
    # magic belt (affixed name) and flask are left out
    assert s["bases"]["text"] == '"expert hunting bow|ringmail coat"'
    assert s["waystone"]["text"].startswith('"!extra cold|')
    assert "extra fire" not in s["waystone"]["text"]
    assert "poison" in s["waystone"]["text"]
    for v in s.values():
        assert len(v["text"]) <= searchstr.MAX_LEN and v["dropped"] == 0
        assert v["label"] and v["why"].endswith(".")


def test_capped_build_has_no_resist_string_and_es_defence():
    es = _build({"Life": 900, "EnergyShield": 6000, "FireResist": 75, "ColdResist": 76,
                 "LightningResist": 80, "ChaosResist": 10})
    s = by_id(es)
    assert "resists" not in s and "bases" not in s
    assert s["defence"]["text"] == '"maximum energy shield"'


def test_build_snapshot_carries_the_strings(tmp_path):
    from server.al.theorycraft import codec
    from server.al.theorycraft.store import BuildStore
    from tc_eval_fixtures import EVAL_BUILD_XML
    store = BuildStore(tmp_path / "build.xml")
    assert store.snapshot()["search_strings"] == []
    store.load_code(codec.encode(EVAL_BUILD_XML))
    ids = [s["id"] for s in store.snapshot()["search_strings"]]
    assert "movement" in ids and "waystone" in ids


def test_unknown_stats_ask_for_everything():
    s = by_id(_build({}))
    assert s["resists"]["text"] == ('"fire res|cold res|lightning res|all elemental res|'
                                    'chaos res"')
    assert s["defence"]["text"] == '"maximum life|maximum energy shield"'
    assert len(s["waystone"]["text"]) <= searchstr.MAX_LEN
