"""Progression view words (PROGRESSION-VIEW, decision 0092).

The server-composed words of the one Progression view: the next-up strip
steps, the source line, the point lines and the honest "unknown" words.
server/al/theorycraft/progression.py composes them; web/panels/
progression.js shows them as they are (textContent only) and holds only
its own headings and button labels. Copy sheet:
docs/design/copy/progression.md. tests/test_progression.py pins every
template. Every line says what AshLight knows from the build, the plan or
the guide; none claims the player took a passive, slotted a gem, finished
a trial or picked up a book. Pure constants and functions; stdlib only.
"""

# where the view's data comes from (the source line)
SOURCE_POB = "From your pasted build"
SOURCE_POB_SPEC = "From your pasted build, tree {title}"
SOURCE_KINDLER = "From Kindler tab {label}"
SOURCE_NONE = "No build yet. Paste one on Build and items."
NO_TREE = ("Passive tree data isn't on this computer yet. Turn on web data in "
           "Settings, Reading and web data.")
NO_IDS = "This build's passives don't match the saved tree data. Paste the build again."

# the next-up strip (at most 3 steps, in this order of kinds)
TAKE_NEXT = "Take next: {names}"
TAKE_NEXT_MORE = "Take next (+{n}): {names}"
NEXT_BAND = "Next tree: {n} more {passives}"
GEM_NOW = "{kind} ready: {name}"
GEM_LATER = "{kind} at level {level}: {name}"
ASC_TRIAL = "After ascendancy trial {trial}: {names}"
ASC_TRIAL_MORE = "After ascendancy trial {trial} (+{n}): {names}"
BOOK_HERE = "Here: {text}"
GEM_WORD = "Gem"
SUPPORT_WORD = "Support"
NOTHING_NEXT = "Nothing new is due at this level."

# point lines
PASSIVES = "Passives: {have} planned by level {level}"
PASSIVES_NO_LEVEL = "Passives: {have} in this tree"
PASSIVES_BUDGET = "{budget} {points} at level {level}, not counting books"
ASC_POINTS = "Ascendancy: {have} planned, {due} after the next trial"
ASC_POINTS_LATER = "Ascendancy: {have} planned, {later} for later trials"
ASC_POINTS_NONE = "Ascendancy: {have} planned"
SPIRIT = "Spirit: {spirit} ({free} free), from Path of Building"
SPIRIT_ONLY = "Spirit: {spirit}, from Path of Building"
WEAPON_SETS = "Weapon set points: {one} on set 1, {two} on set 2"
BOOKS_ACT = "The guide lists {n} {books} of 2 points in {act}: {zones}"
BOOKS_NONE = "The guide lists no point books in {act}."
BOOKS_UNKNOWN = "Point books show once AshLight knows your act."
LEVEL_UNKNOWN = "level unknown"

# gem timing
UNCHECKED = "unchecked"
READY = "ready"
GEM_LEVEL = "gem level {level}"
NO_FIT = "doesn't fit"
WITH = "with {names}"
NO_SUPPORTS = "no supports linked"
NEED_LEVEL = "level {level}"


def plural(n, one, many):
    """`one` for 1, else `many` (ASCII words, design 0001 P7)."""
    return one if n == 1 else many


def names_line(names, limit, more_template, template, **extra):
    """`template` with the first `limit` names joined by ", ", or
    `more_template` naming how many were left out. A name repeated next to
    itself is said once with its count ("Attribute (2)")."""
    counted = []
    for n in names:
        if not n:
            continue
        if counted and counted[-1][0] == n:
            counted[-1][1] += 1
        else:
            counted.append([n, 1])
    shown = [n if k == 1 else f"{n} ({k})" for n, k in counted[:limit]]
    rest = sum(k for _n, k in counted[limit:])
    joined = ", ".join(shown)
    if rest > 0:
        return more_template.format(names=joined, n=rest, **extra)
    return template.format(names=joined, **extra)
