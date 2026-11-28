"""TC-AUGMENT-WHATIF (research 0064 G4, decision 0093): augment what-if on
the item-check press.

For a pressed weapon or armour piece that may have a free augment socket,
this module ranks the augments that fit its slot by Path of Building's
DPS / EHP change for the loaded build (decision 0024 blend). It runs as the last stage of evaluate.stages() (stage "augment"), on the
LastEval stage worker, after the per-mod stage; it is never a price and
never asks a trade site (decisions 0017, 0037).

- Augment rows come only from server/al/theorycraft/pobtext.load_augments
  (PoB-PoE2 src/Data/ModRunes.lua read as text under its pob2_files pin,
  decision 0091). An augment applies to an item the way Path of Building
  applies it (Classes/Item.lua GetSocketedAugmentTypes, read 2026-11-28):
  the rows of its base type key ("weapon", "armour" or "caster") and of
  its specific type key ("helmet", "bow", "quarterstaff", "buckler" ...).
  The item class to keys table is CLASS_KEYS; a class not in it gets no
  what-if (never guessed).
- "Bonded:" lines are left out of a probe: they act only with a bonded
  ascendancy, which the card does not know.
- A free socket: the item's Sockets line names more sockets than it has
  rune lines. The game shows two equal runes as one line, so a free socket
  is possible, not sure; the card words it as "for a free socket", never
  "your free socket". With no rune line every socket is free.
- Corrupted, mirrored or unmodifiable items get no what-if.
- No quality what-if: the bridge's set_item calls PoB's
  Item:NormaliseQuality, which scores every modifiable item below its
  base's top quality at PoB's default quality already, so a quality probe
  always reads 0 (measured on the real bridge 2026-11-28, decision 0093).
- One tier per family: augments whose probe lines differ only in their
  numbers are one family; only its highest rank (PoB's rank field, then
  the larger numbers) is measured.
- Budget: at most delta.MAX_PROBES calc calls for the stage and at most
  TIME_S seconds (decision 0024 R7: the whole warm check, every stage,
  stays under its 12 s probe ceiling); the
  hand stat weights only choose which candidates are measured first; Path of Building's numbers rank them. A newer press
  cancels the stage between two calc calls.

Pure functions plus one calc loop; stdlib only; nothing here reads the
clipboard, the screen or the game, starts a process or sends anything.
"""

import re
import time

from . import delta as delta_mod
from . import weights as weights_mod

# decision 0024 R7 (amendment 2026-11-18): the warm check's probes, every
# stage, 12 s; the pob and mods stages take up to 5.5 s warm, so this stage
# gets 5 s (one call may run past it: about 0.5 s) - decision 0093 amendment
# 2026-11-28 (a 12 s stage measured 13.1 s for the whole warm press)
TIME_S = 5.0
NAME_MAX = 40
TOP_MAX = 3  # measured rows kept in the result, best first
SOURCE_ID = "path-of-building"  # pobtext.SOURCE_ID (decision 0091 point 5)
STATE_PENDING, STATE_READY, STATE_FAILED = "pending", "ready", "failed"
BLOCKING_FLAGS = ("corrupted", "twice_corrupted", "mirrored", "unmodifiable")
FILLED_SECTIONS = ("rune", "added_rune")
_BONDED = "Bonded:"

# game item class (lower case) -> (PoB base type key, PoB specific type key);
# PoB Classes/Item.lua GetSocketedAugmentTypes and src/Data/Bases (pin
# 7d6f530c): weapon bases have a weapon table, wands / staves / sceptres
# are "caster", armour bases (bucklers: a shield of subType Evasion) are
# "armour"; the specific key is PoB's base type, lower case
CLASS_KEYS = {
    "bows": ("weapon", "bow"),
    "crossbows": ("weapon", "crossbow"),
    "quarterstaves": ("weapon", "quarterstaff"),
    "one hand maces": ("weapon", "one hand mace"),
    "two hand maces": ("weapon", "two hand mace"),
    "spears": ("weapon", "spear"),
    "talismans": ("weapon", "talisman"),
    "flails": ("weapon", "flail"),
    "daggers": ("weapon", "dagger"),
    "claws": ("weapon", "claw"),
    "one hand swords": ("weapon", "one hand sword"),
    "two hand swords": ("weapon", "two hand sword"),
    "one hand axes": ("weapon", "one hand axe"),
    "two hand axes": ("weapon", "two hand axe"),
    "wands": ("caster", "wand"),
    "staves": ("caster", "staff"),
    "sceptres": ("caster", "sceptre"),
    "helmets": ("armour", "helmet"),
    "gloves": ("armour", "gloves"),
    "boots": ("armour", "boots"),
    "body armours": ("armour", "body armour"),
    "shields": ("armour", "shield"),
    "bucklers": ("armour", "buckler"),
    "foci": ("armour", "focus"),
}

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class Cancelled(Exception):
    """A newer press (or close) made this stage stale between calc calls."""


def keys_for(parsed):
    """(base key, specific key) for a parsed item's class, or None."""
    c = (getattr(parsed, "item_class", None) or "").strip().lower()
    return CLASS_KEYS.get(c)


def free_socket(parsed):
    """True when the Sockets line names more sockets than the item has rune
    lines (a free socket is possible; see the module text)."""
    sockets = getattr(parsed, "rune_sockets", 0) or 0
    filled = sum(1 for m in getattr(parsed, "mods", ()) or ()
                 if getattr(m, "section", None) in FILLED_SECTIONS)
    return sockets > filled


def room(parsed):
    """True for an item the what-if covers: a known class, not corrupted,
    mirrored or unmodifiable, with a possible free socket."""
    if parsed is None or not getattr(parsed, "is_item", False) or keys_for(parsed) is None:
        return False
    flags = getattr(parsed, "flags", None) or {}
    if any(flags.get(f) for f in BLOCKING_FLAGS):
        return False
    return free_socket(parsed)


def _shape(lines):
    return tuple(_NUMBER.sub("#", line) for line in lines)


def _numbers(lines):
    return tuple(float(n) for line in lines for n in _NUMBER.findall(line))


def candidates(parsed, index):
    """[{"name", "type", "lines"}] the augments of `index` (a
    pobtext.load_augments map) that fit the item's slot keys: the lines of
    its base-type row then its specific-type row, Bonded lines left out;
    one per family (highest rank, then larger numbers; ties by name). In
    file order of each family's first member."""
    keys = keys_for(parsed)
    if keys is None or not isinstance(index, dict):
        return []
    best = {}
    order = []
    for entry in index.values():
        slots = entry.get("slots") if isinstance(entry, dict) else None
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(slots, dict) or not isinstance(name, str) or not name:
            continue
        lines, kinds, rank = [], [], []
        for k in keys:
            row = slots.get(k)
            if not isinstance(row, dict):
                continue
            lines += [s for s in row.get("lines") or () if isinstance(s, str)
                      and not s.startswith(_BONDED)]
            kinds.append(row.get("type"))
            rank += [r for r in row.get("rank") or () if isinstance(r, (int, float))]
        if not lines:
            continue
        shape = _shape(lines)
        cand = {"name": name[:NAME_MAX], "type": kinds[0] if isinstance(kinds[0], str) else None,
                "lines": lines}
        sort_key = (max(rank) if rank else 0, _numbers(lines))
        have = best.get(shape)
        if have is None:
            order.append(shape)
            best[shape] = (sort_key, cand)
        elif sort_key > have[0] or (sort_key == have[0] and cand["name"] < have[1]["name"]):
            best[shape] = (sort_key, cand)
    return [best[s][1] for s in order]


def prescore(cand, table):
    """sum(weight * value) of a candidate's lines under a weights.lookup()
    table: only the order in which candidates are measured, never the rank."""
    total = 0.0
    for line in cand["lines"]:
        key, value = weights_mod.stat_key(line)
        hit = table.get(key.lower()) if key else None
        if hit and value is not None:
            total += hit[1] * value
    return total


def pick(cands, table, limit):
    """At most `limit` candidates: weighted-positive first (by prescore,
    largest first), then unweighted (file order), then negative ones."""
    scored = [(prescore(c, table), i, c) for i, c in enumerate(cands)]
    scored.sort(key=lambda t: (0 if t[0] > 0 else 1 if t[0] == 0 else 2, -t[0], t[1]))
    return [c for _s, _i, c in scored[:max(0, limit)]]


def _measure(calc, build, slot, text, base, blend):
    got = delta_mod.outputs(calc, build, {slot: text})
    delta_mod._swap_sane(base, got)
    pcts = {k: delta_mod.pct(base[k], got[k]) for k in delta_mod.OUTPUTS}
    return {"dps": pcts["dps"], "ehp": pcts["ehp"],
            "score": round(delta_mod.combined(pcts, blend), 4)}


def plan(parsed, index, table):
    """{"cands"} (at most delta.MAX_PROBES, see pick()) for an item the stage
    can answer, else None (no room, or no augment row for its slot)."""
    if not room(parsed):
        return None
    chosen = pick(candidates(parsed, index), table, delta_mod.MAX_PROBES)
    return {"cands": chosen} if chosen else None


def run(calc, build, slot, item_text, base, the_plan, blend=None, cancelled=None,
        clock=time.monotonic, time_s=TIME_S):
    """The stage's calc loop. `base`: the build's {"dps", "ehp"} with the
    pressed item in `slot` (stage "pob" measured it). At most
    delta.MAX_PROBES calc calls and `time_s` seconds; `cancelled()` True
    raises Cancelled before the next call. A candidate whose numbers make
    no sense is skipped. Returns the "augment" result field. Raises
    delta.CalcError when the calc fails."""
    start = clock()
    calls = 0
    rows = []
    for cand in the_plan["cands"]:
        if callable(cancelled) and cancelled():
            raise Cancelled()
        if calls >= delta_mod.MAX_PROBES or clock() - start > time_s:
            break
        calls += 1
        text = item_text
        for line in cand["lines"]:
            text = delta_mod.with_line(text, line)
        try:
            m = _measure(calc, build, slot, text, base, blend)
        except delta_mod.CalcImplausible:
            continue
        rows.append(dict(m, name=cand["name"], type=cand["type"]))
    rows.sort(key=lambda r: (-r["score"], r["name"]))
    best = rows[0] if rows and rows[0]["score"] > 0 else None
    return {"state": STATE_READY, "slot": slot, "tried": len(rows), "calls": calls,
            "best": best, "top": rows[:TOP_MAX], "source": SOURCE_ID}
