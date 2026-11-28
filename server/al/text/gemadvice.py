"""Gem advice words (TC-UNCUT-GEM, decision 0094).

The dashboard notes of the uncut gem card part
(server/al/theorycraft/cardparts/uncut.py over theorycraft/gemadvice.py).
Copy sheet: docs/design/copy/gemadvice.md. Every note is one plain
sentence, subject first, at most WORDS_MAX words (cardparts notes rule),
ASCII, no exclamation mark. No line says the player owns, holds or
socketed a gem: the names are the build's plan, the levels and tiers the
cached skill gem list's. Pure constants and functions; stdlib only.
"""

WORDS_MAX = 20

# the uncut gem press (one note, a second for gems with no tier in the list)
CUT_MAKES = "A level {level} {kind} cut can make your build's {names}."
CUT_MAKES_MORE = "A level {level} {kind} cut can make your build's {names} and {n} more."
CUT_MAKES_COUNT = "A level {level} {kind} cut can make {n} {gems} of your build."
CUT_NONE = "No {kind} gem of your build needs a level {level} cut."
CUT_UNCHECKED = "The skill gem list gives no tier for {names}, so check the cut in game."
CUT_UNCHECKED_COUNT = ("The skill gem list gives no tier for {n} {gems}, so check the cut "
                       "in game.")
GEM, GEMS = "gem", "gems"


def plural(n):
    return GEM if n == 1 else GEMS


def _ascii(text):
    """The name with any non-ASCII character dropped (never a '?')."""
    return " ".join("".join(c for c in str(text) if 32 <= ord(c) < 127).split())


def _fits(line):
    return len(line.split()) <= WORDS_MAX


def _names(rows):
    out = []
    for r in rows if isinstance(rows, list) else ():
        name = r.get("name") if isinstance(r, dict) else r
        name = _ascii(name) if isinstance(name, str) else ""
        if name:
            out.append(name)
    return out


def join(names):
    """'A', 'A and B', 'A, B and C'."""
    if len(names) < 2:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _count(value, field):
    n = value.get(field)
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0


def cut_notes(value):
    """The dashboard notes of one uncut gem answer (gemadvice.cut_options),
    [] for a value that is not one."""
    if not isinstance(value, dict) or value.get("kind") not in ("skill", "support", "spirit"):
        return []
    kind, level = value["kind"], value.get("level")
    names = _names(value.get("gems"))
    extra = _count(value, "more")
    unsure = _names(value.get("unchecked"))
    unsure_extra = _count(value, "unchecked_more")
    out = []
    if names:
        line = None
        for keep in range(len(names), 0, -1):
            rest = len(names) - keep + extra
            cand = (CUT_MAKES_MORE.format(level=level, kind=kind, names=", ".join(names[:keep]),
                                          n=rest)
                    if rest else CUT_MAKES.format(level=level, kind=kind, names=join(names)))
            if _fits(cand):
                line = cand
                break
        total = len(names) + extra
        out.append(line or CUT_MAKES_COUNT.format(level=level, kind=kind, n=total,
                                                  gems=plural(total)))
    elif not unsure:
        out.append(CUT_NONE.format(kind=kind, level=level))
    if unsure:
        line = None if unsure_extra else CUT_UNCHECKED.format(names=join(unsure))
        total = len(unsure) + unsure_extra
        out.append(line if line and _fits(line)
                   else CUT_UNCHECKED_COUNT.format(n=total, gems=plural(total)))
    return out
