"""UX-SETTINGS-IO: AshLight settings export / import (research 0028
section 5, ruling E).

Export: on the player's click the dashboard downloads AshLight's own
settings as one JSON file (the decision 0031 / 0034 download pattern: the
core writes no file anywhere). Import: the player picks that file in a
browser file input; the page posts its JSON and the core merges the
allowed keys into config/local.json.

Allow-list only (ALLOWED). Never in the file, and never taken from one:
the contact (config "contact"), the per-start API token, any session
cookie (AshLight never has one), the Client.txt path ("client_log") and
every other per-host path or key ("port", "loop", ...). Unknown keys in
an imported file are not applied; they are named back to the player as
ignored. A key with a bad value refuses the whole file (nothing applied).

web_data (decision 0013) is never switched ON by an import: a file that
has it on while it is off here is reported as "web_data_offered", and the
dashboard asks the player to turn it on with the existing switch (their
confirm). Turning it off by import is allowed (the safe direction).
AREA-AUDIT P5-2: tc_calc (the decision 0018 calc opt-in) follows the same
rule: never switched ON by an import ("tc_calc_offered", and it is named
in "ignored" so the import sentence says a setting was skipped).

TC-WEIGHTS-DELTA-EXPORT (F-134, decision 0036 amendment 2026-11-21):
schema 2 adds one top-level "weights" block beside "settings": the
player's stat weight changes over AshLight's defaults and the sidegrade
band parts that differ, in the weights file's own version 2 form
({"weights": {stat key: number or null}, "sidegrade": {...}}; null = a
default row the player removed). It is checked by the weights store's
own rules (validate_overrides, then the merged document, at most
weights.MAX_KEYS rows); a bad block refuses the whole file. An import
with the block makes the weights the defaults plus the file's changes;
a file without it (every schema 1 file) leaves the weights alone.
Schema 1 files still import. The block holds stat keys and numbers
only, never a path, contact, token or cookie.

PLAY-TD-04B-THEME-CHOICE (TD-04, F-086): "theme" is the dashboard's
Theme choice, one of THEMES ("dark", "system" = Follow Windows,
"light"), THEME_DEFAULT "dark" when unset; it round trips like any
other allowed key.

PLAY-F-186B-PLAYER-NOTES-UI (F-186, decision 0074 item 8): the player's
zone notes leave the computer only when the player ticks "Include my zone
notes" beside the export (GET /api/settings-export?notes=1). They are a
separate top-level "notes" block, never a key of ALLOWED or "settings", so
no default export carries them: [{"character", "area_id", "text"}],
newest first, as many as fit MAX_BYTES (the import cap); "notes_left_out"
counts the rest when some did not fit. An import with the block never
overwrites a note: a zone that already has a note here keeps it
("notes_kept"), a new zone gets the file's note ("notes_added") while the
notes file's bounds allow ("notes_full" counts the rest); a bad block
refuses the whole file. A file without the block leaves the notes alone.
"""

import json
import re

from . import hotkeys
from . import layout as layout_mod
from . import playernotes
from .theorycraft import weights as weights_mod

KIND = "ashlight-settings"
SCHEMA = 2
SCHEMAS = (1, 2)  # files AshLight can read; schema 1 has no weights block
# The import body cap (pinned by tests/test_security_surface.py). An
# export whose weights block would pass it leaves the block out.
MAX_BYTES = 16 * 1024
FILE_NAME = "ashlight-settings.json"
# PLAY-TD-04B-THEME-CHOICE: the Theme choice; "system" is Follow Windows
THEMES = ("dark", "system", "light")
THEME_DEFAULT = "dark"
WEIGHTS_LABEL = "stat weights"
# PLAY-F-186B: the optional notes block (decision 0074 item 8)
NOTES_KEY = "notes"
NOTES_LEFT_OUT = "notes_left_out"
NOTES_LABEL = "zone notes"
NOTE_FIELDS = ("character", "area_id", "text")

_NAME = re.compile(r"^[^\x00-\x1f\x7f]{0,64}$")


class SettingsError(ValueError):
    pass


def _bool(v):
    if not isinstance(v, bool):
        raise SettingsError("must be true or false")
    return v


def _int(lo, hi):
    def check(v):
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise SettingsError(f"must be a whole number from {lo} to {hi}")
        return v
    return check


def _str(rx):
    def check(v):
        if not isinstance(v, str) or not rx.match(v):
            raise SettingsError("is not a valid value")
        return v.strip()
    return check


def _hotkey(v):
    """AREA-AUDIT P5-3: Ctrl or Alt plus a key the game doesn't use (the
    rule in hotkeys.py, mirrored by app/hotkey.js before Electron registers
    it); stored canonical."""
    ok = hotkeys.safe_accelerator(v)
    if ok is None:
        raise SettingsError("needs Ctrl or Alt held with a key, and can't be a key "
                            "the game uses")
    return ok


def _theme(v):
    if not isinstance(v, str) or v not in THEMES:
        raise SettingsError("must be Dark, Follow Windows or Light")
    return v


def _overlay(v):
    try:
        return layout_mod.normalize(v, strict=True)
    except layout_mod.LayoutError as e:
        raise SettingsError(str(e)) from e


# key -> validator. The ONLY keys an export writes or an import applies.
ALLOWED = {
    "character": _str(_NAME),
    "poll_ms": _int(50, 5000),
    "overlay_toggle": _hotkey,
    "eval_hotkey": _hotkey,
    "league": _str(_NAME),
    "web_data": _bool,
    "tc_calc": _bool,
    "overlay": _overlay,
    "underlevel_gap": _int(1, 20),
    "run_history": _bool,
    "price_watch_pct": _int(5, 500),
    "boots_speed_level": _int(1, 100),
    "worn_gear": _bool,  # TC-WORN-WIRE (decision 0052): on by default
    "wear_hotkey": _hotkey,  # TC-WORN-KEY: the optional wear key, unset by default
    "update_click_only": _bool,  # REL-UPDATE-TRIGGER: updates wait for 'Update now'
    "theme": _theme,  # PLAY-TD-04B-THEME-CHOICE: Dark (default) / Follow Windows / Light
}
# Player words for each key, for the import error sentence (design 0001 P2).
LABELS = {
    "character": "character name", "poll_ms": "log check interval",
    "overlay_toggle": "overlay hotkey", "eval_hotkey": "item check hotkey",
    "league": "league", "web_data": "web data switch", "tc_calc": "calc switch",
    "overlay": "overlay position", "underlevel_gap": "under-level gap",
    "run_history": "run history switch", "price_watch_pct": "price watch threshold",
    "boots_speed_level": "boots speed level", "worn_gear": "worn gear switch",
    "wear_hotkey": "wear item hotkey", "update_click_only": "update on click only switch",
    "theme": "theme",
}
# Never exported or imported, even if a later key list grows (tests pin it).
# REL-UPDATE-WIRE (ruling Q-21): web_data_ack, the acknowledged opt-in
# wording version, is set only by the player's own web-data click.
NEVER = ("contact", "client_log", "port", "loop", "token", "poesessid", "web_data_ack")


def _weights_block(block):
    """(clean block, merged full weights document) for a weights block.
    Raises SettingsError for a block the weights store would refuse."""
    if not isinstance(block, dict):
        raise SettingsError("are not valid")
    try:
        clean = weights_mod.validate_overrides(block)
        full = weights_mod.merge(clean)
    except weights_mod.WeightsError as e:
        raise SettingsError("are not valid") from e
    return {"weights": clean["weights"], "sidegrade": clean["sidegrade"]}, full


def _text(doc):
    """The download's bytes as the core sends them (http.py: indent 2,
    ASCII), for the size check."""
    return json.dumps(doc, indent=2, ensure_ascii=True) + "\n"


def export_doc(cfg, version, weights=None):
    """The download: AshLight settings only. A stored value that does not
    validate is left out (a hand-broken config never breaks the export).
    weights: the weights store's changes ({"weights", "sidegrade"}), or
    None for no block; a block that does not validate, or that would push
    the file past MAX_BYTES, is left out the same way."""
    cfg = cfg if isinstance(cfg, dict) else {}
    out = {}
    for key, check in ALLOWED.items():
        if key not in cfg:
            continue
        try:
            out[key] = check(cfg[key])
        except SettingsError:
            continue
    doc = {"kind": KIND, "schema": SCHEMA, "app_version": version, "settings": out}
    if weights is not None:
        try:
            block, _full = _weights_block(weights)
        except SettingsError:
            return doc
        with_block = dict(doc, weights=block)
        if len(_text(with_block).encode("ascii")) <= MAX_BYTES:
            return with_block
    return doc


def weights_of(doc):
    """The full weights document an import puts in place, or None when the
    file carries no weights block (schema 1, or none written). Raises
    SettingsError for a bad block; parse_import checks it first."""
    if not isinstance(doc, dict) or doc.get("schema") != 2 or "weights" not in doc:
        return None
    try:
        return _weights_block(doc["weights"])[1]
    except SettingsError as e:
        raise SettingsError(f"The {WEIGHTS_LABEL} in that file {e}.") from e


def parse_import(doc, current):
    """Validate an imported file against the current config. Returns
    (update, report): update = the keys to merge into config/local.json,
    report = {"applied": [...], "ignored": [...], "web_data_offered": bool,
    "tc_calc_offered": bool, "weights_applied": bool}. The weights block
    (schema 2) is checked here and taken with weights_of(doc).
    Raises SettingsError (nothing applied) on a file that is not an
    AshLight settings backup or holds a bad value. RUN-NO-DEAD-ENDS
    (research 0042 F3): the player-facing name of this file is "settings
    backup"."""
    if not isinstance(doc, dict) or doc.get("kind") != KIND:
        raise SettingsError("This file isn't an AshLight settings backup.")
    schema = doc.get("schema")
    if isinstance(schema, bool) or schema not in SCHEMAS:
        raise SettingsError("This settings backup is from a version AshLight can't read.")
    settings = doc.get("settings")
    if not isinstance(settings, dict):
        raise SettingsError("This settings backup has no settings in it.")
    current = current if isinstance(current, dict) else {}
    update, ignored = {}, []
    for key, value in settings.items():
        check = ALLOWED.get(key) if isinstance(key, str) and key not in NEVER else None
        if check is None:
            ignored.append(str(key)[:40])
            continue
        try:
            update[key] = check(value)
        except SettingsError as e:
            raise SettingsError(f"The {LABELS.get(key, key)} in that file {e}.") from e
    offered = False
    if update.get("web_data") is True and current.get("web_data") is not True:
        del update["web_data"]
        offered = True
    calc_offered = False
    if update.get("tc_calc") is True and current.get("tc_calc") is not True:
        del update["tc_calc"]
        ignored.append("tc_calc")
        calc_offered = True
    weights_applied = weights_of(doc) is not None  # raises on a bad block
    report = {"applied": sorted(update), "ignored": sorted(ignored)[:20],
              "web_data_offered": offered, "tc_calc_offered": calc_offered,
              "weights_applied": weights_applied}
    return update, report


# -- PLAY-F-186B: the zone notes block (decision 0074 item 8) -----------------

def with_notes(doc, book):
    """doc plus the notes block of a notes book ({character: {area id:
    {"text", "at"}}}): newest first, as many as keep the file within
    MAX_BYTES; NOTES_LEFT_OUT counts the ones that did not fit (only when
    some did not). Only called when the player ticked the option."""
    rows = sorted(((e.get("at", 0), name, area, e["text"])
                   for name, per in (book or {}).items() for area, e in per.items()),
                  key=lambda r: (-r[0], r[1], r[2]))
    out = dict(doc, **{NOTES_KEY: []})
    # measured exactly, with room kept for the left-out count
    probe = dict(out, **{NOTES_LEFT_OUT: len(rows)})
    left = 0
    for _at, name, area, text in rows:
        probe[NOTES_KEY].append({"character": name, "area_id": area, "text": text})
        if len(_text(probe).encode("ascii")) > MAX_BYTES:
            probe[NOTES_KEY].pop()
            left += 1
    if left:
        out[NOTES_LEFT_OUT] = left
    return out


def notes_of(doc):
    """[(character, area id, text)] of an imported file's notes block, or
    None when the file has none. Raises SettingsError (nothing applied)
    for a block that is not a list of at most playernotes.MAX_ZONES notes
    the notes store would keep, or that names one zone twice."""
    if not isinstance(doc, dict) or NOTES_KEY not in doc:
        return None
    bad = SettingsError(f"The {NOTES_LABEL} in that file are not valid.")
    rows = doc[NOTES_KEY]
    if not isinstance(rows, list) or len(rows) > playernotes.MAX_ZONES:
        raise bad
    out, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(NOTE_FIELDS):
            raise bad
        try:
            name = playernotes.clean_name(row["character"])
            area = playernotes.clean_area(row["area_id"])
            text = playernotes.clean_text(row["text"])
        except playernotes.NoteError:
            raise bad from None
        if not text or (name, area) in seen:
            raise bad
        seen.add((name, area))
        out.append((name, area, text))
    return out


def merge_notes(book, rows):
    """(adds, report) for imported notes against the current book: adds =
    [(character, area id, text)] to save, in file order; report =
    {"notes_added", "notes_kept", "notes_full"}. A zone that already has a
    note keeps it (kept, unless the text is the same); a new one is added
    while the store's bounds (MAX_ZONES notes, MAX_CHARACTERS characters)
    allow, so a save never pushes an older note out; the rest is full."""
    book = book or {}
    total = playernotes.count(book)
    names = set(book)
    adds, kept, full = [], 0, 0
    for name, area, text in rows:
        have = book.get(name, {}).get(area)
        if have is not None:
            kept += have.get("text") != text
            continue
        if total >= playernotes.MAX_ZONES or (
                name not in names and len(names) >= playernotes.MAX_CHARACTERS):
            full += 1
            continue
        adds.append((name, area, text))
        total += 1
        names.add(name)
    return adds, {"notes_added": len(adds), "notes_kept": kept, "notes_full": full}
