"""KINDLER-PLAN-LIVE (decision 0081 points 14 to 17, decision 0028): the
plan of a real template ranks its non-weapon item focus by Path of Building
per-mod weights from the probe item, within delta.MAX_PROBES calcs, and a
repeat run is identical. Opt-in like the other live calc tests: it carries
the calc mark (tc_live_util.LIVE_CALC) and skips while the optional calc
component, the cached tree export or the base_items snapshot is absent."""

import pytest

from tc_live_util import LIVE_CALC
from server.al.theorycraft import calcwire, delta, genstore, kindler, kindlerplan


class Counting:
    """A calc callable that counts the swapped calculations and passes the
    support-fit command through."""

    def __init__(self, calc):
        self.calc = calc
        self.n = 0
        self.fit = getattr(calc, "fit", None)

    def __call__(self, build, swaps):
        self.n += 1
        return self.calc(build, swaps)


def _plan_once(sources, calc, result):
    counted = Counting(calc)
    planner = kindlerplan.Planner(sources, calc=lambda: counted)
    plan, word = planner.plan(result, wait=True)
    return plan, word, counted.n


@LIVE_CALC
@pytest.mark.slow  # a Generate plus up to 25 PoB calculations (TEST-SLOW-BUDGET)
def test_live_plan_ranks_item_focus_by_pob_weights_and_repeats(warm_bridge):
    sources = kindler.Sources()
    inputs = sources.inputs()
    if inputs["tree"] is None or not inputs["view"]["templates"]:
        pytest.skip("cached tree export or template table absent")
    calc = calcwire.make_calc(lambda: warm_bridge)
    tab = {"class": "", "toggles": dict(genstore.default_toggles(), melee="yes")}
    result = kindler.generate(inputs, tab, 50, calc, limit=2)
    assert result["scored"] and result["best"], result
    plan, word, used = _plan_once(sources, calc, result)
    if word == kindlerplan.FOCUS_NO_BASE:
        pytest.skip("base_items snapshot absent (no carrier base)")
    assert word == kindlerplan.FOCUS_POB, word
    assert 0 < used <= delta.MAX_PROBES + 1, used
    ranked = 0
    for stage in plan["stages"]:
        for row in stage["focus"]:
            if row["source"] == kindlerplan.FOCUS_POB:
                ranked += 1
                assert row["slot"] not in kindlerplan.WEAPON_SLOTS
                assert all(r["weight"] is None or isinstance(r["weight"], float)
                           for r in row["stats"])
            else:
                assert row["slot"] in kindlerplan.WEAPON_SLOTS
    assert ranked, plan
    again, word2, _ = _plan_once(sources, calc, result)
    assert word2 == word and again == plan
