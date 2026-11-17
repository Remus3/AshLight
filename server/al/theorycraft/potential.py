"""MATH-POTENTIAL: ranged-roll "potential" of a checked item (display math).

Advanced item text (Ctrl+Alt+C) and PoB item text carry each mod's roll
range ("+90(80-99) to maximum Life", "+(40-60) to Strength"); the parser
keeps them per value (item.Mod.ranges). From those:

- per mod: where each roll sits in its range (0 percent = the lowest roll,
  100 = the highest; a fixed range reads 100), and the mod's stat value at
  the low and the high end;
- per item: the score now, at the worst and at the best rolls of every
  ranged mod for this build's weights (a "reduced" mod is best at its
  smallest roll when its weight is positive), and where the score sits
  between them.

Pure arithmetic on numbers the item text states, weighted by the weights
the item check already uses (hand or PoB-measured, decision 0022); it
models no game mechanic and computes no damage or EHP (decision 0004).
"""

import math

from . import item as item_mod
from . import weights as weights_mod

MAX_MODS = 32


def _finite(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)


def _clean(n):
    n = round(float(n), 4)
    return int(n) if n.is_integer() else n


def _with_values(text, values):
    """`text` with its numbers replaced, in order, by `values` (signs kept
    where the text has one)."""
    it = iter(values)

    def repl(m):
        try:
            v = next(it)
        except StopIteration:
            return m.group(0)
        body = format(abs(v), "g") if isinstance(v, float) else str(abs(v))
        if m.group(0)[0] in "+-":
            return ("+" if v >= 0 else "-") + body
        return ("-" if v < 0 else "") + body

    return item_mod._NUM_RE.sub(repl, text)


def roll_pct(value, rng):
    """Where `value` sits in rng=(lo, hi), 0..100 (4 decimals); 100 for a
    one-value range; None for no range or a junk one."""
    if not rng or not _finite(value):
        return None
    lo, hi = rng
    if not (_finite(lo) and _finite(hi)):
        return None
    a, b = min(lo, hi), max(lo, hi)
    if a == b:
        return 100
    p = (min(b, max(a, value)) - a) / (b - a) * 100.0
    return _clean(p)


def mod_potential(mod):
    """{"key", "value", "low", "high", "rolls": [{value, min, max, pct}]} for
    a mod with at least one ranged value, else None. `low` / `high`: the
    stat value with every ranged number at its range's low / high end."""
    ranges = getattr(mod, "ranges", ()) or ()
    values = getattr(mod, "values", ()) or ()
    if not ranges or len(ranges) != len(values) or not any(ranges):
        return None
    lows = [min(r) if r else v for v, r in zip(values, ranges)]
    highs = [max(r) if r else v for v, r in zip(values, ranges)]
    key, now = weights_mod.stat_key(mod.text)
    _, low = weights_mod.stat_key(_with_values(mod.text, lows))
    _, high = weights_mod.stat_key(_with_values(mod.text, highs))
    if key is None or now is None or low is None or high is None:
        return None
    rolls = [{"value": v, "min": min(r), "max": max(r), "pct": roll_pct(v, r)}
             for v, r in zip(values, ranges) if r]
    return {"key": key, "value": now, "low": low, "high": high, "rolls": rolls}


def item_potential(parsed, weights=None):
    """{"score", "worst", "best", "pct", "mods": [...]} for a ParsedItem
    under a weights mapping ({key: weight}; default the hand defaults), or
    None when no mod has a roll range. `pct`: where the score sits between
    worst and best (100 when they are equal)."""
    mods = [m for m in (getattr(parsed, "mods", None) or ())][:MAX_MODS]
    table = weights_mod.lookup(weights if isinstance(weights, dict)
                               else weights_mod.DEFAULT_WEIGHTS)
    score = worst = best = 0.0
    rows = []
    for mod in mods:
        key, value = weights_mod.stat_key(mod.text)
        hit = table.get((key or "").lower())
        w = hit[1] if hit else 0.0
        pot = mod_potential(mod)
        if pot is None:
            if value is not None and _finite(w * value):
                score += w * value
                worst += w * value
                best += w * value
            continue
        terms = [w * pot["value"], w * pot["low"], w * pot["high"]]
        if not all(_finite(t) for t in terms):
            continue
        score += terms[0]
        worst += min(terms[1], terms[2])
        best += max(terms[1], terms[2])
        rows.append(dict(pot, weight=_clean(w), weighted=bool(hit)))
    if not rows:
        return None
    span = best - worst
    pct = 100 if span <= 0 else _clean(min(100.0, max(0.0, (score - worst) / span * 100.0)))
    return {"score": _clean(score), "worst": _clean(worst), "best": _clean(best),
            "pct": pct, "mods": rows}
