"""KINDLER-ENGINE (decision 0081 points 2 to 5, 12 and 13): Kindler's
candidates, their Path of Building scores and the fixed ranking.

One Generate click (server/al/plug/kindler.py) runs `Engine.generate` for
one tab of the Kindler store (theorycraft.genstore). The engine:

1. Picks a bounded candidate set from the resolved template table
   (theorycraft.archetypes; unknown node ids already dropped): templates of
   the tab's class (any class while it is empty), none carrying a toggle
   the tab says "no" to, none of another defence than the tab's (unless
   "unsure"), ordered by how many of the tab's "yes" toggles they cover
   (most first), then template id. Each template gives one variant per
   skill of its scored stage (variant i = skill i is the main skill), in
   authored order. At most MAX_CANDIDATES in all.
2. The scored stage is the level band's: the last stage whose plan level
   is at or under the band's top (the first stage when none is); with no
   known character level the band is BAND_ALL and the last stage is scored.
3. Composes each candidate as PoB XML (compose_xml): the class and the
   ascendancy by the cached GGG tree export's own class index and
   ascendancy id (never guessed; no export means nothing is composed), the
   stage's plan level, the passive prefix and ascendancy nodes of every
   stage up to it, the stage's skills with their supports by gem name, gem
   level FULL_GEM_LEVEL (PoB clamps to the gem's own range) and quality 0.
   The one item composed is the template's authored weapon base
   (KINDLER-WEAPON-BASE), a plain normal item in WEAPON_SLOT, and only when
   the cached base_items snapshot names it as a weapon base (checked by
   archetypes.resolve; never guessed). Without it an attack skill has no
   weapon and PoB scores 0 DPS. No other item is composed. A skill gem
   whose name PoB holds under several weapon variants (Mace Strike) also
   carries PoB's skillId attribute when archetypes.resolve found the one
   variant of the weapon's class in the pinned PoB Gems.lua
   (KINDLER-GEM-VARIANT, theorycraft.pobtext); otherwise the gem is
   written by name only, never guessed.
4. Scores them one at a time through the calc callable of decision 0024
   (calcwire: the bridge's load_build then outputs; no new bridge command)
   inside BUDGET_S. Past the budget the rest are left out and the result
   is labelled partial; a partial result is never cached as final.
5. Ranks by PoB outputs only: each candidate's DPS and EHP as a percent of
   the best candidate's, blended by delta.combined (the fixed 50/50 blend
   of decision 0024); ties by template id ascending, then variant index
   ascending. No random source; the clock decides only the budget cut.
6. Keys the result by sha256 of (class, toggle values, archetypes.json
   sha256, PoB pin, tree export version, level band). A final result is
   kept in memory per key (CACHE_MAX keys), so a repeat Generate on the
   same inputs answers the same bytes without a calc.

With the calc off (or no tree export) one template is shown, picked by
toggle-match count then template id, labelled not scored, with no DPS or
EHP number (point 5). The result document carries no time; the store's
summary takes the wall time apart.

AshLight owns no calc, no tree search and no optimiser here (decision
0004): the route is the authored list, the numbers are PoB's. Nothing is
read from the game, the clipboard or the screen; nothing is fetched.
"""

import hashlib
import json
import threading
import time
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .. import hotreload, paths
from ..text import kindler as words
from . import archetypes, delta, genstore, pobtext, treedata

MAX_CANDIDATES = genstore.MAX_CANDIDATES  # decision 0081 point 3
BUDGET_S = 60.0
CACHE_MAX = 16
FULL_GEM_LEVEL = 20
BAND_SIZE = 10
BAND_ALL = "all"
DEFENCE = {"life": "life", "energy_shield": "es", "hybrid": "hybrid"}
TABLE_MAX_BYTES = archetypes.MAX_BYTES
WEAPON_SLOT = "Weapon 1"

# result words (the page says them in plain words; no sentence here)
NO_MATCH = "no_match"
CALC_OFF = "calc_off"
NO_TREE = "no_tree"
NO_SCORE = "no_score"
STATES = ("started", "running", "done", "none")


# --- inputs -----------------------------------------------------------------

def _load_table(path):
    """(validated table, sha256 of the file bytes)."""
    p = Path(path)
    if p.stat().st_size > TABLE_MAX_BYTES:
        raise ValueError("template table too large")
    raw = p.read_bytes()
    return archetypes.validate(json.loads(raw.decode("ascii"))), \
        hashlib.sha256(raw).hexdigest()


def _load_tree(path):
    """(TreeData, TreeGraph, sha256 of the export bytes) from one parse."""
    p = Path(path)
    if p.stat().st_size > treedata.MAX_BYTES:
        raise ValueError("tree file too large")
    raw = p.read_bytes()
    doc = json.loads(raw)
    return treedata.parse(doc), archetypes.tree_graph(doc), \
        hashlib.sha256(raw).hexdigest()


def _load_gems(path):
    p = Path(path)
    if p.stat().st_size > archetypes.GEMS_MAX_BYTES:
        raise ValueError("gems file too large")
    return archetypes.gem_index(json.loads(p.read_bytes()))


def _load_bases(path):
    p = Path(path)
    if p.stat().st_size > archetypes.BASES_MAX_BYTES:
        raise ValueError("base_items file too large")
    return archetypes.base_index(json.loads(p.read_bytes()))


def pob_pin(pins_path=None):
    """The pinned PoB commit of config/tc_pins.json, "" when unreadable."""
    try:
        doc = json.loads(Path(pins_path or paths.tc_pins_file()).read_text(encoding="ascii"))
        commit = doc["pob2"]["commit"]
        return commit if isinstance(commit, str) else ""
    except (OSError, ValueError, KeyError, TypeError):
        return ""


class Sources:
    """The template table, the tree export, the gems snapshot and the
    base_items snapshot's weapon bases, each re-read on change (decision
    0042), the last good copy kept."""

    def __init__(self, table_path=None, tree_path=None, gems_file=None, pins_path=None,
                 bases_file=None, variants=None):
        self._table = hotreload.Watched(table_path or archetypes.PATH, _load_table,
                                        name=words.ENGINE_TABLE_NAME,
                                        default=None, registry=False)
        self._tree = hotreload.Watched(tree_path or treedata.default_path(), _load_tree,
                                       name=words.ENGINE_TREE_NAME,
                                       default=None, registry=False)
        self._gems = hotreload.Watched(gems_file or archetypes.gems_path(), _load_gems,
                                       name=words.ENGINE_GEMS_NAME,
                                       default=None, registry=False)
        self._bases = hotreload.Watched(bases_file or archetypes.default_bases(gems_file),
                                        _load_bases,
                                        name=words.ENGINE_BASES_NAME,
                                        default=None, registry=False)
        self._pins = pins_path
        # KINDLER-GEM-VARIANT: the pinned PoB Gems.lua, read as text
        self._variants = variants if variants is not None else \
            pobtext.GemVariants(pins_path)

    def inputs(self):
        """{"view", "table_sha", "tree", "tree_version", "pin"}; view is the
        resolved table (archetypes.resolve), tree the TreeData or None."""
        table = self._table.get()
        tree = self._tree.get()
        gems = self._gems.get()
        doc, table_sha = table if table else ({}, "")
        data, graph, tree_sha = tree if tree else (None, None, "")
        return {"view": archetypes.resolve(doc, tree=graph, gems=gems,
                                           bases=self._bases.get(),
                                           variants=self._variants.get()),
                "table_sha": table_sha, "tree": data, "tree_version": tree_sha,
                "pin": pob_pin(self._pins)}

    def gems(self):
        """PROGRESSION-VIEW (decision 0088): the cached gems snapshot's
        index (archetypes.gem_index) or None, the same watch inputs() reads."""
        return self._gems.get()


# --- key, band, candidates ----------------------------------------------------

def level_band(level):
    """"1-10", "11-20", ... for a character level 1 to 100; BAND_ALL when
    it is unknown."""
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 100:
        return BAND_ALL
    lo = (level - 1) // BAND_SIZE * BAND_SIZE + 1
    return f"{lo}-{lo + BAND_SIZE - 1}"


def band_top(band):
    return None if band == BAND_ALL else int(band.split("-")[1])


def result_key(cls, toggles, table_sha, pin, tree_version, band):
    """sha256 of the six inputs (decision 0081 point 12), canonical JSON."""
    doc = [cls or "", {k: toggles.get(k, genstore.UNSURE) for k in genstore.TOGGLE_KEYS},
           table_sha or "", pin or "", tree_version or "", band]
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def match_count(template, toggles):
    """How many of the tab's "yes" toggles the template covers; None when
    it carries a "no" toggle or another defence than a chosen one."""
    own = set(template["toggles"])
    for key in genstore.TOGGLES:
        if toggles.get(key) == "no" and key in own:
            return None
    want = DEFENCE.get(toggles.get("defence"))
    if want is not None and template.get("defence") not in (None, want):
        return None
    return sum(1 for k in genstore.TOGGLES if toggles.get(k) == "yes" and k in own)


def ordered_templates(templates, cls, toggles):
    """[(match count, template)] that pass the filters, most matches first,
    then template id."""
    out = []
    for t in templates:
        if cls and t["class"].lower() != cls.lower():
            continue
        n = match_count(t, toggles)
        if n is not None:
            out.append((n, t))
    out.sort(key=lambda nt: (-nt[0], nt[1]["id"]))
    return out


def stage_index(template, band):
    """The scored stage: the last one whose plan level is at or under the
    band's top, else the first; the last stage for BAND_ALL."""
    top = band_top(band)
    stages = template["stages"]
    if top is None:
        return len(stages) - 1
    pick = 0
    for i, st in enumerate(stages):
        if st["level"] <= top:
            pick = i
    return pick


def candidates(templates, cls, toggles, band, limit=MAX_CANDIDATES):
    """[{"template", "variant", "stage", "skill"}] in candidate order, at
    most `limit`. Variant i scores skill i of the stage as the main skill."""
    out = []
    for _n, t in ordered_templates(templates, cls, toggles):
        si = stage_index(t, band)
        skills = t["stages"][si]["skills"]
        for vi, sk in enumerate(skills or [None]):
            if len(out) >= limit:
                return out
            out.append({"template": t, "variant": vi, "stage": si,
                        "skill": sk["gem"]["name"] if sk else None})
    return out


# --- PoB XML -------------------------------------------------------------------

class TreeIdsMissing(ValueError):
    """The tree export does not name the template's class or ascendancy."""


def tree_ids(tree, template):
    """(classInternalId, ascendancyInternalId) from the cached GGG export:
    the class's index in its classes list and the ascendancy's export id
    ("" for none). Raises TreeIdsMissing; never guessed."""
    want = template["class"].lower()
    idx = next((i for i, name in enumerate(tree.classes)
                if isinstance(name, str) and name.lower() == want), None)
    if idx is None:
        raise TreeIdsMissing(template["class"])
    asc = template.get("ascendancy")
    asc_id = ""
    if asc:
        asc_id = tree.ascendancy_id(asc)
        if not asc_id:
            raise TreeIdsMissing(asc)
    return idx, asc_id


def _gem(name, skill_id=None):
    """One Gem line by name; with a checked skill id (KINDLER-GEM-VARIANT)
    PoB loads that exact variant (its own skillId attribute)."""
    sid = f" skillId={quoteattr(skill_id)}" if skill_id else ""
    return (f'\t\t\t\t<Gem nameSpec={quoteattr(name)}{sid} level="{FULL_GEM_LEVEL}" '
            f'quality="0" enabled="true" count="1"/>')


def weapon_text(base):
    """A plain normal item of `base` with no mods (PoB reads a normal
    item's name line as its base)."""
    return f"Rarity: NORMAL\n{base}"


def _items(template):
    """The Items block lines: the checked weapon base in WEAPON_SLOT, else
    an empty item set."""
    weapon = template.get("weapon")
    if not (isinstance(weapon, dict) and weapon.get("checked")):
        return ['\t<Items activeItemSet="1">', '\t\t<ItemSet id="1"/>', "\t</Items>"]
    return ['\t<Items activeItemSet="1">', '\t\t<Item id="1">',
            escape(weapon_text(weapon["name"])), "\t\t</Item>",
            '\t\t<ItemSet id="1">',
            f'\t\t\t<Slot name={quoteattr(WEAPON_SLOT)} itemId="1"/>',
            "\t\t</ItemSet>", "\t</Items>"]


def compose_xml(template, stage, variant, ids):
    """PoB XML of one candidate: `stage` is the stage index, `variant` the
    main skill index, `ids` tree_ids(). Passives and ascendancy nodes of
    every stage up to `stage`, in authored order; the template's checked
    weapon base in WEAPON_SLOT."""
    class_idx, asc_id = ids
    stages = template["stages"][:stage + 1]
    nodes = [n for st in stages for n in st["passives"]]
    nodes += [n for st in stages for n in ((st["ascendancy"] or {}).get("nodes") or ())]
    st = stages[-1]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<PathOfBuilding2>",
             f'\t<Build level="{st["level"]}" className={quoteattr(template["class"])} '
             f'ascendClassName={quoteattr(template.get("ascendancy") or "None")} '
             f'mainSocketGroup="{variant + 1}" targetVersion="0_1"/>',
             '\t<Skills activeSkillSet="1" defaultGemLevel="normalMaximum" '
             'defaultGemQuality="0">', '\t\t<SkillSet id="1">']
    for i, sk in enumerate(st["skills"]):
        full = "true" if i == variant else "false"
        lines.append(f'\t\t\t<Skill enabled="true" includeInFullDPS="{full}" '
                     'mainActiveSkill="1" mainActiveSkillCalcs="1" label="">')
        lines.append(_gem(sk["gem"]["name"], sk["gem"].get("skill_id")))
        lines.extend(_gem(s["name"]) for s in sk["supports"])
        lines.append("\t\t\t</Skill>")
    lines += ["\t\t</SkillSet>", "\t</Skills>", '\t<Tree activeSpec="1">',
              f'\t\t<Spec classInternalId="{class_idx}" '
              f'ascendancyInternalId={quoteattr(asc_id)} secondaryAscendClassId="0" '
              f'masteryEffects="" nodes="{",".join(str(n) for n in nodes)}"/>',
              "\t</Tree>"] + _items(template) + ["</PathOfBuilding2>", ""]
    return "\n".join(lines)


class _Xml:
    """The build object the calc callable reads (raw_xml only)."""

    def __init__(self, xml):
        self.raw_xml = xml


def score_xml(calc, xml):
    """{"dps", "ehp"} of one PoB XML through the calc callable (decision
    0024: calcwire loads it, then reads PoB's outputs). Raises CalcError."""
    out = delta.outputs(calc, _Xml(xml))
    return {"dps": out["dps"], "ehp": out["ehp"]}


# --- ranking ---------------------------------------------------------------------

def _num(v):
    v = round(float(v), 4)
    return int(v) if v.is_integer() else v


def rank(scored):
    """Scored candidates ({"template", "variant", "dps", "ehp", ...}) with
    "score" set, best first: each output as a percent of the best one's,
    blended by delta.combined (0024's 50/50); ties by template id, then
    variant."""
    if not scored:
        return []
    best = {k: max(c[k] for c in scored) for k in delta.OUTPUTS}
    out = []
    for c in scored:
        pcts = {k: (delta.pct(best[k], c[k]) or 0.0) if best[k] else 0.0
                for k in delta.OUTPUTS}
        out.append(dict(c, score=round(delta.combined(pcts), 4)))
    out.sort(key=lambda c: (-c["score"], c["template"], c["variant"]))
    return out


def _entry(cand, numbers=None):
    t = cand["template"]
    row = {"template": t["id"], "label": t["label"], "variant": cand["variant"],
           "skill": cand["skill"], "stage": t["stages"][cand["stage"]]["id"]}
    if numbers is not None:
        row.update(dps=_num(numbers["dps"]), ehp=_num(numbers["ehp"]))
    return row


def unscored(templates, cls, toggles, key, band, word):
    """The calc-off result: the top template by toggle match, then id; no
    number (decision 0081 points 5 and 12)."""
    order = ordered_templates(templates, cls, toggles)
    if not order:
        return {"key": key, "band": band, "scored": False, "partial": False,
                "candidates": [], "best": None, "note": NO_MATCH}
    t = order[0][1]
    si = stage_index(t, band)
    skills = t["stages"][si]["skills"]
    row = _entry({"template": t, "variant": 0, "stage": si,
                  "skill": skills[0]["gem"]["name"] if skills else None})
    return {"key": key, "band": band, "scored": False, "partial": False,
            "candidates": [row], "best": row, "note": word}


def generate(inputs, tab, level, calc, clock=time.monotonic, budget_s=BUDGET_S,
             limit=MAX_CANDIDATES):
    """The result document of one Generate for `tab` (a genstore tab) at
    character `level`. `calc` is the calc callable or None (calc off)."""
    cls = tab.get("class") or ""
    toggles = dict(genstore.default_toggles(), **(tab.get("toggles") or {}))
    band = level_band(level)
    key = result_key(cls, toggles, inputs["table_sha"], inputs["pin"],
                     inputs["tree_version"], band)
    templates = inputs["view"]["templates"]
    if calc is None:
        return unscored(templates, cls, toggles, key, band, CALC_OFF)
    tree = inputs["tree"]
    if tree is None:
        return unscored(templates, cls, toggles, key, band, NO_TREE)
    cands = candidates(templates, cls, toggles, band, limit)
    if not cands:
        return unscored(templates, cls, toggles, key, band, NO_MATCH)
    deadline = clock() + budget_s
    scored, partial, failed = [], False, 0
    for cand in cands:
        if clock() >= deadline:
            partial = True
            break
        try:
            xml = compose_xml(cand["template"], cand["stage"], cand["variant"],
                              tree_ids(tree, cand["template"]))
            numbers = score_xml(calc, xml)
        except (TreeIdsMissing, delta.CalcError):
            failed += 1
            continue
        scored.append(dict(_entry(cand, numbers)))
    if not scored:
        doc = unscored(templates, cls, toggles, key, band, NO_SCORE)
        doc["partial"] = partial
        return doc
    ranked = rank(scored)
    return {"key": key, "band": band, "scored": True, "partial": partial,
            "candidates": ranked, "best": ranked[0], "failed": failed,
            "note": "partial" if partial else ""}


def dumps(doc):
    """The canonical bytes of a result (repeat runs compare equal)."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def summary(doc, at):
    """The store's result summary of a result document (genstore
    clean_result fields); None when there is nothing to show."""
    best = doc.get("best")
    if not best:
        return None
    scored = bool(doc.get("scored"))
    return {"template": best["template"], "at": int(at),
            "dps": best.get("dps") if scored else None,
            "ehp": best.get("ehp") if scored else None,
            "partial": bool(doc.get("partial")), "scored": scored, "key": doc["key"]}


# --- the engine: one run at a time, results kept per key -------------------------

class Engine:
    """One Generate at a time on its own daemon worker. `calc()` returns
    the calc callable or None; `level()` the character level or None;
    `store` is the GenStore whose tab gets the summary."""

    def __init__(self, sources, calc, level, store, clock=time.monotonic,
                 wall=time.time, budget_s=BUDGET_S):
        self.sources = sources
        self._calc = calc
        self._level = level
        self.store = store
        self._clock = clock
        self._wall = wall
        self.budget_s = budget_s
        self._lock = threading.Lock()
        self._cache = {}    # key -> final result document (insertion order)
        self._last = {}     # tab id -> last result document (partial too)
        self._running = None  # tab id of the run in flight
        self._thread = None
        self.on_save_error = None

    def _key_of(self, tab):
        inputs = self.sources.inputs()
        toggles = dict(genstore.default_toggles(), **(tab.get("toggles") or {}))
        key = result_key(tab.get("class") or "", toggles, inputs["table_sha"],
                         inputs["pin"], inputs["tree_version"], level_band(self._level()))
        return inputs, key

    def last(self, tab_id):
        """The tab's last result document, or None."""
        with self._lock:
            return self._last.get(tab_id)

    def running(self):
        with self._lock:
            return self._running

    def generate(self, tab_id, wait=False):
        """Start one Generate for the tab. ("running", None) while one is in
        flight (this tab's or another's), ("done", doc) for a cached final
        result of the same key, else ("started", None). Raises GenError
        when the tab is gone. wait=True runs it on the caller's thread."""
        tab = self.store.tab(tab_id)
        inputs, key = self._key_of(tab)
        try:
            calc_on = self._calc() is not None
        except Exception:  # noqa: BLE001 - a broken provider reads as off
            calc_on = False
        with self._lock:
            if self._running is not None:
                return "running", None
            # with the calc off a cached PoB result is not shown (point 5)
            hit = self._cache.get(key) if calc_on else None
            if hit is not None:
                self._last[tab_id] = hit
            else:
                self._running = tab_id
        if hit is not None:
            self._publish(tab_id, hit)
            return "done", hit
        if wait:
            self._run(tab_id, tab, inputs)
            return "done", self.last(tab_id)
        self._thread = threading.Thread(target=self._run, args=(tab_id, tab, inputs),
                                        name="al-kindler", daemon=True)
        self._thread.start()
        return "started", None

    def join(self, timeout=None):
        t = self._thread
        if t is not None:
            t.join(timeout)

    def _run(self, tab_id, tab, inputs):
        try:
            try:
                calc = self._calc()
            except Exception:  # noqa: BLE001 - a broken provider reads as off
                calc = None
            doc = generate(inputs, tab, self._level(), calc, clock=self._clock,
                           budget_s=self.budget_s)
            with self._lock:
                self._last[tab_id] = doc
                if doc["scored"] and not doc["partial"]:
                    self._cache[doc["key"]] = doc
                    while len(self._cache) > CACHE_MAX:
                        self._cache.pop(next(iter(self._cache)))
            self._publish(tab_id, doc)
        finally:
            with self._lock:
                self._running = None

    def _publish(self, tab_id, doc):
        summ = summary(doc, self._wall())
        if summ is None:
            return
        count = len(doc["candidates"]) if doc["scored"] else 0
        try:
            self.store.set_result(tab_id, summ, candidates=count)
        except genstore.GenError:
            pass  # the tab was closed meanwhile
        except OSError:
            if self.on_save_error is not None:
                self.on_save_error()
