"""TC-UPGRADE (decision 0017 item 3): an upgrade-search link per item check.

On each item-hotkey press the item check (theorycraft.evaluate) picks the
build's gear slot the checked item goes in (the best swap for rings and
charms). `link(result, league)` turns that into an offline trade2 search URL
for upgrade candidates in that slot: rare items of the base the build wears
there (decision 0014 build view), else of the checked item's base when the
slot is empty. Base type and rarity only; no stat filters until
TC-UPGRADE-STATS finds a permitted stat-id source (trade.upgrade_query also
checks the site's complexity cap). The URL comes from trade.link_for, the
same builder as the price link (PRICE-TRADE-LINK).

Pure: no network, no clipboard, nothing sent to the game. The core never
opens the URL; the dashboard shows it as a link the player may click. It
rides on the item check card, so a build or weights change re-scores the
item and rebuilds the link with no click (ZERO-CLICK).
"""

from . import trade

RARITY = "rare"


def _best(result):
    slot = result.get("slot")
    for c in result.get("comparisons") or ():
        if isinstance(c, dict) and c.get("slot") == slot:
            return c
    return None


def link(result, league=None):
    """The upgrade link doc for an evaluate() result, or None when there is
    no slot to search (not an item, no gear slot, no build loaded) or no base
    type. Doc: slot, base, source ("equipped" | "item"), rarity, league, url.
    Never raises on input content."""
    if not isinstance(result, dict) or not result.get("ok") or not result.get("slot"):
        return None
    comp = _best(result)
    if comp is None:
        return None
    equipped = comp.get("equipped") if isinstance(comp.get("equipped"), dict) else {}
    item = result.get("item") if isinstance(result.get("item"), dict) else {}
    base, source = equipped.get("base"), "equipped"
    if not (isinstance(base, str) and base.strip()):
        base, source = item.get("base"), "item"
    if not (isinstance(base, str) and base.strip()):
        return None
    league = trade.league_or_default(league)
    try:
        url = trade.upgrade_link(base, league)
    except ValueError:
        return None
    if not trade.is_search_link(url):
        return None
    return {"slot": result["slot"], "base": base.strip(), "source": source,
            "rarity": RARITY, "league": league, "url": url}
