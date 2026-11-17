"""MATH-VALUE: price-per-stat value math on cached poe.ninja rates.

Pure functions, no network (decision 0013: the rates come from the cached
ninja snapshot, which is empty while web data is off; then there is no
value, never a guess). Prices shown come from poe.ninja rates only
(decision 0013 item 3); the price itself is the item's own Note line
("~price 5 exalted", "~b/o 1/2 divine"), read from the same per-press item
text as the item check (decision 0003). Nothing here calls a trade
endpoint (decision 0017).

- `parse_note_price(note)` -> {"kind", "amount", "currency"} or None.
- `to_primary(amount, currency, snap)` -> the amount in the snapshot's
  primary currency, or None when a rate is missing or not positive.
- `convert(amount, src, dst, snap)` -> a cross-rate conversion, or None.
- `per_unit(score, price)` -> score per one unit of price, or None.
- `value_of(note, score_delta, snap)` -> the value doc for an item check.
"""

import math
import re
from fractions import Fraction

SIG = 6
MAX_AMOUNT = 1e9

# note currency tokens (lower case) -> poe.ninja exchange ids
ALIASES = {
    "exalted": "exalted", "exalt": "exalted", "exalts": "exalted", "ex": "exalted",
    "exa": "exalted", "divine": "divine", "divines": "divine", "div": "divine",
    "chaos": "chaos", "c": "chaos", "alch": "alch", "alchemy": "alch",
    "regal": "regal", "vaal": "vaal", "annul": "annul", "mirror": "mirror",
    "chance": "chance", "transmute": "transmute", "aug": "aug",
}

_NOTE_RE = re.compile(
    r"^~(price|b/o)\s+(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\s+([a-z][a-z-]{0,30})\s*$", re.I)


def _clean(n):
    """Six significant digits (a small exalted price in divines keeps its
    digits, a large ratio drops float noise); whole numbers as int."""
    n = float(f"{float(n):.{SIG}g}")
    return int(n) if n.is_integer() and abs(n) < 1e15 else n


def _amount(text):
    """A positive finite amount from "5", "1.5" or "1/2", else None."""
    try:
        if "/" in text:
            num, den = text.split("/", 1)
            val = Fraction(num) / Fraction(den)
        else:
            val = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None
    val = float(val)
    if not math.isfinite(val) or val <= 0 or val > MAX_AMOUNT:
        return None
    return val


def parse_note_price(note):
    """{"kind": "price" | "b/o", "amount": float, "currency": ninja id} for a
    note price, else None (no note, other text, zero / huge amount)."""
    if not isinstance(note, str):
        return None
    m = _NOTE_RE.match(note.strip())
    if not m:
        return None
    amount = _amount(m.group(2))
    if amount is None:
        return None
    token = m.group(3).lower()
    return {"kind": m.group(1).lower(), "amount": amount,
            "currency": ALIASES.get(token, token)}


def _rate(currency, snap):
    """Value of one unit of `currency` in the primary, or None."""
    if not isinstance(snap, dict) or not isinstance(currency, str):
        return None
    primary = snap.get("primary")
    rates = snap.get("rates") if isinstance(snap.get("rates"), dict) else {}
    entry = rates.get(currency)
    value = entry.get("value") if isinstance(entry, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value) or value <= 0:
        return 1.0 if currency == primary and primary else None
    return float(value)


def to_primary(amount, currency, snap):
    """`amount` of `currency` in the snapshot's primary currency, or None."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) \
            or not math.isfinite(amount) or amount < 0:
        return None
    rate = _rate(currency, snap)
    if rate is None:
        return None
    return amount * rate


def convert(amount, src, dst, snap):
    """`amount` of `src` in units of `dst` through the primary (cross rate)."""
    base = to_primary(amount, src, snap)
    rate = _rate(dst, snap)
    if base is None or rate is None:
        return None
    return base / rate


def per_unit(score, price):
    """Score per one unit of price; None for no / non-positive price."""
    if isinstance(score, bool) or not isinstance(score, (int, float)) \
            or not math.isfinite(score):
        return None
    if isinstance(price, bool) or not isinstance(price, (int, float)) \
            or not math.isfinite(price) or price <= 0:
        return None
    return score / price


def _name(currency, snap):
    rates = snap.get("rates") if isinstance(snap, dict) and isinstance(
        snap.get("rates"), dict) else {}
    entry = rates.get(currency)
    name = entry.get("name") if isinstance(entry, dict) else None
    return name if isinstance(name, str) and name else currency


def value_of(note, score_delta, snap):
    """The value doc for one item check, or None when the item has no note
    price. Doc: price {kind, amount, currency, name}, primary, primary_name,
    price_primary (None without a rate), score_per_primary (None without a
    price or a score delta), stale (the rates' own flag), credit."""
    price = parse_note_price(note)
    if price is None:
        return None
    snap = snap if isinstance(snap, dict) else {}
    primary = snap.get("primary") if isinstance(snap.get("primary"), str) else None
    in_primary = to_primary(price["amount"], price["currency"], snap) if primary else None
    ratio = per_unit(score_delta, in_primary)
    return {"price": dict(price, amount=_clean(price["amount"]),
                          name=_name(price["currency"], snap)),
            "primary": primary,
            "primary_name": _name(primary, snap) if primary else None,
            "price_primary": None if in_primary is None else _clean(in_primary),
            "score_per_primary": None if ratio is None else _clean(ratio),
            "stale": bool(snap.get("stale", True)),
            "credit": snap.get("credit")}
