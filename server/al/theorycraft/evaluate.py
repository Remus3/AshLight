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

import copy
import math

from . import delta as delta_mod
from . import item as item_parser
from . import pobweights
from . import potential as potential_mod
from . import weights as weights_mod

UPGRADE, SIDEGRADE, DOWNGRADE = "upgrade", "sidegrade", "downgrade"
SOURCE_WORN = "worn"  # worngear.SOURCE_WORN: a baseline slot answered by the worn item

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


# MATH-COMPARE (decision 0032): the off-hand base words of PoE2 (shields,
# bucklers, foci, quivers carry one of these in their base name); an
# equipped Weapon 2 whose class or base has none of them is a weapon, so the
# player dual wields and a checked one-hand weapon fits either hand
_OFF_HAND_WORDS = ("shield", "buckler", "focus", "quiver", "targe")
# AREA-AUDIT P4-1: released shield / buckler bases whose names carry none
# of the words above (repoe-fork base_items snapshot, 2026-11-17: the Targe
# family plus these three, each also Runemastered); matched as a phrase of
# the (possibly magic) name line
_OFF_HAND_NAMES = ("glacial fortress", "golden flame", "venerable defender")


def _is_one_hand(item_class):
    c = (item_class or "").strip().lower()
    singular = c[:-1] if c.endswith("s") else c
    return c in _ONE_HAND or singular in _ONE_HAND


def _holds_weapon(item):
    """True when an equipped item (model.Item) is a weapon, not an off-hand."""
    if item is None:
        return False
    parsed = item_parser.parse(item.text or "")
    if parsed.item_class:
        return _is_one_hand(parsed.item_class)
    # a magic item's line is its full name ("... Buckler of the Fox"), so
    # any word of the line counts, not only the last
    words = str(item.base or parsed.base or "").lower().split()
    line = " " + " ".join(w.strip(",'") for w in words) + " "
    if any(f" {n} " in line for n in _OFF_HAND_NAMES):
        return False
    return bool(words) and not any(w.strip(",'") in _OFF_HAND_WORDS for w in words)


def slots_for_build(item, build):
    """The gear slots to compare a checked item against: slots_for_class,
    plus Weapon 2 for a one-hand weapon when the build dual wields (its
    Weapon 2 holds a weapon, not a shield, focus or quiver). `item`: item
    text or a parsed item."""
    parsed = item_parser.parse(item) if isinstance(item, str) else item
    slots = slots_for_class(parsed.item_class)
    if (slots == ("Weapon 1",) and _is_one_hand(parsed.item_class) and build is not None
            and _holds_weapon(build.equipped("Weapon 2"))):
        return ("Weapon 1", "Weapon 2")
    return slots


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


def _worn_at(ref, slot):
    """True when `ref` is a baseline whose `slot` answer is the worn item."""
    source = getattr(ref, "source", None)
    return callable(source) and source(slot) == SOURCE_WORN


def _rebase(base, d, blend):
    """TC-WORN-BASELINE: a swap delta measured against the worn item,
    measured again against the build's own outputs (the plan); no calc
    call."""
    out = {k: delta_mod.change(base[k], d[k]["new"]) for k in delta_mod.OUTPUTS}
    out["score_delta"] = round(delta_mod.combined(
        {k: out[k]["pct"] for k in delta_mod.OUTPUTS}, blend), 4)
    return out


def _pob_deltas(calc, build, slots, item_text, blend, ref=None):
    """TC-PRESS-STAGED-EVAL stage "pob" calls: the build's outputs once,
    then PoB's DPS / EHP delta per slot. Returns [(slot, old_item, delta or
    None, unusable skill, plan delta or None)]; a slot whose weapon the
    main skill cannot use (MATH-WEAPON-TYPE, decision 0032 amendment) has
    no delta. TC-WORN-BASELINE: `ref` answers equipped(slot) (a baseline;
    default the build); a slot holding a worn item is measured from the
    build with that item swapped in (one more calc call), and its plan
    delta is the same swap against the build itself. Raises
    delta.CalcError."""
    ref = build if ref is None else ref
    base = delta_mod.outputs(calc, build)
    rows = []
    for s in slots:
        old_item = ref.equipped(s)
        worn = old_item is not None and _worn_at(ref, s)
        s_base = delta_mod.outputs(calc, build, {s: old_item.text}) if worn else base
        try:
            d = delta_mod.item_delta(calc, build, s, item_text, blend=blend, base=s_base)
        except delta_mod.CalcWeaponUnusable as e:
            rows.append((s, old_item, None, e.skill, None))
            continue
        plan = _rebase(base, d, blend) if worn and build.equipped(s) is not None else None
        rows.append((s, old_item, d, None, plan))
    return rows


def _pob_comp(row, new_stats, table, side):
    """One compared slot scored with `table`, its verdict from PoB."""
    s, old_item, d, skill = row[:4]
    c = _compare(s, new_stats, score(new_stats, table), old_item, table, side)
    if d is None:
        # PoB says the main skill cannot use this weapon here; a real
        # downgrade, shown in words, no PoB numbers and no probes
        c.update(verdict=delta_mod.DOWNGRADE, weapon_unusable={"skill": skill})
    else:
        c.update(score_delta=_clean(d["score_delta"]),
                 verdict=delta_mod.verdict(d["score_delta"]), dps=d["dps"], ehp=d["ehp"])
    return c


def _best_pob(comps):
    # a hand the main skill can use always beats one it cannot
    return max(comps, key=lambda c: (not c.get("weapon_unusable"), c["score_delta"]))


def _pob_out(out, comps, best, new_stats, table, mod_weights):
    """Fill `out` from PoB-verdict comparisons; `table` scores the item."""
    unusable = bool(best.get("weapon_unusable"))
    out.update(ok=True, comparisons=comps, slot=best["slot"], verdict=best["verdict"],
               score_delta=best["score_delta"], score=_clean(score(new_stats, table)),
               unweighted=sorted(k for k in new_stats if k.lower() not in table),
               calc={"source": delta_mod.SOURCE_POB,
                     "notice": delta_mod.NOTICE_WEAPON_TYPE if unusable else None},
               mod_weights=mod_weights)
    return out


def _pob_stage(out, rows, new_stats, side):
    """Stage "pob" (TC-DELTA, decision 0024): PoB's DPS / EHP deltas and
    verdicts; the per-mod rows still carry the hand weights. No calc call."""
    hand_weights = dict(out["mod_weights"]["weights"])
    hand = weights_mod.lookup(hand_weights)
    comps = [_pob_comp(r, new_stats, hand, side) for r in rows]
    return _pob_out(out, comps, _best_pob(comps), new_stats, hand,
                    {"source": "hand", "weights": hand_weights})


def _mods_stage(out, rows, item_text, new_stats, calc, build, blend, side, cache=None):
    """Stage "mods": PoB-derived per-mod weights for every usable slot.
    `out` is the hand-weight result. Raises delta.CalcError. MATH-WEIGHTS:
    with a pobweights cache only unmeasured keys are probed."""
    probe = cache.mod_weights if cache is not None else delta_mod.mod_weights
    hand_weights = dict(out["mod_weights"]["weights"])
    hand = weights_mod.lookup(hand_weights)
    comps, per_slot = [], {}
    for row in rows:
        s, old_item, d = row[:3]
        if d is None:
            comps.append(_pob_comp(row, new_stats, hand, side))
            per_slot[s] = ({"weights": hand_weights, "detail": {}}, hand)
            continue
        old_parsed = item_parser.parse(old_item.text) if old_item is not None else None
        old_stats = stats_of(old_parsed) if old_parsed is not None else {}
        carrier = old_item.text if old_item is not None else item_text
        mw = probe(calc, build, s, carrier, _keys(new_stats, old_stats), blend=blend)
        table = weights_mod.lookup(mw["weights"])
        comps.append(_pob_comp(row, new_stats, table, side))
        per_slot[s] = (mw, table)
    best = _best_pob(comps)
    mw, table = per_slot[best["slot"]]
    if best.get("weapon_unusable"):
        mod_weights = {"source": "hand", "weights": hand_weights}
    else:
        mod_weights = {"source": "pob", "slot": best["slot"],
                       "weights": dict(mw["weights"]), "detail": dict(mw["detail"])}
    return _pob_out(out, comps, best, new_stats, table, mod_weights)


def _cached(out, build, slots, new_stats, cache, blend, side, notice, ref=None):
    """MATH-WEIGHTS: with the calc off or failing, score with the weights PoB
    measured earlier for this same build, when every slot has some. The
    score is then PoB's blended percent per point, so the verdict uses
    delta.verdict's band. Returns True when it scored. `ref` answers
    equipped(slot) (TC-WORN-BASELINE; default the build)."""
    ref = build if ref is None else ref
    if build is None:
        return False
    tables = {}
    for s in slots:
        w = cache.fallback(build, s, blend)
        if not w:
            return False
        tables[s] = (w, weights_mod.lookup(w))
    comps = []
    for s in slots:
        table = tables[s][1]
        c = _compare(s, new_stats, score(new_stats, table), ref.equipped(s), table, side)
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


def _marks(out, ref, new_stats, side, rows=None):
    """TC-WORN-BASELINE: with a baseline, each comparison gains "source"
    ("worn" / "plan" / None) and the result gains "plan": the headline
    slot's item checked against the build's planned item, when that slot's
    answer is the worn item and the plan has an item there; else None.
    Its verdict follows the stage (PoB's delta in the "pob" / "mods"
    stages, the stage's weights otherwise). Without a baseline, or for a
    result that is not ok, `out` is unchanged."""
    if not out.get("ok") or not callable(getattr(ref, "source", None)):
        return out
    for c in out["comparisons"]:
        c["source"] = ref.source(c["slot"])
    out["plan"] = None
    best = next((c for c in out["comparisons"] if c["slot"] == out["slot"]), None)
    plan_item = ref.plan(out["slot"]) if best is not None else None
    if plan_item is None or best["source"] != SOURCE_WORN or best.get("weapon_unusable"):
        return out
    table = weights_mod.lookup(out["mod_weights"].get("weights") or {})
    p = _compare(best["slot"], new_stats, score(new_stats, table), plan_item, table, side)
    source = out["calc"]["source"]
    if source == delta_mod.SOURCE_POB:
        d = next((r[4] for r in rows or () if r[0] == best["slot"]), None)
        if d is None:
            return out
        p.update(score_delta=_clean(d["score_delta"]),
                 verdict=delta_mod.verdict(d["score_delta"]), dps=d["dps"], ehp=d["ehp"])
    elif source == pobweights.SOURCE_CACHED:
        p["verdict"] = delta_mod.verdict(p["score_delta"])
    out["plan"] = {"slot": p["slot"], "equipped": p["equipped"], "verdict": p["verdict"],
                   "score_delta": p["score_delta"], "source": source,
                   **{k: p[k] for k in ("dps", "ehp") if k in p}}
    return out


STAGE_WEIGHTS, STAGE_POB, STAGE_MODS = "weights", "pob", "mods"
STAGES = (STAGE_WEIGHTS, STAGE_POB, STAGE_MODS)


def evaluate(item_text, build, weights=None, slot=None, calc=None, blend=None,
             cache=None, baseline=None):
    """Evaluate item text against a Build (or None). Never raises on input
    content; problems come back as `error` / `warnings`.

    `calc` (TC-DELTA): the optional PoB calc callable (theorycraft.delta);
    None means the component is off. With it the verdict comes from PoB's
    DPS / EHP deltas; without it, or when it fails, the stat weights score
    the item and `calc.notice` says why ("off" / "failed").

    `cache` (MATH-WEIGHTS): an optional pobweights.PobWeightCache; it
    saves calc probes, and with the calc off or failing it scores with the
    PoB weights measured earlier for this build (calc.source
    "pob_cached").

    `baseline` (TC-WORN-BASELINE, decision 0052): an optional
    worngear.Baseline; equipped(slot) then answers from the worn item first
    and the build's plan second, so an item checks with no build once a
    worn item exists for its slot (the stat weights score it; the calc
    needs a build). With no build only slots with a worn item are
    compared; "no build loaded" stays when the baseline has nothing for
    every slot. With a baseline each comparison carries "source" and the
    result "plan" (see _marks). None: unchanged.

    The result is the last stage of stages()."""
    result = None
    for _name, result in stages(item_text, build, weights, slot, calc, blend, cache,
                                baseline):
        pass
    return result


def stages(item_text, build, weights=None, slot=None, calc=None, blend=None,
           cache=None, baseline=None):
    """TC-PRESS-STAGED-EVAL: evaluate() in all-or-nothing stages. A
    generator of (stage name, result) pairs; each result is a complete,
    independent evaluate()-shaped result (same keys):

    - "weights": no calc call; the hand weights (or, with a cache, the PoB
      weights measured earlier for this build) score the item. With the
      calc off, or without an item, a slot or a build, it is the only
      stage.
    - "pob": PoB's DPS / EHP deltas and verdicts per slot; the per-mod rows
      still carry the hand weights.
    - "mods": PoB-derived per-mod weights (the probes).

    A calc error in stage "pob" or "mods" ends the generator with one more
    "weights" result carrying its notice ("failed" / "implausible"). The
    last stage always equals evaluate(). Closing the generator early makes
    no further calc call. Same arguments as evaluate()."""
    ref = build if baseline is None else baseline
    final, (base, parsed, new_stats, slots, side) = _evaluate(
        item_text, build, weights, slot, calc, baseline)
    if final is not None:
        yield STAGE_WEIGHTS, _finish(final, parsed)
        return

    def done(out, rows=None):
        return _finish(_marks(out, ref, new_stats, side, rows), parsed)

    yield STAGE_WEIGHTS, done(_weights_result(
        _copy(base), build, slots, new_stats, cache, blend, side, ref))
    if calc is None or build is None:
        return
    try:
        rows = _pob_deltas(calc, build, slots, item_text, blend, ref)
    except delta_mod.CalcError as e:
        yield STAGE_WEIGHTS, done(_failed(base, e, build, slots, new_stats, cache,
                                          blend, side, ref))
        return
    yield STAGE_POB, done(_pob_stage(_copy(base), rows, new_stats, side), rows)
    try:
        # all or nothing: the stage is built only after every probe succeeded
        out = _mods_stage(_copy(base), rows, item_text, new_stats, calc, build, blend,
                          side, cache)
    except delta_mod.CalcError as e:
        yield STAGE_WEIGHTS, done(_failed(base, e, build, slots, new_stats, cache,
                                          blend, side, ref))
        return
    yield STAGE_MODS, done(out, rows)


def _copy(out):
    return copy.deepcopy(out)


def _finish(out, parsed):
    """A stage result: an independent copy plus the MATH-POTENTIAL field,
    the roll-range potential under the weights that scored the item (hand,
    PoB or cached PoB); None without ranges."""
    out = _copy(out)
    out["potential"] = (potential_mod.item_potential(
        parsed, out["mod_weights"].get("weights")) if parsed.is_item else None)
    return out


def _weights_result(out, build, slots, new_stats, cache, blend, side, ref=None):
    """The weights result: with a cache, the PoB weights measured earlier
    score it when every slot has some (MATH-WEIGHTS)."""
    if cache is not None:
        _cached(out, build, slots, new_stats, cache, blend, side, out["calc"]["notice"],
                ref)
    return out


def _failed(base, err, build, slots, new_stats, cache, blend, side, ref=None):
    """The weights result after a calc error, with its notice."""
    out = _copy(base)
    if isinstance(err, delta_mod.CalcImplausible):
        # MATH-DPS-SANITY (decision 0032): numbers that make no sense for
        # the card are not shown; the weights score it
        notice = delta_mod.NOTICE_IMPLAUSIBLE
    else:
        notice = delta_mod.NOTICE_FAILED
    out["calc"] = {"source": delta_mod.SOURCE_WEIGHTS, "notice": notice}
    return _weights_result(out, build, slots, new_stats, cache, blend, side, ref)


def _evaluate(item_text, build, weights, slot, calc, baseline=None):
    """(final, (base, parsed, new_stats, slots, side)). `final` is the
    whole result when no stage can follow (not an item, no gear slot, no
    build and nothing worn); else None and `base` is the hand-weight result
    the stages start from. `baseline` (TC-WORN-BASELINE) answers
    equipped(slot) in place of the build."""
    ref = build if baseline is None else baseline
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
        return out, (out, parsed, {}, (), side)
    if parsed.flags.get("unidentified"):
        out["warnings"].append("unidentified: its mods are hidden")
    new_stats = stats_of(parsed)
    out["score"] = _clean(score(new_stats, table))
    out["unweighted"] = sorted(k for k in new_stats if k.lower() not in table)
    if slot:
        slots = (slot,)
    else:
        slots = slots_for_build(parsed, ref)
    out["slots"] = list(slots)
    ctx = (out, parsed, new_stats, slots, side)
    if not slots:
        out["error"] = "no gear slot for this item class"
        return out, ctx
    if build is None:
        # TC-WORN-BASELINE: with no build only a worn item is something to
        # compare against (an unknown slot is not an empty one)
        slots = tuple(s for s in slots if baseline is not None
                      and baseline.equipped(s) is not None)
        ctx = (out, parsed, new_stats, slots, side)
        if not slots:
            out["error"] = "no build loaded"
            return out, ctx
    comps = [_compare(s, new_stats, out["score"], ref.equipped(s), table, side)
             for s in slots]
    best = max(comps, key=lambda c: c["score_delta"])
    out.update(ok=True, comparisons=comps, slot=best["slot"], verdict=best["verdict"],
               score_delta=best["score_delta"])
    return None, ctx
