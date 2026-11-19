"""TC-PRESS-STAGED-LIVE (decision 0024 amendment 2026-11-19): the card
says that Path of Building numbers are still coming.

A card part (TC-CARD-PARTS). The core publishes the item check in stages:
the stat-weight card at once, then Path of Building's DPS / EHP change,
then its per-mod rows (theorycraft/live.py). While a later stage is still
pending, this part's value is {"stage": <the shown stage name>} and its
words add one dashboard note; the last stage carries no value, so the note
goes away by itself. It never changes the word, tone or head: the verdict
already shown stays the card's until a stage replaces it.

Nothing here reads the clipboard or sends anything anywhere.
"""

NAME = "stage"
ORDER = 1  # first: the note must survive the NOTES_MAX cut while it shows

PENDING_NOTE = "Path of Building numbers are coming."


def compute(ctx):
    stage = ctx.get("stage") if isinstance(ctx, dict) else None
    if not isinstance(stage, dict) or stage.get("pending") is not True:
        return None
    name = stage.get("name")
    return {"stage": name if isinstance(name, str) else None}


def words(value, card, out):
    if isinstance(value, dict):
        out["notes"].append(PENDING_NOTE)
