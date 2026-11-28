"""Augment and quality what-if words (TC-AUGMENT-WHATIF, research 0064 G4,
decision 0093).

The dashboard notes of the item check card's "augment" part
(server/al/theorycraft/cardparts/augment.py). The numbers come from Path
of Building through theorycraft/augment.py; this module only words them.
Never a price (decision 0017). Templates: docs/design/copy/augment.md,
edited in both places together; tests/test_tc_augment_whatif.py pins every
sentence exactly. Pure functions and constants; stdlib only.
"""

from .common import _signed

NAME_MAX = 40  # characters of an augment name kept in a note
WORDS_MAX = 20  # design 0001 section 8 rule 1: words in a dashboard sentence

BEST_TEXT = "Best augment for a free socket: {name}, DPS {dps}, EHP {ehp} (Path of Building)."
NONE_TEXT = "Path of Building tried {tried} for a free socket; none raises DPS or EHP."
QUALITY_TEXT = "At {to}% quality, Path of Building gives DPS {dps}, EHP {ehp}."
FAILED_TEXT = "Path of Building could not rank augments for this item."
NEEDS_CALC_TEXT = "Augment ranking for this item needs the Path of Building calc."
# decision 0091 point 5: the credit wherever a ModRunes.lua row reaches the player
CREDIT_TEXT = "Augment data: Path of Building (MIT), community-written, may be out of date."


def _pct(p):
    """'+4.2%', '-1%', '0%'; 'unknown' when Path of Building gave no number
    (a 0 base)."""
    if isinstance(p, bool) or not isinstance(p, (int, float)):
        return "unknown"
    t = _signed(p)
    return ("0" if t in ("+0", "-0") else t) + "%"


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _name(value):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    if not value or not value.isascii():
        return None
    return value[:NAME_MAX]


def best_text(name, dps, ehp):
    """The best augment's note: 'Best augment for a free socket: Iron Rune,
    DPS +4.2%, EHP 0% (Path of Building).'; None for a name that cannot
    show."""
    name = _name(name)
    if name is None:
        return None
    # design 0001 section 8 rule 1: at most WORDS_MAX words; only the name
    # gives way, with "..." (section 9 rule 6)
    room = WORDS_MAX - (len(BEST_TEXT.format(name="N", dps="x", ehp="x").split()) - 1)
    parts = name.split()
    if len(parts) > room:
        name = " ".join(parts[:max(1, room)]) + "..."
    return BEST_TEXT.format(name=name, dps=_pct(dps), ehp=_pct(ehp))


def none_text(tried):
    """No measured augment raised the blend: 'Path of Building tried 12
    augments for a free socket; none raises DPS or EHP.'"""
    return NONE_TEXT.format(tried=_plural(int(tried), "augment"))


def quality_text(to, dps, ehp):
    """'At 20% quality, Path of Building gives DPS +3%, EHP 0%.'"""
    return QUALITY_TEXT.format(to=int(to), dps=_pct(dps), ehp=_pct(ehp))
