"""The loaded PoB build as the game's `.build` JSON (TC-BUILDFILE).

GGG documents a tool-made build file, Build object "Version 1
(Experimental)", on its File Formats page (research 0018 section 3,
research 0027). This module only BUILDS the JSON text: it has no file,
path or OS code (a test holds that). GET /api/buildfile answers with the
text as a download on the player's click; the player places the file.
AshLight never writes it into the game's own folders (decision 0034,
tests/test_audit_buildfile.py).

Mapping (research 0027), never guessed; anything that does not map is
dropped and named in `notes`:
- passives: PoB spec node id == GGG tree export `skill` (research 0015);
  the `.build` id is that export node's string `id` (treedata Node.gid,
  e.g. `strength89`, a PassiveSkills id). Needs the cached tree export; a
  node with no slug is dropped. When the spec's ids mostly miss the tree
  (treedata.id_match not ok) no passives are written.
- ascendancy: the tree export's ascendancy id (e.g. `Warrior1`) for PoB's
  ascendClassName.
- skills: PoB `gemId` (the BaseItemTypes id, `Metadata/Items/Gems/...`);
  per enabled socket group the first enabled non-support gem is the skill
  and its enabled supports are `support_skills`.
- inventory_slots: only the inventory ids GGG's page shows (`Weapon1`,
  `Helm1`, ...); a unique is named by `unique_name`, any other item is
  described in `additional_text`.
Not written (no source in a PoB build): author, link, level_interval,
weapon_set.
"""

import json
import re

# Documented Build object fields (GGG File Formats page, research 0027):
# field -> required. The file is ONE bare Build object (no version key).
BUILD_FIELDS = {"name": True, "author": False, "link": False, "description": False,
                "ascendancy": False, "passives": False, "skills": False,
                "inventory_slots": False}
PASSIVE_FIELDS = {"id": True, "level_interval": False, "weapon_set": False,
                  "additional_text": False}
SKILL_FIELDS = {"id": True, "level_interval": False, "additional_text": False,
                "support_skills": False}
SUPPORT_FIELDS = {"id": True, "level_interval": False, "additional_text": False}
SLOT_FIELDS = {"inventory_id": True, "slot_x": False, "slot_y": False,
               "level_interval": False, "unique_name": False, "additional_text": False}

# PoB gear slot -> GGG Inventories id. Only the ids GGG's page shows (its
# example build); off-hand, swap set, flasks and charms are left out until
# GGG shows their ids (research 0027: never guessed).
INVENTORY_IDS = {"Weapon 1": "Weapon1", "Helmet": "Helm1", "Body Armour": "BodyArmour1",
                 "Gloves": "Gloves1", "Boots": "Boots1", "Belt": "Belt1",
                 "Amulet": "Amulet1", "Ring 1": "Ring1", "Ring 2": "Ring2"}

PASSIVE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
GEM_ID = re.compile(r"^Metadata/Items/Gems/[A-Za-z0-9_]+$")
INVENTORY_ID = re.compile(r"^[A-Za-z]+[0-9]*$")
DESCRIPTION = "Made by AshLight from a Path of Building build."
EXTENSION = ".build"
_UNSAFE = re.compile(r"[^A-Za-z0-9]+")
_MARKUP = re.compile(r"[{}<>]")  # GGG's additional_text markup characters


def _text(v):
    return isinstance(v, str) and bool(v.strip())


def _uint(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _interval(v):
    return _uint(v) or (isinstance(v, list) and len(v) == 2 and all(_uint(x) for x in v))


def _check_obj(row, fields, where, out, ids=None):
    """One documented sub-object, or a bare id string where allowed."""
    if isinstance(row, str):
        if ids is not None and not ids.match(row):
            out.append(f"{where} bad id {row!r}")
        return
    if not isinstance(row, dict):
        out.append(f"{where} must be an object or an id")
        return
    for k in row:
        if k not in fields:
            out.append(f"{where} unknown field {k}")
    for k, needed in fields.items():
        if needed and not _text(row.get(k)):
            out.append(f"{where}.{k} is required text")
    if ids is not None and _text(row.get("id")) and not ids.match(row["id"]):
        out.append(f"{where} bad id {row['id']!r}")
    for k in ("unique_name", "additional_text"):
        if k in row and not _text(row[k]):
            out.append(f"{where}.{k} must be text")
    if "level_interval" in row and not _interval(row["level_interval"]):
        out.append(f"{where}.level_interval must be a uint or [uint, uint]")
    if "weapon_set" in row and not (_uint(row["weapon_set"]) and row["weapon_set"] <= 2):
        out.append(f"{where}.weapon_set must be 0, 1 or 2")
    for k in ("slot_x", "slot_y"):
        if k in row and not _uint(row[k]):
            out.append(f"{where}.{k} must be a uint")


def validate(doc):
    """Problems with a `.build` document against GGG's documented Build
    object ([] = valid). Unknown fields are problems: the format is
    experimental and the game may refuse them."""
    if not isinstance(doc, dict):
        return ["the build must be one object"]
    out = []
    for k, needed in BUILD_FIELDS.items():
        if needed and not _text(doc.get(k)):
            out.append(f"{k} is required text")
    for k in doc:
        if k not in BUILD_FIELDS:
            out.append(f"unknown field {k}")
    for k in ("author", "link", "description", "ascendancy"):
        if k in doc and not _text(doc[k]):
            out.append(f"{k} must be text")
    lists = (("passives", PASSIVE_FIELDS, PASSIVE_ID), ("skills", SKILL_FIELDS, GEM_ID),
             ("inventory_slots", SLOT_FIELDS, None))
    for key, fields, ids in lists:
        if key not in doc:
            continue
        rows = doc[key]
        if not isinstance(rows, list):
            out.append(f"{key} must be a list")
            continue
        for i, row in enumerate(rows):
            if key == "inventory_slots" and not isinstance(row, dict):
                out.append(f"{key}[{i}] must be an object")
                continue
            _check_obj(row, fields, f"{key}[{i}]", out, ids)
            if key == "inventory_slots" and _text(row.get("inventory_id")) \
                    and not INVENTORY_ID.match(row["inventory_id"]):
                out.append(f"{key}[{i}] bad inventory_id {row['inventory_id']!r}")
            sup = row.get("support_skills") if isinstance(row, dict) else None
            if key == "skills" and sup is not None:
                if not isinstance(sup, list):
                    out.append(f"skills[{i}].support_skills must be a list")
                    continue
                for j, s in enumerate(sup):
                    _check_obj(s, SUPPORT_FIELDS, f"skills[{i}].support_skills[{j}]",
                               out, GEM_ID)
    return out


NO_TREE_NOTE = ("No passives yet: turn on web data and add a contact in the "
                "Prices and web data card.")


def _passives(build, tree, notes):
    spec = build.active_spec
    nodes = list(spec.nodes) if spec else []
    stats = {"mapped": 0, "total": len(nodes), "ok": False}
    if not nodes:
        return [], stats
    if tree is None:
        # TC-BUILDFILE-TEXTS (F-187): the tree export is a GGG source, fetched
        # only with web data on and a contact set (snapshot.CONTACT_SOURCES).
        notes.append(NO_TREE_NOTE)
        return [], stats
    stats["ok"] = bool(tree.id_match(nodes)["ok"])
    if not stats["ok"]:
        notes.append("No passives: this build's tree doesn't match the downloaded "
                     "passive tree data.")
        return [], stats
    rows, seen = [], set()
    for nid in nodes:
        n = tree.node(nid)
        gid = n.gid if n is not None else None
        if gid and PASSIVE_ID.match(gid) and gid not in seen:
            seen.add(gid)
            rows.append(gid)
    stats["mapped"] = len(rows)
    left = stats["total"] - len(rows)
    if left:
        notes.append(f"{left} of {stats['total']} {_plural(stats['total'], 'passive')} "
                     "left out: the game doesn't list them yet.")
    return rows, stats


def _is_support(gem):
    return "/SupportGem" in (gem.gem_id or "") or (gem.skill_id or "").startswith("Support")


def _skills(build, notes):
    rows, dropped = [], 0
    for group in build.skills:
        if not group.enabled:
            continue
        gems = [g for g in group.gems if g.enabled]
        main = next((g for g in gems if not _is_support(g)), None)
        if main is None:
            continue
        if not (main.gem_id and GEM_ID.match(main.gem_id)):
            dropped += 1
            continue
        row = {"id": main.gem_id}
        sup = []
        for g in gems:
            if g is main or not _is_support(g):
                continue
            if g.gem_id and GEM_ID.match(g.gem_id):
                sup.append(g.gem_id)
            else:
                dropped += 1
        if sup:
            row["support_skills"] = sup
        rows.append(row)
    if dropped:
        notes.append(f"{dropped} {_plural(dropped, 'gem')} left out: "
                     "the build doesn't name them.")
    return rows


def _plural(n, word):
    return word if n == 1 else word + "s"


def _clean(text):
    return " ".join(_MARKUP.sub("", text or "").split())


def _slots(build, notes):
    rows = []
    for slot, inv in INVENTORY_IDS.items():
        item = build.equipped(slot)
        if item is None:
            continue
        name, base = _clean(item.name), _clean(item.base)
        if item.rarity == "UNIQUE" and name:
            rows.append({"inventory_id": inv, "unique_name": name})
        elif name or base:
            rows.append({"inventory_id": inv,
                         "additional_text": ", ".join(x for x in (name, base) if x)})
    other = [s for s in build.gear if s not in INVENTORY_IDS and build.gear[s] is not None
             and not s.lower().startswith(("flask", "charm"))]
    if other:
        notes.append(f"{len(other)} {_plural(len(other), 'gear slot')} left out: "
                     "off-hand and weapon swap have no place in the file yet.")
    return rows


def _name(build):
    head = build.ascendancy or build.class_name or "Build"
    return _clean(head + (f", level {build.level}" if build.level is not None else ""))


def filename(name):
    """A safe download name from the build's own name (never user path
    input): letters and digits only, then `.build`."""
    stem = _UNSAFE.sub("-", name or "").strip("-")[:60] or "build"
    return "ashlight-" + stem + EXTENSION


def export(build, tree=None):
    """{"doc", "text", "filename", "passives": {mapped, total, ok}, "notes"}
    for a model.Build. `tree`: optional treedata.TreeData. `notes` names
    every part left out (plain sentences for the dashboard)."""
    notes = []
    name = _name(build)
    doc = {"name": name, "description": DESCRIPTION}
    if build.ascendancy:
        asc = tree.ascendancy_id(build.ascendancy) if tree is not None else None
        if asc:
            doc["ascendancy"] = asc
        else:
            notes.append("Ascendancy left out: the game doesn't list it yet.")
    passives, pstats = _passives(build, tree, notes)
    if passives:
        doc["passives"] = passives
    skills = _skills(build, notes)
    if skills:
        doc["skills"] = skills
    slots = _slots(build, notes)
    if slots:
        doc["inventory_slots"] = slots
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    return {"doc": doc, "text": text, "filename": filename(name), "passives": pstats,
            "notes": notes}
