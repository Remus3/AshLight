"""TC-GEM-UNLOCK (research 0064 G3): which gems of the loaded build the
player's new level makes usable.

Inputs are only what the floor allows: the player's own level-up line from
the opted-in Client.txt tail, the gem names of the loaded Path of Building
build (pasted or loaded by the player; enabled skill groups and enabled
gems only) and the level requirements of the cached repoe-fork gems
snapshot (DATA-GEMS-SNAP, decision 0009; nothing of it is tracked), all
looked up through the one gem helper theorycraft/gemadvice.py (decision
0095). No screen or memory read, nothing sent to the game, and nothing
says the player owns a gem.

A gem unlocks at a level-up from `prev` to `level` when its snapshot level
requirement L has prev < L <= level (only L == level when prev is
unknown). The state shows at most one card per level-up, naming every gem
that unlocked (text/gemunlock.py words), and lists one row in the recent
events (the dashboard twin). No build, no snapshot or a gem the snapshot
gives no level: nothing. Stdlib only; the caller holds the state lock.
"""

from .text import gemunlock as words
from .theorycraft import gemadvice

MAX_GEMS = gemadvice.MAX_GEMS
ORDER_STEP = 15  # the next-up strip: after the passive step (10), before the gem one (20)


def build_gems(build):
    """The enabled gem names of a loaded build, each once (case-insensitive),
    in build order; [] without a build."""
    out, seen = [], set()
    for g in gemadvice.pob_gems(build):
        if g["on"] and g["name"].lower() not in seen:
            seen.add(g["name"].lower())
            out.append(g["name"])
    return out


def unlocked(prev, level, gems, index):
    """The build gem names whose snapshot level the move from `prev` to
    `level` now meets, in build order; [] when nothing does. `index` is
    gemadvice.table() of the snapshot."""
    rows = [{"name": g, "on": True} for g in gems or () if isinstance(g, str) and g]
    return [r["name"] for r in gemadvice.unlocked(prev, level, rows, index)]


def next_steps(ctx, index):
    """TC-GEM-UNLOCK next-up source (progression.add_next_source): for a
    pasted build at a known level, one step per build gem whose snapshot
    level requirement is exactly that level (it has just become usable),
    words from text/gemunlock.step_lines. A Kindler plan has its own gem
    steps (decision 0092), so it adds nothing here."""
    if not isinstance(ctx, dict) or ctx.get("source") != "pob" or ctx.get("build") is None:
        return []
    rows = gemadvice.unlocked(None, ctx.get("level"), gemadvice.pob_gems(ctx["build"]), index)
    return [{"kind": "gem-unlock", "text": t} for t in words.step_lines(rows)]


class GemUnlock:
    """The build gems, the snapshot index and the last unlock shown
    ({"at", "level", "names"}, None before one)."""

    def __init__(self):
        self.gems = []
        self.index = None
        self.last = None

    def set(self, gems=False, index=False):
        """Any of the build gem names and the snapshot index; an argument
        left out keeps its value. True on a change."""
        new_gems = self.gems if gems is False else [
            g for g in (gems or ())[:MAX_GEMS] if isinstance(g, str) and g]
        new_index = self.index if index is False else (
            index if isinstance(index, dict) and index else None)
        if new_gems == self.gems and new_index is self.index:
            return False
        self.gems, self.index = new_gems, new_index
        return True

    def on_level(self, prev, level, now):
        """The player's own level-up: the names that unlocked (recorded as
        the last unlock), or [] (the last unlock stays)."""
        names = unlocked(prev, level, self.gems, self.index)
        if names:
            self.last = {"at": now, "level": level, "names": list(names)}
        return names
