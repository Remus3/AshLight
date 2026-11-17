"""MATH-TRADESTAT-COVER: which default weights find a trade stat id.

Template strings below are short excerpts copied from the cached repoe-fork
stat_descriptions.json (accessed 2026-11-17); the ids are invented (no real
id table is bundled, decision 0009 item 1). Finding: repoe-fork attaches no
`trade_stats` to an entry whose English string holds game markup, so
resistances, attributes, armour / evasion / energy shield and most damage
mods have no id in the file and stay unfiltered (decision 0037 item 3)."""

import json
import re

import pytest

from server.al import tradestats
from server.al.theorycraft import weights


def _entry(ids, string, fmt, rows):
    return {"ids": ids, "English": [{"condition": [{}], "format": fmt,
                                     "string": string}], "trade_stats": rows}


def _row(tid, text, kind="explicit"):
    return {"id": tid, "text": text, "type": kind, "option": None}


# real shapes: markup entries ship trade_stats null, plain ones carry rows
REAL = [
    _entry(["base_fire_damage_resistance_%"],
           "{0}% to [Resistances|Fire Resistance]", ["+#"], None),
    _entry(["additional_strength"], "{0} to [Strength|Strength]", ["+#"], None),
    _entry(["local_physical_damage_reduction_rating_+%"],
           "{0}% increased [Armour|Armour]", ["#"], None),
    _entry(["base_maximum_life"], "{0} to maximum Life", ["+#"], [
        _row("crafted.stat_2000001", "# to maximum Life", "crafted"),
        _row("explicit.stat_2000001", "# to maximum Life"),
        _row("implicit.stat_2000001", "# to maximum Life", "implicit")]),
    _entry(["damage_taken_goes_to_mana_%"],
           "{0}% of Damage taken [Recoup|Recouped] as Mana", ["#"], [
               _row("explicit.stat_2000002", "#% of Damage taken Recouped as Mana")]),
    _entry(["global_minimum_added_physical_damage",
            "global_maximum_added_physical_damage"],
           "Adds {0} to {1} Physical Damage", ["#", "#"], [
               _row("explicit.stat_2000003", "Adds # to # Physical Damage")]),
    _entry(["base_movement_velocity_+%"], "{0}% increased Movement Speed", ["#"], [
        _row("pseudo.pseudo_increased_movement_speed",
             "#% increased Movement Speed", "pseudo"),
        _row("explicit.stat_2000004", "#% increased Movement Speed")]),
]


def test_markup_entries_without_trade_stats_stay_unfiltered():
    idx = tradestats.build_index(REAL)
    for key in ("+#% to Fire Resistance", "+# to Strength", "#% increased Armour"):
        assert tradestats.lookup(idx, key) is None
    assert tradestats.lookup(idx, "+# to maximum Life") == "explicit.stat_2000001"
    assert tradestats.lookup(idx, "Adds # to # Physical Damage") == "explicit.stat_2000003"
    assert tradestats.lookup(idx, "#% increased Movement Speed") == "explicit.stat_2000004"
    assert "pseudo" not in json.dumps(sorted(idx.values()))


def test_markup_is_reduced_to_its_shown_text():
    assert tradestats.norm("{0}% to [Resistances|Fire Resistance]") == \
        "{0}% to fire resistance"
    assert tradestats.norm("+# to [Spirit]") == "# to spirit"
    assert tradestats.norm("#% of Damage taken [Recoup|Recouped] as Life") == \
        "#% of damage taken recouped as life"
    # a marked-up trade text still matches its plain weights key exactly
    idx = tradestats.build_index([{"trade_stats": [
        _row("explicit.stat_2000005", "#% to [Resistances|Cold Resistance]")]}])
    assert tradestats.lookup(idx, "+#% to Cold Resistance") == "explicit.stat_2000005"
    # no fuzzy match: a near text is no match
    assert tradestats.lookup(idx, "+#% to Cold Resistances") is None
    assert tradestats.lookup(idx, "+#% to Cold and Lightning Resistances") is None


def test_every_default_key_maps_once_its_trade_text_exists():
    """Matching covers every default key form ("+#%", "Adds # to #",
    "Gain # ... per") the moment the file carries its explicit trade row."""
    keys = list(weights.DEFAULT_WEIGHTS)
    rows = [_row("explicit.stat_%d" % (3000000 + i), k.lstrip("+"))
            for i, k in enumerate(keys)]
    idx = tradestats.build_index([{"trade_stats": rows}])
    cov = tradestats.coverage(idx, keys)
    assert cov["unmapped"] == []
    assert len(set(cov["mapped"].values())) == len(keys)


def test_coverage_shape_and_bad_input():
    idx = tradestats.build_index(REAL)
    cov = tradestats.coverage(idx, ["+# to maximum Life", "+# to Strength"])
    assert cov == {"mapped": {"+# to maximum Life": "explicit.stat_2000001"},
                   "unmapped": ["+# to Strength"]}
    assert tradestats.coverage(idx, None) == {"mapped": {}, "unmapped": []}
    assert tradestats.coverage(None, ["x"]) == {"mapped": {}, "unmapped": ["x"]}


def test_live_cache_unmapped_keys_have_no_trade_stats_in_the_file():
    """On the real cached snapshot: every default key that has an explicit
    trade row maps, and every unmapped key's template is in the file with
    no explicit trade_stats (so nothing was missed by the matcher)."""
    path = tradestats.default_path()
    if not path.is_file():
        pytest.skip("no cached stat_translations snapshot")
    doc = json.loads(path.read_text(encoding="utf-8"))
    idx = tradestats.build_index(doc)
    explicit = {tradestats.norm(r.get("text")) for e in doc if isinstance(e, dict)
                for r in e.get("trade_stats") or () if isinstance(r, dict)
                and r.get("type") == "explicit"}
    cov = tradestats.coverage(idx, list(weights.DEFAULT_WEIGHTS))
    for key in weights.DEFAULT_WEIGHTS:
        if tradestats.norm(key) in explicit:
            assert key in cov["mapped"], key
    templ = {}
    for e in doc:
        if not isinstance(e, dict):
            continue
        has = any(isinstance(r, dict) and r.get("type") == "explicit"
                  for r in e.get("trade_stats") or ())
        for x in e.get("English") or ():
            k = tradestats.norm(re.sub(r"\{\d+\}", "#", x.get("string") or ""))
            if k:
                templ.setdefault(k, []).append(has)
    for key in cov["unmapped"]:
        assert not any(templ.get(tradestats.norm(key), ())), key
    assert len(cov["mapped"]) >= 11
