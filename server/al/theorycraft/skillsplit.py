"""MATH-SKILL-SPLIT: per-skill and ailment DPS from Path of Building.

PoB writes one `<FullDPSSkill stat value skillPart source>` element per
contributing skill into every saved build XML (research 0031 section 2),
so the split works with the optional calc component off. The ailment
figures (BleedDPS, IgniteDPS, PoisonDPS, ImpaleDPS, TotalDotDPS) are PoB's
own PlayerStat entries, or the calc's output for the loaded build when the
calc is on. Nothing is recomputed (decision 0004): the only arithmetic is
each skill's share of the summed PoB values, and the order.
"""

import math
import re

from . import model

SOURCE = "PoB"
# PoB output id, shown label (research 0031 section 2, BuildDisplayStats)
AILMENTS = (("BleedDPS", "Bleed"), ("IgniteDPS", "Ignite"), ("PoisonDPS", "Poison"),
            ("ImpaleDPS", "Impale"), ("TotalDotDPS", "All damage over time"))
KEYS = tuple(k for k, _ in AILMENTS)


def _finite(v):
    """A finite float from a number or numeric text, else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        try:
            v = float(v.strip())
        except ValueError:
            return None
    if not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


# PoB writes a skill used more than once as "<count>x <name>" (Build.lua,
# s_format("%g", skillCount).."x "..name); the value is already dps * count
_COUNT = re.compile(r"^(\d+(?:\.\d+)?)x (.+)$")


def _name_count(stat):
    """(name, count) from PoB's stat text; count None when PoB wrote none."""
    m = _COUNT.match(stat)
    if not m:
        return stat, None
    n = float(m.group(1))
    if not math.isfinite(n) or n <= 0:
        return stat, None
    return m.group(2).strip(), int(n) if n.is_integer() else n


def skills(xml):
    """[{"name", "part", "source", "count", "dps"}] from the build XML's
    FullDPSSkill elements, the biggest DPS first. A missing name or a
    non-finite, zero or negative value is dropped."""
    if not isinstance(xml, str) or not xml.strip():
        return []
    try:
        root = model._root(xml)
    except model.BuildError:
        return []
    b = root.find("Build")
    if b is None:
        return []
    out = []
    for el in b.findall("FullDPSSkill"):
        name, count = _name_count((el.get("stat") or "").strip())
        dps = _finite(el.get("value"))
        if not name or dps is None or dps <= 0:
            continue
        out.append({"name": name, "part": (el.get("skillPart") or "").strip() or None,
                    "source": (el.get("source") or "").strip() or None,
                    "count": count, "dps": dps})
    out.sort(key=lambda s: -s["dps"])  # stable: PoB's order on ties
    return out


def split(build, calc_out=None):
    """{"source", "skills": [... + "share"], "total", "ailments":
    [{"id", "label", "dps"}], "from_calc"}. `calc_out`: PoB's output table
    for the loaded build when the calc is on (it wins over the saved
    PlayerStat); None with the calc off."""
    out = {"source": SOURCE, "skills": [], "total": None, "ailments": [],
           "from_calc": False}
    if build is None:
        return out
    rows = skills(getattr(build, "raw_xml", None))
    total = sum(r["dps"] for r in rows)
    if rows and total > 0:
        for r in rows:
            r["share"] = r["dps"] / total
        out["skills"], out["total"] = rows, total
    stats = getattr(build, "stats", None)
    stats = stats if isinstance(stats, dict) else {}
    calc = calc_out if isinstance(calc_out, dict) else {}
    for key, label in AILMENTS:
        v = _finite(calc.get(key))
        if v is not None:
            out["from_calc"] = True
        else:
            v = _finite(stats.get(key))
        if v is not None and v > 0:
            out["ailments"].append({"id": key, "label": label, "dps": v})
    return out
