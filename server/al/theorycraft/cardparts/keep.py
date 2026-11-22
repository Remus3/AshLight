"""TC-CAMPAIGN-KEEP (decision 0057): keep or vendor with no build loaded.

A card part (TC-CARD-PARTS). It computes only on an item-check press
whose evaluate() result is "no build loaded" for an item with a gear slot
the levelling rule table covers (theorycraft/levelrules.py); a loaded build
keeps the normal comparison and this part adds nothing. The verdict comes
from AshLight's own level-band thresholds and the player level from the
opted-in Client.txt tail; it is labelled a levelling rule and names the
thresholds the item met.

Value: {"status": "keep" | "vendor", "level", "need", "of", "count",
"met": [{"label", "min", "have"}], "missed": [{"label", "min", "have"}]},
or {"status": "no_level"} / {"status": "unidentified"} when it cannot
answer (a note names the missing input; the card stays "No build loaded").

Words (design 0001 section 9, AshLight's own): word Keep (edge upgrade) or
Vendor (edge note), head "<word> - <k> of <n> met, Lv <lv>" or, for a
missed must check, "Vendor - no <label>, Lv <lv>" (at most HEAD_FIT, 26
characters: over it the level drops), dashboard notes "Worth keeping: it meets ..." / "Vendor:
..." and "Thresholds met: ...", and answers True so the overlay keeps the
item card. Nothing here reads the clipboard or sends anything anywhere.
"""

from .. import evaluate, levelrules

NAME = "keep"
ORDER = 20  # after buildload (5): an item part

WORD_KEEP = "Keep"
WORD_VENDOR = "Vendor"
TONE = {"keep": "upgrade", "vendor": "note"}
NO_LEVEL_NOTE = "Keep or vendor needs your character level from Client.txt."
UNIDENTIFIED_NOTE = "Keep or vendor needs the item identified first."


def _row(r):
    return {"label": r["label"], "min": r["min"], "have": r["have"]}


def compute(ctx):
    if not isinstance(ctx, dict) or ctx.get("build") is not None:
        return None
    result = ctx.get("result")
    if not isinstance(result, dict) or result.get("error") != "no build loaded":
        return None
    parsed = ctx.get("parsed")
    slots = result.get("slots") or ()
    doc = levelrules.table()
    if parsed is None or not doc or not any(s in doc["slots"] for s in slots):
        return None
    if parsed.flags.get("unidentified"):
        return {"status": "unidentified"}
    level = ctx.get("level")
    if levelrules.band_for(doc, level) is None:
        return {"status": "no_level"}
    v = levelrules.verdict(doc, level, slots, evaluate.stats_of(parsed))
    if v is None:
        return None
    return {"status": v["status"], "level": v["level"], "need": v["need"],
            "of": v["of"], "count": v["count"], "met": [_row(r) for r in v["met"]],
            "missed": [_row(r) for r in v["missed_must"]]}


def _n(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


HEAD_FIT = 26  # CARD-LINE-LIMIT-COPY: the head is worded to fit 26
HEAD_MAX = HEAD_FIT  # design 0001 section 9 rule 6; 26 since CARD-LINE-LIMIT-FLIP


def head(value):
    """The overlay head: "<word> - <k> of <n> met, Lv <lv>"; a Vendor
    caused by a missed must check names it instead ("Vendor - no life,
    Lv 30"). Over HEAD_FIT the ", Lv <lv>" part drops ("Vendor - no move
    speed"), so the head never clips and a count never reads like a pass."""
    missed = value.get("missed") or []
    if value["status"] != "keep" and missed:
        text = f"{WORD_VENDOR} - no {missed[0]['label']}"
    else:
        word = WORD_KEEP if value["status"] == "keep" else WORD_VENDOR
        text = f"{word} - {value['count']} of {value['of']} met"
    full = f"{text}, Lv {value['level']}"
    return full if len(full) <= HEAD_FIT else text


def verdict_note(value):
    k, n, lv = value["count"], value["of"], value["level"]
    if value["status"] == "keep":
        return f"Worth keeping: it meets {k} of {n} levelling thresholds for level {lv}."
    missed = value.get("missed") or []
    if missed:
        m = missed[0]
        return (f"Vendor: it lacks {m['label']} {_n(m['min'])}+, which this levelling "
                f"rule needs at level {lv}.")
    need = value["need"]
    verb = "is" if need == 1 else "are"
    return (f"Vendor: it meets {k} of {n} levelling thresholds for level {lv}, "
            f"and {need} {verb} needed.")


def met_note(value):
    met = value.get("met") or []
    if not met:
        return None
    return "Thresholds met: " + ", ".join(f"{r['label']} {_n(r['min'])}+" for r in met) + "."


def words(value, card, out):
    if not isinstance(value, dict):
        return
    status = value.get("status")
    if status == "no_level":
        out["notes"].append(NO_LEVEL_NOTE)
        return
    if status == "unidentified":
        out["notes"].append(UNIDENTIFIED_NOTE)
        return
    if status not in TONE:
        return
    out["word"] = WORD_KEEP if status == "keep" else WORD_VENDOR
    out["tone"] = TONE[status]
    out["head"] = head(value)
    out["answers"] = True
    out["notes"].append(verdict_note(value))
    met = met_note(value)
    if met:
        out["notes"].append(met)
