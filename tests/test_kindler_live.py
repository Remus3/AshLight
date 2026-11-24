"""KINDLER-ENGINE live checks (decision 0081 point 13, decision 0028):
the reference build scored through Kindler's XML path matches the
bridge's direct numbers within 0.1 percent, and real templates composed
as PoB XML score through the bridge with byte-identical repeats, and the
attack templates score above 0 DPS with their authored weapon base.

Opt-in like the other live calc tests: each carries the calc mark
(tc_live_util.LIVE_CALC) and skips while the optional calc component, the
PoB GUI reference or the cached tree export is absent."""

import math

import pytest

import tc_live_util
from tc_live_util import LIVE_CALC
from server.al.theorycraft import calcwire, genstore, kindler


@LIVE_CALC
def test_live_reference_build_through_kindler_matches_the_bridge(warm_bridge):
    ref = tc_live_util.reference()
    if ref is None:
        pytest.skip("PoB GUI reference absent (sidecar Cache\\tc_bridge)")
    want_ref, xml = ref
    warm_bridge.load_build(xml)
    direct = calcwire.map_outputs(warm_bridge.outputs(list(calcwire.OUTPUT_KEYS)))
    calc = calcwire.make_calc(lambda: warm_bridge)
    got = kindler.score_xml(calc, xml)
    for key in ("dps", "ehp"):
        assert got[key] == pytest.approx(direct[key], rel=1e-3), key
    if want_ref["pob"] == tc_live_util.tested_tag():
        outs = want_ref["outputs"]
        assert got["dps"] == pytest.approx(outs["FullDPS"], rel=1e-3)
        assert got["ehp"] == pytest.approx(outs["TotalEHP"], rel=1e-3)


@LIVE_CALC
@pytest.mark.slow  # six PoB builds through the live calc (TEST-SLOW-BUDGET)
def test_live_real_templates_score_and_repeat_byte_identical(warm_bridge):
    inputs = kindler.Sources().inputs()
    if inputs["tree"] is None or not inputs["view"]["templates"]:
        pytest.skip("cached tree export or template table absent")
    calc = calcwire.make_calc(lambda: warm_bridge)
    tab = {"class": "", "toggles": dict(genstore.default_toggles(), melee="yes")}
    one = kindler.generate(inputs, tab, 30, calc, limit=2)
    assert one["scored"] and not one["partial"], one
    for row in one["candidates"]:
        assert math.isfinite(row["dps"]) and row["dps"] >= 0
        assert math.isfinite(row["ehp"]) and row["ehp"] > 0
    two = kindler.generate(inputs, tab, 30, calc, limit=2)
    assert kindler.dumps(one) == kindler.dumps(two)
    # KINDLER-WEAPON-BASE: with the authored weapon base composed, every
    # attack template (melee, bow) scores above 0 DPS: its best variant
    # (live finding: the mace template's Boneshatter read 0 with no
    # weapon). KINDLER-GEM-VARIANT: every named skill of the early stages
    # scores too, Mace Strike included (its name matches several PoB weapon
    # variants; the composer names the one skill id the weapon picks).
    if not inputs["view"]["bases"]:
        return
    attack = {t["id"] for t in inputs["view"]["templates"]
              if set(t["toggles"]) & {"melee", "bow"}}
    assert attack
    seen = set()
    runs = [(one, None)]
    for toggle, level in (("melee", 50), ("bow", 30)):
        tab = {"class": "", "toggles": dict(genstore.default_toggles(), **{toggle: "yes"})}
        runs.append((kindler.generate(inputs, tab, level, calc, limit=1), level))
    for doc, level in runs:
        assert doc["scored"] and not doc["partial"], doc
        rows = [r for r in doc["candidates"] if r["template"] in attack]
        assert rows, doc
        for tid in {r["template"] for r in rows}:
            assert max(r["dps"] for r in rows if r["template"] == tid) > 0, (tid, rows)
            seen.add(tid)
        if level == 50:
            assert [r["skill"] for r in rows] == ["Boneshatter"] and rows[0]["dps"] > 0
    assert seen == attack


@LIVE_CALC
@pytest.mark.slow  # up to eight PoB builds through the live calc (TEST-SLOW-BUDGET)
def test_live_every_early_attack_skill_scores_above_zero(warm_bridge):
    """KINDLER-GEM-VARIANT: each attack template's named skill of the first
    zone and the first act stage scores above 0 DPS with its weapon base
    (live finding: Mace Strike by name read 0, by skill id 5.96)."""
    inputs = kindler.Sources().inputs()
    view = inputs["view"]
    if inputs["tree"] is None or not view["templates"] or not view["bases"]:
        pytest.skip("cached tree export, template table or base_items absent")
    calc = calcwire.make_calc(lambda: warm_bridge)
    attack = [t for t in view["templates"] if set(t["toggles"]) & {"melee", "bow"}]
    assert attack
    variant_gems = 0
    for t in attack:
        toggle = sorted(set(t["toggles"]) & {"melee", "bow"})[0]
        tab = {"class": t["class"],
               "toggles": dict(genstore.default_toggles(), **{toggle: "yes"})}
        for level in (5, 20):
            si = kindler.stage_index(t, kindler.level_band(level))
            skills = t["stages"][si]["skills"]
            variant_gems += sum(1 for sk in skills if sk["gem"].get("skill_id"))
            doc = kindler.generate(inputs, tab, level, calc, limit=len(skills))
            assert doc["scored"] and not doc["partial"], doc
            rows = [r for r in doc["candidates"] if r["template"] == t["id"]]
            assert sorted(r["skill"] for r in rows) == sorted(
                sk["gem"]["name"] for sk in skills), (t["id"], level, rows)
            for r in rows:
                assert math.isfinite(r["dps"]) and r["dps"] > 0, (t["id"], level, r)
    # the pinned PoB Gems.lua was read: Mace Strike carries its skill id
    assert variant_gems, "no skill id composed; check the Gems.lua pin"
