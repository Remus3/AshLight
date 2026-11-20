"""Price check text (PRICE-1-UI, design 0001 section 9, decision 0016).

Moved byte for byte out of server/al/state.py (TEST-STATE-TEXT-2);
state.py re-exports every name, so state.<name> is the same object.
PRICE_TEXT stays the only place price wording is made. The empty
clipboard text (OVL-COPY-FIRST) lives here because PRICE_TEXT carries
it; state.py's EVAL_ERROR_TEXT takes it through the re-export. Pure
functions and constants; stdlib only.
"""

import math

from .common import CARD_LINE, _dict, _dicts, _is_time, _key, _num_text, _text


# OVL-COPY-FIRST (F-054): the press found a blank clipboard (the game had not
# written the item yet); core.eval_press publishes this error and asks for no
# price check. The player copies the item and presses again: no retry.
EMPTY_CLIPBOARD = "empty clipboard"
EMPTY_CLIPBOARD_TEXT = ("Copy the item first", "Hover it in game, press Ctrl+C",
                        "The clipboard was empty when you pressed the hotkey. Hover an "
                        "item in game, press Ctrl+C, then press the hotkey again.")

# "link" (decision 0017) is the only success status the core produces now;
# searching / waiting / done / off are kept for the 0016 contract's readers
PRICE_STATUSES = ("link", "searching", "waiting", "done", "off", "error")
PRICE_LISTINGS = 10


# -- PRICE-1-UI: price check text (design 0001 section 9, decision 0016).
# The PRICE-1 result contract (state snapshot "price") is documented in
# docs/decisions/0016-price-ui-contract.md; these templates are the only
# place price wording is made.
PRICE_TEXT = {
    # status / error: (overlay price line, overlay detail line, dashboard sentence)
    # PRICE-TRADE-LINK (decision 0017): the overlay says only that the link
    # is ready; the dashboard shows the link itself
    "link": ("Trade link ready", "",
             "A trade site search for this item in {league} is ready. Click the link to "
             "see who sells it."),
    "searching": ("Searching prices...", "On the official trade site",
                  "Searching the official trade site for this item..."),
    # DATA-PRICE-CARD-TEXT (F-018): the blocked copy names poe.ninja and the
    # dashboard card, never a file
    "off": ("Web data is off", "Turn it on in Prices and web data",
            "poe.ninja prices need web data, which is off. Turn it on in the Prices and "
            "web data card on this page."),
    "contact not set": ("Contact not set", "Add it in Prices and web data",
                        "poe.ninja prices need a contact, such as an email or a name. Add "
                        "it in the Prices and web data card on this page, then press the "
                        "hotkey again."),
    "not an item": ("Not an item", "Copy an item in game first",
                    "The clipboard did not hold an item. Hover an item in game, press "
                    "Ctrl+C, then press the hotkey."),
    EMPTY_CLIPBOARD: EMPTY_CLIPBOARD_TEXT,
    "no base type": ("Can't price this item", "Try a different item",
                     "AshLight can't make a trade search for this item. Try a different "
                     "one."),
    "no league": ("League unknown", "Try again in a minute",
                  "AshLight doesn't know which league to search yet. Try again in a "
                  "minute."),
    "error": ("Price check failed", "Press the hotkey again",
              "AshLight couldn't make a trade search for this item. Press the hotkey "
              "again."),
    # PRICE-UNIQUE / PRICE-STACKABLES: after a poe.ninja value sentence
    "link_too": "A trade site search in {league} is ready too; click the link to "
                "see who sells it.",
    "none": ("No listings found", "Nobody sells this now",
             "Nobody lists this item in {league} right now, so AshLight can't price it."),
    # DATA-PRICE-CARD-TEXT (F-036): a cached poe.ninja price by its age at
    # the press; over PRICE_OLD_S the card is the link alone
    "aged": "This price is from {hours} h ago.",
    "aged_detail": "Price from {hours} h ago",
    "aged_rough": "Rough price from {hours} h ago",
    "too_old": "The poe.ninja price for it is over a day old, so AshLight does not show "
               "it.",
}

# DATA-PRICE-CARD-TEXT: ages are press time minus the cache's checked_at
# (F-036) and press time minus the league change (F-031), in seconds
PRICE_AGED_S = 2 * 3600  # older than this: the card says how old
PRICE_OLD_S = 24 * 3600  # older than this: the link only
LEAGUE_NEW_S = 24 * 3600  # the overlay line names the league this long


def _price_amount(value):
    """A listed amount: digits, at most 2 decimals, no trailing zeros."""
    try:
        n = round(float(value), 2)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(n):
        return None
    if n == 0:
        n = 0.0
    return str(int(n)) if n.is_integer() else f"{n:.2f}".rstrip("0")


def _listing_text(row):
    row = row if isinstance(row, dict) else {}
    amount = _price_amount(row.get("amount"))
    cur = _text(row.get("currency"), "")
    if amount is None:
        return "price unknown"
    return f"{amount} {cur}" if cur else f"{amount} (currency unknown)"


def _ninja_amount(v):
    """A poe.ninja value: 2 decimals from 1 up, 3 significant digits below,
    None for dust (under 0.001)."""
    v = float(v)
    if v >= 1:
        return _price_amount(v)
    if v < 0.001:
        return None
    return f"{v:.3g}"


def _age_s(at, then):
    """Seconds from `then` to the press `at`, or None when either is not a
    usable time or `then` lies after the press (a clock step)."""
    if not (_is_time(at) and _is_time(then)) or then > at:
        return None
    return float(at) - float(then)


def ninja_text(ninja, at=None):
    """PRICE-UNIQUE / PRICE-STACKABLES: {line, detail, sentence} for the
    card's cached poe.ninja price, or None. `at` is the press time: a price
    older than PRICE_AGED_S says its age (F-036), and for LEAGUE_NEW_S
    after a league change the overlay line names the league (F-031); the
    caller drops a price older than PRICE_OLD_S. Exact tests in
    tests/test_price_book.py and tests/test_price_card_age.py."""
    if not isinstance(ninja, dict):
        return None
    v = ninja.get("value")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0:
        return None
    unit = _text(ninja.get("unit"), "")
    amount = _ninja_amount(v)
    dust = amount is None
    amount = "0.001" if dust else amount
    money = f"{amount} {unit}" if unit else amount
    league = _text(ninja.get("league"), "this league")
    listings = ninja.get("listings")
    has_n = isinstance(listings, int) and not isinstance(listings, bool)
    change = ninja.get("change")
    has_ch = (isinstance(change, (int, float)) and not isinstance(change, bool)
              and change == change and abs(change) >= 0.5)
    trend = ""
    if has_ch:
        word = "up" if change > 0 else "down"
        trend = f"{word} {_num_text(abs(change))}% over 7 days"
    if ninja.get("few"):
        detail = "Few listings: rough price"
    elif trend:
        detail = trend[0].upper() + trend[1:] + " (poe.ninja)"
    else:
        detail = "From poe.ninja"
    sentence = (f"poe.ninja puts this at under {money} in {league}" if dust
                else f"poe.ninja puts this at about {money} in {league}")
    rough = has_n and ninja.get("few")
    if rough:
        sentence += f", but only {listings} {'is' if listings == 1 else 'are'} listed."
        sentence += f" The price is rough; {trend}." if trend else " The price is rough."
    else:
        if has_n:
            sentence += f", from {listings} listing{'' if listings == 1 else 's'}"
        sentence += f"; {trend}." if trend else "."
    line = f"Under {money}" if dust else f"About {money}"
    age = _age_s(at, ninja.get("checked_at"))
    if age is not None and age > PRICE_AGED_S:
        hours = int(age // 3600)
        detail = PRICE_TEXT["aged_rough" if ninja.get("few") else "aged_detail"].format(
            hours=hours)
        sentence += " " + PRICE_TEXT["aged"].format(hours=hours)
    changed = _age_s(at, ninja.get("league_changed_at"))
    named = ninja.get("league")
    # the league on the price line; a long name takes the detail line; a
    # non-ASCII name stays in the sentence only (design 0001 overlay text)
    if (changed is not None and changed < LEAGUE_NEW_S and isinstance(named, str)
            and named.strip() and named.isascii()):
        if len(f"{line} in {named}") <= CARD_LINE:
            line = f"{line} in {named}"
        else:
            detail = f"League: {named}"
            if len(detail) > CARD_LINE:
                detail = detail[:CARD_LINE - 3].rstrip() + "..."
    return {"line": line, "detail": detail, "sentence": sentence}


def price_card_text(card):
    """The words for one price check (PRICE-1-UI): `head`, `line` and
    `detail` for the overlay card, `sentence` and `rows` (one per listing)
    for the dashboard. Missing values read honestly; every template has an
    exact-output test (tests/test_price_text.py)."""
    card = _dict(card)
    item = _dict(card.get("item"))
    name = _text(item.get("name") or item.get("base"), "Unnamed item")
    listings = _dicts(card.get("listings"))
    rows = [_listing_text(r) for r in listings[:PRICE_LISTINGS]]
    out = {"head": f"Price: {name}", "item": name, "line": "", "detail": "",
           "sentence": "", "rows": rows}
    status = _key(card.get("status"))
    league = _text(card.get("league"), "this league")
    if status == "waiting":
        try:
            secs = max(1, int(-(-float(card.get("wait_s") or 0) // 1)))
        except (TypeError, ValueError, OverflowError):
            secs = 1
        out.update(line=f"Prices in about {secs} s", detail="Waiting for the trade site",
                   sentence=f"Waiting about {secs} s for the trade site, then AshLight "
                            "searches by itself.")
        return out
    if status == "done":
        count = card.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < len(rows):
            count = len(rows)
        if not rows:
            line, detail, sentence = PRICE_TEXT["none"]
            out.update(line=line, detail=detail, sentence=sentence.format(league=league))
            return out
        low, mid = rows[0], rows[(len(rows) - 1) // 2]
        out["line"] = f"{count} listed, ~{mid}"
        out["detail"] = f"Lowest {low}"
        if len(rows) == 1:
            out["sentence"] = f"{count} listed in {league}, for {low}."
        else:
            out["sentence"] = (f"{count} listed in {league}. The cheapest is {low}; the "
                               f"middle of the {len(rows)} cheapest is {mid}.")
        return out
    if status == "link":
        line, detail, sentence = PRICE_TEXT["link"]
        out.update(line=line, detail=detail, sentence=sentence.format(league=league))
        raw = _dict(card.get("ninja"))
        age = _age_s(card.get("at"), raw.get("checked_at"))
        if age is not None and age > PRICE_OLD_S:
            # F-036: a day-old price is left out; the link stands alone
            if ninja_text(raw) is not None:
                out["sentence"] += " " + PRICE_TEXT["too_old"]
            return out
        ninja = ninja_text(raw, card.get("at"))
        if ninja:
            out.update(line=ninja["line"], detail=ninja["detail"],
                       sentence=ninja["sentence"] + " " + PRICE_TEXT["link_too"].format(
                           league=league))
        return out
    if status == "searching":
        key = status
    elif status == "off":
        key = "contact not set" if card.get("error") == "contact not set" else "off"
    else:
        err = _key(card.get("error"))
        key = err if err in PRICE_TEXT else "error"
        if key in ("link", "searching", "off", "none", "contact not set"):
            key = "error"
    line, detail, sentence = PRICE_TEXT[key]
    out.update(line=line, detail=detail, sentence=sentence)
    return out
