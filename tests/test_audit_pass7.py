"""AREA-AUDIT pass 7 regression tests.

P7-1 (medium): MATH-DEF-BREAKDOWN's flask and charm rows (FlaskChargeGen,
Life- / ManaFlaskChargeGen, CharmEffect) were always empty with the calc
on: the pinned PoB sets them only `if breakdown then` (CalcPerform.lua),
i.e. in the CALCS pass, and bridge.lua read only mainOutput (the MAIN pass,
no breakdown). The outputs handler now fills a REQUESTED key that the main
table lacks from PoB's own calcsOutput (same build, same frame; nothing
recomputed, decision 0004).

P7-2 (medium): UTIL-WAYSTONE-REWARD added a visible "N% increased <reward>"
mod line to the matching "(augmented)" property, but the game's property
is already the sum of every source, so a waystone with both showed the
reward twice. A property now wins for its kind; a mod line counts only for
a kind with no property.

P7-3 (low): jsonfile.read_json promises never to raise, but a deeply nested
hand-broken file raised RecursionError out of json.loads."""

from pathlib import Path

import pytest

from server.al import jsonfile
from server.al.theorycraft import bridge, health, waystone
from tests.test_waystone import LIFE_BUILD, WAYSTONE

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "tc_bridge"
FLASK_KEYS = ("FlaskChargeGen", "LifeFlaskChargeGen", "ManaFlaskChargeGen", "CharmEffect")


# ---- P7-1 ---------------------------------------------------------------

def test_bridge_outputs_falls_back_to_the_calcs_pass_for_requested_keys():
    text = (ROOT / "server" / "al" / "theorycraft" / "bridge.lua").read_text(encoding="ascii")
    handler = text.split('handlers["outputs"]', 1)[1].split("\nend\n", 1)[0]
    assert "calcsOutput" in handler
    # only requested keys: a keyless read stays the main table alone
    assert "want" in handler.split("calcsOutput", 1)[1]


def test_flask_and_charm_rows_are_asked_from_the_calc():
    assert set(FLASK_KEYS) <= set(health.CALC_KEYS)


@pytest.mark.skipif(not bridge.available(),
                    reason="optional calc component absent (setup.ps1 -TcCalc)")
@pytest.mark.slow
def test_live_flask_and_charm_outputs_reach_the_build_view(warm_bridge):
    xml = (FIX / "minimal_build.xml").read_text(encoding="ascii")
    warm_bridge.load_build(xml)
    out = warm_bridge.outputs(list(health.CALC_KEYS))
    for key in FLASK_KEYS:
        assert key in out, key
    rows = {r["id"] for r in health.defence(out, True)}
    assert set(FLASK_KEYS) <= rows
    # a keyless read is unchanged: the main table alone
    assert "FlaskChargeGen" not in warm_bridge.outputs()


# ---- P7-2 ---------------------------------------------------------------

def _rew(text):
    return {r["id"]: r["pct"] for r in waystone.check(text, LIFE_BUILD)["rewards"]}


def test_property_total_is_not_doubled_by_a_mod_line():
    text = WAYSTONE.replace("Monsters take 22% reduced Extra Damage from Critical Hits",
                            "38% increased Rarity of Items found in this Area")
    assert _rew(text) == {"rarity": 38, "pack": 12}


def test_mod_line_counts_for_a_kind_with_no_property():
    text = WAYSTONE.replace("Monsters take 22% reduced Extra Damage from Critical Hits",
                            "10% increased Quantity of Items found in this Area")
    assert _rew(text) == {"quantity": 10, "rarity": 38, "pack": 12}


def test_two_mod_lines_of_one_kind_sum_without_a_property():
    text = WAYSTONE.replace("Monster Pack Size: +12% (augmented)\n", "").replace(
        "Monsters take 22% reduced Extra Damage from Critical Hits",
        "10% increased Monster Pack Size\n5% increased Pack Size")
    assert _rew(text) == {"rarity": 38, "pack": 15}


# ---- P7-3 ---------------------------------------------------------------

def test_read_json_deep_nesting_reads_as_default(tmp_path):
    p = tmp_path / "deep.json"
    p.write_text("[" * 200000 + "]" * 200000, encoding="ascii")
    assert jsonfile.read_json(p, default="d") == "d"
