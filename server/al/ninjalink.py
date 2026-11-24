"""DATA-PRICE-NINJA-LINK (folded into DATA-GUIDE-ONE-BLOCK; research 0036
R12, decision 0016 amendment 2026-11-23): the poe.ninja category page of a
checked item, as a link the player opens in their own browser.

Pure: no request, no file, no clock. The app requests nothing; the
player's browser does, on the player's click (as decision 0017 does for
the trade site).

poe.ninja does not document its page URLs. The page form
https://poe.ninja/poe2/economy/<league slug>/<category slug> and every slug
below were READ from poe.ninja's public pages on 2026-11-23 (research 0036,
section "Economy page forms"): robots.txt (allows them) and the English
sitemap, which lists every page; 21 of the category pages of the current
league were also fetched once each (each 200).
Adjudicator LE-39 (2026-11-18): never a derived or guessed slug, so these
are literal tables, never computed from a type or a league name. A pair is
listed only when the page's slug spells the overview type or league id
word for word (lower case, words joined by '-' for a category, run
together for a league); a renamed page (Abyss, Ritual, Delirium, Breach,
UniqueSanctumRelics) and a league whose slug reorders its words (the HC
challenge leagues) get no link. A type or league not in a table gets no link.
"""

import re

BASE = "https://poe.ninja/poe2/economy/"

# poe.ninja overview type (server/al/data/price_types.json, ninja.OVERVIEW_TYPE)
# -> category page slug, as read 2026-11-23
CATEGORY_PAGES = {
    "Currency": "currency",
    "Fragments": "fragments",
    "UncutGems": "uncut-gems",
    "LineageSupportGems": "lineage-support-gems",
    "Essences": "essences",
    "SoulCores": "soul-cores",
    "Idols": "idols",
    "Runes": "runes",
    "Expedition": "expedition",
    "Verisium": "verisium",
    "UniqueWeapons": "unique-weapons",
    "UniqueArmours": "unique-armours",
    "UniqueAccessories": "unique-accessories",
    "UniqueFlasks": "unique-flasks",
    "UniqueCharms": "unique-charms",
    "UniqueJewels": "unique-jewels",
    "UniqueTablets": "unique-tablets",
    "PrecursorTablets": "precursor-tablets",
}

# poe.ninja league id (the cached leagues list, leagues.py) -> page slug,
# as read 2026-11-23
LEAGUE_PAGES = {
    "Forbidden Rites": "forbiddenrites",
    "Runes of Aldur": "runesofaldur",
    "Standard": "standard",
    "Hardcore": "hardcore",
}

# the one shape a link may have: https, the exact host, the economy path,
# two lower-case slugs, nothing after (no query, no fragment, no /api/)
PAGE_RE = re.compile(r"^https://poe\.ninja/poe2/economy/[a-z0-9]+(?:-[a-z0-9]+)*"
                     r"/[a-z0-9]+(?:-[a-z0-9]+)*$")


def is_page_url(url):
    """True only for an https poe.ninja PoE2 economy category page URL."""
    return isinstance(url, str) and len(url) <= 200 and bool(PAGE_RE.match(url))


def _league_id(league):
    if isinstance(league, dict):
        league = league.get("id")
    return league if isinstance(league, str) else None


def url_for(type_name, league):
    """The category page URL for a poe.ninja overview type in a league (a
    league id, or a leagues-list entry {id, name}), or None when either
    form was not read."""
    category = CATEGORY_PAGES.get(type_name) if isinstance(type_name, str) else None
    slug = LEAGUE_PAGES.get(_league_id(league))
    if category is None or slug is None:
        return None
    url = BASE + slug + "/" + category
    return url if is_page_url(url) else None
