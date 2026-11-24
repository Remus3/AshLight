"""KINDLER-PLAN (decision 0081 points 14 to 17): the plan of Kindler's
top-ranked template, and the resolver that picks the stage the player is
in from what the snapshot already publishes.

`build_plan` turns one resolved template (theorycraft.archetypes.resolve:
unknown node ids already dropped, every gem with checked and a level) into
a plan document, stage by stage from levelling to maps:

- skills in use, each with its support links (the authored sockets) and
  per support "applies": what Path of Building reports through the bridge
  when a `fit` callable is given, else None (not reported; never guessed);
- gem steps (pick / swap / drop) with the stage trigger they belong to and
  the level the gem can be used at (the gems snapshot's level when the
  snapshot names it, checked=True; else the authored level, checked=False;
  point 16);
- the passives this stage adds, in the authored allocation order, the
  running point count and the stage's point budget; ascendancy nodes apart
  with the trial number ("after your Nth Ascendancy trial", worded by the
  page; never a claim the trial was done; points 14 and 15);
- per-slot item focus. With the calc on, the stats of the non-weapon
  slots are ranked by Path of Building's per-mod weights (decision 0024,
  delta.mod_weights on one probe carrier item, `focus_weights`); stats
  PoB cannot weigh (no stat key, or a zero weight: no DPS / EHP change,
  such as movement speed) keep their authored place. Weapon slots and the
  calc-off plan keep the authored priority (focus source "authored").

`current_stage` is the follow-Play-guidance resolver (point 17). It reads
only the snapshot's published "area_id", "area_level" and "level" (and the
act of the area id by acts.act_of, the same helper the snapshot's acts view
uses): no new read, no log parse. Priority: a zone trigger on the area id,
then an act trigger on the campaign act, then an area-level band, then a
character-level band, then the first stage planned at or above the level.
It answers which stage to highlight and why, never that a step was done.

`Planner` keeps one PoB focus run at a time on its own daemon worker and
the weights per result key in memory (CACHE_MAX keys). Nothing here owns a
calc, a tree search or an optimiser (decision 0004); nothing is read from
the game, the clipboard or the screen, and nothing is fetched.
"""

import threading

from .. import acts, hotreload
from . import archetypes, basetypes, delta, kindler

CACHE_MAX = 16
CARRIER_SLOT = "Amulet"
CARRIER_CLASS = "Amulet"
WEAPON_SLOTS = ("Weapon 1", "Weapon 2")
FOCUS_POB, FOCUS_AUTHORED = "pob", "authored"
# focus words (the page says them in plain words; no sentence here)
FOCUS_PENDING = "pending"
FOCUS_CALC_OFF = "calc_off"
FOCUS_NO_BASE = "no_base"
FOCUS_FAILED = "failed"
FOCUS_NO_TREE = "no_tree"
BY_ZONE, BY_ACT, BY_AREA_LEVEL, BY_LEVEL, BY_NEAREST = (
    "zone", "act", "area_level", "level", "nearest_level")
CAMPAIGN_PREFIX = "G"  # acts.act_of key prefix of the campaign acts

# Authored focus words -> the stat key PoB is probed with (the weights
# table's own key shapes, theorycraft.weights). A word missing here has no
# probe and keeps its authored place.
STAT_KEYS = {
    "maximum life": "+# to maximum Life",
    "life": "+# to maximum Life",
    "energy shield": "+# to maximum Energy Shield",
    "maximum mana": "+# to maximum Mana",
    "spirit": "+# to Spirit",
    "resistances": "+#% to all Elemental Resistances",
    "strength": "+# to Strength",
    "dexterity": "+# to Dexterity",
    "intelligence": "+# to Intelligence",
    "armour": "+# to Armour",
    "evasion": "+# to Evasion Rating",
    "physical damage": "#% increased Physical Damage",
    "added physical damage": "Adds # to # Physical Damage",
    "added lightning damage": "Adds # to # Lightning Damage",
    "lightning damage": "#% increased Lightning Damage",
    "spell damage": "#% increased Spell Damage",
    "minion damage": "Minions deal #% increased Damage",
    "attack speed": "#% increased Attack Speed",
    "cast speed": "#% increased Cast Speed",
    "accuracy": "+# to Accuracy Rating",
    "level of minion skills": "+# to Level of all Minion Skills",
    "level of lightning spell skills": "+# to Level of all Lightning Spell Skills",
    "level of projectile skills": "+# to Level of all Projectile Skills",
}


# --- the probe carrier ---------------------------------------------------------

def carrier_base_from_doc(doc):
    """The probe carrier's base name from a parsed base_items snapshot: the
    first released CARRIER_CLASS base by name (fixed, no drop level read);
    None when there is none."""
    if not isinstance(doc, dict):
        return None
    names = []
    for entry in doc.values():
        if not isinstance(entry, dict) or entry.get("item_class") != CARRIER_CLASS:
            continue
        if entry.get("release_state") != "released":
            continue
        name = entry.get("name")
        if isinstance(name, str) and name.strip() and name.isascii() and name.isprintable():
            names.append(" ".join(name.split()))
    return min(names) if names else None


def _load_base(path):
    return carrier_base_from_doc(hotreload.load_json(path))


def carrier_text(base):
    """A plain rare item of `base` with no mods: the line each probe is
    appended to (delta.mod_weights)."""
    return ("Item Class: Amulets\nRarity: Rare\nAshLight Probe\n"
            f"{base}\n--------\nItem Level: 1\n--------")


# --- focus ---------------------------------------------------------------------

def stat_key(word):
    return STAT_KEYS.get(word.lower()) if isinstance(word, str) else None


def focus_keys(template):
    """The distinct probe keys of the template's non-weapon focus stats, in
    stage, slot and authored order, at most delta.MAX_PROBES."""
    out = []
    for st in template["stages"]:
        for slot, stats in st["focus"].items():
            if slot in WEAPON_SLOTS:
                continue
            for word in stats:
                key = stat_key(word)
                if key and key not in out:
                    out.append(key)
    return out[:delta.MAX_PROBES]


def rank_stats(stats, weights):
    """[{"stat", "weight"}]: stats with a non-zero PoB weight re-ordered
    among their own places by weight (highest first, ties keep authored
    order); a stat with no weight (None) or a zero one (PoB saw no DPS / EHP
    change, e.g. damage on a build composed without a weapon) keeps its
    authored place."""
    weights = weights or {}
    rows = [{"stat": w, "weight": weights.get(stat_key(w))} for w in stats]
    slots = [i for i, r in enumerate(rows) if r["weight"]]
    order = sorted(slots, key=lambda i: (-rows[i]["weight"], i))
    out = list(rows)
    for place, src in zip(slots, order):
        out[place] = rows[src]
    return out


def stage_focus(focus, weights):
    """[{"slot", "stats", "source"}] in the authored slot order."""
    out = []
    for slot, stats in focus.items():
        pob = weights is not None and slot not in WEAPON_SLOTS
        out.append({"slot": slot,
                    "stats": rank_stats(stats, weights if pob else None),
                    "source": FOCUS_POB if pob else FOCUS_AUTHORED})
    return out


def focus_weights(calc, xml, base, keys):
    """{probe key: blended pct per point} from Path of Building (decision
    0024): each key's line appended to the carrier in CARRIER_SLOT of the
    composed build. Raises delta.CalcError."""
    if not keys:
        return {}
    got = delta.mod_weights(calc, kindler._Xml(xml), CARRIER_SLOT,
                            carrier_text(base), keys)
    return dict(got["weights"])


# --- the plan --------------------------------------------------------------------

def _gem(info):
    return {"name": info["name"], "level": info["level"], "checked": info["checked"]}


def _applies(fit, skill, supports):
    """{support name: True / False} from `fit`, {} when it is None or fails;
    a name it does not answer stays None in the plan."""
    if fit is None:
        return {}
    try:
        got = fit(skill, list(supports))
    except Exception:  # noqa: BLE001 - extra info only; never fail the plan
        return {}
    return {k: v for k, v in (got or {}).items() if isinstance(v, bool)} \
        if isinstance(got, dict) else {}


def _node(tree, nid):
    name = tree.name(nid) if tree is not None else None
    return {"id": nid, "name": name}


def build_plan(template, weights=None, fit=None, tree=None, note=""):
    """The plan document of one resolved template. `weights` is
    focus_weights() or None (authored focus), `fit(skill, supports)` the
    bridge's support applicability or None, `tree` a TreeData for node
    names or None, `note` the focus word when weights is None."""
    stages, points = [], 0
    for st in template["stages"]:
        skills = []
        for sk in st["skills"]:
            fits = _applies(fit, sk["gem"]["name"], [s["name"] for s in sk["supports"]])
            skills.append(dict(_gem(sk["gem"]), sockets=sk["sockets"],
                               supports=[dict(_gem(s), applies=fits.get(s["name"]))
                                         for s in sk["supports"]]))
        points += len(st["passives"])
        asc = st["ascendancy"]
        stages.append({
            "id": st["id"], "label": st["label"], "trigger": dict(st["trigger"]),
            "level": st["level"], "skills": skills,
            "gems": [{"name": g["name"], "action": g["action"], "for": g["for"],
                      "level": g["level"], "checked": g["checked"],
                      "trigger": dict(st["trigger"])} for g in st["gems"]],
            "passives": [_node(tree, n) for n in st["passives"]],
            "points": points,
            "budget": archetypes.point_budget(st["level"], st.get("bonus_points") or 0),
            "ascendancy": None if asc is None else {
                "trial": asc["trial"], "nodes": [_node(tree, n) for n in asc["nodes"]]},
            "focus": stage_focus(st["focus"], weights),
        })
    return {"template": template["id"], "label": template["label"],
            "class": template["class"], "ascendancy": template.get("ascendancy"),
            "focus": FOCUS_POB if weights is not None else FOCUS_AUTHORED,
            "focus_note": "" if weights is not None else note,
            "stages": stages}


# --- follow Play guidance ------------------------------------------------------

def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def here_of(snapshot):
    """The three published values the resolver reads from a snapshot-like
    mapping (or object): {"area_id", "area_level", "level"}."""
    get = snapshot.get if isinstance(snapshot, dict) else (
        lambda k: getattr(snapshot, k, None))
    area = get("area_id")
    return {"area_id": area if isinstance(area, str) else None,
            "area_level": _int(get("area_level")), "level": _int(get("level"))}


def current_stage(plan, here):
    """{"stage": index, "id", "by"} of the stage to highlight for `here`
    (here_of), or None when nothing is known. Never a claim of progress."""
    stages = (plan or {}).get("stages") or []
    if not stages:
        return None
    area, alvl, lvl = here.get("area_id"), here.get("area_level"), here.get("level")
    act = acts.act_of(area)
    act_n = act["n"] if act and act["key"].startswith(CAMPAIGN_PREFIX) else None

    def pick(by, test):
        for i, st in enumerate(stages):
            if test(st["trigger"]):
                return {"stage": i, "id": st["id"], "by": by}
        return None

    for by, ok, test in (
            (BY_ZONE, area is not None,
             lambda t: t["kind"] == "zone" and t["zone"] == area),
            (BY_ACT, act_n is not None,
             lambda t: t["kind"] == "act" and t["act"] == act_n),
            (BY_AREA_LEVEL, alvl is not None and act_n is None,
             lambda t: t["kind"] == "area_level" and t["min"] <= alvl <= t["max"]),
            (BY_LEVEL, lvl is not None,
             lambda t: t["kind"] == "level" and t["min"] <= lvl <= t["max"])):
        if ok:
            hit = pick(by, test)
            if hit is not None:
                return hit
    if lvl is None:
        return None
    for i, st in enumerate(stages):
        if st["level"] >= lvl:
            return {"stage": i, "id": st["id"], "by": BY_NEAREST}
    return {"stage": len(stages) - 1, "id": stages[-1]["id"], "by": BY_NEAREST}


# --- the planner: PoB focus weights, one run at a time ------------------------------

def best_of(result, templates):
    """(template, stage index, variant) of a Kindler result's best row, or
    None when the table no longer has it."""
    best = (result or {}).get("best")
    if not best:
        return None
    t = next((x for x in templates if x["id"] == best["template"]), None)
    if t is None:
        return None
    si = next((i for i, st in enumerate(t["stages"]) if st["id"] == best.get("stage")),
              len(t["stages"]) - 1)
    return t, si, best.get("variant") or 0


class Planner:
    """Plans for Kindler results. `sources` is a kindler.Sources (or the
    same shape), `calc()` the calc callable or None, `fit` the support
    applicability callable or None, `base_path` the base_items snapshot."""

    def __init__(self, sources, calc, fit=None, base_path=None):
        self.sources = sources
        self._calc = calc
        self.fit = fit
        self._base = hotreload.Watched(base_path or basetypes.default_path(), _load_base,
                                       name=basetypes.FILE_NAME,
                                       default=None, registry=False,
                                       check=hotreload.check_json(basetypes.MAX_BYTES),
                                       from_doc=carrier_base_from_doc, share=True)
        self._lock = threading.Lock()
        self._cache = {}     # result key -> weights dict, or FOCUS_FAILED etc.
        self._running = None
        self._missing = False  # the last run found no carrier base
        self._thread = None

    def _calc_now(self):
        try:
            return self._calc()
        except Exception:  # noqa: BLE001 - a broken provider reads as off
            return None

    def join(self, timeout=None):
        t = self._thread
        if t is not None:
            t.join(timeout)

    def running(self):
        with self._lock:
            return self._running

    def plan(self, result, busy=False, wait=False):
        """(plan document or None, focus word). With the calc on and a scored
        result, the first call starts the PoB focus run (unless `busy`, the
        engine's run in flight) and answers the authored plan with
        FOCUS_PENDING; later calls answer the PoB-ranked plan."""
        inputs = self.sources.inputs()
        hit = best_of(result, inputs["view"]["templates"])
        if hit is None:
            return None, ""
        template, si, variant = hit
        tree = inputs.get("tree")
        calc = self._calc_now()
        if calc is None or not result.get("scored"):
            return build_plan(template, tree=tree, fit=self.fit,
                              note=FOCUS_CALC_OFF), FOCUS_CALC_OFF
        if tree is None:
            return build_plan(template, fit=self.fit, note=FOCUS_NO_TREE), FOCUS_NO_TREE
        key = result.get("key")
        start = False
        with self._lock:
            got = self._cache.get(key)
            if got is None and self._running is None and not busy:
                self._running, start = key, True
        if start:
            args = (key, calc, template, si, variant, tree)
            if wait:
                self._run(*args)
            else:
                self._thread = threading.Thread(target=self._run, args=args,
                                                name="al-kindler-plan", daemon=True)
                self._thread.start()
        with self._lock:
            got = self._cache.get(key)
            if got is None and self._missing and self._running is None:
                got = FOCUS_NO_BASE
        if isinstance(got, dict):
            return build_plan(template, weights=got, fit=self.fit, tree=tree), FOCUS_POB
        word = got if isinstance(got, str) else FOCUS_PENDING
        return build_plan(template, fit=self.fit, tree=tree, note=word), word

    def _run(self, key, calc, template, si, variant, tree):
        try:
            base = self._base.get()
            if not base:
                got = FOCUS_NO_BASE
            else:
                try:
                    xml = kindler.compose_xml(template, si, variant,
                                              kindler.tree_ids(tree, template))
                    got = focus_weights(calc, xml, base, focus_keys(template))
                except (kindler.TreeIdsMissing, delta.CalcError):
                    got = FOCUS_FAILED
            with self._lock:
                if got == FOCUS_NO_BASE:  # asked again once the snapshot lands
                    self._missing = True
                    return
                self._missing = False
                self._cache[key] = got
                while len(self._cache) > CACHE_MAX:
                    self._cache.pop(next(iter(self._cache)))
        finally:
            with self._lock:
                self._running = None
