"""UTIL-UNDERLEVEL: "N levels under this zone" (research 0028 section 3,
ruling B).

The gap is a subtraction of two values the opted-in Client.txt tail
already gives: the area level from the `Generating level N area` line and
the player level from the player's own level-up lines (research 0002).
When the log gave no area level (rare: a core started mid-zone with no
generation line read back), the zone's level from the build-time
world_areas snapshot (decision 0020) is used; with neither, nothing shows.
No XP-penalty formula is shown or computed.

Skipped: an unknown player level, towns and hideouts (no monsters there),
and a gap under the threshold (setting "underlevel_gap", default 3).
"""

DEFAULT_GAP = 3
MIN_GAP, MAX_GAP = 1, 20
CONFIG_KEY = "underlevel_gap"
# the overlay HUD status word is at most 15 characters (design 0001 7.2)
WORD_MAX = 15


def gap_setting(value):
    """The threshold from the local config: an int in [MIN_GAP, MAX_GAP],
    else the default."""
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_GAP
    return value if MIN_GAP <= value <= MAX_GAP else DEFAULT_GAP


def _is_level(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _is_quiet(area_id, zone, in_hideout, table_town):
    if in_hideout or table_town:
        return True
    for text in (area_id, zone):
        low = text.lower() if isinstance(text, str) else ""
        if "hideout" in low or "town" in low:
            return True
    return False


def _table_row(table, area_id, zone):
    """The world_areas row for this area (by id, else by name), or None."""
    if not isinstance(table, dict):
        return None
    by_name = None
    for rows in table.values():
        for r in rows if isinstance(rows, list) else ():
            if not isinstance(r, dict):
                continue
            if area_id is not None and r.get("id") == area_id:
                return r
            if by_name is None and zone is not None and r.get("name") == zone:
                by_name = r
    return by_name


def view(level, area_level, area_id, zone, in_hideout, table=None,
         threshold=DEFAULT_GAP):
    """The snapshot `underlevel` part: {"gap", "zone_level", "level",
    "text", "word", "source"} when the player is at least `threshold`
    levels under the zone, else None."""
    if not _is_level(level):
        return None
    row = _table_row(table, area_id, zone)
    source = "log"
    zone_level = area_level if _is_level(area_level) else None
    if zone_level is None and row is not None and _is_level(row.get("level")):
        zone_level, source = row["level"], "zone table"
    if zone_level is None:
        return None
    if _is_quiet(area_id, zone, in_hideout, bool(row and row.get("town"))):
        return None
    gap = zone_level - level
    if gap < gap_setting(threshold):
        return None
    unit = "level" if gap == 1 else "levels"
    word = f"{gap} lv under"
    return {"gap": gap, "zone_level": zone_level, "level": level,
            # UX-B9-CARDS: the player level is the big value right above
            # this line, so the sentence names only the zone level
            "text": f"{gap} {unit} under this zone (zone level {zone_level}).",
            "word": word[:WORD_MAX], "source": source}
