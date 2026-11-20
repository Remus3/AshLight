"""TC-WORN-BASELINE (decision 0052): the item check compares against the
worn item first and the build's plan second.

Synthetic item texts only (tests/tc_eval_fixtures.py and the ones below);
no clipboard, no network, no game process, every file under tmp_path.
"""

import copy

import pytest

from server.al.state import eval_card_text
from server.al.theorycraft import cardparts
from server.al.theorycraft import evaluate as ev
from server.al.theorycraft import live, model
from server.al.theorycraft import worngear as wg
from server.al.theorycraft.cardparts import keep as keep_part
from server.al.theorycraft.cardparts import worn as worn_part
from server.al.theorycraft import item as item_parser
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, JEWEL, RARE_GLOVES

# fake PoB (as tests/test_tc_delta.py): per-point effect of a stat
DPS_PER = {"adds # to # lightning damage to attacks": 2.0, "#% increased attack speed": 3.0}
EHP_PER = {"+# to maximum life": 10.0, "+#% to cold resistance": 20.0,
           "+#% to lightning resistance": 20.0, "+#% to fire resistance": 20.0}


class FakeCalc:
    """dps / ehp linear in the summed stats of the gear after the swaps;
    counts calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, build, swaps):
        self.calls.append(dict(swaps))
        gear = {slot: it.text for slot, it in build.gear.items()}
        gear.update(swaps)
        dps, ehp = 100.0, 1000.0
        for text in gear.values():
            for key, value in ev.stats_of(item_parser.parse(text)).items():
                dps += DPS_PER.get(key.lower(), 0) * value
                ehp += EHP_PER.get(key.lower(), 0) * value
        return {"dps": dps, "ehp": ehp}


def _ring(name, base, life, extra=""):
    return ("Item Class: Rings\nRarity: Rare\n%s\n%s\n--------\n"
            "Item Level: 70\n--------\n+%d to maximum Life\n%s" % (name, base, life, extra))


RING_A = _ring("Alpha Loop", "Ruby Ring", 40)
RING_B = _ring("Beta Loop", "Sapphire Ring", 90)
RING_WEAK = _ring("Weak Loop", "Iron Ring", 5)
GLOVES_30 = ("Item Class: Gloves\nRarity: Rare\nTest Piece\nPlain Base\n--------\n"
             "Item Level: 40\n--------\n+12 to maximum Life\n+9% to Fire Resistance\n")


@pytest.fixture(autouse=True)
def fresh_parts():
    cardparts.reset()
    yield
    cardparts.reset()


class _State:
    def __init__(self, character="Tester", level=None):
        self.eval = None
        self.character = character
        self.level = level
        self.upgrades = None

    def set_eval(self, card, keep_time=False, at=None):
        self.eval = card

    def set_upgrades(self, view):
        self.upgrades = view


class _Builds:
    def __init__(self, build=None):
        self.build = build


class _Weights:
    def get(self):
        return None


def _store(tmp_path):
    return wg.WornGear(tmp_path / wg.FILE_NAME)


def _build():
    return model.parse(EVAL_BUILD_XML)


def _last(tmp_path, build=None, level=None, calc=None):
    st = _State(level=level)
    last = live.LastEval(_Builds(build), _Weights(), st, worn=_store(tmp_path),
                         calc=(lambda: calc) if calc is not None else None)
    return st, last


# -- no build: the worn item is the baseline ----------------------------------

def test_no_build_wear_then_check_names_the_worn_base(tmp_path):
    st, last = _last(tmp_path)
    r = last.run(RING_A)
    assert not r["ok"] and r["error"] == "no build loaded"
    assert last.wear_last() == "Ring 1"
    r = last.run(RING_B)
    assert r["ok"] and r["error"] is None and r["build_loaded"] is False
    # only the worn slot is compared: an unknown slot is not an empty one
    assert [c["slot"] for c in r["comparisons"]] == ["Ring 1"]
    c = r["comparisons"][0]
    assert c["source"] == "worn" and not c["empty"]
    assert c["equipped"] == {"name": None, "base": "Ruby Ring", "rarity": "RARE"}
    assert r["slot"] == "Ring 1" and r["verdict"] == "upgrade"
    assert r["plan"] is None
    assert st.eval["comparisons"][0]["equipped"]["base"] == "Ruby Ring"
    t = eval_card_text(st.eval)
    assert t["head"].startswith("Upgrade") and "Ring 1" in t["head"]
    assert "Ruby Ring" in t["sentence"]
    assert not any(n.startswith("Against your build's plan") for n in t["notes"])


def test_wear_last_with_given_text_and_slot(tmp_path):
    _st, last = _last(tmp_path)
    assert last.wear_last() is None  # nothing checked yet
    assert last.wear_last(slot="Ring 2", text=RING_A) == "Ring 2"
    assert last.worn.entry("Tester", "Ring 2")["base"] == "Ruby Ring"
    assert last.wear_last(text=JEWEL) is None
    r = last.run(RING_B)
    assert [c["slot"] for c in r["comparisons"]] == ["Ring 2"]


def test_wear_last_files_in_the_compared_slot(tmp_path):
    _st, last = _last(tmp_path, build=_build())
    r = last.run(ADVANCED_RING)
    assert r["slot"] == "Ring 1"
    assert last.wear_last() == r["slot"]


def test_no_worn_store_wear_last_is_none(tmp_path):
    last = live.LastEval(_Builds(None), _Weights(), _State())
    last.run(RING_A)
    assert last.wear_last() is None and last.baseline() is None


def test_no_build_and_nothing_worn_for_the_slot_stays_no_build_loaded(tmp_path):
    _st, last = _last(tmp_path)
    last.wear_last(text=RING_A)
    r = last.run(RARE_GLOVES)
    assert not r["ok"] and r["error"] == "no build loaded"
    base = wg.Baseline(_store(tmp_path), "Tester", None)
    r = ev.evaluate(RARE_GLOVES, None, baseline=base)
    assert r["error"] == "no build loaded" and "plan" not in r
    # another character's worn ring is not this one's baseline
    r = ev.evaluate(RING_B, None, baseline=wg.Baseline(_store(tmp_path), "Other", None))
    assert r["error"] == "no build loaded"


def test_keep_part_yields_once_a_worn_item_exists(tmp_path):
    st, last = _last(tmp_path, level=30)
    last.run(GLOVES_30)
    assert keep_part.NAME in st.eval["parts"]
    last.wear_last(text=RARE_GLOVES)
    last.run(GLOVES_30)
    assert st.eval["ok"] and keep_part.NAME not in st.eval["parts"]
    assert st.eval["comparisons"][0]["slot"] == "Gloves"


def test_no_build_with_calc_on_is_not_left_pending(tmp_path):
    calc = FakeCalc()
    st = _State()
    last = live.LastEval(_Builds(None), _Weights(), st, worn=_store(tmp_path),
                         calc=lambda: calc, staged=True)
    try:
        last.wear_last(text=RING_A)
        r = last.run(RING_B)
        assert last.wait(5)
        assert r["ok"] and calc.calls == []
        assert "stage" not in st.eval["parts"]
    finally:
        last.close()


def test_rescore_uses_the_baseline(tmp_path):
    st, last = _last(tmp_path)
    last.wear_last(text=RING_B, slot="Ring 1")
    assert last.run(RING_A)["verdict"] == "downgrade"
    assert st.upgrades["items"] == []
    last.wear_last(text=RING_WEAK, slot="Ring 1")
    assert [n["replaces"] for n in st.upgrades["items"]] == ["Iron Ring"]


# -- with a build: worn first, the plan as the second line --------------------

def test_with_build_the_card_carries_both_lines(tmp_path):
    st, last = _last(tmp_path, build=_build())
    last.wear_last(slot="Ring 1", text=RING_WEAK)
    r = last.run(RING_B, slot="Ring 1")
    assert r["ok"] and r["build_loaded"]
    c = r["comparisons"][0]
    assert c["source"] == "worn" and c["equipped"]["base"] == "Iron Ring"
    assert r["verdict"] == "upgrade"
    plan = r["plan"]
    assert plan["slot"] == "Ring 1" and plan["source"] == "weights"
    assert plan["equipped"]["name"] == model.parse(EVAL_BUILD_XML).equipped("Ring 1").name
    assert st.eval["parts"][worn_part.NAME]["slot"] == "Ring 1"
    t = eval_card_text(st.eval)
    assert "Iron Ring" in t["sentence"]
    line = worn_part.note(st.eval["parts"][worn_part.NAME])
    assert line in t["notes"]
    assert line.startswith("Against your build's plan: ")
    assert line.isascii() and len(line.split()) <= 20 and "!" not in line


def test_plan_line_words_exact():
    v = {"slot": "Ring 1", "verdict": "upgrade", "name": "Storm Loop"}
    assert worn_part.note(v) == "Against your build's plan: an upgrade over its Ring 1 (Storm Loop)."
    v["verdict"] = "downgrade"
    assert worn_part.note(v) == "Against your build's plan: a downgrade from its Ring 1 (Storm Loop)."
    v.update(verdict="sidegrade", name=None)
    assert worn_part.note(v) == ("Against your build's plan: about the same as its Ring 1 "
                                 "(an unnamed item).")
    assert worn_part.note({"slot": "Ring 1", "verdict": "bogus"}) is None
    assert worn_part.compute({"result": {"ok": True, "plan": None}}) is None


def test_plan_slot_without_worn_item_has_no_plan_line(tmp_path):
    base = wg.Baseline(_store(tmp_path), "Tester", _build())
    r = ev.evaluate(RARE_GLOVES, _build(), baseline=base)
    assert r["ok"] and r["comparisons"][0]["source"] == "plan" and r["plan"] is None


def test_with_calc_worn_slot_measured_from_the_worn_swap(tmp_path):
    store = _store(tmp_path)
    store.wear("Tester", RING_WEAK, slot="Ring 1")
    b = _build()
    calc = FakeCalc()
    r = ev.evaluate(RING_B, b, calc=calc, slot="Ring 1",
                    baseline=wg.Baseline(store, "Tester", b))
    assert r["calc"]["source"] == "pob"
    c = r["comparisons"][0]
    worn_text = store.item("Tester", "Ring 1").text
    assert {"Ring 1": worn_text} in calc.calls
    # 90 life vs the worn 5 life: +850 EHP from the worn swap
    assert c["ehp"]["delta"] == 850
    plan = r["plan"]
    plan_d = ev.delta_mod.item_delta(FakeCalc(), b, "Ring 1", RING_B)
    assert plan["source"] == "pob" and plan["ehp"] == plan_d["ehp"]
    assert plan["score_delta"] == round(plan_d["score_delta"], 4)


# -- without a baseline nothing changes ---------------------------------------

@pytest.mark.parametrize("text", [RARE_GLOVES, ADVANCED_RING, JEWEL])
@pytest.mark.parametrize("with_calc", [False, True])
def test_without_baseline_unchanged(text, with_calc):
    b = _build()
    kw = {"calc": FakeCalc()} if with_calc else {}
    a = ev.evaluate(text, b, **copy.deepcopy(kw))
    kw2 = {"calc": FakeCalc()} if with_calc else {}
    z = ev.evaluate(text, b, baseline=None, **kw2)
    assert a == z
    assert "plan" not in a and all("source" not in c for c in a["comparisons"])
    assert ev.evaluate(text, None) == ev.evaluate(text, None, baseline=None)


def test_empty_baseline_with_build_matches_no_baseline_but_marks(tmp_path):
    b = _build()
    base = wg.Baseline(_store(tmp_path), "Tester", b)
    a = ev.evaluate(ADVANCED_RING, b)
    z = ev.evaluate(ADVANCED_RING, b, baseline=base)
    assert z.pop("plan") is None
    for c in z["comparisons"]:
        assert c.pop("source") == "plan"
    assert a == z
