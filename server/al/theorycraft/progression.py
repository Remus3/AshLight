"""PROGRESSION-VIEW (decision 0088): the one Progression view model.

The character's progression in one compact document: the passive tree
(drawn by the page from the export's own positions), the ascendancy tree,
the skill gems with their support links, the point lines (passives,
ascendancy, Spirit and weapon-set points when the build states them, the
guide's point books) and the next-up strip of at most NEXT_MAX steps due
at the current level.

Sources, only the permitted ones, never a guess (decision 0088 point 2):
- the pasted Path of Building build (theorycraft.model.Build): the spec
  node ids, the skill groups and gem levels, PoB's own Spirit stats and
  weapon-set node lists;
- a Kindler tab's plan (theorycraft.kindlerplan.build_plan): the ordered
  passives, the ascendancy nodes by trial, the gem steps with their
  snapshot-or-authored level and KINDLER-SUPPORT-FIT's applies flags;
- the cached GGG tree export (treedata.TreeData): positions, links, kinds
  (decision 0034: ids are the export's `skill` ids);
- the cached gems snapshot (archetypes.gem_index): the level a gem can be
  used at; a gem it does not name reads "unchecked";
- the zone guide (decision 0043, DATA-GUIDE-FACTS): its 'A book of 2
  points' entries, counted, never claimed taken;
- the snapshot's published level, area id and zone only (no log read).

States of a node: "h" planned by the current level (a PoB spec's nodes,
or a Kindler plan's first point_budget(level) passives), "d" due next (the
next DUE_MAX planned passives, or the next spec's new nodes), "l" planned
later, "o" not in the plan. Nothing here says a passive was taken.

TC-SPEC-FOLLOW hook: pick_specs() reads the chosen spec through one
`picker(build, level) -> spec index or None` callable with a fallback to
the active spec; server/al/plug/progression.py `spec_picker()` is the one
place that passes it (None until TC-SPEC-FOLLOW lands).

Next-up hook: add_next_source(name, fn, order) lets a later package
(TC-UNCUT-GEM, TC-GEM-UNLOCK) add its own steps to the strip; fn(ctx)
returns a list of {"kind", "text"}; the strip is ordered by `order` (the
built-in kinds use 10 to 40) and cut to NEXT_MAX.

Pure functions; stdlib only; no read, no request, no clock.
"""

import hashlib
import json
import math
import threading

from .. import acts
from ..text import progression as words
from . import archetypes

SCHEMA = 1
MAX_NODES = 700        # main tree nodes sent per view
MAX_EDGES = 1400
MAX_ASC_NODES = 48
MAX_NAMED = 260        # nodes that carry a name (and up to 2 stat lines)
MAX_STATS = 2
STAT_CHARS = 90
NAME_CHARS = 60
MAX_BYTES = 160 * 1024  # the whole model, as JSON
DUE_MAX = 3
NEXT_MAX = 3
STEP_CHARS = 60       # one strip step (about 11 words; region I holds 60)
MAX_SKILLS = 8
MAX_SUPPORTS = 6
PAD = 600              # export units around the framed nodes
MIN_SPAN = 2400
FOLLOW_LOOK = 25       # levels pick_specs looks ahead for the next spec
STATES = ("h", "d", "l", "o")
KINDS = ("s", "n", "k", "j", "c", "a")
BOOK_PREFIX = "A book of "

# the built-in next-up kinds and their order on the strip
ORDER_PASSIVE, ORDER_GEM, ORDER_ASC, ORDER_BOOK = 10, 20, 30, 40
HOOK_ORDER = 100
HOOK_KIND_MAX = 16
HOOK_TEXT_MAX = 120


# --- the next-up hook ------------------------------------------------------------

_hooks_lock = threading.Lock()
_hooks = []  # [(order, name, fn)]


def add_next_source(name, fn, order=HOOK_ORDER):
    """Add (or replace by name) one next-up source: fn(ctx) -> a list of
    {"kind", "text"} steps. ctx holds "level", "area_id", "zone", "act",
    "source", "build" (a model.Build or None), "plan" and "stage" (the
    Kindler plan and stage index or None); it is read only."""
    if not isinstance(name, str) or not name or not callable(fn):
        raise ValueError("add_next_source needs a name and a callable")
    if isinstance(order, bool) or not isinstance(order, (int, float)):
        raise ValueError("add_next_source: order is a number")
    with _hooks_lock:
        _hooks[:] = [h for h in _hooks if h[1] != name]
        _hooks.append((order, name, fn))
        _hooks.sort(key=lambda h: (h[0], h[1]))


def remove_next_source(name):
    with _hooks_lock:
        _hooks[:] = [h for h in _hooks if h[1] != name]


def _hook_steps(ctx):
    with _hooks_lock:
        hooks = list(_hooks)
    out = []
    for order, _name, fn in hooks:
        try:
            got = fn(dict(ctx))
        except Exception:  # noqa: BLE001 - a broken source never breaks the view
            continue
        for st in got if isinstance(got, (list, tuple)) else ():
            if not isinstance(st, dict):
                continue
            kind, text = st.get("kind"), st.get("text")
            if (isinstance(kind, str) and 0 < len(kind) <= HOOK_KIND_MAX
                    and isinstance(text, str) and 0 < len(text) <= HOOK_TEXT_MAX
                    and text.isascii()):
                out.append((order, {"kind": kind, "text": text}))
    return out


# --- TC-SPEC-FOLLOW adapter ------------------------------------------------------

def _good_index(build, idx):
    return (isinstance(idx, int) and not isinstance(idx, bool)
            and 0 <= idx < len(build.specs))


def pick_specs(build, level, picker=None):
    """(index of the spec to show, index of the next spec or None).

    `picker(build, level)` is TC-SPEC-FOLLOW's choice (a spec index, or
    None); without one, or when it answers nothing usable, the build's
    active spec is shown and there is no next spec. The next spec is the
    picker's first different answer within FOLLOW_LOOK levels above."""
    if build is None or not build.specs:
        return None, None
    active = build.active_spec_index if _good_index(build, build.active_spec_index) else 0
    if picker is None or not isinstance(level, int) or isinstance(level, bool):
        return active, None
    try:
        cur = picker(build, level)
    except Exception:  # noqa: BLE001 - the fallback is the active spec
        return active, None
    if not _good_index(build, cur):
        return active, None
    nxt = None
    for up in range(level + 1, min(100, level + FOLLOW_LOOK) + 1):
        try:
            got = picker(build, up)
        except Exception:  # noqa: BLE001
            break
        if _good_index(build, got) and got != cur:
            nxt = got
            break
    return cur, nxt


# --- tree drawing ------------------------------------------------------------------

def kind_of(node):
    if node.asc_start:
        return "a"
    if node.class_start:
        return "c"
    if node.keystone:
        return "k"
    if node.jewel_socket:
        return "j"
    if node.notable:
        return "n"
    return "s"


def _drawable(node):
    return node is not None and node.x is not None and node.y is not None \
        and not node.mastery


def _clip(text, limit):
    text = " ".join(str(text).split())
    if not text.isascii():
        text = text.encode("ascii", "replace").decode("ascii")
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _box(points, pad=PAD, min_span=MIN_SPAN):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    if x1 - x0 < min_span:
        c = (x0 + x1) / 2
        x0, x1 = c - min_span / 2, c + min_span / 2
    if y1 - y0 < min_span:
        c = (y0 + y1) / 2
        y0, y1 = c - min_span / 2, c + min_span / 2
    return [int(math.floor(x0)), int(math.floor(y0)),
            int(math.ceil(x1 - x0)), int(math.ceil(y1 - y0))]


def _inside(node, box):
    return box[0] <= node.x <= box[0] + box[2] and box[1] <= node.y <= box[1] + box[3]


def _edge_state(a, b):
    pair = {a, b}
    if pair == {"h"}:
        return "h"
    if "o" in pair:
        return "o"
    if "d" in pair:
        return "d"
    return "l"


def _names(nodes, states, limit=MAX_NAMED):
    """{str id: [name, up to MAX_STATS stat lines]} for the planned and the
    notable nodes (planned first), at most `limit`."""
    out = {}
    order = sorted(nodes, key=lambda n: (states.get(n.id, "o") == "o",
                                         kind_of(n) == "s", n.id))
    for n in order:
        if len(out) >= limit:
            break
        if states.get(n.id, "o") == "o" and kind_of(n) == "s":
            continue
        if not n.name:
            continue
        out[str(n.id)] = [_clip(n.name, NAME_CHARS)] + [
            _clip(s, STAT_CHARS) for s in n.display_stats[:MAX_STATS]]
    return out


def tree_view(tree, states, start=None):
    """The main-tree drawing: {"box", "n", "e", "names"} or None.

    `states` maps node id -> "h" / "d" / "l"; the view frames itself on
    those nodes (else on the `start` node), takes their neighbours ring by
    ring and then the rest of the box until MAX_NODES, and keeps the
    export's links among the nodes it sends (MAX_EDGES)."""
    if tree is None:
        return None
    main = {nid: n for nid, n in tree.nodes.items() if _drawable(n) and not n.ascendancy}
    focus = [main[i] for i in states if i in main]
    if not focus and start in main:
        focus = [main[start]]
    if not focus:
        return None
    box = _box([(n.x, n.y) for n in focus])
    picked = {n.id for n in focus}
    ring = list(picked)
    while ring and len(picked) < MAX_NODES:
        nxt = []
        for nid in ring:
            for oid in main[nid].links:
                o = main.get(oid)
                if o is not None and oid not in picked and _inside(o, box):
                    picked.add(oid)
                    nxt.append(oid)
                    if len(picked) >= MAX_NODES:
                        break
            if len(picked) >= MAX_NODES:
                break
        ring = nxt
    if len(picked) < MAX_NODES:
        cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
        rest = sorted((n for n in main.values() if n.id not in picked and _inside(n, box)),
                      key=lambda n: ((n.x - cx) ** 2 + (n.y - cy) ** 2, n.id))
        for n in rest[:MAX_NODES - len(picked)]:
            picked.add(n.id)
    return _drawing(main, sorted(picked), states, box)


def _drawing(nodes, ids, states, box):
    index = {nid: i for i, nid in enumerate(ids)}
    rows = []
    for nid in ids:
        n = nodes[nid]
        rows.append([nid, int(round(n.x)), int(round(n.y)), kind_of(n), states.get(nid, "o")])
    edges, seen = [], set()
    for nid in ids:
        for oid in nodes[nid].links:
            if oid not in index or (min(nid, oid), max(nid, oid)) in seen:
                continue
            seen.add((min(nid, oid), max(nid, oid)))
            if len(edges) >= MAX_EDGES:
                break
            i, j = index[nid], index[oid]
            edges.append([i, j, _edge_state(rows[i][4], rows[j][4])])
    return {"box": box, "n": rows, "e": edges,
            "names": _names([nodes[i] for i in ids], states)}


def asc_view(tree, name, states):
    """The ascendancy drawing for the ascendancy `name` (its own box), or
    None when the export has no node of it."""
    if tree is None or not isinstance(name, str) or not name:
        return None
    nodes = {nid: n for nid, n in tree.nodes.items()
             if _drawable(n) and n.ascendancy == name}
    if not nodes:
        return None
    ids = sorted(nodes, key=lambda i: (not nodes[i].asc_start, i))[:MAX_ASC_NODES]
    picked = {i: nodes[i] for i in ids}
    box = _box([(n.x, n.y) for n in picked.values()], pad=150, min_span=600)
    view = _drawing(picked, sorted(ids), states, box)
    view["name"] = _clip(name, NAME_CHARS)
    return view


# --- sources -------------------------------------------------------------------------

def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _pob_states(tree, build, cur, nxt):
    """(main states, asc states, due count) from the shown and next spec."""
    spec = build.specs[cur]
    have = set(spec.nodes)
    due = (set(build.specs[nxt].nodes) - have) if nxt is not None else set()
    main, asc = {}, {}
    for nid in sorted(have | due):
        node = tree.nodes.get(nid) if tree is not None else None
        st = "h" if nid in have else "d"
        if node is not None and node.ascendancy:
            asc[nid] = st
        else:
            main[nid] = st
    return main, asc


def _kindler_order(plan):
    out = []
    for st in plan.get("stages") or []:
        for p in st.get("passives") or []:
            nid = _int(p.get("id")) if isinstance(p, dict) else None
            if nid is not None and nid not in out:
                out.append(nid)
    return out


def _stage_bonus(stage):
    budget, lvl = _int(stage.get("budget")), _int(stage.get("level"))
    if budget is None or lvl is None:
        return 0
    return max(0, budget - max(0, lvl - 1))


def _kindler_states(plan, stage_i, level):
    """(main states, asc states, due ids in plan order, asc trial or None,
    due asc ids)."""
    stages = plan.get("stages") or []
    order = _kindler_order(plan)
    main = {nid: "l" for nid in order}
    due_ids = []
    if level is not None and stages:
        st = stages[stage_i] if stage_i is not None else stages[0]
        budget = archetypes.point_budget(level, _stage_bonus(st))
        for nid in order[:budget]:
            main[nid] = "h"
        due_ids = order[budget:budget + DUE_MAX]
        for nid in due_ids:
            main[nid] = "d"
    asc, trial, asc_due = {}, None, []
    for i, st in enumerate(stages):
        a = st.get("ascendancy")
        if not isinstance(a, dict):
            continue
        state = "l"
        if stage_i is not None:
            state = "h" if i < stage_i else ("d" if i == stage_i else "l")
        for node in a.get("nodes") or []:
            nid = _int(node.get("id")) if isinstance(node, dict) else None
            if nid is None:
                continue
            asc[nid] = state
            if state == "d":
                asc_due.append(nid)
        if state == "d":
            trial = _int(a.get("trial"))
    return main, asc, due_ids, trial, asc_due


def _is_support(gem):
    sid = gem.skill_id or ""
    return sid.startswith("Support")


def _need(gems, name):
    """(level, checked) of a gem from the gems snapshot index."""
    hit = (gems or {}).get(name.lower()) if isinstance(name, str) else None
    if hit and _int(hit.get("level")) is not None:
        return hit["level"], True
    return None, False


def _gem_row(name, level, need, checked, player):
    return {"name": _clip(name, NAME_CHARS), "level": level, "need": need,
            "checked": bool(checked),
            "ready": bool(checked and need is not None and player is not None
                          and need <= player)}


def gem_word(row):
    """The timing word of one gem row: "ready", "level N" (from the gems
    snapshot or the plan's checked level) or "unchecked"."""
    if not row["checked"] or row["need"] is None:
        return words.UNCHECKED
    if row["ready"]:
        return words.READY
    return words.NEED_LEVEL.format(level=row["need"])


def _lines(rows):
    """Add the composed "meta" and "with" words to each skill row."""
    for row in rows:
        meta = [gem_word(row)]
        if row["level"] is not None:
            meta.insert(0, words.GEM_LEVEL.format(level=row["level"]))
        row["meta"] = ", ".join(meta)
        sups = []
        for s in row["supports"]:
            word = words.NO_FIT if s.get("applies") is False else gem_word(s)
            sups.append(f"{s['name']} ({word})")
        row["with"] = words.WITH.format(names=", ".join(sups)) if sups else words.NO_SUPPORTS
    return rows


def pob_skills(build, gems, level):
    rows = []
    for group in build.skills:
        if not group.enabled:
            continue
        gs = [g for g in group.gems if g.enabled and g.name]
        sups = [g for g in gs if _is_support(g)]
        for g in gs:
            if _is_support(g) or len(rows) >= MAX_SKILLS:
                continue
            need, ok = _need(gems, g.name)
            row = _gem_row(g.name, g.level, need, ok, level)
            row["supports"] = []
            for s in sups[:MAX_SUPPORTS]:
                sn, sok = _need(gems, s.name)
                row["supports"].append(dict(_gem_row(s.name, s.level, sn, sok, level),
                                            applies=None))
            rows.append(row)
    return rows


def kindler_skills(plan, stage_i, level):
    stages = plan.get("stages") or []
    if not stages:
        return []
    st = stages[stage_i if stage_i is not None else 0]
    rows = []
    for sk in (st.get("skills") or [])[:MAX_SKILLS]:
        row = _gem_row(sk.get("name") or "", None, _int(sk.get("level")),
                       sk.get("checked"), level)
        row["supports"] = [dict(_gem_row(s.get("name") or "", None, _int(s.get("level")),
                                         s.get("checked"), level),
                                applies=s.get("applies") if isinstance(s.get("applies"), bool)
                                else None)
                           for s in (sk.get("supports") or [])[:MAX_SUPPORTS]]
        rows.append(row)
    return rows


def _support_names(plan):
    out = set()
    for st in plan.get("stages") or []:
        for sk in st.get("skills") or []:
            for s in sk.get("supports") or []:
                if isinstance(s, dict) and isinstance(s.get("name"), str):
                    out.add(s["name"])
    return out


def _gem_step_pob(skills, level):
    """GEM_LATER for the lowest checked gem level above the player's."""
    if level is None:
        return None
    best = None
    for row in skills:
        for g, kind in [(row, words.GEM_WORD)] + [(s, words.SUPPORT_WORD)
                                                  for s in row["supports"]]:
            if g["checked"] and g["need"] is not None and g["need"] > level:
                if best is None or g["need"] < best[0]:
                    best = (g["need"], kind, g["name"])
    if best is None:
        return None
    return words.GEM_LATER.format(kind=best[1], level=best[0], name=best[2])


def _gem_step_kindler(plan, stage_i, level):
    stages = plan.get("stages") or []
    if level is None or not stages:
        return None
    sups = _support_names(plan)
    start = stage_i if stage_i is not None else 0
    cur = stages[start]
    for g in cur.get("gems") or []:
        lv = _int(g.get("level"))
        if g.get("action") != "drop" and lv is not None and lv <= level:
            kind = words.SUPPORT_WORD if g.get("name") in sups else words.GEM_WORD
            return words.GEM_NOW.format(kind=kind, name=_clip(g.get("name"), NAME_CHARS))
    for st in stages[start:]:
        for g in st.get("gems") or []:
            lv = _int(g.get("level"))
            if g.get("action") != "drop" and lv is not None and lv > level:
                kind = words.SUPPORT_WORD if g.get("name") in sups else words.GEM_WORD
                return words.GEM_LATER.format(kind=kind, level=lv,
                                              name=_clip(g.get("name"), NAME_CHARS))
    return None


# --- point lines and books -----------------------------------------------------------

def books(guide, area_id, zone):
    """(act label or None, [zone names with a book], the book text of this
    zone or None) from the guide's 'A book of ...' bonus entries."""
    act = acts.act_of(area_id)
    if act is None or not isinstance(guide, dict):
        return None, [], None
    table = ((guide.get("acts") or {}).get(act["key"]) or {}).get("zones") or {}
    found, here = [], None
    for name, z in table.items() if isinstance(table, dict) else ():
        for opt in (z.get("optional") or []) if isinstance(z, dict) else ():
            text = opt.get("text") if isinstance(opt, dict) else None
            if isinstance(text, str) and text.startswith(BOOK_PREFIX):
                if name not in found:
                    found.append(name)
                if name == zone and here is None:
                    here = text
    return act["label"], found, here


def _points(source, main, asc, level, build, spec, trial, guide_books):
    have = sum(1 for s in main.values() if s == "h")
    lines = []
    if source == "pob" or level is None:
        lines.append(words.PASSIVES_NO_LEVEL.format(have=have))
    else:
        lines.append(words.PASSIVES.format(have=have, level=level))
    if level is not None:
        budget = archetypes.point_budget(level)
        lines.append(words.PASSIVES_BUDGET.format(
            budget=budget, points=words.plural(budget, "point", "points"), level=level))
    a_have = sum(1 for s in asc.values() if s == "h")
    a_due = sum(1 for s in asc.values() if s == "d")
    a_later = sum(1 for s in asc.values() if s == "l")
    if a_due:
        lines.append(words.ASC_POINTS.format(have=a_have, due=a_due))
    elif a_later:
        lines.append(words.ASC_POINTS_LATER.format(have=a_have, later=a_later))
    elif asc:
        lines.append(words.ASC_POINTS_NONE.format(have=a_have))
    if build is not None:
        spirit = build.stats.get("Spirit")
        free = build.stats.get("SpiritUnreserved")
        if isinstance(spirit, (int, float)) and not isinstance(spirit, bool):
            if isinstance(free, (int, float)) and not isinstance(free, bool):
                lines.append(words.SPIRIT.format(spirit=_num(spirit), free=_num(free)))
            else:
                lines.append(words.SPIRIT_ONLY.format(spirit=_num(spirit)))
        if spec is not None and spec.weapon_sets:
            one = sum(1 for v in spec.weapon_sets.values() if v == 1)
            two = sum(1 for v in spec.weapon_sets.values() if v == 2)
            lines.append(words.WEAPON_SETS.format(one=one, two=two))
    label, found, _here = guide_books
    if label is None:
        lines.append(words.BOOKS_UNKNOWN)
    elif found:
        lines.append(words.BOOKS_ACT.format(n=len(found), books=words.plural(
            len(found), "book", "books"), act=label, zones=", ".join(found)))
    else:
        lines.append(words.BOOKS_NONE.format(act=label))
    return lines


def _num(v):
    return str(int(v)) if float(v).is_integer() else f"{v:.1f}"


# --- the model -----------------------------------------------------------------------

def step_text(text):
    """One next-up step as the strip shows it (at most STEP_CHARS)."""
    return _clip(text, STEP_CHARS)


def _due_names(tree, ids):
    out = []
    for nid in ids:
        n = tree.nodes.get(nid) if tree is not None else None
        out.append(_clip(n.name, NAME_CHARS) if n is not None and n.name else None)
    return [n for n in out if n]


def build_model(build=None, tree=None, level=None, area_id=None, zone=None, guide=None,
                kindler=None, gems=None, picker=None, prev=None):
    """The whole Progression model (see the module docstring).

    `kindler` is None or {"plan", "stage" (index or None), "label"}; it is
    used only while no PoB build is loaded. `prev` is the last model of the
    same core: a node due now and not due in `prev` (same source) is listed
    in "new" (the page marks it with a steady edge; nothing moves)."""
    level = _int(level)
    tree_ok = tree is not None
    note = ""
    source, line, spec, plan, stage_i = "none", words.SOURCE_NONE, None, None, None
    main, asc, due_ids, trial, asc_due, asc_name, start = {}, {}, [], None, [], None, None
    skills, gem_step, next_band = [], None, 0
    if build is not None and build.specs:
        source = "pob"
        cur, nxt = pick_specs(build, level, picker)
        spec = build.specs[cur]
        line = (words.SOURCE_POB_SPEC.format(title=_clip(spec.title, 40)) if spec.title
                and len(build.specs) > 1 else words.SOURCE_POB)
        main, asc = _pob_states(tree, build, cur, nxt)
        due_ids = sorted(n for n, s in main.items() if s == "d")
        next_band = len(due_ids)
        asc_name = build.ascendancy
        if tree_ok and spec.nodes and not tree.id_match(spec.nodes)["ok"]:
            note = words.NO_IDS
            main, asc, due_ids, next_band = {}, {}, [], 0
        skills = pob_skills(build, gems, level)
        gem_step = _gem_step_pob(skills, level)
        start = _class_start(tree, build.class_name)
    elif kindler and isinstance(kindler.get("plan"), dict):
        source = "kindler"
        plan = kindler["plan"]
        stage_i = _int(kindler.get("stage"))
        if stage_i is not None and not 0 <= stage_i < len(plan.get("stages") or []):
            stage_i = None
        line = words.SOURCE_KINDLER.format(label=_clip(kindler.get("label") or "Kindler", 32))
        main, asc, due_ids, trial, asc_due = _kindler_states(plan, stage_i, level)
        asc_name = plan.get("ascendancy")
        skills = kindler_skills(plan, stage_i, level)
        gem_step = _gem_step_kindler(plan, stage_i, level)
        start = _class_start(tree, plan.get("class"))
    if not tree_ok and source != "none":
        note = words.NO_TREE
    guide_books = books(guide, area_id, zone)
    tview = tree_view(tree, main, start) if tree_ok else None
    aview = asc_view(tree, asc_name, asc) if tree_ok else None
    prev_due = set()
    if isinstance(prev, dict) and prev.get("source") == source:
        prev_due = set(prev.get("due") or ())
    all_due = sorted(set(n for n, s in main.items() if s == "d")
                     | set(n for n, s in asc.items() if s == "d"))
    new = [n for n in all_due if n not in prev_due] if isinstance(prev, dict) else []
    steps = []
    if source == "kindler" and due_ids:
        names = _due_names(tree, due_ids)
        if names:
            steps.append((ORDER_PASSIVE, {"kind": "passive", "text": words.names_line(
                names, 2, words.TAKE_NEXT_MORE, words.TAKE_NEXT)}))
    elif source == "pob" and next_band:
        steps.append((ORDER_PASSIVE, {"kind": "passive", "text": words.NEXT_BAND.format(
            n=next_band, passives=words.plural(next_band, "passive", "passives"))}))
    if gem_step:
        steps.append((ORDER_GEM, {"kind": "gem", "text": gem_step}))
    if trial is not None and asc_due:
        names = _due_names(tree, asc_due)
        if names:
            steps.append((ORDER_ASC, {"kind": "ascendancy", "text": words.names_line(
                names, 2, words.ASC_TRIAL_MORE, words.ASC_TRIAL, trial=trial)}))
    if guide_books[2]:
        steps.append((ORDER_BOOK, {"kind": "book", "text": words.BOOK_HERE.format(
            text=_clip(guide_books[2], 90))}))
    act = acts.act_of(area_id)
    steps.extend(_hook_steps({"level": level, "area_id": area_id, "zone": zone,
                              "act": act["key"] if act else None, "source": source,
                              "build": build, "plan": plan, "stage": stage_i}))
    steps.sort(key=lambda s: s[0])
    strip = [dict(s, text=step_text(s["text"])) for _o, s in steps][:NEXT_MAX]
    model = {
        "schema": SCHEMA, "source": source, "source_line": line, "level": level,
        "note": note, "tree": tview, "asc": aview, "new": new, "due": all_due,
        "skills": _lines(skills), "empty": words.NOTHING_NEXT,
        "points": _points(source, main, asc, level, build, spec, trial, guide_books)
        if source != "none" else [],
        "next": strip,
        "counts": {"have": sum(1 for s in main.values() if s == "h"),
                   "due": sum(1 for s in main.values() if s == "d"),
                   "later": sum(1 for s in main.values() if s == "l"),
                   "asc_have": sum(1 for s in asc.values() if s == "h"),
                   "asc_due": sum(1 for s in asc.values() if s == "d")},
    }
    _bound(model)
    model["key"] = digest(model)
    return model


def _class_start(tree, class_name):
    if tree is None or not isinstance(class_name, str):
        return None
    starts = {k.lower(): v for k, v in tree.class_starts().items() if isinstance(k, str)}
    nid = starts.get(class_name.lower())
    if nid is None:
        base = tree.class_map.get(class_name)  # an ascendancy name
        nid = starts.get(base.lower()) if isinstance(base, str) else None
    return nid


def _size(model):
    return len(json.dumps(model, separators=(",", ":")))


def _bound(model):
    """Keep the model under MAX_BYTES: stat lines go first, then names of
    unplanned nodes, then unplanned nodes farthest down the list."""
    if _size(model) <= MAX_BYTES:
        return
    for view in (model.get("tree"), model.get("asc")):
        if view:
            view["names"] = {k: v[:1] for k, v in view["names"].items()}
    view = model.get("tree")
    while view and _size(model) > MAX_BYTES and len(view["n"]) > 1:
        keep = [r for r in view["n"] if r[4] != "o"]
        rest = [r for r in view["n"] if r[4] == "o"]
        if not rest:
            break
        rows = keep + rest[:int(len(rest) * 0.8)]
        ids = sorted(r[0] for r in rows)
        index = {r[0]: r for r in rows}
        old = view["n"]
        view["n"] = [index[i] for i in ids]
        pos = {r[0]: i for i, r in enumerate(view["n"])}
        view["e"] = [[pos[old[a][0]], pos[old[b][0]], s] for a, b, s in view["e"]
                     if old[a][0] in pos and old[b][0] in pos]
        view["names"] = {k: v for k, v in view["names"].items() if int(k) in pos}


def digest(model):
    """16 hex of the model without its key (the page re-reads on a change)."""
    body = {k: v for k, v in model.items() if k != "key"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii", "replace")
    return hashlib.sha256(raw).hexdigest()[:16]


def summary(model):
    """The small published part (the snapshot's "progression" view)."""
    if not model:
        return None
    return {"key": model["key"], "source": model["source"],
            "source_line": model["source_line"], "level": model["level"],
            "note": model["note"], "next": [dict(s) for s in model["next"]],
            "empty": model["empty"],
            "counts": dict(model["counts"]), "new": len(model["new"]),
            "tree": model["tree"] is not None}
