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

Checked against GGG's filter reference (pathofexile.com/item-filter/about,
read 2026-11-17, research 0025; PoE2 uses the same grammar): SetFontSize
1-45, colours 0-255 per channel, PlayEffect / MinimapIcon colour and shape
words, `Import "<file>" Optional`. A Show block without `Continue` stops
matching for the items it catches, so the Import goes near the top. When
the build-time base list is cached (decision 0009) a base name the game
data does not know is left out: such a BaseType value would make the
player's filter fail to load.
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


def known(names, base_names):
    """(kept, dropped): the names found in `base_names` ({lower: name},
    basetypes.NamesCache) in the game's spelling; all kept when no list."""
    if not isinstance(base_names, dict) or not base_names:
        return list(names), []
    kept, dropped = [], []
    for n in names:
        real = base_names.get(n.lower())
        if isinstance(real, str) and _clean(real) == real:
            if real not in kept:
                kept.append(real)
        else:
            dropped.append(n)
    return kept, dropped


def generate(build, base_names=None):
    """The filter text (ASCII, LF). With no build or no bases it is a valid
    filter made of comments only, so an Import of it changes nothing.
    `base_names` (optional, the cached snapshot base list) drops names the
    game data does not know."""
    lines = ["# ashlight.filter - made by AshLight from your loaded build.",
             "# " + NOTICE,
             "# Save this file in your item filter folder, then add this line",
             "# near the top of your own filter:",
             "#   " + IMPORT_LINE,
             ""]
    names, dropped = known(bases(build) if build is not None else [], base_names)
    if dropped:
        n = len(dropped)
        lines.append(f"# Left out {n} item base{'s' if n != 1 else ''} that the game data "
                     "does not list.")
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
