"""League identity (DATA-LEAGUE-IDENTITY, finding F-031): poe.ninja's
leagues list kept whole, as id plus name.

poe.ninja's documented GET /poe2/api/economy/leagues answers
[{"id", "name"}, ...] with the newest league first (research 0005, 0013,
0019). The id goes into poe.ninja URLs; the name goes into trade links and
labels. Today they are equal, but the PoE2 1.0 league (2026-12-11) may give
them apart (research 0036, drift risk 1), so both are kept.

Pure functions: no request, no file, no clock. ninja.py owns the GET and
the cache (rates.json, keys "leagues" and "league_list_etag").
"""

import json

MAX_LEAGUES = 64  # the real list holds about 6; a hostile body is cut here
MAX_LEN = 80


def _text(value):
    if isinstance(value, str) and value.strip():
        return value.strip()[:MAX_LEN]
    return None


def parse_list(body):
    """[{"id", "name"}] from a leagues response, in its order. An entry
    without an id uses its name as the id and one without a name uses its
    id; the first entry of an id wins, so ids are unique. Tolerates
    {"leagues": [...]} and {"result": [...]}. Raises ValueError when no
    league is left."""
    doc = json.loads(body)
    if isinstance(doc, dict):
        doc = doc.get("leagues") or doc.get("result") or []
    out, seen = [], set()
    for entry in doc if isinstance(doc, list) else []:
        if not isinstance(entry, dict):
            continue
        lid = _text(entry.get("id")) or _text(entry.get("name"))
        if lid is None or lid in seen:
            continue
        seen.add(lid)
        out.append({"id": lid, "name": _text(entry.get("name")) or lid})
        if len(out) >= MAX_LEAGUES:
            break
    if not out:
        raise ValueError("no league in the leagues response")
    return out


def entries(listed):
    """The well-formed {id, name} entries of a cached list (a cache file a
    user edited may hold anything)."""
    for entry in listed if isinstance(listed, list) else ():
        if (isinstance(entry, dict) and isinstance(entry.get("id"), str)
                and isinstance(entry.get("name"), str)):
            yield entry


def entry_of(listed, value):
    """The cached entry a league id or name names, or None. An exact id
    wins, then an exact name, then either ignoring case."""
    value = _text(value)
    if value is None:
        return None
    rows = list(entries(listed))
    for key in ("id", "name"):
        for entry in rows:
            if entry[key] == value:
                return entry
    low = value.lower()
    for entry in rows:
        if low in (entry["id"].lower(), entry["name"].lower()):
            return entry
    return None


def name_of(listed, league_id):
    """The display name of a cached league id (exact match), or None."""
    for entry in entries(listed):
        if entry["id"] == league_id:
            return entry["name"]
    return None


def id_of(listed, value):
    """The poe.ninja id of a cached league given by id or name, or None."""
    entry = entry_of(listed, value)
    return entry["id"] if entry is not None else None
