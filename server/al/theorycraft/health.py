"""MATH-BUILD-HEALTH and MATH-NEXT-LOOK (research 0028 sections 1-2).

Pure functions on the loaded Path of Building build. Every number is one
PoB exported itself: a `<PlayerStat>` of the build XML (BuildModel.stats)
or a stat weight PoB measured for this build (theorycraft.pobweights).
Nothing is recomputed (decision 0004, research 0028 ruling A):

- health(): each element resistance compared to the 75 cap (chaos shown as
  a number, never a fail), ReqStr / ReqDex / ReqInt above Str / Dex / Int
  (PoB's own warning condition), SpiritUnreserved below 0 (PoB's own
  warning), the weakest element as the smallest of PoB's
  *MaximumHitTaken, and Life / ES / armour / evasion / block as plain
  values. A missing or non-numeric stat shows nothing.
- next_look(): per equipped gear slot, the health gaps first (biggest
  first) then the stats with the highest PoB-measured weight that the
  equipped item does not carry, as one line and one search string built
  by the UTIL-SEARCHSTR builder (250 characters, copied only on the
  player's click, decision 0014 / 0030).

The build XML stats need no calc run, so this works with the optional
calc component off: it shows PoB's numbers from the last build load.

MATH-DEF-BREAKDOWN (research 0031 sections 2, 4.2) adds PoB's remaining
warnFunc conditions (unreserved Life <= 0, unreserved Mana < 0, Accuracy
below Life with Precise Technique, DoT DPS at or above PoB's DotDpsCap) and
a compact defence / sustain list of PoB values. CalcDefence / CalcPerform
values (ailment and stun avoidance, flask and charm figures) exist only in
the calc's output table, so those rows show only with the calc on
(`calc_out`). No own uptime or "enough" verdict.
"""

import math
import re

from . import item as item_parser
from . import searchstr, waystone
from . import weights as weights_mod
from .model import SLOTS

SOURCE = "PoB"
RES_CAP = waystone.RES_CAP
ELEMENTS = ("fire", "cold", "lightning")
ATTRS = (("str", "Str", "ReqStr", "Strength"),
         ("dex", "Dex", "ReqDex", "Dexterity"),
         ("int", "Int", "ReqInt", "Intelligence"))
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
# id, label, unit: shown as plain values (no "enough" threshold, research
# 0028 section 2 item 3)
VALUES = (("Life", "Life", ""), ("EnergyShield", "Energy shield", ""),
          ("Armour", "Armour", ""), ("Evasion", "Evasion", ""),
          ("EffectiveBlockChance", "Block chance", "%"),
          ("ChaosResist", "Chaos resistance", "%"),
          ("Spirit", "Spirit", ""), ("SpiritUnreserved", "Spirit left", ""))
# MATH-DEF-BREAKDOWN: id, label, unit, decimals, calc only. Labels are
# PoB's stat meanings; the values are shown as PoB exports them. The pinned
# checkout (7d6f530c) names: <Ailment>AvoidChance for Ignite / Chill /
# Freeze / Shock / Bleed / Poison (CalcDefence.lua, data.*AilmentTypeList),
# StunThreshold / StunAvoidChance, FlaskChargeGen / Life- / ManaFlaskChargeGen
# (FlaskChargesGenerated BASE), CharmEffect (an INC sum, so a percent);
# Mana sustain from BuildDisplayStats.lua (saved PlayerStat too). Decimals
# are display only and follow PoB: avoid chances are m_floor'd whole
# numbers, StunThreshold prints with %d, mana sustain with .1f / .2f.
DEFENCE = (
    ("IgniteAvoidChance", "Ignite avoid chance", "%", 0, True),
    ("ShockAvoidChance", "Shock avoid chance", "%", 0, True),
    ("FreezeAvoidChance", "Freeze avoid chance", "%", 0, True),
    ("ChillAvoidChance", "Chill avoid chance", "%", 0, True),
    ("BleedAvoidChance", "Bleed avoid chance", "%", 0, True),
    ("PoisonAvoidChance", "Poison avoid chance", "%", 0, True),
    ("StunThreshold", "Stun threshold", "", 0, True),
    ("StunAvoidChance", "Stun avoid chance", "%", 0, True),
    ("FlaskChargeGen", "Flask charges gained per second", "", 2, True),
    ("LifeFlaskChargeGen", "Life flask charges gained per second", "", 2, True),
    ("ManaFlaskChargeGen", "Mana flask charges gained per second", "", 2, True),
    ("CharmEffect", "Increased charm effect", "%", 0, True),
    ("ManaPerSecondCost", "Mana cost per second", "", 1, False),
    ("ManaRegenRecovery", "Mana regeneration per second", "", 1, False),
    ("NetManaRegen", "Net mana regeneration per second", "", 1, False),
)
# PoB's data.misc.DotDpsCap (Data.lua: 35791394, (2^31 - 1) / 60); the live
# test reads the pinned checkout when it is installed (TC-DRIFT)
DOT_DPS_CAP = 35791394
# the DPS stats PoB's warnFunc checks against DotDpsCap, with our words
DOT_STATS = (("TotalDotDPS", "damage over time"), ("BleedDPS", "bleed damage"),
             ("IgniteDPS", "ignite damage"), ("PoisonDPS", "poison damage"))
# Precise Technique: PoB checks MainHand / OffHand Accuracy (saved as
# PlayerStat MainHandAccuracy / OffHandAccuracy) against Life, only while
# its output flag PreciseTechnique is set (a calc output)
ACCURACY_STATS = (("MainHandAccuracy", "main hand"), ("OffHandAccuracy", "off hand"))
# every PoB output the build health reads from the calc (calcwire asks only
# for these)
CALC_KEYS = tuple(d[0] for d in DEFENCE) + tuple(k for k, _ in DOT_STATS) + (
    "LifeUnreserved", "ManaUnreserved", "Life", "PreciseTechnique")
# API only: the dashboard hides the card with no build (the build card
# carries that empty state)
NO_BUILD = "Load a build to see its health."
NO_STATS = ("This build has no Path of Building numbers. Open it in Path of Building, "
            "then copy its code again.")

# MATH-NEXT-LOOK: resist / attribute gaps go to the armour and jewellery
# slots; a weapon slot gets only the stats PoB measured for it
GAP_SLOTS = ("Helmet", "Body Armour", "Gloves", "Boots", "Amulet",
             "Ring 1", "Ring 2", "Belt")
SKIP_PREFIX = ("flask", "charm")
MAX_TERMS = 3
RES_KEY = "+#% to {} Resistance"
ATTR_KEY = "+# to {}"


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _stats(build):
    s = getattr(build, "stats", None)
    return s if isinstance(s, dict) else {}


def _fmt(n):
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    if isinstance(n, int):
        return f"{n:,}"
    return f"{n:,.1f}"


def res_gaps(stats):
    """[(element, value)] for elements PoB puts below the cap, the biggest
    gap first (ties in element order). A missing stat is no gap."""
    out = []
    for el in ELEMENTS:
        v = _num(stats.get(waystone.RES_STAT[el]))
        if v is not None and v < RES_CAP:
            out.append((el, v))
    return sorted(out, key=lambda t: (t[1], ELEMENTS.index(t[0])))


def attr_gaps(stats):
    """[(id, have, need, name)] where PoB's ReqX is above X (PoB's own
    warning condition), the biggest shortfall first."""
    out = []
    for aid, have_k, need_k, name in ATTRS:
        have, need = _num(stats.get(have_k)), _num(stats.get(need_k))
        if have is not None and need is not None and need > have:
            out.append((aid, have, need, name))
    return sorted(out, key=lambda t: -(t[2] - t[1]))


def weakest(stats):
    """{"element", "hit"}: the element with PoB's smallest maximum hit
    taken, or None when PoB gave none."""
    hits = [(el, _num(stats.get(el.capitalize() + "MaximumHitTaken"))) for el in ELEMENTS]
    hits = [(el, h) for el, h in hits if h is not None]
    if not hits:
        return None
    el, h = min(hits, key=lambda t: (t[1], ELEMENTS.index(t[0])))
    return {"element": el, "hit": h}


def _calc(calc_out):
    """The calc's output table with only finite numbers and booleans."""
    if not isinstance(calc_out, dict):
        return {}
    return {k: v for k, v in calc_out.items()
            if isinstance(k, str) and (isinstance(v, bool) or (
                _num(v) is not None and math.isfinite(v)))}


def more_warnings(stats, calc):
    """MATH-DEF-BREAKDOWN: PoB's remaining warnFunc conditions. `stats`:
    the saved PlayerStat values with the calc's outputs laid over them;
    `calc`: the calc outputs alone (Precise Technique is a calc flag)."""
    warns = []
    life = _num(stats.get("LifeUnreserved"))
    if life is not None and life <= 0:
        warns.append({"id": "life-reserved", "severity": "high", "stat": "LifeUnreserved",
                      "value": life, "limit": 0,
                      "text": f"Your unreserved Life is {_fmt(life)}: your skills "
                              "reserve all of your Life."})
    mana = _num(stats.get("ManaUnreserved"))
    if mana is not None and mana < 0:
        warns.append({"id": "mana-reserved", "severity": "high", "stat": "ManaUnreserved",
                      "value": mana, "limit": 0,
                      "text": f"Your unreserved Mana is {_fmt(mana)}: your skills "
                              "reserve more Mana than you have."})
    max_life = _num(stats.get("Life"))
    precise = calc.get("PreciseTechnique")
    if precise is True or (_num(precise) is not None and precise != 0):
        for sid, hand in ACCURACY_STATS:
            acc = _num(stats.get(sid))
            if acc is not None and max_life is not None and acc < max_life:
                warns.append({"id": "precise-" + sid, "severity": "high", "stat": sid,
                              "value": acc, "limit": max_life,
                              "text": f"Your {hand} Accuracy ({_fmt(acc)}) is below your "
                                      f"Life ({_fmt(max_life)}), and Precise Technique "
                                      "needs at least as much Accuracy as Life."})
    for sid, words in DOT_STATS:
        dot = _num(stats.get(sid))
        if dot is not None and dot >= DOT_DPS_CAP:
            warns.append({"id": "dot-cap-" + sid, "severity": "medium", "stat": sid,
                          "value": dot, "limit": DOT_DPS_CAP,
                          "text": f"Your {words} ({_fmt(dot)} per second) is at the game's "
                                  "limit, so more of it adds nothing."})
    return warns


def defence(stats, calc_on):
    """MATH-DEF-BREAKDOWN: [{"id", "label", "value", "unit", "digits"}] in
    DEFENCE order; calc-only rows only when the calc is on. A missing or
    non-numeric stat shows nothing."""
    out = []
    for sid, label, unit, digits, calc_only in DEFENCE:
        if calc_only and not calc_on:
            continue
        v = _num(stats.get(sid))
        if v is not None and math.isfinite(v):
            out.append({"id": sid, "label": label, "value": v, "unit": unit,
                        "digits": digits})
    return out


def health(build, calc_out=None):
    """{"loaded", "has_stats", "source", "message", "warnings", "values",
    "defence", "calc_on", "weakest"}. warnings: [{"id", "severity" (high /
    medium / low), "text", "stat", "value", "limit"}], high first.
    `calc_out`: PoB's output table for the loaded build when the optional
    calc is on (it wins over the saved PlayerStat), None with it off."""
    out = {"loaded": build is not None, "has_stats": False, "source": SOURCE,
           "message": None, "warnings": [], "values": [], "defence": [],
           "calc_on": False, "weakest": None}
    if build is None:
        out["message"] = NO_BUILD
        return out
    calc = _calc(calc_out)
    out["calc_on"] = bool(calc)
    stats = dict(_stats(build))
    out["has_stats"] = any(_num(v) is not None for v in stats.values())
    if not stats and not calc:
        out["message"] = NO_STATS
        return out
    warns = []
    for aid, have, need, name in attr_gaps(stats):
        warns.append({"id": "attr-" + aid, "severity": "high", "stat": "Req" + aid.capitalize(),
                      "value": have, "limit": need,
                      "text": f"You don't meet the {name} requirement: you have "
                              f"{_fmt(have)}, your gear and skills need {_fmt(need)}."})
    spirit = _num(stats.get("SpiritUnreserved"))
    if spirit is not None and spirit < 0:
        warns.append({"id": "spirit", "severity": "high", "stat": "SpiritUnreserved",
                      "value": spirit, "limit": 0,
                      "text": f"Your unreserved Spirit is {_fmt(spirit)}: your skills "
                              "reserve more Spirit than you have."})
    for el, v in res_gaps(stats):
        warns.append({"id": "res-" + el, "severity": "medium", "stat": waystone.RES_STAT[el],
                      "value": v, "limit": RES_CAP,
                      "text": f"{el.capitalize()} resistance is {_fmt(v)}%, below the "
                              f"{RES_CAP}% cap."})
    merged = dict(stats, **calc)
    warns.extend(more_warnings(merged, calc))
    weak = weakest(stats)
    if weak is not None:
        warns.append({"id": "weakest", "severity": "low",
                      "stat": weak["element"].capitalize() + "MaximumHitTaken",
                      "value": weak["hit"], "limit": None,
                      "text": f"Your weakest element is {weak['element']}: the biggest "
                              f"{weak['element']} hit you can take is {_fmt(weak['hit'])} damage."})
    warns.sort(key=lambda w: SEVERITY_RANK[w["severity"]])  # stable
    out["warnings"] = warns
    out["weakest"] = weak
    for sid, label, unit in VALUES:
        v = _num(stats.get(sid))
        if v is not None:
            out["values"].append({"id": sid, "label": label, "value": v, "unit": unit})
    out["defence"] = defence(merged, out["calc_on"])
    return out


# ---- MATH-NEXT-LOOK ------------------------------------------------------

_HASH = re.compile(r"[+-]?#%?")


def term_for(key):
    """A short search term for a stat key ("+# to maximum Life" ->
    "maximum life"), None when nothing is left."""
    t = str(key or "").lower()
    t = re.sub(r"\badds\s+#\s+to\s+#", " ", t)
    t = _HASH.sub(" ", t)
    t = re.sub(r"\bresistances?\b", "res", t)
    t = " ".join(t.split())
    if t.startswith("to "):
        t = t[3:]
    t = searchstr.clean(t)
    return t or None


def label_for(term):
    """The shown words for a search term: "cold res" -> "cold resistance"."""
    if term.endswith("elemental res"):
        return term + "istances"
    return re.sub(r"\bres\b", "resistance", term)


def _item_keys(item):
    text = getattr(item, "text", None)
    if not isinstance(text, str):
        return set()
    try:
        parsed = item_parser.parse(text)
    except Exception:  # noqa: BLE001 - a bad item text is no keys
        return set()
    out = set()
    for mod in parsed.mods:
        key, _ = weights_mod.stat_key(mod.text)
        if key:
            out.add(key.lower())
    return out


def _gear(build):
    gear = getattr(build, "gear", None)
    gear = gear if isinstance(gear, dict) else {}
    order = {s.lower(): i for i, s in enumerate(SLOTS)}
    names = [s for s in gear if not str(s).lower().startswith(SKIP_PREFIX)]
    return sorted(names, key=lambda s: (order.get(str(s).lower(), len(SLOTS)), str(s)))


def next_look(build, weights_for=None):
    """{"slots": [{"slot", "terms", "line", "text", "dropped"}],
    "pob_weights": bool}. `weights_for(build, slot)` returns the stat
    weights PoB measured for this build and slot (pobweights fallback);
    without one, or when it fails, only the health gaps are used."""
    out = {"slots": [], "pob_weights": False}
    if build is None:
        return out
    stats = _stats(build)
    gaps = [(RES_KEY.format(el.capitalize()), f"{el} res") for el, _ in res_gaps(stats)]
    gaps += [(ATTR_KEY.format(name), name.lower()) for _, _, _, name in attr_gaps(stats)]
    gap_slots = {s.lower() for s in GAP_SLOTS}
    for slot in _gear(build):
        terms = []
        if slot.lower() in gap_slots:
            terms.extend(t for _, t in gaps)
        table = {}
        if callable(weights_for):
            try:
                table = weights_for(build, slot) or {}
            except Exception:  # noqa: BLE001 - weights are optional
                table = {}
        if table:
            out["pob_weights"] = True
        have = _item_keys(build.gear.get(slot))
        gap_keys = {k.lower() for k, _ in gaps}
        ranked = sorted(((k, w) for k, w in table.items()
                         if _num(w) is not None and w > 0 and k.lower() not in have
                         and k.lower() not in gap_keys),
                        key=lambda kw: (-kw[1], kw[0].lower()))
        for k, _ in ranked:
            t = term_for(k)
            if t and t not in terms:
                terms.append(t)
        terms = terms[:MAX_TERMS]
        if not terms:
            continue
        text, kept = searchstr.join(terms)
        if text is None:
            continue
        dropped = len(terms) - kept
        terms = terms[:kept]
        out["slots"].append({"slot": slot, "terms": terms,
                             "line": ", then ".join(label_for(t) for t in terms),
                             "text": text, "dropped": dropped})
    return out
