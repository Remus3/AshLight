"""MATH-WEAPON-TYPE (decision 0032 amendment): when Path of Building itself
reports that the build's main skill cannot use the checked weapon (PoB's
own disableReason, read through the bridge's "main_skill" command), the card
says "Your main skill can't use this weapon type" as a real downgrade, not
PoB's -100 % DPS number and not the "numbers don't add up" fallback. The
sanity fallback stays for every other 0 DPS / nonsense answer. Unit legs
use fakes; the live leg skips without the calc component."""

import pytest

from server.al.state import eval_card_text
from server.al.theorycraft import calcwire, delta
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import model
from tc_live_util import LIVE, reference
from test_math_compare import ONE_HAND, _weapons_xml

MAIN_HAND = "Main Hand weapon is not usable with this skill"
UNUSABLE = {"skill": "Ice Shot", "reason": MAIN_HAND}


class SkillBridge:
    """A bridge double whose main skill PoB disables while a weapon slot
    holds the swapped item."""

    def __init__(self, reason=MAIN_HAND, name="Ice Shot", has_main_skill=True):
        self.reason, self.name = reason, name
        self.swapped = []
        self.asked = 0
        if not has_main_skill:
            self.main_skill = None

    def load_build(self, xml):
        self.swapped = []

    def set_item(self, text, slot=None):
        self.swapped.append(slot)

    def outputs(self, keys=None):
        return {"FullDPS": 0.0 if self.swapped else 500.0, "Life": 1000.0}

    def main_skill(self):
        self.asked += 1
        if not self.swapped:
            return {"found": True, "disabled": False, "name": self.name}
        return {"found": True, "disabled": True, "reason": self.reason, "name": self.name}


def _build():
    return model.parse(_weapons_xml("Example Shield"))


# -- calcwire: PoB's reason becomes a neutral flag on the calc answer -------

def test_calcwire_flags_a_weapon_the_main_skill_cannot_use():
    b = SkillBridge()
    calc = calcwire.make_calc(lambda: b)
    assert calc(_build(), {}) == {"dps": 500.0, "ehp": 1000.0}
    assert b.asked == 0  # no swap: nothing to ask
    got = calc(_build(), {"Weapon 1": ONE_HAND})
    assert got == {"dps": 0.0, "ehp": 1000.0, "weapon_unusable": UNUSABLE}


@pytest.mark.parametrize("reason", [
    "Off Hand weapon is not usable with this skill",
    "No usable weapon equipped",
    "Weapon Types Need to be Different",
])
def test_calcwire_knows_every_pob_weapon_reason(reason):
    calc = calcwire.make_calc(lambda: SkillBridge(reason=reason))
    got = calc(_build(), {"Weapon 2": ONE_HAND})
    assert got["weapon_unusable"] == {"skill": "Ice Shot", "reason": reason}


def test_calcwire_ignores_other_reasons_other_slots_and_old_bridges():
    other = SkillBridge(reason="Skills of this type are disabled")
    assert "weapon_unusable" not in calcwire.make_calc(lambda: other)(
        _build(), {"Weapon 1": ONE_HAND})
    gloves = SkillBridge()
    assert "weapon_unusable" not in calcwire.make_calc(lambda: gloves)(
        _build(), {"Gloves": "x"})
    assert gloves.asked == 0  # only a weapon swap asks PoB about the skill
    old = SkillBridge(has_main_skill=False)
    assert "weapon_unusable" not in calcwire.make_calc(lambda: old)(
        _build(), {"Weapon 1": ONE_HAND})


# -- delta: a flagged swap is its own CalcError, not "implausible" ----------

def test_item_delta_raises_weapon_unusable_with_the_skill_name():
    def calc(build, swaps):
        if swaps:
            return {"dps": 0, "ehp": 900, "weapon_unusable": UNUSABLE}
        return {"dps": 500, "ehp": 1000}
    with pytest.raises(delta.CalcWeaponUnusable) as err:
        delta.item_delta(calc, _build(), "Weapon 1", ONE_HAND)
    assert not isinstance(err.value, delta.CalcImplausible)
    assert err.value.skill == "Ice Shot"
    # the plain 0 DPS sanity guard is unchanged
    with pytest.raises(delta.CalcImplausible):
        delta.item_delta(lambda b, s: {"dps": 0 if s else 500, "ehp": 1000},
                         _build(), "Weapon 1", ONE_HAND)


def test_p4_5_the_swapped_items_flag_decides_alone():
    """AREA-AUDIT P4-5: calcwire asks PoB's main_skill only after a weapon
    swap, so the base never carries weapon_unusable and _swap_sane no longer
    tests the base for it. A swap PoB flags raises CalcWeaponUnusable
    whatever the base holds; a base flag alone never does."""
    flagged = {"dps": 0, "ehp": 900, "weapon_unusable": UNUSABLE}
    for base in ({"dps": 500, "ehp": 1000},
                 {"dps": 500, "ehp": 1000, "weapon_unusable": UNUSABLE}):
        with pytest.raises(delta.CalcWeaponUnusable):
            delta._swap_sane(base, flagged)
    delta._swap_sane({"dps": 500, "ehp": 1000, "weapon_unusable": UNUSABLE},
                     {"dps": 450, "ehp": 1000})


def _unusable_calc(slots=("Weapon 1", "Weapon 2")):
    def calc(build, swaps):
        if any(s in slots for s in swaps):
            return {"dps": 0, "ehp": 1000, "weapon_unusable": UNUSABLE}
        return {"dps": 500 + 10 * len(swaps), "ehp": 1000}
    return calc


def test_evaluate_gives_a_downgrade_with_the_weapon_type_notice():
    b = model.parse(_weapons_xml("Example Wand"))  # dual wield: both hands
    r = tc_evaluate.evaluate(ONE_HAND, b, calc=_unusable_calc())
    assert r["ok"] and r["verdict"] == "downgrade"
    assert r["calc"] == {"source": "pob", "notice": "weapon_type"}
    assert [c["slot"] for c in r["comparisons"]] == ["Weapon 1", "Weapon 2"]
    for c in r["comparisons"]:
        assert c["verdict"] == "downgrade"
        assert c["weapon_unusable"] == {"skill": "Ice Shot"}
        assert "dps" not in c and "ehp" not in c  # no -100 % number


def test_evaluate_prefers_a_hand_the_skill_can_use():
    b = model.parse(_weapons_xml("Example Wand"))
    r = tc_evaluate.evaluate(ONE_HAND, b, calc=_unusable_calc(slots=("Weapon 1",)))
    assert r["slot"] == "Weapon 2" and r["calc"] == {"source": "pob", "notice": None}
    w1 = next(c for c in r["comparisons"] if c["slot"] == "Weapon 1")
    assert w1["weapon_unusable"] and w1["verdict"] == "downgrade"


# -- card text -------------------------------------------------------------

HEAD = "Downgrade - wrong weapon type"
LINE = "Main skill can't use this weapon"
CALC = ("Your main skill can't use this weapon type, so this item is a downgrade "
        "for this build. Path of Building counts no damage from Ice Shot with it "
        "in Weapon 1.")
COMP = "Downgrade: your main skill can't use this weapon type in Weapon 1 (Main Twig)."


def test_card_says_the_main_skill_cannot_use_this_weapon_type():
    r = tc_evaluate.evaluate(ONE_HAND, _build(), calc=_unusable_calc())
    t = eval_card_text(r)
    assert t["head"] == HEAD and len(HEAD) <= 34
    assert t["line"] == LINE and len(LINE) <= 34
    assert t["calc"] == CALC
    assert t["sentence"] == COMP
    assert t["comparisons"][0]["sentence"] == COMP
    assert t["comparisons"][0]["calc"] == ""
    assert "-100" not in " ".join(str(v) for v in t.values())
    assert "don't add up" not in t["calc"]


def test_card_without_a_skill_name_still_reads():
    r = tc_evaluate.evaluate(ONE_HAND, _build(), calc=_unusable_calc())
    r["comparisons"][0]["weapon_unusable"] = {"skill": None}
    assert eval_card_text(r)["calc"].endswith(
        "counts no damage from that skill with it in Weapon 1.")


# -- live: the pinned PoB really reports it (bow build, wand swap) ----------

WAND = """Item Class: Wands
Rarity: Rare
Grim Song
Withered Wand
--------
Item Level: 70
--------
+50 to maximum Mana
"""


@LIVE
@pytest.mark.slow
def test_live_bow_build_cannot_use_a_wand(warm_bridge):
    ref = reference()
    if ref is None:
        pytest.skip("PoB GUI reference build absent (sidecar Cache\\tc_bridge)")
    build = model.parse(ref[1])
    calc = calcwire.make_calc(lambda: warm_bridge)
    got = calc(build, {"Weapon 1": WAND})
    assert got["weapon_unusable"]["reason"] == MAIN_HAND
    assert got["weapon_unusable"]["skill"]
    r = tc_evaluate.evaluate(WAND, build, calc=calc, slot="Weapon 1")
    assert r["verdict"] == "downgrade"
    assert r["calc"] == {"source": "pob", "notice": "weapon_type"}
