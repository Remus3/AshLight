"""UTIL-SEARCHSTR: stash / vendor search strings from the loaded build.

Pure functions (decision 0030): the loaded Path of Building build in, a
short list of search strings out. The player copies one with the
dashboard's Copy button (the clipboard write happens only on that click,
decision 0014) and pastes it into the game's search box. AshLight never
types into the game.

Syntax (the in-game stash / vendor search box, research 0023): one quoted
string; `|` between terms means OR; a leading `!` inside the quotes means
NOT. Terms are matched as text on the item, case-insensitive. Terms here
are plain lower-case words: every character the search box treats as
syntax (quotes, `|`, `!`, regex marks) is removed, so a term never breaks
the string. A string is at most MAX_LEN characters (250, reported, not yet
verified in game); whole terms are dropped from the end to fit, never cut.
"""

import re

from . import waystone

MAX_LEN = 250
RES_CAP = waystone.RES_CAP
_UNSAFE = re.compile(r"[^a-z0-9 '%-]")


def clean(term):
    """A term with search syntax removed, lower case, single spaces."""
    t = _UNSAFE.sub(" ", str(term or "").lower())
    return " ".join(t.split())


def join(terms, negate=False, cap=MAX_LEN):
    """(string, kept count) for terms OR-ed in one quoted string, at most
    `cap` characters; (None, 0) when no term is left."""
    out = []
    for t in terms:
        c = clean(t)
        if c and c not in out:
            out.append(c)
    while out:
        text = '"' + ("!" if negate else "") + "|".join(out) + '"'
        if len(text) <= cap:
            return text, len(out)
        out.pop()
    return None, 0


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _resist_terms(stats):
    terms = []
    for el in ("fire", "cold", "lightning"):
        v = _num(stats.get(waystone.RES_STAT[el]))
        if v is None or v < RES_CAP:
            terms.append(f"{el} res")
    if len(terms) >= 2:
        terms.append("all elemental res")
    chaos = _num(stats.get(waystone.RES_STAT["chaos"]))
    if chaos is None or chaos < 0:
        terms.append("chaos res")
    return terms


def _defence_terms(stats):
    life, es = _num(stats.get("Life")), _num(stats.get("EnergyShield"))
    if life is None and es is None:
        return ["maximum life", "maximum energy shield"]
    life, es = life or 0, es or 0
    if es >= life * 2:
        return ["maximum energy shield"]
    if life >= es * 2:
        return ["maximum life"]
    return ["maximum life", "maximum energy shield"]


def _bases(build):
    out = []
    gear = getattr(build, "gear", None)
    for slot, item in (gear.items() if isinstance(gear, dict) else ()):
        if str(slot).lower().startswith(("flask", "charm")):
            continue
        rarity = (getattr(item, "rarity", None) or "").upper()
        base = getattr(item, "base", None)
        if rarity in ("RARE", "NORMAL", "UNIQUE") and isinstance(base, str) and base.strip():
            out.append(base)
    return out


# id, label (dashboard heading), why (one plain sentence)
SPEC = (
    ("resists", "Resistances you still need",
     "Finds gear with the resistances your build has below the cap."),
    ("defence", "Life or energy shield",
     "Finds gear with the defence your build stacks."),
    ("movement", "Faster boots", "Finds boots with movement speed."),
    ("bases", "Item bases you wear", "Finds the item bases your build wears."),
    ("waystone", "Waystones without risky mods",
     "Finds waystones without the mods that are risky for your build."),
)


def strings(build):
    """[{"id", "label", "why", "text", "terms", "dropped"}] for the loaded
    build; [] with no build. A string with no term is left out."""
    if build is None:
        return []
    stats = getattr(build, "stats", None)
    stats = stats if isinstance(stats, dict) else {}
    sources = {
        "resists": (_resist_terms(stats), False),
        "defence": (_defence_terms(stats), False),
        "movement": (["movement speed"], False),
        "bases": (_bases(build), False),
        "waystone": (waystone.avoid_terms(build), True),
    }
    out = []
    for sid, label, why in SPEC:
        terms, negate = sources[sid]
        wanted = len({clean(t) for t in terms if clean(t)})
        text, kept = join(terms, negate=negate)
        if text is None:
            continue
        out.append({"id": sid, "label": label, "why": why, "text": text,
                    "terms": kept, "dropped": wanted - kept})
    return out
