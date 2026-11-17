"""MATH-ITEM: item-mod parsing and stat-key normalisation robustness.

Synthetic fixtures over many item classes (tests/math_item_fixtures.py);
no network, no game data. Plus stdlib-only property tests: the parser and
stat_key never raise on arbitrary text, and normalisation is idempotent.
"""

import random

import math_item_fixtures as F
import pytest

from server.al.theorycraft import evaluate as ev
from server.al.theorycraft import item as it
from server.al.theorycraft import weights as w


def texts(parsed):
    return [m.text for m in parsed.mods]


@pytest.mark.parametrize("name", sorted(F.ALL))
def test_every_fixture_parses_as_an_item(name):
    p = it.parse(F.ALL[name])
    assert p.is_item and p.item_class and p.rarity and p.base
    assert p.warnings == []


def test_weapon_properties_quality_sockets_corrupted():
    p = it.parse(F.RARE_BOW)
    assert (p.name, p.base, p.quality, p.item_level) == ("Dusk Song", "Example Bow", 20, 50)
    assert p.requirements == {"level": 33, "dex": 62}
    assert p.rune_sockets == 2 and p.flags == {"corrupted": True}
    assert p.properties["Attacks per Second"] == "1.10"
    assert p.mods[0].section == "rune"
    assert ev.stats_of(p)["Adds # to # Physical Damage"] == 7


def test_normal_item_has_no_mods():
    p = it.parse(F.NORMAL_HELMET)
    assert p.mods == [] and p.base == "Example Helm" and p.name is None


def test_flask_and_charm_property_lines_are_not_mods():
    flask = it.parse(F.LIFE_FLASK)
    assert texts(flask) == ["40% increased Amount Recovered", "25% reduced Charges per use"]
    assert flask.properties["Recovers"] == "300 Life over 3 Seconds"
    assert flask.properties["Consumes"] == "10 of 60 Charges on use"
    assert flask.properties["Currently has"] == "60 Charges"
    charm = it.parse(F.CHARM)
    assert texts(charm) == ["Used when you become Frozen", "+15 to maximum Life"]
    assert charm.mods[0].section == "implicit"
    assert charm.properties["Lasts"] == "3 Seconds"


def test_flavour_and_help_text_with_numbers_is_not_a_mod():
    shield = it.parse(F.UNIQUE_SHIELD)
    assert not any("flavour" in t for t in texts(shield))
    gem = it.parse(F.GEM)
    assert gem.mods == []


def test_bare_range_resolves_to_its_midpoint():
    shield = it.parse(F.UNIQUE_SHIELD)
    life = shield.mods[0]
    assert life.text == "+50 to maximum Life" and life.values == (50,)
    assert ev.stats_of(shield)["+# to maximum Life"] == 50


def test_signed_roll_ranges_are_stripped():
    p = it.parse(F.ADVANCED_NEGATIVE)
    assert texts(p) == ["+90 to maximum Life", "-15% to Chaos Resistance",
                        "10% reduced Attribute Requirements",
                        "+1.5% to maximum Life Regeneration"]
    assert p.mods[1].values == (-15,) and p.mods[1].kind == "suffix"
    stats = ev.stats_of(p)
    assert stats["+#% to Chaos Resistance"] == -15
    assert stats["#% increased Attribute Requirements"] == -10
    assert stats["+#% to maximum Life Regeneration"] == 1.5


def test_crlf_bom_and_trailing_blanks():
    p = it.parse(F.CRLF_BOM_BELT)
    assert texts(p) == ["+20 to maximum Life", "+15% to Fire Resistance"]


def test_unidentified_keeps_implicits_only():
    p = it.parse(F.UNID_AMULET)
    assert p.flags == {"unidentified": True, "corrupted": True}
    assert texts(p) == ["+10 to Strength"]


@pytest.mark.parametrize("line,value", [
    ("{range:0}+(40-60) to maximum Life", 40),
    ("{range:1}+(40-60) to maximum Life", 60),
    ("{range:0.5}+(40-60) to maximum Life", 50),
    ("{range:0.25}+(41-60) to maximum Life", 46),  # 45.75 rounds half away
    ("{range:0.5}(1.2-1.8)% to maximum Life Regeneration", 1.5),
    ("{range:0.5}-(10-20)% to Fire Resistance", -15),
    ("{range:7}+(40-60) to maximum Life", 60),  # clamped to [0, 1]
])
def test_pob_range_prefix_picks_the_roll(line, value):
    text = "Rarity: UNIQUE\nExample\nExample Base\nImplicits: 0\n" + line + "\n"
    p = it.parse(text)
    assert p.mods and p.mods[-1].values == (value,)


@pytest.mark.parametrize("line,key,value", [
    ("+25% to Fire Resistance", "+#% to Fire Resistance", 25),
    ("-10% to Fire Resistance", "+#% to Fire Resistance", -10),
    ("10% reduced Attack Speed", "#% increased Attack Speed", -10),
    ("15% less Damage taken", "#% more Damage taken", -15),
    ("Adds 3 to 7 Physical Damage", "Adds # to # Physical Damage", 5),
    ("Adds 3(2-4) to 7(6-8) Physical Damage", "Adds # to # Physical Damage", 5),
    ("+15(10-20) to maximum Life", "+# to maximum Life", 15),
    ("-15(-20--10)% to Chaos Resistance", "+#% to Chaos Resistance", -15),
    ("0.5% of Physical Attack Damage Leeched as Life",
     "#% of Physical Attack Damage Leeched as Life", 0.5),
    # sign follows the word that governs the first number only
    ("10% reduced Mana Cost of Skills and 5% less Damage",
     "#% increased Mana Cost of Skills and #% more Damage", -10),
    ("10% increased Mana Cost of Skills and 5% reduced Damage",
     "#% increased Mana Cost of Skills and #% increased Damage", 10),
    ("Bow Attacks fire an additional Arrow", "Bow Attacks fire an additional Arrow", None),
])
def test_stat_key_edge_cases(line, key, value):
    assert w.stat_key(line) == (key, value)


def test_reduced_and_increased_share_a_weight():
    a, va = w.stat_key("12% reduced Movement Speed")
    b, vb = w.stat_key("12% increased Movement Speed")
    assert a == b and va == -vb


# ---- property tests (stdlib random, fixed seeds: deterministic) ----------

ALPHABET = ("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            " +-%().:{}[]\"'/\n\r\t-" + chr(0xFEFF) + chr(0x2014) + chr(0xE9))


def _rand_text(rng, n):
    return "".join(rng.choice(ALPHABET) for _ in range(n))


def test_parser_and_stat_key_never_raise_on_random_text():
    rng = random.Random(4004)
    for i in range(1500):
        body = _rand_text(rng, rng.randint(0, 200))
        head = rng.choice(["", "Item Class: Rings\nRarity: Rare\nA\nB\n--------\n",
                           "Rarity: UNIQUE\nX\nY\nImplicits: 1\n"])
        p = it.parse(head + body)
        assert isinstance(p.to_dict(), dict)
        for m in p.mods:
            w.stat_key(m.text)
        w.stat_key(body)


def test_fixture_mutations_never_raise():
    rng = random.Random(77)
    sources = list(F.ALL.values())
    for _ in range(600):
        src = list(rng.choice(sources))
        for _ in range(rng.randint(1, 8)):
            op = rng.random()
            pos = rng.randrange(len(src) + 1)
            if op < 0.4 and src:
                del src[min(pos, len(src) - 1)]
            elif op < 0.8:
                src.insert(pos, rng.choice(ALPHABET))
            else:
                src.insert(pos, "\n--------\n")
        p = it.parse("".join(src))
        ev.stats_of(p)


def test_stat_key_is_idempotent_on_its_key():
    rng = random.Random(9)
    lines = [m.text for t in F.ALL.values() for m in it.parse(t).mods]
    for line in lines:
        key, _ = w.stat_key(line)
        again, _ = w.stat_key(key)
        assert again == key
    for _ in range(300):
        key, _ = w.stat_key(_rand_text(rng, 40).replace("\n", " "))
        assert w.stat_key(key)[0] == key


def test_stat_key_value_matches_a_generated_number():
    rng = random.Random(123)
    for _ in range(500):
        n = rng.choice([rng.randint(1, 999), round(rng.uniform(0.1, 99.9), 1)])
        sign = rng.choice(["+", "-", ""])
        word = rng.choice(["increased", "reduced", "more", "less"])
        if sign:
            line = f"{sign}{n}% to Example Resistance"
            want = -n if sign == "-" else n
        else:
            line = f"{n}% {word} Example Damage"
            want = -n if word in ("reduced", "less") else n
        _, value = w.stat_key(line)
        assert value == pytest.approx(want)
