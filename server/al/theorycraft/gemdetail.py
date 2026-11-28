"""ITEM-INFO-GEM-DETAIL (decision 0083 amendment 2026-11-28): the in-game
details of a skill, spirit or support gem for the shared item popover.

Source: the repoe-fork poe2 export only, as cached by the snapshot tool
(decision 0009, one web_data opt-in): gems.json (the export's
skill_gems.json), skills.json and gem_tags.json. The export already holds
each level's stat lines worded by the game's own stat description files
("Deals 1 to 10 [Lightning] Damage"), so no stat_translations rendering
and no Path of Building file is needed; this module reads the words, it
never writes its own.

Two halves:

- derive() / refresh(): run by the snapshot tool in its own process
  (never by the core), after a fetch. skills.json is about 28 MB, too big
  for the core to parse in play (decision 0002 budgets), so the tool
  writes one small file per gem name into <cache>/gem_details/
  (<file_key(name)>.json, a few KB each) plus stamp.json naming the
  sha256 of the three inputs; a refresh with the same inputs writes
  nothing. The folder is derived data: it is rebuilt whole and the old
  one removed.
- GemDetails.lookup(key, level): the core's read of one such file
  (capped at FILE_MAX_BYTES, every value re-checked), answered as the
  popover's "gem" field for one gem level.

Fields (each only when the export holds it; nothing is guessed):
kind (active / support / spirit), tags (the gem's shown tag words; tags
with no shown word are left out), description (the active skill's
description, or the support text), max_level, level, costs [{type,
amount}] (type is the export's cost id), spirit (reservation),
cooldown_s, cast_time_s (only for a non-attack skill with a cast time),
cost_multiplier (supports), sets [{label?, damage_pct?, crit_pct?,
lines}] (each stat set's lines in the game's tooltip order; the label
only when the skill has more than one set). Left out on purpose: quality
lines (their numbers need the game's per-quality maths), attack speed
multipliers (the export does not say how the game shows them),
attribute and level requirements (the export has no per-level value) and
the skills a gem grants beside its first one.

Standard library only; no network code.
"""

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from .. import jsonfile

DIR_NAME = "gem_details"
STAMP = "stamp.json"
SCHEMA = 1
INPUTS = ("gems", "skills", "gem_tags")   # snapshot source names
FILE_MAX_BYTES = 256 * 1024
NAME_MAX = 120
TEXT_MAX = 600
LINE_MAX = 200
LINES_MAX = 12        # per stat set
SETS_MAX = 3
TAGS_MAX = 12
LEVEL_MAX = 40
KINDS = ("active", "support", "spirit")
COST_ID = re.compile(r"[A-Za-z]{1,32}\Z")
_MARKUP = re.compile(r"\[([^\[\]|]*)\|([^\[\]]*)\]|\[([^\[\]]*)\]")
_HEX = re.compile(r"[0-9a-f]{32}\Z")


def key(name):
    """The match key of a name: spacing folded, lower case."""
    return " ".join(name.split()).lower() if isinstance(name, str) else ""


def file_key(name):
    """The file stem of one gem name (sha256 of its key, 32 hex)."""
    return hashlib.sha256(key(name).encode("utf-8")).hexdigest()[:32]


def plain(raw, cap=LINE_MAX):
    """Export text with its [Id|Shown] / [Shown] markup read as the shown
    words, line breaks folded to spaces; None for no text."""
    if not isinstance(raw, str):
        return None

    def shown(m):
        return m.group(2) if m.group(2) is not None else (m.group(3) or "")
    out = " ".join(_MARKUP.sub(shown, raw).split())
    return out[:cap] if out else None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _levels(per_level):
    """{int level: row} of a per_level object (keys "1".."40")."""
    out = {}
    for k, row in (per_level.items() if isinstance(per_level, dict) else ()):
        try:
            n = int(k)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= LEVEL_MAX and isinstance(row, dict):
            out[n] = row
    return out


def _pick(row, static, field):
    """A per-level value, else the skill's static one (the export moves a
    value that never changes into "static")."""
    if isinstance(row, dict) and field in row:
        return row[field]
    return static.get(field) if isinstance(static, dict) else None


def _set_lines(stat_set, level):
    """The ordered lines of one stat set at one level: static and
    per-level stat_text, in the set's tooltip_order, then any others."""
    static = stat_set.get("static") if isinstance(stat_set.get("static"), dict) else {}
    row = _levels(stat_set.get("per_level")).get(level, {})
    text = {}
    for src in (static.get("stat_text"), row.get("stat_text")):
        if isinstance(src, dict):
            for k, v in src.items():
                if isinstance(k, str):
                    text[k] = v
    order = [k for k in (static.get("tooltip_order") or []) if isinstance(k, str)]
    keys = [k for k in order if k in text] + sorted(k for k in text if k not in order)
    lines = []
    for k in keys:
        line = plain(text[k])
        if line and line not in lines:
            lines.append(line)
    return lines[:LINES_MAX]


def _set_label(stat_set):
    label = stat_set.get("label")
    if isinstance(label, list) and len(label) > 1:
        label = label[1]
    return plain(label, 40) if isinstance(label, str) else None


def _level_row(skill, sets, level, kind, attack):
    static = skill.get("static") if isinstance(skill.get("static"), dict) else {}
    row = _levels(skill.get("per_level")).get(level, {})
    out = {}
    costs = _pick(row, static, "costs")
    if isinstance(costs, dict):
        cl = [{"type": t, "amount": a} for t, a in costs.items()
              if isinstance(t, str) and COST_ID.match(t) and _num(a) is not None and a > 0]
        if cl:
            out["costs"] = cl
    res = _pick(row, static, "reservations")
    if isinstance(res, dict) and _num(res.get("spirit")) and res["spirit"] > 0:
        out["spirit"] = res["spirit"]
    cd = _num(_pick(row, static, "cooldown"))
    if cd and cd > 0:
        out["cooldown_s"] = round(cd / 1000.0, 3)
    if kind == "support":
        cm = _num(_pick(row, static, "cost_multiplier"))
        if cm and cm > 0:
            out["cost_multiplier"] = cm
    shown = []
    for st in sets:
        sst = st.get("static") if isinstance(st.get("static"), dict) else {}
        srow = _levels(st.get("per_level")).get(level, {})
        one = {}
        if len(sets) > 1:
            label = _set_label(st)
            if label:
                one["label"] = label
        dmg = _num(_pick(srow, sst, "damage_multiplier"))
        if dmg and attack:
            one["damage_pct"] = dmg
        crit = _num(_pick(srow, sst, "crit_chance"))
        if crit and crit > 0:
            one["crit_pct"] = round(crit / 100.0, 2)
        one["lines"] = _set_lines(st, level)
        if one["lines"] or "damage_pct" in one or "crit_pct" in one:
            shown.append(one)
    if shown:
        out["sets"] = shown
    return out


def _rank(gem_id, entry):
    """Sort key: the released, normal (not unique-granted) gem first."""
    base = entry.get("base_item") if isinstance(entry.get("base_item"), dict) else {}
    gid = gem_id if isinstance(gem_id, str) else ""
    return (base.get("release_state") != "released",
            "unique" in gid.lower(),
            not gid.startswith("Metadata/Items/Gems/"),
            gid)


def _tags(entry, tag_words):
    out = []
    for t in entry.get("tags") or ():
        word = plain(tag_words.get(t), 40) if isinstance(t, str) else None
        if word and word not in out:
            out.append(word)
    return out[:TAGS_MAX]


def detail(entry, skills, tag_words):
    """One gem's file document, or None when the export has nothing to
    show for it."""
    base = entry.get("base_item") if isinstance(entry.get("base_item"), dict) else {}
    name = base.get("display_name")
    kind = entry.get("gem_type")
    granted = entry.get("grants_skills")
    if (not isinstance(name, str) or not name.strip() or len(name) > NAME_MAX
            or kind not in KINDS or not isinstance(granted, list) or not granted):
        return None
    skill = skills.get(granted[0])
    if not isinstance(skill, dict):
        return None
    doc = {"schema": SCHEMA, "name": " ".join(name.split()), "kind": kind}
    tags = _tags(entry, tag_words)
    if tags:
        doc["tags"] = tags
    active = skill.get("active_skill") if isinstance(skill.get("active_skill"), dict) else {}
    desc = plain(entry.get("support_text") if kind == "support" else active.get("description"),
                 TEXT_MAX)
    if desc:
        doc["description"] = desc
    types = active.get("types") if isinstance(active.get("types"), list) else []
    attack = "Attack" in types
    cast = _num(skill.get("cast_time"))
    if cast and cast > 0 and not attack and kind != "support":
        doc["cast_time_s"] = round(cast / 1000.0, 3)
    sets = [s for s in (skill.get("stat_sets") or []) if isinstance(s, dict)][:SETS_MAX]
    levels = sorted(_levels(skill.get("per_level"))) or [1]
    doc["max_level"] = levels[-1]
    doc["levels"] = {str(n): _level_row(skill, sets, n, kind, attack) for n in levels}
    return doc


def derive(gems_doc, skills_doc, tags_doc):
    """{file_key: document} for every gem name of the export (one per
    name: the released normal gem wins over a unique-granted copy)."""
    if not isinstance(gems_doc, dict) or not isinstance(skills_doc, dict):
        return {}
    tag_words = tags_doc if isinstance(tags_doc, dict) else {}
    out, seen = {}, set()
    for gid, entry in sorted((i for i in gems_doc.items() if isinstance(i[1], dict)),
                             key=lambda i: _rank(*i)):
        doc = detail(entry, skills_doc, tag_words)
        if doc is None or key(doc["name"]) in seen:
            continue
        seen.add(key(doc["name"]))
        out[file_key(doc["name"])] = doc
    return out


def _stamp_of(manifest):
    files = manifest.get("files") if isinstance(manifest, dict) else None
    files = files if isinstance(files, dict) else {}
    out = {}
    for name in INPUTS:
        sha = (files.get(name) or {}).get("sha256") if isinstance(files.get(name), dict) else None
        if not isinstance(sha, str):
            return None
        out[name] = sha
    return {"schema": SCHEMA, "inputs": out}


def refresh(directory, manifest, load=None):
    """Rebuild <directory>/gem_details when the three inputs' sha256 in the
    snapshot manifest differ from its stamp. Returns "fresh", "written
    (<n> gems)", "skipped: <why>" or "error: <why>"; never raises."""
    directory = Path(directory)
    stamp = _stamp_of(manifest)
    if stamp is None:
        return "skipped: gem data not cached"
    target = directory / DIR_NAME
    if jsonfile.read_json(target / STAMP, max_bytes=4096) == stamp:
        return "fresh"
    load = load or (lambda p: json.loads(Path(p).read_bytes()))
    try:
        docs = [load(directory / f"{n}.json") for n in INPUTS]
        details = derive(*docs)
        del docs
    except (OSError, ValueError, MemoryError) as e:
        return f"error: {type(e).__name__}"
    if not details:
        return "skipped: no gems in the cached export"
    fresh = directory / (DIR_NAME + ".new")
    old = directory / (DIR_NAME + ".old")
    try:
        for p in (fresh, old):
            if p.exists():
                shutil.rmtree(p)
        fresh.mkdir(parents=True)
        for stem, doc in details.items():
            jsonfile.write_json(fresh / f"{stem}.json", doc, indent=None, sync=False)
        jsonfile.write_json(fresh / STAMP, stamp, sync=True)
        if target.exists():
            os.replace(target, old)
        os.replace(fresh, target)
        if old.exists():
            shutil.rmtree(old)   # derived data, rebuilt from the cache any time
    except OSError as e:
        return f"error: {type(e).__name__}"
    return f"written ({len(details)} gems)"


# -- the core's read


def _text_list(v, cap, n):
    out = []
    for x in v if isinstance(v, list) else ():
        if isinstance(x, str) and 0 < len(x) <= cap:
            out.append(x)
    return out[:n]


def _clean_row(row):
    out = {}
    if not isinstance(row, dict):
        return out
    costs = [c for c in row.get("costs") or () if isinstance(c, dict)
             and isinstance(c.get("type"), str) and COST_ID.match(c["type"])
             and _num(c.get("amount")) is not None and c["amount"] > 0]
    if costs:
        out["costs"] = [{"type": c["type"], "amount": c["amount"]} for c in costs[:4]]
    for f in ("spirit", "cooldown_s", "cost_multiplier"):
        v = _num(row.get(f))
        if v is not None and v > 0:
            out[f] = v
    sets = []
    for s in (row.get("sets") or [])[:SETS_MAX] if isinstance(row.get("sets"), list) else ():
        if not isinstance(s, dict):
            continue
        one = {}
        if isinstance(s.get("label"), str) and 0 < len(s["label"]) <= 40:
            one["label"] = s["label"]
        for f in ("damage_pct", "crit_pct"):
            v = _num(s.get(f))
            if v is not None and v > 0:
                one[f] = v
        one["lines"] = _text_list(s.get("lines"), LINE_MAX, LINES_MAX)
        if one["lines"] or len(one) > 1:
            sets.append(one)
    if sets:
        out["sets"] = sets
    return out


class GemDetails:
    """The core's reader of <cache>/gem_details (one small file a look)."""

    def __init__(self, directory):
        self.dir = Path(directory)

    def lookup(self, name_key, level=None):
        """The popover's "gem" field for one name key at one gem level
        (default 1; a level the gem lacks reads as the nearest one below,
        else its lowest), or None."""
        doc = jsonfile.read_json(self.dir / f"{file_key(name_key)}.json",
                                 max_bytes=FILE_MAX_BYTES, kind=dict)
        if not doc or doc.get("schema") != SCHEMA or key(doc.get("name")) != key(name_key):
            return None
        if doc.get("kind") not in KINDS:
            return None
        out = {"kind": doc["kind"]}
        tags = _text_list(doc.get("tags"), 40, TAGS_MAX)
        if tags:
            out["tags"] = tags
        if isinstance(doc.get("description"), str) and 0 < len(doc["description"]) <= TEXT_MAX:
            out["description"] = doc["description"]
        cast = _num(doc.get("cast_time_s"))
        if cast is not None and cast > 0:
            out["cast_time_s"] = cast
        levels = {}
        for k, row in (doc.get("levels") or {}).items() if isinstance(doc.get("levels"), dict) else ():
            try:
                n = int(k)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= LEVEL_MAX:
                levels[n] = row
        if levels:
            want = level if isinstance(level, int) and 1 <= level <= LEVEL_MAX else 1
            below = [n for n in levels if n <= want]
            at = max(below) if below else min(levels)
            out["max_level"] = max(levels)
            out["level"] = at
            out.update(_clean_row(levels[at]))
        return out
