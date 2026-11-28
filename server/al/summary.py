"""UTIL-SESSION-SUMMARY: the end-of-session summary card.

A play stretch starts with the first game activity (zone change, area
generation, level-up, death, an outgoing whisper, a finished trade) and
ends by itself, ZERO-CLICK, when either:
- no game activity came for IDLE_S (reason "idle"), checked from the core's
  main loop; or
- Client.txt starts a new game run (`***** LOG FILE OPENING *****`, parsed
  as `log_opened`): the previous game closed (reason "game_closed"). No
  line is known to mark the exit itself, so the next launch stands in.

The card counts the stretch only: time played (gaps longer than IDLE_S are
not counted), the level reached and levels gained with their hourly pace,
maps opened, deaths, and the biggest poe.ninja price movers the dashboard
had at the end (from the cached overviews; no request). It is built from
counters the state already keeps; the core saves the last MAX_SAVED cards
under the runtime dir (ops/runtime, gitignored) and nowhere else.

UTIL-SALES-TALLY (research 0064 G8, decision 0088): the stretch also counts
its sales, a "Trade accepted." line that closed an open trade card (decision
0019 pairing), and adds up the listed prices of those cards per currency.
The tally lives in memory on the Tracker; the card keeps only the count,
the per-currency sums and the unsummed count, never an item, a sender or
whisper text, inside the existing MAX_SAVED bound.
"""

import math
import re

from . import jsonfile, paths
from .runs import clock_text
from .text.events import sales_line

IDLE_S = 1200.0  # 20 minutes with no game activity ends the stretch
MAX_SAVED = 20
MOVERS_SHOWN = 3
MIN_PACE_S = 600.0  # the hourly pace needs 10 minutes of play
SALE_CURRENCIES = 4  # currencies summed per stretch; more go unsummed
# A currency word as the whisper template gives it ("exalted", "Divine
# Orb"): letters, digits, spaces, ' and -, at most 32 characters.
CURRENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9' -]{0,31}$")

REASON_TEXT = {"idle": f"after {int(IDLE_S // 60)} minutes with no game activity",
               "game_closed": "when the game closed"}

# Event types that count as playing (not incoming whispers or AFK lines,
# which arrive while the player is away).
ACTIVITY = frozenset({"scene_changed", "area_generated", "area_entered",
                      "level_up", "death", "whisper_out", "trade_accepted",
                      "trade_cancelled"})


def _num(n):
    if isinstance(n, bool) or not isinstance(n, (int, float)) or n != n:
        return None
    if n in (float("inf"), float("-inf")):
        return None
    return n


def _pct(n):
    r = round(abs(n), 1)
    return str(int(r)) if float(r).is_integer() else str(r)


def mover_parts(movers, n=MOVERS_SHOWN):
    """`<name> up 61%` parts of the biggest movers by size of change."""
    rows = []
    doc = movers if isinstance(movers, dict) else {}
    for side in ("up", "down"):
        lst = doc.get(side)
        if not isinstance(lst, list):
            continue
        for r in lst:
            if not isinstance(r, dict) or not isinstance(r.get("name"), str):
                continue
            ch = _num(r.get("change"))
            if ch is None or round(ch, 1) == 0 or not r["name"].strip():
                continue
            rows.append((r["name"].strip(), ch))
    rows.sort(key=lambda x: -abs(x[1]))
    return [f"{name} {'up' if ch > 0 else 'down'} {_pct(ch)}%" for name, ch in rows[:n]]


def _currency(text):
    if not isinstance(text, str):
        return None
    word = " ".join(text.split())
    return word if CURRENCY_RE.match(word) else None


class Sales:
    """UTIL-SALES-TALLY: one stretch's sales, in memory. Keeps counts and
    per-currency sums only."""

    def __init__(self):
        self.count = 0
        self.unsummed = 0
        self.sums = {}  # currency -> amount, first-seen order

    def add(self, amount, currency):
        """One sale at the closed card's listed price (None when the card
        had none)."""
        self.count += 1
        cur = _currency(currency)
        ok = (isinstance(amount, (int, float)) and not isinstance(amount, bool)
              and math.isfinite(amount) and amount > 0 and cur is not None)
        if ok and (cur in self.sums or len(self.sums) < SALE_CURRENCIES):
            self.sums[cur] = self.sums.get(cur, 0) + amount
        else:
            self.unsummed += 1

    def view(self):
        return {"count": self.count, "unsummed": self.unsummed,
                "sums": [[c, a] for c, a in self.sums.items()]}


def build(start, end, played_s, ended_at, reason, movers=None, sales=None):
    """The card for one stretch. start / end: counters {level, level_ups,
    deaths, maps} at its first and last activity; sales: Sales.view() or
    None."""
    lv_from = start.get("level") if isinstance(start.get("level"), int) else None
    lv_to = end.get("level") if isinstance(end.get("level"), int) else None
    levels = (lv_to - lv_from) if lv_from is not None and lv_to is not None else 0
    levels = max(0, levels)
    maps = max(0, int(end.get("maps") or 0) - int(start.get("maps") or 0))
    deaths = max(0, int(end.get("deaths") or 0) - int(start.get("deaths") or 0))
    played_s = max(0.0, float(played_s))
    t = clock_text(played_s)
    if lv_to is None:
        lines = [f"Played {t}."]
    elif levels:
        lines = [f"Played {t} and reached level {lv_to}."]
    else:
        lines = [f"Played {t} at level {lv_to}."]
    per_hour = None
    if levels:
        text = f"Levels: {lv_from} to {lv_to}"
        if played_s >= MIN_PACE_S:
            per_hour = levels / (played_s / 3600.0)
            text += f", at {per_hour:.1f} an hour"
        lines.append(text + ".")
    lines.append(f"Maps: {maps}.")
    lines.append(f"Deaths: {deaths}.")
    sales = sales if isinstance(sales, dict) else {}
    n_sales = sales.get("count") if isinstance(sales.get("count"), int) else 0
    sums = [(c, a) for c, a in sales.get("sums") or ()]
    unsummed = sales.get("unsummed") if isinstance(sales.get("unsummed"), int) else 0
    line = sales_line(n_sales, sums, unsummed)
    if line:
        lines.append(line)
    parts = mover_parts(movers)
    if parts:
        lines.append("Price movers: " + ", ".join(parts) + ".")
    return {"reason": reason, "reason_text": REASON_TEXT.get(reason, ""),
            "ended_at": float(ended_at), "played_s": played_s,
            "level_from": lv_from, "level_to": lv_to, "levels": levels,
            "per_hour": per_hour, "maps": maps, "deaths": deaths,
            "sales": n_sales, "sales_unsummed": unsummed,
            "sales_sums": [[c, a] for c, a in sums], "lines": lines}


class Tracker:
    """The open play stretch. Not thread-safe: the SessionState lock
    guards it."""

    def __init__(self, idle_s=IDLE_S):
        self.idle_s = idle_s
        self.start = None
        self.last = None
        self.last_at = None
        self.played_s = 0.0
        self.sales = Sales()

    def begin(self, counters):
        """Before an activity event changes the counters: open a stretch
        with them as its baseline when none is open."""
        if self.start is None:
            self.start = dict(counters)
            self.last_at = None
            self.played_s = 0.0
            self.sales = Sales()

    def sale(self, amount, currency):
        """UTIL-SALES-TALLY: a trade accepted that closed a card with this
        listed price, inside the open stretch (begin runs first)."""
        if self.start is not None:
            self.sales.add(amount, currency)

    def touch(self, at, counters):
        """After an activity event: count the time since the last one
        (unless it was an idle gap) and keep the counters."""
        if self.start is None:
            self.begin(counters)
        if self.start.get("level") is None and isinstance(counters.get("level"), int):
            # the first level the stretch learns is where it started
            self.start["level"] = counters["level"]
        if self.last_at is not None:
            gap = at - self.last_at
            if 0 < gap <= self.idle_s:
                self.played_s += gap
        self.last_at = at if self.last_at is None else max(self.last_at, at)
        self.last = dict(counters)

    def due(self, now):
        return (self.start is not None and self.last_at is not None
                and now - self.last_at >= self.idle_s)

    def close(self, reason, movers=None):
        """The card for the open stretch (None when none is open)."""
        if self.start is None or self.last is None:
            self.start = None
            return None
        card = build(self.start, self.last, self.played_s, self.last_at,
                     reason, movers, self.sales.view())
        self.start = None
        self.last = None
        self.last_at = None
        self.played_s = 0.0
        self.sales = Sales()
        return card


def summary_file():
    return paths.runtime_dir() / "session_summaries.json"


def save(path, card, keep=MAX_SAVED):
    """Append `card` to the saved list (newest last, at most `keep`).
    Atomic replace with one .bak (F-014); a half-written file is restored
    from its .bak first, an unreadable one starts a new list."""
    doc = jsonfile.read_json(path, kind=dict, default={}, backup=True)
    rows = doc.get("summaries")
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    rows.append(card)
    rows = rows[-keep:]
    jsonfile.write_json(path, {"summaries": rows}, backup=True)


def load_last(path):
    """The newest saved card, or None."""
    doc = jsonfile.read_json(path, kind=dict, backup=True)
    rows = doc.get("summaries") if isinstance(doc, dict) else None
    if not isinstance(rows, list) or not rows or not isinstance(rows[-1], dict):
        return None
    return rows[-1]
