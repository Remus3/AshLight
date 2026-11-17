"""UTIL-PRICE-WATCH: flag price moves of the items the player checked
(research 0028 section 4, ruling D).

The item-check press already prices the item from the cached poe.ninja
price book (price.py `ninja`). The press records what it already read
(name, base, rarity, corrupted, value, unit, time) for at most MAX_ITEMS
items, in memory and in one bounded file under the runtime dir
(ops/runtime, gitignored). When the price book refreshes (hourly,
decision 0026) the core re-reads each item's price from the SAME cache
(RatesClient.lookup: never a request, None while web data is off) and an
item whose price moved by at least the threshold (setting
"price_watch_pct", default 25) since its press is flagged.

No clipboard or screen read on refresh, no trade call, no URL opened, no
new request of any kind: zero network. While web data is off (decision
0013) nothing is re-read and nothing is flagged. The list is clearable.
"""

from pathlib import Path

from . import jsonfile

FILE_NAME = "price_watch.json"
CONFIG_KEY = "price_watch_pct"
SCHEMA = 1
MAX_ITEMS = 20
MAX_TEXT = 100
MAX_BYTES = 64 * 1024
DEFAULT_PCT = 25
MIN_PCT, MAX_PCT = 5, 500
SHOWN = 10

# Dashboard copy (design 0001 section 9); the page prints these as given.
OFF_TEXT = ("Price watch is paused while web data is off. Turn on web data to "
            "see price moves of the items you checked.")
# UX-B9-CARDS: off with nothing watched still says how the card fills
OFF_EMPTY_TEXT = ("Price watch is paused while web data is off. With web data on, "
                  "items you price with the item check hotkey are watched here by "
                  "themselves.")
EMPTY_TEXT = ("No items watched yet. Items you price with the item check "
              "hotkey are watched here by themselves.")
QUIET_TEXT = "Watching {items}. No price moved by {pct}% or more since you checked."


def pct_setting(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_PCT
    return value if MIN_PCT <= value <= MAX_PCT else DEFAULT_PCT


def _text(value):
    return value[:MAX_TEXT] if isinstance(value, str) and value.strip() else None


def _value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")) or value <= 0:
        return None
    return float(value)


def _clean(row):
    if not isinstance(row, dict):
        return None
    name, unit = _text(row.get("name")), _text(row.get("unit"))
    value, at = _value(row.get("value")), _value(row.get("at"))
    if not name or not unit or value is None or at is None:
        return None
    out = {"name": name, "base": _text(row.get("base")),
           "rarity": _text(row.get("rarity")), "corrupted": row.get("corrupted") is True,
           "value": value, "unit": unit, "at": at,
           "now_value": _value(row.get("now_value")), "now_unit": _text(row.get("now_unit"))}
    return out


def _num(n):
    if n >= 100:
        return str(int(round(n)))
    text = f"{n:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def move_text(row, change):
    word = "up" if change > 0 else "down"
    return (f"{row['name']}: {word} {abs(round(change * 100))}%, from "
            f"{_num(row['value'])} to {_num(row['now_value'])} {row['unit']}")


class PriceWatch:
    """The watched items, newest last. Not thread-safe: the core guards it."""

    def __init__(self, path):
        self.path = Path(path)
        self.items = self._load()

    def _load(self):
        doc = jsonfile.read_json(self.path, max_bytes=MAX_BYTES)
        rows = doc.get("items") if isinstance(doc, dict) else None
        return [r for r in (_clean(x) for x in rows or ()) if r is not None][-MAX_ITEMS:]

    def _save(self):
        jsonfile.write_json(self.path, {"schema": SCHEMA, "items": self.items})

    @staticmethod
    def _same(a, b):
        return (a["name"] == b["name"] and a["base"] == b["base"]
                and a["rarity"] == b["rarity"] and a["corrupted"] == b["corrupted"])

    def record(self, item, ninja, at):
        """One priced press: item {name, base, rarity, corrupted} as the
        press parsed it, ninja the card's cached price (price.ninja_of).
        A press without a price records nothing. True when recorded."""
        if not isinstance(item, dict) or not isinstance(ninja, dict):
            return False
        row = _clean({"name": item.get("name") or ninja.get("name"),
                      "base": item.get("base"), "rarity": item.get("rarity"),
                      "corrupted": item.get("corrupted") is True,
                      "value": ninja.get("value"), "unit": ninja.get("unit"),
                      "at": at})
        if row is None:
            return False
        self.items = [r for r in self.items if not self._same(r, row)]
        self.items.append(row)
        self.items = self.items[-MAX_ITEMS:]
        self._save()
        return True

    def clear(self):
        self.items = []
        self._save()

    def refresh(self, lookup):
        """Re-read every watched item's price from the cache (lookup: the
        core's RatesClient.lookup, cache only). Called on a price book
        refresh while web data is on. True when a price changed."""
        changed = False
        for r in self.items:
            try:
                found = lookup({"name": r["name"], "base": r["base"], "rarity": r["rarity"],
                                "flags": {"corrupted": r["corrupted"]}})
            except Exception:  # noqa: BLE001 - a cache read never breaks the tick
                found = None
            found = found if isinstance(found, dict) else {}
            now_value, now_unit = _value(found.get("value")), _text(found.get("unit"))
            if (now_value, now_unit) != (r["now_value"], r["now_unit"]):
                r["now_value"], r["now_unit"] = now_value, now_unit
                changed = True
        if changed:
            self._save()
        return changed

    def view(self, enabled, pct=DEFAULT_PCT):
        """The snapshot `price_watch` part. Nothing is flagged while web
        data is off."""
        pct = pct_setting(pct)
        n = len(self.items)
        if not enabled:
            return {"on": False, "count": n, "moved": [], "pct": pct,
                    "text": OFF_TEXT if n else OFF_EMPTY_TEXT}
        moved = []
        for r in reversed(self.items):
            if r["now_value"] is None or r["now_unit"] != r["unit"]:
                continue  # gone from the book, or a different unit: no flag
            change = (r["now_value"] - r["value"]) / r["value"]
            if abs(change) * 100 >= pct:
                moved.append({"name": r["name"], "was": r["value"], "now": r["now_value"],
                              "unit": r["unit"], "change_pct": round(change * 100),
                              "at": r["at"], "text": move_text(r, change)})
        items = "1 item" if n == 1 else f"{n} items"
        text = EMPTY_TEXT if not n else ("" if moved else QUIET_TEXT.format(items=items, pct=pct))
        return {"on": True, "count": n, "moved": moved[:SHOWN], "pct": pct, "text": text}
