"""UX-ZONE-NOTES (decision 0030): one short AshLight-written note per
campaign zone, shown on zone entry.

The notes live in the tracked data file `server/al/data/zone_notes.json`
(our own words, decision 0009: no wiki or poe2db prose). A note is found by
the act of the area id (acts.act_of) and the zone name the log gave; a zone
with no note of its own gets its act's default, so every campaign area id
has a note. Hideouts, maps and unknown ids get none. Read only from the
already tailed area / scene lines; nothing new is read.
"""

import json
from pathlib import Path

from . import acts as acts_mod

PATH = Path(__file__).resolve().parent / "data" / "zone_notes.json"
MAX_NOTE = 110
_cache = {}


def load(path=PATH):
    """The notes document ({} when missing or malformed)."""
    key = str(path)
    if key not in _cache:
        try:
            doc = json.loads(Path(path).read_text(encoding="ascii"))
        except (OSError, ValueError):
            doc = {}
        _cache[key] = doc if isinstance(doc, dict) else {}
    return _cache[key]


def _act_entry(doc, area_id):
    info = acts_mod.act_of(area_id)
    if info is None:
        return None
    table = doc.get("acts") if isinstance(doc.get("acts"), dict) else {}
    key = info["key"]
    entry = table.get(key)
    if entry is None and key.startswith("C"):
        entry = table.get("C")
    return entry if isinstance(entry, dict) else None


def note_for(area_id, zone=None, doc=None):
    """{"text", "source": "zone"|"act"} for a campaign area, else None."""
    doc = load() if doc is None else doc
    entry = _act_entry(doc, area_id)
    if entry is None:
        return None
    zones = entry.get("zones") if isinstance(entry.get("zones"), dict) else {}
    if isinstance(zone, str) and isinstance(zones.get(zone.strip()), str):
        return {"text": zones[zone.strip()], "source": "zone"}
    if isinstance(entry.get("default"), str):
        return {"text": entry["default"], "source": "act"}
    return None
