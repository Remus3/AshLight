"""TC-PRESS-STAGED-LIVE (decision 0024 amendment 2026-11-19): the card
says that Path of Building numbers are still coming.

A card part (TC-CARD-PARTS). The core publishes the item check in stages:
the stat-weight card at once, then Path of Building's DPS / EHP change,
then its per-mod rows (theorycraft/live.py). While a later stage is still
pending, this part's value is {"stage": <the shown stage name>} and its
words add one dashboard note; the last stage carries no value, so the note
goes away by itself. It never changes the word, tone, head or overlay
line: the verdict already shown stays the card's until a stage replaces it.

When that pending card was scored with the weights Path of Building
measured for this build earlier (calc source "pob_cached", no notice),
the dashboard calc sentence would otherwise say the calc is off; this part
replaces it with PENDING_CALC until a state.py pending key exists. A card
with a notice (off, failed, implausible) keeps its own sentence.

Nothing here reads the clipboard or sends anything anywhere.
"""

NAME = "stage"
ORDER = 1  # first: the note must survive the NOTES_MAX cut while it shows

PENDING_NOTE = "Path of Building numbers are coming."
PENDING_CALC = ("Scored with the stat weights Path of Building measured for this "
                "build earlier. Path of Building's DPS and EHP numbers are coming.")


def compute(ctx):
    stage = ctx.get("stage") if isinstance(ctx, dict) else None
    if not isinstance(stage, dict) or stage.get("pending") is not True:
        return None
    name = stage.get("name")
    return {"stage": name if isinstance(name, str) else None}


def words(value, card, out):
    if not isinstance(value, dict):
        return
    calc = card.get("calc") if isinstance(card, dict) else None
    if (isinstance(calc, dict) and calc.get("source") == "pob_cached"
            and calc.get("notice") is None
            and isinstance(out.get("calc"), str) and out["calc"]):
        out["calc"] = PENDING_CALC
    out["notes"].append(PENDING_NOTE)
