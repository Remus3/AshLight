"""TC-UPGRADE (decision 0017 item 3): an upgrade-search link per item check.

On each item-hotkey press the item check (theorycraft.evaluate) picks the
build's gear slot the checked item goes in (the best swap for rings and
charms). `link(result, league)` turns that into an offline trade2 search URL
for upgrade candidates in that slot: rare items of the base the build wears
there (decision 0014 build view), else of the checked item's base when the
slot is empty. TC-UPGRADE-STATS (decision 0037): the top weighted stats
that have an explicit trade id in the cached repoe-fork snapshot
(server/al/tradestats.py) become one weighted stat group; a stat without an
id gets no filter, and with no snapshot (or web data off) the link stays
base type and rarity only. trade.upgrade_query checks the complexity cap. The URL comes from trade.link_for, the
same builder as the price link (PRICE-TRADE-LINK).

Pure: no network, no clipboard, nothing sent to the game. The core never
opens the URL; the dashboard shows it as a link the player may click. It
rides on the item check card, so a build or weights change re-scores the
item and rebuilds the link with no click (ZERO-CLICK).
"""

from . import trade, tradestats

RARITY = "rare"
MAX_TOP = 6


def _weights(result, comp):
    """TC-DELTA (decision 0024): which weights valued this slot ("pob" when
    the PoB calc answered, else "hand") and the top positive per-mod
    weights among the compared stats; those with a trade id become the
    link's stat filters (TC-UPGRADE-STATS)."""
    mw = result.get("mod_weights") if isinstance(result.get("mod_weights"), dict) else {}
    # MATH-WEIGHTS: "pob_cached" = PoB weights measured earlier for this build
    source = mw.get("source") if mw.get("source") in ("pob", "pob_cached") else "hand"
    top = []
    for row in comp.get("stats") or ():
        w = row.get("weight") if isinstance(row, dict) else None
        if row.get("weighted") and isinstance(w, (int, float)) \
                and not isinstance(w, bool) and w > 0:
            top.append({"key": row.get("key"), "weight": w})
    top.sort(key=lambda r: (-r["weight"], str(r["key"]).lower()))
    return {"source": source, "top": top[:MAX_TOP]}


def _best(result):
    slot = result.get("slot")
    for c in result.get("comparisons") or ():
        if isinstance(c, dict) and c.get("slot") == slot:
            return c
    return None


def _filters(top, ids):
    """[{key, id, weight}] for the top weights that have a trade id in the
    snapshot index `ids` (tradestats.load_index); never guesses an id."""
    out, seen = [], set()
    for row in top:
        tid = tradestats.lookup(ids, row.get("key"))
        if tid is not None and tid not in seen:
            seen.add(tid)
            out.append({"key": row["key"], "id": tid, "weight": row["weight"]})
    return out


def link(result, league=None, ids=None):
    """The upgrade link doc for an evaluate() result, or None when there is
    no slot to search (not an item, no gear slot, no build loaded) or no base
    type. Doc: slot, base, source ("equipped" | "item"), rarity, league, url,
    weights ({source: "pob" | "hand", top: [{key, weight}]}), filters
    ([{key, id, weight}] put in the URL; [] without a trade id index).
    `ids`: the trade id index (tradestats), None or {} for no filters.
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
    weights = _weights(result, comp)
    filters = _filters(weights["top"], ids) if ids else []
    try:
        url = trade.upgrade_link(base, league,
                                 [(f["id"], f["weight"]) for f in filters])
    except ValueError:
        return None
    if not trade.is_search_link(url):
        return None
    return {"slot": result["slot"], "base": base.strip(), "source": source,
            "rarity": RARITY, "league": league, "url": url,
            "weights": weights, "filters": filters}
