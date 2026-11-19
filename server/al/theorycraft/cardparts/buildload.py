"""TC-PRESS-BUILD: the words of a build loaded by the item key (F-042).

The item-key press that held a PoB code, character JSON or share link
(theorycraft/press.py) publishes an eval card whose parts carry this
part's value; an item press never does (its ctx has no "build_press"), so
compute() adds nothing there. The value is
{"status": "loaded", "class_name", "ascendancy", "level", "character",
"replaced"} or
{"status": "refused", "reason": one of REASONS}. words() gives the card
the status word "Build loaded" (design 0001 section 10, status card
words) or keeps "Not checked" for a refused link, adds one dashboard note,
and answers without an item. AshLight's own words only; nothing here reads
the clipboard or sends anything anywhere.
"""

NAME = "buildload"
ORDER = 5  # before every item part: this card is about the build, not an item

WORD = "Build loaded"
NAME_MAX = 40  # characters of a class or character name kept in a note
# a refused share link: why, as one dashboard note each
REASONS = {
    # the existing refusal words of POST /api/build-code (decision 0013)
    "web_data_off": ("Web data is off: turn it on to load share links, or paste "
                     "the build code itself."),
    "not_supported": ("This share link's site is not supported, so copy the build "
                      "code in Path of Building instead."),
    "fetch_failed": "AshLight couldn't fetch that share link, so check the link or copy the code.",
    "not_a_build": "The share link did not hold a build AshLight can read.",
}


def _text(value):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    if not value or not value.isascii():
        return None
    return value[:NAME_MAX]


def _level(value):
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value < 1000:
        return value
    return None


def clean(doc):
    """The part value for a press doc of theorycraft/press.py, or None."""
    if not isinstance(doc, dict):
        return None
    if doc.get("status") == "loaded":
        return {"status": "loaded", "class_name": _text(doc.get("class_name")),
                "ascendancy": _text(doc.get("ascendancy")), "level": _level(doc.get("level")),
                "character": _text(doc.get("character")),
                "replaced": doc.get("replaced") is True}
    if doc.get("status") == "refused" and doc.get("reason") in REASONS:
        return {"status": "refused", "reason": doc["reason"]}
    return None


def compute(ctx):
    """The value only on the build press (ctx "build_press"); None on an
    item press."""
    return clean(ctx.get("build_press")) if isinstance(ctx, dict) else None


def describe(value):
    """'Infernalist, level 42': the build's class (its ascendancy when it
    has one) and level, the card's second line."""
    value = value if isinstance(value, dict) else {}
    who = value.get("ascendancy") or value.get("class_name")
    level = value.get("level")
    if who and level:
        return f"{who}, level {level}"
    if who:
        return who
    if level:
        return f"Level {level} build"
    return "Build from the clipboard"


def _article(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def loaded_note(value):
    """One dashboard sentence: what was loaded, for whom, and that the
    build it replaced was kept (the store's undo copy)."""
    who = value.get("ascendancy") or value.get("class_name")
    level = value.get("level")
    if who and level:
        what = f"a level {level} {who} build"
    elif who:
        what = f"{_article(who)} {who} build"
    elif level:
        what = f"a level {level} build"
    else:
        what = "the build you copied"
    whose = f" for {value['character']}" if value.get("character") else ""
    kept = " and kept the old build as a copy" if value.get("replaced") else ""
    return f"AshLight loaded {what}{whose}{kept}."


def words(value, card, out):
    if not isinstance(value, dict):
        return
    out["answers"] = True
    if value.get("status") == "loaded":
        out["word"] = WORD
        out["head"] = WORD
        out["notes"].append(loaded_note(value))
    elif value.get("status") == "refused" and value.get("reason") in REASONS:
        out["notes"].append(REASONS[value["reason"]])
