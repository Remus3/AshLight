"""TC-GEM-UNLOCK (research 0064 G3, decision 0095): the gem unlock card, its
event row and its Progression next-up steps.

Copy sheet: docs/design/copy/gemunlock.md. The card (overlayview
CARD_HOLDERS "gem") answers first: line 1 says how many gems the new level
made usable, line 2 and line 3 name them, each inside the 26-character
card line (CARD_LINE, design 0001 section 9 rule 6). The recent events
row, its dashboard twin, names every gem up to ROW_NAMES. The next-up
steps (theorycraft/progression.add_next_source) name one gem each, at most
STEPS_MAX, inside STEP_CHARS. No line says the player owns a gem: the
names are the build's plan, the level the snapshot's. Pure functions and
constants; stdlib only.
"""

from .common import CARD_LINE
from .overlaycard import clip

HEAD_ONE = "Gem usable at level {level}"
HEAD_MANY = "{n} gems usable at level {level}"
HEAD_MANY_SHORT = "{n} gems usable, Lv {level}"  # when HEAD_MANY passes CARD_LINE
MORE_LINE = "and {n} more"
ROW_TEXT = "Level {level} makes {names} usable"
ROW_NAMES = 2  # names a row lists before "and N more"


def _ascii(name):
    """A gem name as one ASCII line: non-ASCII characters dropped."""
    return " ".join("".join(c for c in str(name) if 32 <= ord(c) < 127).split())


def _clean(names):
    return [n for n in (_ascii(x) for x in names if isinstance(x, str)) if n]


def card_lines(level, names):
    """(head, line2, line3) for one level-up's unlocked gem names (at least
    one), each at most CARD_LINE characters; the head keeps the level."""
    names = _clean(names)
    n = len(names)
    if n == 1:
        return (clip(HEAD_ONE.format(level=level)), clip(names[0]), "")
    head = HEAD_MANY.format(n=n, level=level)
    if len(head) > CARD_LINE:
        head = HEAD_MANY_SHORT.format(n=n, level=level)
    third = names[1] if n == 2 else MORE_LINE.format(n=n - 1)
    return (clip(head), clip(names[0]), clip(third, CARD_LINE))


def _join(names):
    names = [clip(x) for x in names]
    if len(names) > ROW_NAMES:
        return ", ".join(names[:ROW_NAMES]) + " " + MORE_LINE.format(n=len(names) - ROW_NAMES)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def row_text(level, names):
    """The recent events row: 'Level 14 makes Frost Bomb and Flame Wall
    usable'; at most ROW_NAMES names, each clipped at CARD_LINE."""
    return ROW_TEXT.format(level=level, names=_join(_clean(names)))


# the Progression next-up steps (one gem each, the last one counting the rest)
STEP_ONE = "{kind} usable now: {name}"
STEP_MORE = "{kind} usable now (+{n}): {name}"
GEM_WORD = "Gem"
SUPPORT_WORD = "Support"
STEPS_MAX = 2
STEP_CHARS = 52  # theorycraft/progression.STEP_CHARS (the region I row budget)


def _fit(template, name, **values):
    """The template with the name clipped with "..." so the step keeps
    STEP_CHARS."""
    room = STEP_CHARS - len(template.format(name="", **values))
    if len(name) > room:
        name = name[:max(0, room - 3)].rstrip() + "..."
    return template.format(name=name, **values)


def step_lines(rows):
    """The next-up step texts for unlocked gems ([{"name", "kind"}], build
    order): one step per gem up to STEPS_MAX; the last step counts the gems
    left out."""
    rows = [r for r in rows if isinstance(r, dict) and isinstance(r.get("name"), str)
            and _ascii(r["name"])]
    out = []
    for i, r in enumerate(rows[:STEPS_MAX]):
        kind = SUPPORT_WORD if r.get("kind") == "support" else GEM_WORD
        rest = len(rows) - STEPS_MAX if i == STEPS_MAX - 1 else 0
        name = _ascii(r["name"]) or "..."
        out.append(_fit(STEP_MORE, name, kind=kind, n=rest) if rest > 0
                   else _fit(STEP_ONE, name, kind=kind))
    return out
