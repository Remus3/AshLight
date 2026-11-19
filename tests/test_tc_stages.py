"""TC-PRESS-STAGED-EVAL: evaluate() in all-or-nothing stages.

evaluate.stages() yields (name, result) pairs: "weights" (no calc call),
"pob" (PoB's DPS / EHP deltas) and "mods" (the per-mod probes). Every
result has evaluate()'s shape; the last one equals evaluate(). A calc error
after stage 1 ends the generator with the weights result and its notice.
Synthetic fixtures and the fake calc of test_tc_delta only."""

import pytest

from server.al.theorycraft import delta
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import item as item_parser
from server.al.theorycraft import model
from server.al.theorycraft import pobweights as pw
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, JEWEL, RARE_GLOVES

# private copies of the test_tc_delta fake calc (a test file never imports another)
GLOVES_SLOT = '\t\t\t<Slot name="Gloves" itemId="1"/>\n'
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


def _run(item, build, **kw):
    return list(tc_evaluate.stages(item, build, **kw))


def _names(stages):
    return [name for name, _r in stages]


class _FailAfter(FakeCalc):
    """FakeCalc that raises once it has answered `n` calls."""

    def __init__(self, n, exc=OSError("bridge died")):
        super().__init__()
        self.n, self.exc = n, exc

    def __call__(self, build, swaps):
        if len(self.calls) >= self.n:
            self.calls.append(dict(swaps))
            raise self.exc
        return super().__call__(build, swaps)


class _NegativeOnSwap(FakeCalc):
    def __call__(self, build, swaps):
        got = super().__call__(build, swaps)
        return dict(got, dps=-1.0) if swaps else got


# -- names and shape --------------------------------------------------------

@pytest.mark.parametrize("item", [RARE_GLOVES, ADVANCED_RING])
def test_stage_names_in_order(item):
    got = _run(item, _build(), calc=FakeCalc())
    assert _names(got) == ["weights", "pob", "mods"]
    assert tuple(_names(got)) == tc_evaluate.STAGES


def test_each_stage_is_a_full_evaluate_result():
    b = _build()
    final = tc_evaluate.evaluate(RARE_GLOVES, b, calc=FakeCalc())
    got = dict(_run(RARE_GLOVES, b, calc=FakeCalc()))
    for name, r in got.items():
        assert set(r) == set(final), name
        assert r["ok"] and r["slot"] == "Gloves" and r["slots"] == ["Gloves"]
        assert r["item"] == final["item"] and r["potential"] is not None or \
            final["potential"] is None
    w, p, m = got["weights"], got["pob"], got["mods"]
    hand = tc_evaluate.evaluate(RARE_GLOVES, b)
    # stage 1: the hand weights, calc pending (no notice), no PoB numbers
    assert w["calc"] == {"source": "weights", "notice": None}
    assert w["mod_weights"]["source"] == "hand"
    assert w["comparisons"] == hand["comparisons"] and w["verdict"] == hand["verdict"]
    assert "dps" not in w["comparisons"][0]
    # stage 2: PoB's deltas and verdict, the per-mod rows still hand-weighted
    assert p["calc"] == {"source": "pob", "notice": None}
    assert p["mod_weights"] == hand["mod_weights"]
    assert p["comparisons"][0]["dps"] == m["comparisons"][0]["dps"]
    assert p["comparisons"][0]["ehp"] == m["comparisons"][0]["ehp"]
    assert p["verdict"] == m["verdict"] == "downgrade"
    assert p["score_delta"] == m["score_delta"]
    assert p["score"] == hand["score"] and p["unweighted"] == hand["unweighted"]
    # stage 3: the PoB per-mod weights
    assert m["mod_weights"]["source"] == "pob"
    assert m == final


def test_stage_results_are_independent():
    gen = tc_evaluate.stages(RARE_GLOVES, _build(), calc=FakeCalc())
    _n, first = next(gen)
    first["comparisons"][0]["stats"].clear()
    first["mod_weights"]["weights"].clear()
    rest = dict(gen)
    assert rest["pob"]["comparisons"][0]["stats"]
    assert rest["pob"]["mod_weights"]["weights"]
    assert rest["mods"] == tc_evaluate.evaluate(RARE_GLOVES, _build(), calc=FakeCalc())


def test_calc_off_or_no_build_slot_item_is_one_weights_stage():
    calc = FakeCalc()
    for item, b, c in ((RARE_GLOVES, _build(), None), (RARE_GLOVES, None, calc),
                       (JEWEL, _build(), calc), ("hello", _build(), calc)):
        got = _run(item, b, calc=c)
        assert _names(got) == ["weights"]
        assert got[0][1] == tc_evaluate.evaluate(item, b, calc=c)
    assert calc.calls == []


# -- calc errors ------------------------------------------------------------

def test_calc_error_in_the_pob_stage_ends_with_the_weights_result():
    def broken(build, swaps):
        if swaps:
            raise TimeoutError("bridge timed out")
        return {"dps": 1, "ehp": 1}
    b = _build()
    got = _run(RARE_GLOVES, b, calc=broken)
    assert _names(got) == ["weights", "weights"]
    last = got[-1][1]
    assert last["calc"] == {"source": "weights", "notice": "failed"}
    hand = tc_evaluate.evaluate(RARE_GLOVES, b)
    assert last["comparisons"] == hand["comparisons"] and last["verdict"] == hand["verdict"]
    assert last == tc_evaluate.evaluate(RARE_GLOVES, b, calc=broken)


def test_calc_error_in_the_mods_stage_ends_with_the_weights_result():
    b = _build()
    # base outputs + one item delta succeed, the first probe fails
    got = _run(RARE_GLOVES, b, calc=_FailAfter(2))
    assert _names(got) == ["weights", "pob", "weights"]
    last = got[-1][1]
    assert last["calc"] == {"source": "weights", "notice": "failed"}
    assert last["mod_weights"]["source"] == "hand"
    assert "dps" not in last["comparisons"][0]
    assert last == tc_evaluate.evaluate(RARE_GLOVES, b, calc=_FailAfter(2))


def test_implausible_numbers_end_with_the_weights_result_and_notice():
    b = _build()
    got = _run(RARE_GLOVES, b, calc=_NegativeOnSwap())
    assert _names(got) == ["weights", "weights"]
    assert got[-1][1]["calc"] == {"source": "weights", "notice": "implausible"}
    assert got[-1][1] == tc_evaluate.evaluate(RARE_GLOVES, b, calc=_NegativeOnSwap())


def test_calc_error_with_a_cache_scores_with_the_cached_pob_weights():
    b = _build()
    cache = pw.PobWeightCache()
    tc_evaluate.evaluate(RARE_GLOVES, b, calc=FakeCalc(), cache=cache)
    got = _run(RARE_GLOVES, b, calc=_FailAfter(0), cache=cache)
    assert _names(got) == ["weights", "weights"]
    # stage 1 already scores with this build's measured weights
    assert got[0][1]["calc"] == {"source": "pob_cached", "notice": None}
    assert got[-1][1]["calc"] == {"source": "pob_cached", "notice": "failed"}


# -- last stage equals evaluate() ------------------------------------------

def _calcs():
    def broken(build, swaps):
        if swaps:
            raise TimeoutError("bridge timed out")
        return {"dps": 1, "ehp": 1}
    return {"off": lambda: None, "pob": FakeCalc, "broken": lambda: broken,
            "probe_fails": lambda: _FailAfter(2)}


@pytest.mark.parametrize("calc_kind", sorted(_calcs()))
@pytest.mark.parametrize("item", [RARE_GLOVES, ADVANCED_RING, JEWEL, "hello"])
@pytest.mark.parametrize("xml", [EVAL_BUILD_XML, EVAL_BUILD_XML.replace(GLOVES_SLOT, ""),
                                 None])
@pytest.mark.parametrize("cached", [False, True])
def test_last_stage_equals_evaluate(calc_kind, item, xml, cached):
    make = _calcs()[calc_kind]

    def cache():
        if not cached:
            return None
        c = pw.PobWeightCache()
        if xml is not None:  # this build's weights measured earlier
            tc_evaluate.evaluate(item, _build(xml), calc=FakeCalc(), cache=c)
        return c
    b = None if xml is None else _build(xml)
    got = _run(item, b, calc=make(), cache=cache())
    want = tc_evaluate.evaluate(item, None if xml is None else _build(xml), calc=make(),
                                cache=cache())
    assert got[-1][1] == want
    assert _names(got)[0] == "weights"


def test_explicit_slot_and_blend_pass_through():
    b = _build()
    blend = {"dps": 1.0, "ehp": 0.0}
    got = _run(RARE_GLOVES, b, slot="Gloves", calc=FakeCalc(), blend=blend)
    assert got[-1][1] == tc_evaluate.evaluate(RARE_GLOVES, b, slot="Gloves",
                                              calc=FakeCalc(), blend=blend)
    assert got[-1][1]["score_delta"] == -36.0


# -- closing early ----------------------------------------------------------

def test_closing_after_the_weights_stage_makes_no_calc_call():
    calc = FakeCalc()
    gen = tc_evaluate.stages(RARE_GLOVES, _build(), calc=calc)
    assert next(gen)[0] == "weights"
    gen.close()
    assert calc.calls == []


def test_closing_after_the_pob_stage_makes_no_probe():
    calc = FakeCalc()
    gen = tc_evaluate.stages(ADVANCED_RING, _build(), calc=calc)
    assert [next(gen)[0], next(gen)[0]] == ["weights", "pob"]
    # the base outputs and one item delta per ring slot, no probe
    assert calc.calls == [{}, {"Ring 1": ADVANCED_RING}, {"Ring 2": ADVANCED_RING}]
    gen.close()
    assert len(calc.calls) == 3
    with pytest.raises(StopIteration):
        next(gen)


def test_stages_never_raise_on_calc_errors():
    for exc in (OSError("x"), delta.CalcError("x"), delta.CalcImplausible("x")):
        for n in range(4):
            got = _run(ADVANCED_RING, _build(), calc=_FailAfter(n, exc))
            assert got[-1][1]["ok"]
            assert got[-1][1]["calc"]["source"] == "weights"
