"""UTIL-FILTER: an AshLight-original `ashlight.filter` snippet.

A pure function: the loaded Path of Building build in, filter text out
(decision 0031, adjudicator ruling in research 0022 section 3). The
dashboard offers it as a download on the player's click; the player saves
it into their own filter folder and adds `Import "ashlight.filter"
Optional` to their main filter. AshLight never writes into the game's
documents folder or any game folder: this module writes no file at all,
and the core only returns the text in an HTTP answer.

The text uses GGG's documented filter syntax only (Show blocks with
conditions and actions, `#` comments). It highlights the item bases the
build wears, so a better roll of the same base stands out on the ground.
Nothing from another filter is copied.
"""

import re

FILE_NAME = "ashlight.filter"
IMPORT_LINE = f'Import "{FILE_NAME}" Optional'
MAX_BASES = 40
_SAFE = re.compile(r"[^A-Za-z0-9 ',-]")
NOTICE = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."


def _clean(name):
    return " ".join(_SAFE.sub(" ", str(name or "")).split())


def bases(build):
    """The base names the build wears (rare, normal or unique gear; flasks
    and charms out; a magic item's line holds affixes, so it is out too)."""
    out = []
    gear = getattr(build, "gear", None)
    for slot, item in (gear.items() if isinstance(gear, dict) else ()):
        if str(slot).lower().startswith(("flask", "charm")):
            continue
        if (getattr(item, "rarity", None) or "").upper() not in ("RARE", "NORMAL", "UNIQUE"):
            continue
        name = _clean(getattr(item, "base", None))
        if name and name not in out:
            out.append(name)
    return out[:MAX_BASES]


def generate(build):
    """The filter text (ASCII, LF). With no build or no bases it is a valid
    filter made of comments only, so an Import of it changes nothing."""
    lines = ["# ashlight.filter - made by AshLight from your loaded build.",
             "# " + NOTICE,
             "# Save this file in your item filter folder, then add this line",
             "# near the top of your own filter:",
             "#   " + IMPORT_LINE,
             ""]
    names = bases(build) if build is not None else []
    if not names:
        lines += ["# No build loaded, or no gear in it.",
                  "# Load a build in AshLight, then download this again."]
        return "\n".join(lines) + "\n"
    who = " ".join(str(x) for x in (getattr(build, "class_name", None),
                                     getattr(build, "ascendancy", None)) if x)
    if who:
        lines.append("# Build: " + _clean(who))
    lines += ["# Rare items of the bases your build wears show larger:",
              "# check them for an upgrade.",
              "Show",
              "    Rarity Rare",
              "    BaseType == " + " ".join(f'"{n}"' for n in names),
              "    SetFontSize 40",
              "    SetBorderColor 255 190 60",
              "    PlayEffect Yellow",
              "    MinimapIcon 1 Yellow Diamond",
              ""]
    return "\n".join(lines)
