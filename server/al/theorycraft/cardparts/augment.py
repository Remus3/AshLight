"""TC-AUGMENT-WHATIF (research 0064 G4, decision 0093): the item check
card's augment and quality what-if lines.

A card part (TC-CARD-PARTS). The press's last stage, "augment"
(theorycraft/augment.py, run from evaluate.stages() on the stage worker),
puts result["augment"] on the result: the augment Path of Building ranks
best for a free socket of the pressed item, and the item's DPS / EHP at 20
percent quality. This part turns it into dashboard notes; it never changes
the word, tone, head or overlay line, and never shows a price (decision
0017).

Value, or None:
- {"state": "ready", "best": {"name", "dps", "ehp"} or None, "tried": n,
  "socket": bool, "quality": {"to", "dps", "ehp"} or None}
- {"state": "failed"}: the calc failed during the stage.
- {"state": "needs_calc"}: the calc is off and the item has augment or
  quality room; one sentence says the calc is needed. Never guessed.
While the stage is pending (state "pending") the stage part's note shows
and this part adds nothing. With no pinned augment data nothing shows.

Words: server/al/text/augment.py (copy sheet docs/design/copy/augment.md).
Nothing here reads the clipboard or sends anything anywhere.
"""

from ...text import augment as words_mod
from .. import augment as augment_mod
from .. import delta as delta_mod

NAME = "augment"
ORDER = 40  # after worn (30): an item part
NEEDS_CALC = "needs_calc"


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 2)


def _row(row, keys):
    if not isinstance(row, dict):
        return None
    out = {k: _num(row.get(k)) for k in keys}
    return out


def compute(ctx):
    result = ctx.get("result") if isinstance(ctx, dict) else None
    if not isinstance(result, dict) or not result.get("ok"):
        return None
    aug = result.get("augment")
    if isinstance(aug, dict):
        state = aug.get("state")
        if state == augment_mod.STATE_FAILED:
            return {"state": augment_mod.STATE_FAILED}
        if state != augment_mod.STATE_READY:
            return None
        best = aug.get("best")
        name = words_mod._name(best.get("name")) if isinstance(best, dict) else None
        tried = aug.get("tried")
        quality = _row(aug.get("quality"), ("dps", "ehp"))
        if quality is not None:
            quality["to"] = augment_mod.QUALITY_MAX
        return {"state": augment_mod.STATE_READY,
                "best": (dict(_row(best, ("dps", "ehp")), name=name)
                         if name is not None else None),
                "tried": tried if isinstance(tried, int) and not isinstance(tried, bool)
                else 0,
                "socket": aug.get("socket") is True, "quality": quality}
    calc = result.get("calc") if isinstance(result.get("calc"), dict) else {}
    if calc.get("notice") != delta_mod.NOTICE_OFF:
        return None
    return {"state": NEEDS_CALC} if augment_mod.room(ctx.get("parsed")) else None


def notes(value):
    """The part's dashboard notes for a value, in order."""
    if not isinstance(value, dict):
        return []
    state = value.get("state")
    if state == NEEDS_CALC:
        return [words_mod.NEEDS_CALC_TEXT]
    if state == augment_mod.STATE_FAILED:
        return [words_mod.FAILED_TEXT]
    if state != augment_mod.STATE_READY:
        return []
    out = []
    best = value.get("best")
    tried = value.get("tried") or 0
    if value.get("socket") and isinstance(best, dict):
        line = words_mod.best_text(best.get("name"), best.get("dps"), best.get("ehp"))
        if line:
            out.append(line)
    elif value.get("socket") and tried > 0:
        out.append(words_mod.none_text(tried))
    q = value.get("quality")
    if isinstance(q, dict):
        out.append(words_mod.quality_text(q.get("to") or augment_mod.QUALITY_MAX,
                                          q.get("dps"), q.get("ehp")))
    if value.get("socket") and tried > 0:
        out.append(words_mod.CREDIT_TEXT)
    return out


def words(value, card, out):
    out["notes"].extend(notes(value))
