"""MATH-MAGIC-BASE: a magic item's true base type (synthetic fixtures)."""

import json
import random

import pytest

from server.al import trade
from server.al.theorycraft import basetypes as bt
from server.al.theorycraft import item as item_mod

NAMES = {n.lower(): n for n in (
    "Iron Ring", "Sapphire Ring", "Gold Amulet", "Leather Belt", "Stocky Mitts",
    "Ultimate Life Flask", "Life Flask", "Thawing Charm", "Expert Shrine Sceptre",
    "Shrine Sceptre", "Broadhead Quiver", "Crude Bow", "Rusted Cuirass",
    "Wooden Buckler", "Twig Focus", "Iron Greaves", "Leather Cap", "Ring")}


def magic(item_class, line, explicits, implicit=None, extra=""):
    body = "\n".join(explicits)
    imp = f"--------\n{implicit} (implicit)\n" if implicit else ""
    return (f"Item Class: {item_class}\nRarity: Magic\n{line}\n--------\n"
            f"Item Level: 40\n{imp}--------\n{body}\n{extra}")


# (class, name line, explicit lines, base by shape, base by snapshot)
CASES = [
    ("Rings", "Hale Iron Ring of the Bear", ["+20 to maximum Life", "+10 to Strength"],
     "Iron Ring", "Iron Ring"),
    ("Rings", "Iron Ring of the Bear", ["+10 to Strength"], "Iron Ring", "Iron Ring"),
    ("Rings", "Hale Iron Ring", ["+20 to maximum Life"], "Iron Ring", "Iron Ring"),
    ("Amulets", "Glinting Gold Amulet of Skill",
     ["+30 to Accuracy Rating", "5% increased Attack Speed"], "Gold Amulet", "Gold Amulet"),
    ("Belts", "Leather Belt of the Whale", ["+15 to maximum Mana"],
     "Leather Belt", "Leather Belt"),
    ("Gloves", "Reinforced Stocky Mitts", ["+40 to Armour"], "Stocky Mitts", "Stocky Mitts"),
    ("Life Flasks", "Bubbling Ultimate Life Flask of the Surgeon",
     ["50% increased Amount Recovered", "20% reduced Charges per use"],
     "Ultimate Life Flask", "Ultimate Life Flask"),
    ("Charms", "Thawing Charm of the Quiet", ["+15 to maximum Life"],
     "Thawing Charm", "Thawing Charm"),
    ("Sceptres", "Vivid Expert Shrine Sceptre of the Mage",
     ["+20 to maximum Mana", "10% increased Cast Speed"],
     "Expert Shrine Sceptre", "Expert Shrine Sceptre"),
    ("Quivers", "Broadhead Quiver of Puncturing", ["20% increased Critical Hit Chance"],
     "Broadhead Quiver", "Broadhead Quiver"),
    ("Bows", "Heavy Crude Bow", ["40% increased Physical Damage"], "Crude Bow", "Crude Bow"),
    ("Body Armours", "Rusted Cuirass of the Lizard", ["+15% to Chaos Resistance"],
     "Rusted Cuirass", "Rusted Cuirass"),
    ("Shields", "Wooden Buckler of Light", ["+20 to Evasion Rating"],
     "Wooden Buckler", "Wooden Buckler"),
    ("Foci", "Twig Focus of Thought", ["+10 to Intelligence"], "Twig Focus", "Twig Focus"),
    ("Boots", "Fleet Iron Greaves of Warmth",
     ["20% increased Movement Speed", "+25% to Fire Resistance"],
     "Iron Greaves", "Iron Greaves"),
    ("Helmets", "Leather Cap of the Bear", ["+10 to Strength"], "Leather Cap", "Leather Cap"),
]


@pytest.mark.parametrize("cls,line,mods,shape,snap", CASES)
def test_shape_strip_without_snapshot(cls, line, mods, shape, snap):
    p = item_mod.parse(magic(cls, line, mods), names={})
    assert p.name == line and p.base == shape and p.base_source == bt.SHAPE


@pytest.mark.parametrize("cls,line,mods,shape,snap", CASES)
def test_snapshot_list_wins(cls, line, mods, shape, snap):
    p = item_mod.parse(magic(cls, line, mods), names=NAMES)
    assert p.name == line and p.base == snap and p.base_source == bt.SNAPSHOT


def test_snapshot_longest_match_beats_shorter_base():
    # "Ring" and "Shrine Sceptre" are bases too; the longest run wins
    assert bt.from_names("Hale Iron Ring of the Bear", NAMES) == "Iron Ring"
    assert bt.from_names("Vivid Expert Shrine Sceptre", NAMES) == "Expert Shrine Sceptre"
    assert bt.from_names("Iron Ring", {"iron ring": "Iron Ring"}) == "Iron Ring"
    assert bt.from_names("Unknown Thing", NAMES) is None
    assert bt.from_names("iron ring of x", NAMES) == "Iron Ring"  # list spelling


def test_snapshot_miss_falls_back_to_shape():
    p = item_mod.parse(magic("Rings", "Hale Odd Band of the Bear",
                             ["+20 to maximum Life", "+10 to Strength"]), names=NAMES)
    assert p.base == "Odd Band" and p.base_source == bt.SHAPE


def test_implicits_and_runes_do_not_count_as_affixes():
    # one explicit + an implicit + no " of ": the first word is the prefix
    p = item_mod.parse(magic("Rings", "Hale Iron Ring", ["+20 to maximum Life"],
                             implicit="+8% to Cold Resistance"), names={})
    assert p.base == "Iron Ring"
    # a suffix and one explicit plus an implicit: no prefix
    p = item_mod.parse(magic("Rings", "Iron Ring of the Bear", ["+10 to Strength"],
                             implicit="+8% to Cold Resistance"), names={})
    assert p.base == "Iron Ring"


def test_advanced_headers_name_the_affixes():
    text = ("Item Class: Rings\nRarity: Magic\nHale Odd Band of the Bear\n--------\n"
            "Item Level: 40\n--------\n"
            '{ Prefix Modifier "Hale" (Tier: 7) - Life }\n+20 to maximum Life\n'
            '{ Suffix Modifier "of the Bear" (Tier: 6) - Attribute }\n+10 to Strength\n')
    p = item_mod.parse(text, names={})
    assert p.advanced and p.base == "Odd Band" and p.base_source == bt.ADVANCED
    # a two-word base kept whole even with only a suffix
    text2 = ("Item Class: Rings\nRarity: Magic\nOdd Old Band of the Bear\n--------\n"
             '{ Suffix Modifier "of the Bear" (Tier: 6) - Attribute }\n+10 to Strength\n')
    assert item_mod.parse(text2, names={}).base == "Odd Old Band"


def test_unidentified_and_plain_magic_left_alone():
    text = ("Item Class: Rings\nRarity: Magic\nIron Ring\n--------\nItem Level: 40\n"
            "--------\nUnidentified\n")
    p = item_mod.parse(text, names={})
    assert p.name is None and p.base == "Iron Ring" and p.base_source is None
    # a magic item with no affix words and no explicit lines
    p = item_mod.parse(magic("Rings", "Iron Ring", []), names={})
    assert p.base == "Iron Ring" and p.name is None


def test_other_rarities_untouched():
    rare = ("Item Class: Rings\nRarity: Rare\nDoom Loop\nIron Ring\n--------\n"
            "+20 to maximum Life\n")
    p = item_mod.parse(rare, names=NAMES)
    assert (p.name, p.base, p.base_source) == ("Doom Loop", "Iron Ring", None)
    normal = "Item Class: Rings\nRarity: Normal\nIron Ring\n"
    p = item_mod.parse(normal, names=NAMES)
    assert (p.name, p.base) == (None, "Iron Ring")


def test_display_name_not_doubled():
    p = item_mod.parse(magic("Rings", "Hale Iron Ring of the Bear",
                             ["+20 to maximum Life", "+1 to Strength"]), names={})
    assert p.display_name == "Hale Iron Ring of the Bear"
    assert p.to_dict()["base_source"] == "shape"


def test_trade_query_uses_true_base():
    p = item_mod.parse(magic("Rings", "Hale Iron Ring of the Bear",
                             ["+20 to maximum Life", "+1 to Strength"]), names={})
    q = trade.build_query(p)
    assert q["query"]["type"] == "Iron Ring"


def test_registered_provider_and_failure():
    text = magic("Rings", "Hale Odd Band", ["+20 to maximum Life"])
    try:
        item_mod.set_base_names(lambda: {"odd band": "Odd Band"})
        assert item_mod.parse(text).base_source == bt.SNAPSHOT

        def boom():
            raise OSError("bad cache")
        item_mod.set_base_names(boom)
        p = item_mod.parse(text)
        assert p.base == "Odd Band" and p.base_source == bt.SHAPE
    finally:
        item_mod.set_base_names(None)


def test_load_names_and_cache(tmp_path):
    f = tmp_path / bt.FILE_NAME
    f.write_text(json.dumps({
        "Metadata/Items/Rings/Ring1": {"name": "Iron Ring", "release_state": "released"},
        "Metadata/Items/Rings/RingX": {"name": "Secret Ring", "release_state": "unreleased"},
        "bad": "x", "noname": {"item_class": "Ring"},
        "spaced": {"name": "  Gold   Amulet "}}), encoding="utf-8")
    assert bt.load_names(f) == {"iron ring": "Iron Ring", "gold amulet": "Gold Amulet"}
    c = bt.NamesCache(f)
    assert c.get()["iron ring"] == "Iron Ring"
    f.write_text("{not json", encoding="utf-8")
    assert bt.load_names(f) == {}
    assert bt.NamesCache(tmp_path / "missing.json").get() == {}
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    assert bt.load_names(tmp_path / "list.json") == {}


def test_property_never_raises_and_base_is_a_word_run():
    rng = random.Random(4242)
    words = ["Hale", "Iron", "Ring", "of", "the", "Bear", "Gold", "Amulet", "x", "Of", "OF"]
    for _ in range(2000):
        line = " ".join(rng.choice(words) for _ in range(rng.randint(0, 7)))
        mods = [item_mod.Mod(text="+1 to Strength")] * rng.randint(0, 3)
        for names in (None, {}, NAMES):
            base, source = bt.magic_base(line, mods, names)
            assert source in (bt.SNAPSHOT, bt.ADVANCED, bt.SHAPE, bt.AS_IS)
            if line.strip():
                # the base is always a contiguous run of the line's words
                assert base and (" " + base.lower() + " ") in (" " + " ".join(
                    line.split()).lower() + " ")
    for junk in (None, "", "   ", 5):
        assert bt.magic_base(junk)[1] == bt.AS_IS


def test_core_registers_snapshot_names(tmp_path):
    from server.al.core import Core
    gd = tmp_path / "rt" / "gamedata"
    gd.mkdir(parents=True)
    (gd / bt.FILE_NAME).write_text(json.dumps({"a": {"name": "Odd Band"}}), encoding="utf-8")
    try:
        log = tmp_path / "Client.txt"
        log.write_text("", encoding="utf-8")
        Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
        p = item_mod.parse(magic("Rings", "Hale Odd Band of Bears", ["+1 to Strength"]))
        assert p.base == "Odd Band" and p.base_source == bt.SNAPSHOT
    finally:
        item_mod.set_base_names(None)
