"""Per-map stats text (UTIL-MAP-STATS, research 0064 G5).

The words of the per-map table on the Run tab's Maps card (its "By map"
page) and of the current map's line on the Play tab's map context card.
The numbers come from server/al/mapstats.py; this module only words them.
Templates: docs/design/copy/mapstats.md, edited in both places together;
tests/test_map_stats.py pins every sentence exactly. Pure functions and
constants; stdlib only.
"""

EMPTY_TEXT = "No maps yet. Each map shows here by itself as you play it."
MEDIAN_NOTE = "Median time counts finished runs."


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def head_text(areas, title):
    """The page sentence: how many maps the table holds, and from where
    (the ladder's title, 'This session' or 'All saved sessions')."""
    return f"{title}: {_plural(areas, 'map')}. {MEDIAN_NOTE}"


def row_text(name, runs, deaths, median_text):
    """One table row: 'Sun Temple: 3 runs, 1 death, median 6:30'. A map
    with no finished run has no median yet and says so."""
    med = f"median {median_text}" if median_text else "no finished run yet"
    return f"{name}: {_plural(runs, 'run')}, {_plural(deaths, 'death')}, {med}"


def here_text(runs, deaths, median_text):
    """The map context card's line for the map the player is in, this run
    counted: '3 runs here, median 6:30, 1 death'."""
    parts = [_plural(runs, "run") + " here"]
    if median_text:
        parts.append(f"median {median_text}")
    parts.append(_plural(deaths, "death"))
    return ", ".join(parts)
