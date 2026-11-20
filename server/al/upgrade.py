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
same builder as the price link (PRICE-TRADE-LINK). TC-UPGRADE-PER-SLOT:
`slot_link(base, slot, weights, league, ids)` is the per-slot core of
link(), also used for each "look for next" row of the build view, so a
search for any slot needs no item press first.

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


# AREA-AUDIT P6-1: the trade site lists a "(Local)" twin of some stats (the
# PoB fallback carries them): on an armour piece its armour, evasion and
# energy shield roll local, on a weapon its attack speed / accuracy do, on
# jewellery nothing does. The slot picks the id; where the item class is
# not known from the slot (off hand: shield, focus, quiver or weapon;
# flasks, charms) a stat with a local twin gets no filter.
ARMOUR_SLOTS = frozenset({"Helmet", "Body Armour", "Gloves", "Boots"})
WEAPON_SLOTS = frozenset({"Weapon 1"})
GLOBAL_SLOTS = frozenset({"Amulet", "Ring 1", "Ring 2", "Belt"})
LOCAL_SUFFIX = " (Local)"
_DEFENCE = ("armour", "evasion", "energy shield")


def _slot_id(ids, key, slot):
    """The trade id of `key` for an item in `slot`, or None (no filter)."""
    tid = tradestats.lookup(ids, key)
    local = (tradestats.lookup(ids, key + LOCAL_SUFFIX)
             if isinstance(key, str) else None)
    if local is None:
        return tid
    defence = any(w in key.lower() for w in _DEFENCE)
    if slot in GLOBAL_SLOTS:
        return tid
    if slot in ARMOUR_SLOTS:
        return local if defence else tid
    if slot in WEAPON_SLOTS:
        return None if defence else local
    return None


def _filters(top, ids, slot=None):
    """[{key, id, weight}] for the top weights that have a trade id in the
    snapshot index `ids` (tradestats.load_index) for an item in `slot`
    (P6-1: local or global id); never guesses an id."""
    out, seen = [], set()
    for row in top:
        tid = _slot_id(ids, row.get("key"), slot)
        if tid is not None and tid not in seen:
            seen.add(tid)
            out.append({"key": row["key"], "id": tid, "weight": row["weight"]})
    return out


def slot_link(base, slot, weights=None, league=None, ids=None):
    """TC-UPGRADE-PER-SLOT: the upgrade link doc for rare items of `base`
    in gear `slot`, or None with no base type (or a link the trade site
    would refuse). `weights`: [{key, weight}] in rank order (the first
    MAX_TOP positive ones are used); `ids`: the trade id index (tradestats),
    None or {} for no filters. Doc: slot, base, rarity, league, url,
    filters ([{key, id, weight}] put in the URL). Shared by the item check
    link (link()) and the build view's "look for next" rows. Pure; never
    raises on input content."""
    if not (isinstance(base, str) and base.strip()):
        return None
    top = []
    for row in weights if isinstance(weights, (list, tuple)) else ():
        w = row.get("weight") if isinstance(row, dict) else None
        if isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0 \
                and isinstance(row.get("key"), str):
            top.append({"key": row["key"], "weight": w})
    league = trade.league_or_default(league)
    filters = _filters(top[:MAX_TOP], ids, slot) if ids else []
    try:
        url = trade.upgrade_link(base, league,
                                 [(f["id"], f["weight"]) for f in filters])
    except ValueError:
        return None
    if not trade.is_search_link(url):
        return None
    return {"slot": slot, "base": base.strip(), "rarity": RARITY,
            "league": league, "url": url, "filters": filters}


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
    weights = _weights(result, comp)
    doc = slot_link(base, result["slot"], weights["top"], league, ids)
    if doc is None:
        return None
    return {"slot": doc["slot"], "base": doc["base"], "source": source,
            "rarity": doc["rarity"], "league": doc["league"], "url": doc["url"],
            "weights": weights, "filters": doc["filters"]}
