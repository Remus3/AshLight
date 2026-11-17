"""TC-DELTA: PoB-backed evaluation (decision 0024).

The calc component (TC-BRIDGE: pinned LuaJIT + unmodified PoB-PoE2) is a
callable `calc(build, swaps) -> {"dps", "ehp"}`; these tests drive the
delta engine with a deterministic fake calc on the TC-EVAL fixtures, so
they need no LuaJIT. With no calc (component off) or a calc that fails, the
item check falls back to the stat weights and says so on the card."""

import math

import pytest

from server.al import upgrade
from server.al.state import eval_card_text
from server.al.theorycraft import delta
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import item as item_parser
from server.al.theorycraft import live, model
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, JEWEL, RARE_GLOVES

GLOVES_SLOT = '\t\t\t<Slot name="Gloves" itemId="1"/>\n'

# fake PoB: per-point effect of a stat on the two outputs
DPS_PER = {"adds # to # lightning damage to attacks": 2.0, "#% increased attack speed": 3.0}
EHP_PER = {"+# to maximum life": 10.0, "+#% to cold resistance": 20.0,
           "+#% to lightning resistance": 20.0, "+#% to fire resistance": 20.0}
BASE_DPS, BASE_EHP = 100.0, 1000.0


class FakeCalc:
    """dps / ehp as a linear function of the summed stats of the gear after
    the swaps; counts calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, build, swaps):
        self.calls.append(dict(swaps))
        gear = {slot: it.text for slot, it in build.gear.items()}
        gear.update(swaps)
        dps, ehp = BASE_DPS, BASE_EHP
        for text in gear.values():
            for key, value in tc_evaluate.stats_of(item_parser.parse(text)).items():
                dps += DPS_PER.get(key.lower(), 0) * value
                ehp += EHP_PER.get(key.lower(), 0) * value
        return {"dps": dps, "ehp": ehp}


def _build(xml=EVAL_BUILD_XML):
    return model.parse(xml)


def _base():
    # equipped: gloves 40 life 20 cold; ring1 7 cold 20 life; ring2 9 cold 80
    # life 40 light 40 fire -> life 140, cold 36, light 40, fire 40
    return BASE_DPS, BASE_EHP + 140 * 10 + 36 * 20 + 40 * 20 + 40 * 20


# -- delta engine -----------------------------------------------------------

def test_outputs_validates_the_calc_answer():
    b = _build()
    assert delta.outputs(lambda build, swaps: {"dps": 1, "ehp": 2.5}, b) == \
        {"dps": 1.0, "ehp": 2.5}
    for bad in (None, {}, {"dps": 1}, {"dps": "1", "ehp": 2}, {"dps": math.nan, "ehp": 1},
                {"dps": True, "ehp": 1}, [1, 2]):
        with pytest.raises(delta.CalcError):
            delta.outputs(lambda build, swaps, bad=bad: bad, b)

    def boom(build, swaps):
        raise OSError("bridge died")
    with pytest.raises(delta.CalcError, match="OSError"):
        delta.outputs(boom, b)


def test_change_and_pct():
    assert delta.change(100, 112) == {"old": 100, "new": 112, "delta": 12, "pct": 12.0}
    assert delta.change(200, 150)["pct"] == -25.0
    assert delta.change(0, 0)["pct"] == 0.0
    assert delta.change(0, 5)["pct"] is None


def test_item_delta_gloves():
    calc, b = FakeCalc(), _build()
    d = delta.item_delta(calc, b, "Gloves", RARE_GLOVES)
    dps0, ehp0 = _base()
    # new gloves: life 70 (+30), cold 30 (+10), light -10, fire 15, attack speed -12
    ehp1 = ehp0 + 30 * 10 + 10 * 20 - 10 * 20 + 15 * 20
    dps1 = dps0 - 12 * 3
    assert d["dps"] == delta.change(dps0, dps1)
    assert d["ehp"] == delta.change(ehp0, ehp1)
    want = round(0.5 * d["dps"]["pct"] + 0.5 * d["ehp"]["pct"], 4)
    assert d["score_delta"] == want
    assert calc.calls == [{}, {"Gloves": RARE_GLOVES}]


def test_probe_line():
    assert delta.probe_line("+# to maximum Life") == "+10 to maximum Life"
    assert delta.probe_line("#% increased Attack Speed") == "10% increased Attack Speed"
    assert delta.probe_line("Adds # to # Lightning Damage to Attacks") == \
        "Adds 10 to 10 Lightning Damage to Attacks"
    assert delta.probe_line("Cannot be Example Frozen") is None


def test_mod_weights_from_pob_deltas():
    calc, b = FakeCalc(), _build()
    carrier = b.equipped("Gloves").text
    keys = ["+# to maximum Life", "#% increased Attack Speed", "Cannot be Example Frozen",
            "+#% to Chaos Resistance"]
    w = delta.mod_weights(calc, b, "Gloves", carrier, keys)
    dps0, ehp0 = _base()
    life_ehp_pct = 10 * 10 / ehp0 * 100 / 10  # per point
    speed_dps_pct = 10 * 3 / dps0 * 100 / 10
    assert w["weights"]["+# to maximum Life"] == round(0.5 * life_ehp_pct, 6)
    assert w["weights"]["#% increased Attack Speed"] == round(0.5 * speed_dps_pct, 6)
    assert w["weights"]["+#% to Chaos Resistance"] == 0
    assert "Cannot be Example Frozen" not in w["weights"]
    assert w["detail"]["+# to maximum Life"] == {"dps": 0.0, "ehp": round(life_ehp_pct, 6)}
    # one carrier baseline plus one probe per numeric key
    assert len(calc.calls) == 1 + 3
    assert calc.calls[1]["Gloves"].endswith("\n+10 to maximum Life")


def test_mod_weights_blend_and_probe_cap():
    calc, b = FakeCalc(), _build()
    carrier = b.equipped("Gloves").text
    off = delta.mod_weights(calc, b, "Gloves", carrier, ["+# to maximum Life"],
                            blend={"dps": 1.0, "ehp": 0.0})
    assert off["weights"]["+# to maximum Life"] == 0
    keys = [f"+# to Example Stat {i}" for i in range(delta.MAX_PROBES + 5)]
    calc.calls.clear()
    delta.mod_weights(calc, b, "Gloves", carrier, keys)
    assert len(calc.calls) == 1 + delta.MAX_PROBES


# -- evaluate with a calc ---------------------------------------------------

def test_evaluate_with_calc_uses_pob_deltas():
    calc, b = FakeCalc(), _build()
    r = tc_evaluate.evaluate(RARE_GLOVES, b, calc=calc)
    assert r["ok"] and r["calc"]["source"] == "pob" and r["calc"]["notice"] is None
    c = r["comparisons"][0]
    d = delta.item_delta(FakeCalc(), b, "Gloves", RARE_GLOVES)
    assert c["dps"] == d["dps"] and c["ehp"] == d["ehp"]
    assert c["score_delta"] == round(d["score_delta"], 4)
    # +12.7% EHP, -36% DPS blended: a downgrade under the PoB verdict
    assert c["verdict"] == r["verdict"] == "downgrade"
    rows = {s["key"]: s for s in c["stats"]}
    assert rows["#% increased Attack Speed"]["weighted"]
    assert rows["#% increased Attack Speed"]["weight"] > 0
    assert r["mod_weights"]["source"] == "pob"
    assert r["mod_weights"]["slot"] == "Gloves"
    assert "+# to maximum Life" in r["mod_weights"]["weights"]
    # the hand weights are not used once PoB answered
    assert r["unweighted"] == ["Cannot be Example Frozen"]


def test_evaluate_with_calc_ring_picks_best_slot():
    calc, b = FakeCalc(), _build()
    r = tc_evaluate.evaluate(ADVANCED_RING, b, calc=calc)
    assert [c["slot"] for c in r["comparisons"]] == ["Ring 1", "Ring 2"]
    best = max(r["comparisons"], key=lambda c: c["score_delta"])
    assert r["slot"] == best["slot"] == "Ring 1"
    assert r["comparisons"][0]["verdict"] == "upgrade"


def test_sidegrade_band_is_one_percent():
    assert delta.verdict(0.99) == "sidegrade"
    assert delta.verdict(-0.99) == "sidegrade"
    assert delta.verdict(1.01) == "upgrade"
    assert delta.verdict(-1.01) == "downgrade"


def test_component_off_falls_back_with_notice():
    b = _build()
    hand = tc_evaluate.evaluate(RARE_GLOVES, b)
    assert hand["calc"] == {"source": "weights", "notice": "off"}
    assert hand["mod_weights"]["source"] == "hand"
    assert "dps" not in hand["comparisons"][0]
    assert hand["verdict"] == "upgrade"  # the TC-EVAL hand-weight verdict


def test_calc_failure_falls_back_with_notice():
    def broken(build, swaps):
        if swaps:
            raise TimeoutError("bridge timed out")
        return {"dps": 1, "ehp": 1}
    b = _build()
    r = tc_evaluate.evaluate(RARE_GLOVES, b, calc=broken)
    hand = tc_evaluate.evaluate(RARE_GLOVES, b)
    assert r["calc"]["source"] == "weights" and r["calc"]["notice"] == "failed"
    assert r["verdict"] == hand["verdict"] and r["comparisons"] == hand["comparisons"]


def test_calc_not_called_without_build_or_slot():
    calc = FakeCalc()
    assert not tc_evaluate.evaluate(RARE_GLOVES, None, calc=calc)["ok"]
    assert not tc_evaluate.evaluate(JEWEL, _build(), calc=calc)["ok"]
    assert not tc_evaluate.evaluate("hello", _build(), calc=calc)["ok"]
    assert calc.calls == []


def test_empty_slot_probes_on_the_checked_item():
    calc = FakeCalc()
    b = _build(EVAL_BUILD_XML.replace(GLOVES_SLOT, ""))
    r = tc_evaluate.evaluate(RARE_GLOVES, b, calc=calc)
    c = r["comparisons"][0]
    assert c["empty"] and r["calc"]["source"] == "pob"
    assert c["ehp"]["delta"] > 0
    assert any(call.get("Gloves", "").startswith(RARE_GLOVES.rstrip("\n")) and
               call["Gloves"] != RARE_GLOVES for call in calc.calls)


# -- TC-UPGRADE gets the weights --------------------------------------------

def test_upgrade_doc_carries_the_weights_source():
    b = _build()
    pob = upgrade.link(tc_evaluate.evaluate(RARE_GLOVES, b, calc=FakeCalc()))
    assert pob["weights"]["source"] == "pob"
    keys = [w["key"] for w in pob["weights"]["top"]]
    assert keys[0] == "#% increased Attack Speed"
    assert all(w["weight"] > 0 for w in pob["weights"]["top"])
    assert len(keys) <= upgrade.MAX_TOP
    hand = upgrade.link(tc_evaluate.evaluate(RARE_GLOVES, b))
    assert hand["weights"]["source"] == "hand"
    assert hand["weights"]["top"][0] == {"key": "#% increased Attack Speed", "weight": 2}


# -- live: recompute on change, card text -----------------------------------

class _State:
    def __init__(self):
        self.eval = None

    def set_eval(self, card, keep_time=False, at=None):
        self.eval = card


class _Builds:
    def __init__(self, build):
        self.build = build


class _Weights:
    def get(self):
        return None


def test_live_reruns_with_the_calc_and_without():
    st = _State()
    calc = FakeCalc()
    last = live.LastEval(_Builds(_build()), _Weights(), st, calc=lambda: calc)
    last.run(RARE_GLOVES)
    card = st.eval
    assert card["calc"]["source"] == "pob"
    assert card["comparisons"][0]["dps"]["pct"] == -36.0
    assert card["upgrade"]["weights"]["source"] == "pob"
    n = len(calc.calls)
    last.rerun()  # build or weights change: recompute, no click
    assert len(calc.calls) == 2 * n
    last.calc = lambda: None  # component switched off
    last.rerun()
    assert st.eval["calc"] == {"source": "weights", "notice": "off"}


def test_card_text_pob_and_notices():
    st = _State()
    live.LastEval(_Builds(_build()), _Weights(), st, calc=lambda: FakeCalc()).run(RARE_GLOVES)
    t = eval_card_text(st.eval)
    assert t["calc"] == "Path of Building: DPS -36% (from 100 to 64), EHP +12.7% " \
                        "(from 4720 to 5320), with this item in Gloves."
    assert t["line"] == "DPS -36%, EHP +12.7%"
    zero = dict(st.eval, comparisons=[dict(st.eval["comparisons"][0],
                                           dps={"old": 0, "new": 64, "pct": None})])
    assert eval_card_text(zero)["line"] == "DPS unknown, EHP +12.7%"
    st2 = _State()
    live.LastEval(_Builds(_build()), _Weights(), st2).run(RARE_GLOVES)
    t2 = eval_card_text(st2.eval)
    assert t2["calc"] == ("Scored with your stat weights. To see DPS and EHP, turn on the "
                          "optional Path of Building calc in AshLight's settings file.")
    assert t2["line"] == "+30 to maximum Life"
    failed = dict(st2.eval, calc={"source": "weights", "notice": "failed"})
    assert eval_card_text(failed)["calc"] == (
        "Scored with your stat weights. DPS and EHP are not shown because Path of "
        "Building could not be reached. Try the check again.")
    assert eval_card_text({"ok": False, "error": "not an item"})["calc"] == ""
