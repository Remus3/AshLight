"""TC-WORN-BASELINE (decision 0052): the build's plan line of a worn compare.

A card part (TC-CARD-PARTS). With a worn-gear store the item check
compares against the item the player wears first and the build's planned
item second (theorycraft/worngear.Baseline, evaluate(baseline=...)). When
the headline slot was answered by the worn item and the loaded build plans
an item there too, evaluate() puts that second check in result["plan"];
this part turns it into one dashboard note, the card's second line:
"Against your build's plan: an upgrade over its Ring 1 (Ruby Ring)."
It never changes the word, tone, head or overlay line: the verdict
against the worn item stays the card's.

Value: {"slot", "verdict", "name"} or None (no worn compare, no plan item
in that slot, or a result that is not ok). AshLight's own words only;
nothing here reads the clipboard or sends anything anywhere.
"""

NAME = "worn"
ORDER = 30  # after keep (20): an item part
NAME_MAX = 40  # characters of an item name kept in the note

PLAN_NOTE = {
    "upgrade": "Against your build's plan: an upgrade over its {slot} ({name}).",
    "downgrade": "Against your build's plan: a downgrade from its {slot} ({name}).",
    "sidegrade": "Against your build's plan: about the same as its {slot} ({name}).",
}
UNNAMED = "an unnamed item"


def _text(value, cap=NAME_MAX):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    if not value or not value.isascii():
        return None
    return value[:cap]


def compute(ctx):
    result = ctx.get("result") if isinstance(ctx, dict) else None
    if not isinstance(result, dict) or not result.get("ok"):
        return None
    plan = result.get("plan")
    if not isinstance(plan, dict) or plan.get("verdict") not in PLAN_NOTE:
        return None
    slot = _text(plan.get("slot"))
    if slot is None:
        return None
    eq = plan.get("equipped") if isinstance(plan.get("equipped"), dict) else {}
    return {"slot": slot, "verdict": plan["verdict"],
            "name": _text(eq.get("name")) or _text(eq.get("base"))}


def note(value):
    """The plan line for a part value, or None."""
    if not isinstance(value, dict) or value.get("verdict") not in PLAN_NOTE:
        return None
    slot = _text(value.get("slot"))
    if slot is None:
        return None
    return PLAN_NOTE[value["verdict"]].format(slot=slot,
                                              name=_text(value.get("name")) or UNNAMED)


def words(value, card, out):
    line = note(value)
    if line:
        out["notes"].append(line)
