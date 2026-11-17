"""TC-EVAL core: score an item against the build's item in the same slot.

`evaluate(item_text, build, weights)` is a pure function (decision 0004,
phase 1 stat-weight scoring, research 0010 section 4): it parses the item
text the caller hands it (the one per-press clipboard read, decision 0003;
this module never reads the clipboard), maps the item class to the build's
gear slot(s), and scores both items as sum(weight * value) over their
normalised mods. The verdict is upgrade / sidegrade / downgrade with the
per-stat delta; a ring (or a charm) is compared against every slot of its
kind and the headline is the best swap. No game data snapshot is needed
(TC-SNAP data is optional and unused here); base defences and weapon DPS
are compared only through the optional PoB calc (TC-DELTA, `calc=`).
"""

import math

from . import delta as delta_mod
from . import item as item_parser
from . import pobweights
from . import potential as potential_mod
from . import weights as weights_mod

UPGRADE, SIDEGRADE, DOWNGRADE = "upgrade", "sidegrade", "downgrade"

_ONE_HAND = ("wand", "sceptre", "one hand mace", "one hand sword", "one hand axe",
             "claw", "dagger", "spear", "flail")
_TWO_HAND = ("bow", "crossbow", "quarterstaff", "quarterstaves", "staff", "staves",
             "two hand mace", "two hand sword", "two hand axe", "talisman", "warstaff")
_OFF_HAND = ("shield", "buckler", "focus", "foci", "quiver")
_SLOTS_BY_CLASS = (
    (("body armour", "body armours"), ("Body Armour",)),
    (("helmet", "helmets"), ("Helmet",)),
    (("glove", "gloves"), ("Gloves",)),
    (("boot", "boots"), ("Boots",)),
    (("amulet", "amulets"), ("Amulet",)),
    (("ring", "rings"), ("Ring 1", "Ring 2")),
    (("belt", "belts"), ("Belt",)),
    (("life flask", "life flasks"), ("Flask 1",)),
    (("mana flask", "mana flasks"), ("Flask 2",)),
    (("charm", "charms"), ("Charm 1", "Charm 2", "Charm 3")),
)


def slots_for_class(item_class):
    """The PoB gear slot names an item class goes in (() for none: jewels,
    currency, gems, waystones, unknown classes)."""
    c = (item_class or "").strip().lower()
    if not c:
        return ()
    for names, slots in _SLOTS_BY_CLASS:
        if c in names:
            return slots
    singular = c[:-1] if c.endswith("s") else c
    if c in _OFF_HAND or singular in _OFF_HAND:
        return ("Weapon 2",)
    if c in _ONE_HAND or singular in _ONE_HAND or c in _TWO_HAND or singular in _TWO_HAND:
        return ("Weapon 1",)
    return ()


def _weights_of(weights):
    """(stat weights mapping, sidegrade band) from a document or a mapping."""
    if weights is None:
        doc = weights_mod.defaults()
    elif isinstance(weights, dict) and isinstance(weights.get("weights"), dict):
        doc = weights
    elif isinstance(weights, dict):
        doc = {"weights": weights}
    else:
        raise TypeError("weights must be a mapping or a weights document")
    side = dict(weights_mod.DEFAULT_SIDEGRADE)
    side.update(doc.get("sidegrade") or {})
    return doc["weights"], side


def stats_of(parsed):
    """{stat key: summed value} over an item's mods (a flag mod counts 1)."""
    out = {}
    for mod in parsed.mods:
        key, value = weights_mod.stat_key(mod.text)
        if not key:
            continue
        value = 1 if value is None else value
        prev = next((k for k in out if k.lower() == key.lower()), key)
        out[prev] = out.get(prev, 0) + value
    return out


def score(stats, table):
    """sum(weight * value) using a lookup() table."""
    total = 0.0
    for key, value in stats.items():
        hit = table.get(key.lower())
        if hit:
            term = hit[1] * value
            if math.isfinite(term) and math.isfinite(total + term):
                total += term  # MATH-NUM: a non-finite term never poisons the sum
    return round(total, 4)


def verdict(delta, old_score, side):
    if not (math.isfinite(delta) and math.isfinite(old_score)):
        return SIDEGRADE  # MATH-NUM: no verdict from a non-finite number
    band = max(float(side.get("abs", 0)), abs(old_score) * float(side.get("pct", 0)) / 100.0)
    if delta > band:
        return UPGRADE
    if delta < -band:
        return DOWNGRADE
    return SIDEGRADE


def _clean(n):
    if not math.isfinite(n):
        return 0  # MATH-NUM: the feed stays valid JSON
    n = round(n, 4)
    return int(n) if float(n).is_integer() else n


def _compare(slot, new_stats, new_score, old_item, table, side):
    old_parsed = item_parser.parse(old_item.text) if old_item is not None else None
    old_stats = stats_of(old_parsed) if old_parsed is not None else {}
    old_score = score(old_stats, table)
    keys = {}
    for k in list(new_stats) + list(old_stats):
        keys.setdefault(k.lower(), k)
    rows = []
    for low, k in keys.items():
        new_v = next((v for kk, v in new_stats.items() if kk.lower() == low), 0)
        old_v = next((v for kk, v in old_stats.items() if kk.lower() == low), 0)
        hit = table.get(low)
        w = hit[1] if hit else 0.0
        d = new_v - old_v
        rows.append({"key": hit[0] if hit else k, "weight": _clean(w),
                     "new": _clean(new_v), "old": _clean(old_v), "delta": _clean(d),
                     "score_delta": _clean(w * d), "weighted": bool(hit)})
    rows.sort(key=lambda r: (-abs(r["score_delta"]), r["key"].lower()))
    delta = round(new_score - old_score, 4)
    return {"slot": slot, "empty": old_item is None,
            "equipped": None if old_item is None else {
                "name": old_item.name, "base": old_item.base, "rarity": old_item.rarity},
            "equipped_score": _clean(old_score), "score_delta": _clean(delta),
            "verdict": verdict(delta, old_score, side), "stats": rows}


def _keys(new_stats, old_stats):
    keys = {}
    for k in list(new_stats) + list(old_stats):
        keys.setdefault(k.lower(), k)
    return list(keys.values())


def _pob(out, item_text, build, slots, new_stats, calc, blend, side, cache=None):
    """TC-DELTA (decision 0024): replace the hand-weight comparisons with
    PoB deltas and PoB-derived per-mod weights. Raises delta.CalcError.
    MATH-WEIGHTS: with a pobweights cache only unmeasured keys are probed."""
    probe = cache.mod_weights if cache is not None else delta_mod.mod_weights
    base = delta_mod.outputs(calc, build)
    comps, per_slot = [], {}
    for s in slots:
        old_item = build.equipped(s)
        old_parsed = item_parser.parse(old_item.text) if old_item is not None else None
        old_stats = stats_of(old_parsed) if old_parsed is not None else {}
        d = delta_mod.item_delta(calc, build, s, item_text, blend=blend, base=base)
        carrier = old_item.text if old_item is not None else item_text
        mw = probe(calc, build, s, carrier, _keys(new_stats, old_stats), blend=blend)
        table = weights_mod.lookup(mw["weights"])
        c = _compare(s, new_stats, score(new_stats, table), old_item, table, side)
        c.update(score_delta=_clean(d["score_delta"]),
                 verdict=delta_mod.verdict(d["score_delta"]), dps=d["dps"], ehp=d["ehp"])
        comps.append(c)
        per_slot[s] = (mw, table)
    best = max(comps, key=lambda c: c["score_delta"])
    mw, table = per_slot[best["slot"]]
    out.update(ok=True, comparisons=comps, slot=best["slot"], verdict=best["verdict"],
               score_delta=best["score_delta"], score=_clean(score(new_stats, table)),
               unweighted=sorted(k for k in new_stats if k.lower() not in table),
               calc={"source": delta_mod.SOURCE_POB, "notice": None},
               mod_weights={"source": "pob", "slot": best["slot"],
                            "weights": dict(mw["weights"]), "detail": dict(mw["detail"])})


def _cached(out, build, slots, new_stats, cache, blend, side, notice):
    """MATH-WEIGHTS: with the calc off or failing, score with the weights PoB
    measured earlier for this same build, when every slot has some. The
    score is then PoB's blended percent per point, so the verdict uses
    delta.verdict's band. Returns True when it scored."""
    tables = {}
    for s in slots:
        w = cache.fallback(build, s, blend)
        if not w:
            return False
        tables[s] = (w, weights_mod.lookup(w))
    comps = []
    for s in slots:
        table = tables[s][1]
        c = _compare(s, new_stats, score(new_stats, table), build.equipped(s), table, side)
        c["verdict"] = delta_mod.verdict(c["score_delta"])
        comps.append(c)
    best = max(comps, key=lambda c: c["score_delta"])
    w, table = tables[best["slot"]]
    out.update(comparisons=comps, slot=best["slot"], verdict=best["verdict"],
               score_delta=best["score_delta"], score=_clean(score(new_stats, table)),
               unweighted=sorted(k for k in new_stats if k.lower() not in table),
               calc={"source": pobweights.SOURCE_CACHED, "notice": notice},
               mod_weights={"source": pobweights.SOURCE_CACHED, "slot": best["slot"],
                            "weights": dict(w)})
    return True


def evaluate(item_text, build, weights=None, slot=None, calc=None, blend=None,
             cache=None):
    """Evaluate item text against a Build (or None). Never raises on input
    content; problems come back as `error` / `warnings`.

    `calc` (TC-DELTA): the optional PoB calc callable (theorycraft.delta);
    None means the component is off. With it the verdict comes from PoB's
    DPS / EHP deltas; without it, or when it fails, the stat weights score
    the item and `calc.notice` says why ("off" / "failed").

    `cache` (MATH-WEIGHTS): an optional pobweights.PobWeightCache; it
    saves calc probes, and with the calc off or failing it scores with the
    PoB weights measured earlier for this build (calc.source
    "pob_cached")."""
    out, parsed = _evaluate(item_text, build, weights, slot, calc, blend, cache)
    # MATH-POTENTIAL: the roll-range potential under the weights that
    # scored the item (hand, PoB or cached PoB); None without ranges
    out["potential"] = (potential_mod.item_potential(
        parsed, out["mod_weights"].get("weights")) if parsed.is_item else None)
    return out


def _evaluate(item_text, build, weights, slot, calc, blend, cache):
    stat_weights, side = _weights_of(weights)
    table = weights_mod.lookup(stat_weights)
    parsed = item_parser.parse(item_text)
    out = {"ok": False, "error": None, "verdict": None, "slot": None, "slots": [],
           "score": None, "comparisons": [], "unweighted": [],
           "build_loaded": build is not None,
           "item": {"item_class": parsed.item_class, "rarity": parsed.rarity,
                    "name": parsed.name, "base": parsed.base,
                    "item_level": parsed.item_level, "flags": dict(parsed.flags),
                    "mods": [m.to_dict() for m in parsed.mods]},
           "warnings": list(parsed.warnings),
           "calc": {"source": delta_mod.SOURCE_WEIGHTS,
                    "notice": delta_mod.NOTICE_OFF if calc is None else None},
           "mod_weights": {"source": "hand", "weights": dict(stat_weights)}}
    if not parsed.is_item:
        out["error"] = "not an item"
        return out, parsed
    if parsed.flags.get("unidentified"):
        out["warnings"].append("unidentified: its mods are hidden")
    new_stats = stats_of(parsed)
    out["score"] = _clean(score(new_stats, table))
    out["unweighted"] = sorted(k for k in new_stats if k.lower() not in table)
    if slot:
        slots = (slot,)
    else:
        slots = slots_for_class(parsed.item_class)
    out["slots"] = list(slots)
    if not slots:
        out["error"] = "no gear slot for this item class"
        return out, parsed
    if build is None:
        out["error"] = "no build loaded"
        return out, parsed
    comps = [_compare(s, new_stats, out["score"], build.equipped(s), table, side)
             for s in slots]
    best = max(comps, key=lambda c: c["score_delta"])
    out.update(ok=True, comparisons=comps, slot=best["slot"], verdict=best["verdict"],
               score_delta=best["score_delta"])
    if calc is not None:
        try:
            # _pob updates `out` only after every calc call succeeded
            _pob(out, item_text, build, slots, new_stats, calc, blend, side, cache)
            return out, parsed
        except delta_mod.CalcError:
            out["calc"] = {"source": delta_mod.SOURCE_WEIGHTS,
                           "notice": delta_mod.NOTICE_FAILED}
    if cache is not None:
        _cached(out, build, slots, new_stats, cache, blend, side, out["calc"]["notice"])
    return out, parsed
