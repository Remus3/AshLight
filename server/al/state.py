"""Derived session state, built only from bus events.

Times are wall-clock receipt times (time.time()); the line's own timestamp is
local time without a zone, so it is kept for display only. Every buffer is
bounded.
"""

import collections
import threading
import time

from . import acts as acts_mod
from . import pace as pace_mod
from . import runs as runs_mod

RECENT_EVENTS = 30
RECENT_WHISPERS = 10
TRADE_REQUESTS = 5  # open trade whisper cards (HUD-WHISPER); oldest drops
# DS-TRADE-EXPIRE (design 0001 N5): a card clears by itself this long after
# it arrived; the dashboard states the rule and Dismiss stays.
TRADE_EXPIRE_S = 600
# TC-EVAL-UI: the overlay shows the item check card this long after the
# hotkey press, then the card leaves by itself (design 0001 N5); the
# dashboard keeps the last result.
EVAL_CARD_S = 20
# PRICE-1-UI (decision 0016): the price check result rides the same card
# slot for this long after the press; an eval and a price stamped within
# SAME_PRESS_S of each other came from one press and share one card.
PRICE_CARD_S = 20
SAME_PRESS_S = 2.0
# "link" (decision 0017) is the only success status the core produces now;
# searching / waiting / done / off are kept for the 0016 contract's readers
PRICE_STATUSES = ("link", "searching", "waiting", "done", "off", "error")
PRICE_LISTINGS = 10
TRADE_FIELDS = ("kind", "item", "price_amount", "price_currency", "want_amount",
                "league", "stash_tab", "left", "top")

# Event types shown in the dashboard's recent list. UX-COPY: not
# session_connect - the game logs one before every zone change, so
# "Connected to a game server" doubled every "Entered <zone>" row and
# pushed deaths and whispers out of the 30-row list sooner.
LISTED = {"scene_changed", "area_entered", "level_up", "death", "whisper_in",
          "whisper_out", "afk_changed", "dnd_changed", "player_joined_area",
          "player_left_area", "trade_accepted", "tailer_started", "tailer_reset"}


FALLBACK_TEXT = "Something happened in the log"
UNKNOWN_CHARACTER = "Unknown character"
UNKNOWN_PLAYER = "Unknown player"
UNKNOWN_ZONE = "an unknown zone"

# tailer_reset reasons, as plain sentences (design 0001 section 9).
RESET_TEXT = {
    "missing": "Client.txt is missing - waiting for the game",
    "replaced": "Client.txt was replaced - reading the new file",
    "truncated": "Client.txt was cleared - reading from the start",
}


def _text(value, default):
    """A field as display text; missing or empty reads as the default."""
    if value is None:
        return default
    value = str(value)
    return value if value.strip() else default


def _amount(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _trade_text(sender, tr):
    """<from> wants <item> - <price> (design 0001 section 9)."""
    item = _text(tr.get("item"), "an item")
    if tr.get("kind") == "exchange":
        if tr.get("want_amount") is not None:
            item = f"{_amount(tr['want_amount'])} {item}"
        price = "no price set"
        if tr.get("price_amount") is not None:
            price = " ".join(p for p in ("for", _amount(tr["price_amount"]),
                                         _text(tr.get("price_currency"), "")) if p)
    elif tr.get("price_amount") is not None:
        price = " ".join(p for p in (_amount(tr["price_amount"]),
                                     _text(tr.get("price_currency"), "")) if p)
    else:
        price = "no price set"
    return f"{sender} wants {item} - {price}"


def _trade_where(tr):
    """Stash position as the overlay writes it: "tab Sale (3,7)", "tab
    Sale" without a position, "" without a tab."""
    tab = tr.get("stash_tab")
    if tab is None or not str(tab).strip():
        return ""
    where = f"tab {tab}"
    if tr.get("left") is not None and tr.get("top") is not None:
        where += f" ({tr['left']},{tr['top']})"
    return where


def trade_card_text(row):
    """UI-REVIEW-2: the sentence and stash position for one open trade card
    row, so the dashboard prints the section 9 template and never builds
    trade wording itself."""
    sender = _text(row.get("from"), UNKNOWN_PLAYER)
    return {"text": _trade_text(sender, row), "where": _trade_where(row)}


# -- TC-EVAL-UI: item check text (design 0001 section 9). The dashboard and
# the overlay print these; neither builds verdict wording itself.
VERDICT_WORD = {"upgrade": "Upgrade", "sidegrade": "Sidegrade", "downgrade": "Downgrade"}
EVAL_ERROR_TEXT = {
    # error: (overlay head, overlay line, dashboard sentence)
    "no build loaded": ("No build loaded", "Paste a build on the dashboard",
                        "No build loaded yet. Paste a Path of Building code under Build, "
                        "then press the hotkey again."),
    "not an item": ("Not an item", "Copy an item in game first",
                    "The clipboard did not hold an item. Hover an item in game, press "
                    "Ctrl+C, then press the hotkey."),
    "no gear slot for this item class": ("Can't compare this", "Only gear is compared",
                                         "Only gear is compared, and this item has no "
                                         "gear slot."),
}


def _num_text(n):
    """A number as short display text: at most 1 decimal, no trailing .0."""
    try:
        n = round(float(n), 1)
    except (TypeError, ValueError):
        return "0"
    if n == 0:
        n = 0.0  # no "-0"
    return str(int(n)) if n.is_integer() else str(n)


def _signed(n):
    t = _num_text(n)
    return t if t.startswith("-") else "+" + t


def _signed_points(n):
    """"+1 point", "-1 point", "+2.5 points" (rule 7: correct plurals)."""
    t = _signed(n)
    return f"{t} point" + ("" if t in ("+1", "-1") else "s")


def _points(n):
    try:
        t = _num_text(abs(float(n or 0)))
    except (TypeError, ValueError):
        t = "0"
    return f"{t} point" + ("" if t == "1" else "s")


def stat_delta_text(key, delta):
    """One stat change in the item's own words: "+30 to maximum Life",
    "-10% to Lightning Resistance", "+12% increased Attack Speed". A flag
    mod (no number) reads "Gains: <mod>" / "Loses: <mod>"."""
    key = _text(key, "an unknown stat")
    try:
        d = float(delta or 0)
    except (TypeError, ValueError):
        d = 0.0
    if "#" not in key:
        return ("Gains: " if d >= 0 else "Loses: ") + key
    if key.startswith("Adds # to # "):
        return f"{_signed(d)} average {key[len('Adds # to # '):]}"
    if key.startswith("+#"):
        return _signed(d) + key[2:].replace("#", _num_text(abs(d)))
    return ("-" if d < 0 else "+") + key.replace("#", _num_text(abs(d)), 1)


def _equipped_name(comp):
    eq = comp.get("equipped") or {}
    return _text(eq.get("name") or eq.get("base"), "an unnamed item")


def _compare_sentence(comp):
    verdict = VERDICT_WORD.get(comp.get("verdict"), "Checked")
    slot = _text(comp.get("slot"), "that slot")
    delta = comp.get("score_delta") or 0
    if comp.get("empty"):
        return f"{verdict}: your build has nothing in {slot} ({_signed_points(delta)})."
    name = _equipped_name(comp)
    if comp.get("verdict") == "upgrade":
        return f"{verdict}: {_points(delta)} more than your {slot} ({name})."
    if comp.get("verdict") == "downgrade":
        return f"{verdict}: {_points(delta)} less than your {slot} ({name})."
    return f"{verdict}: about the same as your {slot} ({name}), {_signed_points(delta)}."


def _stat_rows(comp):
    rows = []
    for s in comp.get("stats") or []:
        rows.append({"text": stat_delta_text(s.get("key"), s.get("delta")),
                     "points": _signed_points(s.get("score_delta"))
                     if s.get("weighted") else "not counted"})
    return rows


CALC_NOTICE_TEXT = {
    # TC-DELTA (decision 0024): why the card shows stat-weight points, not
    # Path of Building DPS / EHP
    "off": ("Scored with your stat weights. To see DPS and EHP, turn on the "
            "optional Path of Building calc in AshLight's settings file."),
    "failed": ("Scored with your stat weights. DPS and EHP are not shown because "
               "Path of Building could not be reached. Try the check again."),
}


# MATH-WEIGHTS: the calc is off or failed, but Path of Building measured
# stat weights for this same build earlier, so those scored the item
CALC_CACHED_TEXT = {
    "off": ("Scored with the stat weights Path of Building measured for this "
            "build earlier. DPS and EHP are not shown because the Path of "
            "Building calc is off."),
    "failed": ("Scored with the stat weights Path of Building measured for this "
               "build earlier. DPS and EHP are not shown because Path of Building "
               "could not be reached. Try the check again."),
}


def _pct_text(change):
    p = (change or {}).get("pct")
    return "unknown" if p is None else _signed(p) + "%"


def _calc_text(card, best):
    """(dashboard sentence, overlay line or None) for the calc source."""
    calc = card.get("calc") or {}
    if calc.get("source") == "pob" and isinstance(best.get("dps"), dict) \
            and isinstance(best.get("ehp"), dict):
        dps, ehp = best["dps"], best["ehp"]
        slot = _text(best.get("slot"), "its slot")
        line = f"DPS {_pct_text(dps)}, EHP {_pct_text(ehp)}"
        return (f"Path of Building: DPS {_pct_text(dps)} (from {_num_text(dps.get('old'))} "
                f"to {_num_text(dps.get('new'))}), EHP {_pct_text(ehp)} (from "
                f"{_num_text(ehp.get('old'))} to {_num_text(ehp.get('new'))}), with this "
                f"item in {slot}.", line)
    if calc.get("source") == "pob_cached":
        return CALC_CACHED_TEXT.get(calc.get("notice"), CALC_CACHED_TEXT["off"]), None
    return CALC_NOTICE_TEXT.get(calc.get("notice"), ""), None


def eval_card_text(card):
    """The words for one item check (TC-EVAL-UI): `head`, `item` and `line`
    for the 3-line overlay card, `sentence` for the dashboard, and per
    compared slot a sentence and its stat rows. Missing values read
    honestly; every template has an exact-output test
    (tests/test_eval_text.py)."""
    card = card or {}
    item = card.get("item") or {}
    name = _text(item.get("name") or item.get("base"), "Unnamed item")
    if card.get("unidentified"):
        name += " (unidentified)"
    out = {"head": "", "item": name, "line": "", "sentence": "", "comparisons": [],
           "calc": ""}
    if not card.get("ok"):
        head, line, sentence = EVAL_ERROR_TEXT.get(
            card.get("error"), ("Can't check this item", "See the dashboard",
                                "AshLight could not check this item."))
        out.update(head=head, line=line, sentence=sentence)
        return out
    comps = card.get("comparisons") or []
    best = next((c for c in comps if c.get("slot") == card.get("slot")),
                comps[0] if comps else {})
    verdict = VERDICT_WORD.get(card.get("verdict"), "Checked")
    slot = _text(card.get("slot"), "its slot")
    delta = _signed(card.get("score_delta") or 0)
    out["head"] = (f"{verdict} {delta} - {slot} empty" if best.get("empty")
                   else f"{verdict} {delta} vs {slot}")
    counted = [stat_delta_text(s.get("key"), s.get("delta"))
               for s in best.get("stats") or [] if s.get("weighted")]
    if card.get("unidentified"):
        out["line"] = "Mods hidden - identify it first"
    else:
        out["line"] = counted[0] if counted else "No counted stat changes"
    out["calc"], calc_line = _calc_text(card, best)
    if calc_line and not card.get("unidentified"):
        out["line"] = calc_line
    out["sentence"] = _compare_sentence(best) if best else f"{verdict}."
    out["comparisons"] = [{"slot": c.get("slot"), "sentence": _compare_sentence(c),
                           "stats": _stat_rows(c)} for c in comps]
    return out


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
    "off": ("Web data is off", "Switch it on in the dashboard",
            "Price checks need web data, which is off. Turn it on under Prices and web "
            "data on this page."),
    "contact not set": ("Contact not set", "Add it in config/local.json",
                        "Price checks need a contact for the trade site, such as an email "
                        "or a name. Add it as \"contact\" in config/local.json, then press "
                        "the hotkey again."),
    "not an item": ("Not an item", "Copy an item in game first",
                    "The clipboard did not hold an item. Hover an item in game, press "
                    "Ctrl+C, then press the hotkey."),
    "no base type": ("Can't price this item", "Try a different item",
                     "AshLight can't make a trade search for this item. Try a different "
                     "one."),
    "no league": ("League unknown", "Try again in a minute",
                  "AshLight doesn't know which league to search yet. Try again in a "
                  "minute."),
    "error": ("Price check failed", "Press the hotkey again",
              "AshLight couldn't make a trade search for this item. Press the hotkey "
              "again."),
    "none": ("No listings found", "Nobody sells this now",
             "Nobody lists this item in {league} right now, so AshLight can't price it."),
}


def _price_amount(value):
    """A listed amount: digits, at most 2 decimals, no trailing zeros."""
    try:
        n = round(float(value), 2)
    except (TypeError, ValueError):
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


def price_card_text(card):
    """The words for one price check (PRICE-1-UI): `head`, `line` and
    `detail` for the overlay card, `sentence` and `rows` (one per listing)
    for the dashboard. Missing values read honestly; every template has an
    exact-output test (tests/test_price_text.py)."""
    card = card if isinstance(card, dict) else {}
    item = card.get("item") or {}
    name = _text(item.get("name") or item.get("base"), "Unnamed item")
    listings = [r for r in (card.get("listings") or []) if isinstance(r, dict)]
    rows = [_listing_text(r) for r in listings[:PRICE_LISTINGS]]
    out = {"head": f"Price: {name}", "item": name, "line": "", "detail": "",
           "sentence": "", "rows": rows}
    status = card.get("status")
    league = _text(card.get("league"), "this league")
    if status == "waiting":
        try:
            secs = max(1, int(-(-float(card.get("wait_s") or 0) // 1)))
        except (TypeError, ValueError):
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
        return out
    if status == "searching":
        key = status
    elif status == "off":
        key = "contact not set" if card.get("error") == "contact not set" else "off"
    else:
        key = card.get("error") if card.get("error") in PRICE_TEXT else "error"
        if key in ("link", "searching", "off", "none", "contact not set"):
            key = "error"
    line, detail, sentence = PRICE_TEXT[key]
    out.update(line=line, detail=detail, sentence=sentence)
    return out


def _fresh(part, life_s, now):
    return (isinstance(part, dict) and isinstance(part.get("at"), (int, float))
            and now < part["at"] + life_s)


def price_until(price):
    """When the price card leaves: 20 s from the press, and never sooner
    than 20 s after its last update, so a result that waited on the trade
    site's limit still shows for the full time (design 0001 N5)."""
    at = price["at"]
    upd = price.get("updated_at")
    last = upd if isinstance(upd, (int, float)) and upd > at else at
    wait = price.get("wait_s") if price.get("status") == "waiting" else 0
    if not isinstance(wait, (int, float)) or isinstance(wait, bool) or wait < 0:
        wait = 0
    # a long wait keeps the card until the result can arrive (review N4)
    return last + min(float(wait), 600.0) + PRICE_CARD_S


def overlay_card(ev, price, now):
    """The one overlay card (design 0001 section 10, decision 0016 fork 2):
    {kind, head, line2, line3, verdict, expires_at} or None.
    - eval and price both fresh and from one press: a merged card (eval
      head, price line, eval top stat); a price error or "off" leaves the
      eval card unchanged; a "no build loaded" eval gives the price card;
    - from different presses: the newest one;
    - only one fresh: that one."""
    ev_ok = _fresh(ev, EVAL_CARD_S, now)
    pr_ok = (isinstance(price, dict) and isinstance(price.get("at"), (int, float))
             and now < price_until(price))
    if not ev_ok and not pr_ok:
        return None

    def eval_part():
        t = eval_card_text(ev)
        return {"kind": "eval", "head": t["head"], "line2": t["item"], "line3": t["line"],
                "verdict": str(ev.get("verdict") or "") if ev.get("ok") else "note",
                "expires_at": ev["at"] + EVAL_CARD_S}

    def price_part():
        t = price_card_text(price)
        return {"kind": "price", "head": t["head"], "line2": t["line"],
                "line3": t["detail"], "verdict": "price",
                "expires_at": price_until(price)}

    if ev_ok and pr_ok:
        if abs(price["at"] - ev["at"]) >= SAME_PRESS_S:
            return price_part() if price["at"] > ev["at"] else eval_part()
        if not ev.get("ok") and ev.get("error") == "no build loaded":
            return price_part()
        if price.get("status") in ("off", "error"):
            return eval_part()
        card = eval_part()
        card.update(kind="merged", line2=price_card_text(price)["line"],
                    expires_at=max(card["expires_at"], price_until(price)))
        return card
    return eval_part() if ev_ok else price_part()


def summarize(ev):
    """One natural sentence for an event (design 0001 section 9). This is
    the only place event wording is made; every template has an exact-output
    test in tests/test_summarize.py. Missing fields read honestly, never
    "None", and internal ids never show."""
    t = ev.get("type")
    if t in ("scene_changed", "area_entered"):
        zone = _text(ev.get("scene") if t == "scene_changed" else ev.get("name"),
                     UNKNOWN_ZONE)
        tag = " (hideout)" if t == "scene_changed" and ev.get("is_hideout") else ""
        return f"Entered {zone}{tag}"
    if t == "area_generated":
        return f"Area level {_text(ev.get('area_level'), 'unknown')}"
    if t == "level_up":
        who = _text(ev.get("character"), UNKNOWN_CHARACTER)
        if ev.get("level") is None:
            return f"{who} reached a new level (level unknown)"
        return f"{who} reached level {ev['level']}"
    if t == "death":
        who = _text(ev.get("character"), UNKNOWN_CHARACTER)
        return f"{who} died" + (" (self-inflicted)" if ev.get("suicide") else "")
    if t == "whisper_in":
        sender = _text(ev.get("from"), UNKNOWN_PLAYER)
        tr = ev.get("trade")
        if isinstance(tr, dict):
            return _trade_text(sender, tr)
        body = _text(ev.get("text"), "")
        return f'{sender}: "{body}"' if body else f"{sender} sent an empty whisper"
    if t == "whisper_out":
        to = _text(ev.get("to"), "unknown player")
        body = _text(ev.get("text"), "")
        return f'To {to}: "{body}"' if body else f"Sent an empty whisper to {to}"
    if t == "afk_changed":
        return "You're AFK" if ev.get("on") else "You're back"
    if t == "dnd_changed":
        return "Do not disturb on" if ev.get("on") else "Do not disturb off"
    if t == "player_joined_area":
        return f"{_text(ev.get('character'), UNKNOWN_CHARACTER)} joined the area"
    if t == "player_left_area":
        return f"{_text(ev.get('character'), UNKNOWN_CHARACTER)} left the area"
    if t == "trade_accepted":
        return "Trade accepted"
    if t == "trade_cancelled":
        return "Trade cancelled"
    if t == "session_connect":
        return "Connected to a game server"
    if t == "tailer_started":
        return "Reading Client.txt"
    if t == "tailer_reset":
        return RESET_TEXT.get(ev.get("reason"), "Client.txt was reset")
    return FALLBACK_TEXT


class SessionState:
    def __init__(self, character=None, clock=time.time):
        self._lock = threading.Lock()
        self._clock = clock
        self.version = 0
        self.session_started_at = clock()
        # "" (the shipped config default) means "learn it from the log".
        self.character = character or None
        self.character_fixed = bool(character)
        self.char_class = None
        self.level = None
        self.zone = None
        self.area_id = None
        self.area_level = None
        self.zone_entered_at = None
        self.in_hideout = False
        self.deaths = 0
        self.level_ups = 0
        self.afk = False
        self.dnd = False
        self.events_seen = 0
        self.recent_whispers = collections.deque(maxlen=RECENT_WHISPERS)
        self.recent_events = collections.deque(maxlen=RECENT_EVENTS)
        self.trade_requests = collections.deque(maxlen=TRADE_REQUESTS)
        self.overlay_layout = None
        self._trade_ids = 0
        # TC-EVAL-UI / TC-VIEW (server/al/theorycraft/live.py).
        self.eval = None
        self._eval_ids = 0
        # PRICE-1-UI: the last price check (decision 0016 contract).
        self.price = None
        self._price_ids = 0
        self.build_info = None
        # HUD-ACT: per-act splits; zone level table from the game-data cache.
        self.acts = acts_mod.ActSplits()
        self.zone_table = {}
        # UTIL-MAPS / UTIL-DEATHS: map runs and the death recap (runs.py).
        self.maps = runs_mod.MapRuns()
        self.death_log = runs_mod.DeathLog()
        # UTIL-PACE: levelling pace from the player's level-ups (pace.py).
        self.pace = pace_mod.Pace()
        self.tailer = {"consented": False, "reading": False, "path": None,
                       "last_reset": None}

    # -- updates
    def set_tailer(self, **fields):
        with self._lock:
            changed = any(self.tailer.get(k) != v for k, v in fields.items())
            self.tailer.update(fields)
            if changed:
                self.version += 1
            return changed

    def set_overlay_layout(self, layout):
        with self._lock:
            if layout != self.overlay_layout:
                self.overlay_layout = dict(layout)
                self.version += 1

    def now(self):
        """The state clock (server time, s); PRICE-1-WIRE stamps one press
        with it so the item check and the price check share `at`."""
        return self._clock()

    def set_eval(self, card, keep_time=False, at=None):
        """TC-EVAL-UI: publish the last item check (a live.compact() card).
        keep_time keeps the previous card's time (a re-score after a
        weights or build change), so the overlay does not show it again.
        `at`: the press time when the caller already took it."""
        with self._lock:
            if at is None:
                at = self._clock()
                if keep_time and self.eval is not None:
                    at = self.eval["at"]
            self._eval_ids += 1
            self.eval = dict(card, id=self._eval_ids, at=at)
            self.version += 1

    def set_price(self, card, at=None, keep_time=False):
        """PRICE-1-UI (decision 0016): publish the last price check. `card`
        follows the PRICE-1 result contract (status, wait_s, item, league,
        count, listings, error). `at` is the hotkey press time (the same
        press stamps the eval too); keep_time keeps the previous card's time
        for a status update of the same check (searching -> done)."""
        card = dict(card) if isinstance(card, dict) else {}
        card["listings"] = [dict(r) for r in (card.get("listings") or [])
                            if isinstance(r, dict)][:PRICE_LISTINGS]
        with self._lock:
            if at is None:
                at = self._clock()
                if keep_time and self.price is not None:
                    at = self.price["at"]
            self._price_ids += 1
            self.price = dict(card, id=self._price_ids, at=float(at),
                              updated_at=float(self._clock()))
            self.version += 1

    def set_build_info(self, info):
        """TC-VIEW: the loaded build's summary (live.build_info())."""
        with self._lock:
            if info != self.build_info:
                self.build_info = dict(info) if info else None
                self.version += 1

    def set_zone_table(self, table):
        """HUD-ACT: the act / zone level table (acts.load_table())."""
        with self._lock:
            table = table if isinstance(table, dict) else {}
            if table != self.zone_table:
                self.zone_table = table
                self.version += 1

    def dismiss_trade(self, trade_id=None):
        """Drop one open trade card by id, or all of them (trade_id None).
        Returns how many were dismissed. Dashboard only: nothing goes to the
        game."""
        with self._lock:
            before = len(self.trade_requests)
            if trade_id is None:
                self.trade_requests.clear()
            else:
                kept = [r for r in self.trade_requests if r["id"] != trade_id]
                self.trade_requests.clear()
                self.trade_requests.extend(kept)
            n = before - len(self.trade_requests)
            if n:
                self.version += 1
            return n

    def _expire_trades(self, now):
        """Drop trade cards older than TRADE_EXPIRE_S. Caller holds the
        lock. Bumps the version when one goes, so the change is pushed."""
        kept = [r for r in self.trade_requests if now - r["at"] < TRADE_EXPIRE_S]
        if len(kept) != len(self.trade_requests):
            self.trade_requests.clear()
            self.trade_requests.extend(kept)
            self.version += 1

    def _close_trade(self, name=None):
        """OVL-TRADE-CANCEL (decision 0019): a finished trade ("Trade
        accepted." / "Trade cancelled.") closes one open card: the one from
        `name` when a line names the counterparty, else the oldest. Caller
        holds the lock. Returns True when a card went."""
        if not self.trade_requests:
            return False
        rows = list(self.trade_requests)
        drop = next((r for r in rows if name and r.get("from") == name), rows[0])
        self.trade_requests.clear()
        self.trade_requests.extend(r for r in rows if r is not drop)
        return True

    def _trade_row(self, ev, now):
        self._trade_ids += 1
        row = {"id": self._trade_ids, "at": now, "from": ev.get("from")}
        trade = ev.get("trade") or {}
        for k in TRADE_FIELDS:
            if k in trade:
                row[k] = trade[k]
        return row

    def _is_me(self, name):
        return self.character is None or name == self.character

    def apply(self, ev):
        """Fold one event in. Returns True when the snapshot changed."""
        t = ev.get("type")
        now = ev.get("recv_ts") or self._clock()
        with self._lock:
            self.events_seen += 1
            changed = False
            listed = t in LISTED
            if t == "scene_changed":
                # Null and transient scenes (LIVE-1) keep the zone and its
                # timer and are not listed; only a real zone change is.
                listed = False
                if (not ev.get("is_null") and not ev.get("is_transient")
                        and ev.get("scene") != self.zone):
                    self.zone = ev.get("scene")
                    self.in_hideout = bool(ev.get("is_hideout"))
                    self.zone_entered_at = now
                    self.maps.on_scene(self.zone, now, self.in_hideout)
                    listed = True
                    changed = True
            elif t == "area_generated":
                self.area_id = ev.get("area_id")
                self.area_level = ev.get("area_level")
                self.acts.fold(self.area_id, now, self.level)
                self.maps.on_generated(self.area_id, now, self.area_level)
                changed = True
            elif t == "area_entered":
                if ev.get("name") != self.zone:
                    self.zone = ev.get("name")
                    self.in_hideout = "hideout" in (self.zone or "").lower()
                    self.zone_entered_at = now
                    self.maps.on_scene(self.zone, now, self.in_hideout)
                    changed = True
            elif t == "level_up":
                # The first level-up names the character unless one was
                # configured; other players' level-ups are listed, not counted.
                if self.character is None:
                    self.character = ev.get("character")
                if ev.get("character") == self.character:
                    self.char_class = ev.get("class")
                    self.level = ev.get("level")
                    self.level_ups += 1
                    self.pace.on_level(self.level, now)
                    changed = True
            elif t == "death":
                if self._is_me(ev.get("character")):
                    self.deaths += 1
                    self.death_log.add(
                        at=now, zone=self.zone, area_level=self.area_level,
                        level=self.level,
                        zone_s=(max(0.0, now - self.zone_entered_at)
                                if self.zone_entered_at else None))
                    self.maps.on_death(now)
                    changed = True
            elif t in ("whisper_in", "whisper_out"):
                self.recent_whispers.append(self._row(ev, now))
                if t == "whisper_in" and ev.get("trade"):
                    self._expire_trades(now)
                    self.trade_requests.append(self._trade_row(ev, now))
                changed = True
            elif t in ("trade_accepted", "trade_cancelled"):
                self._expire_trades(now)
                if self._close_trade(ev.get("name")):
                    changed = True
            elif t == "afk_changed":
                self.afk = bool(ev.get("on"))
                changed = True
            elif t == "dnd_changed":
                self.dnd = bool(ev.get("on"))
                changed = True
            elif t == "tailer_started":
                self.tailer["reading"] = True
                self.tailer["path"] = ev.get("path")
                changed = True
            elif t == "tailer_reset":
                self.tailer["last_reset"] = ev.get("reason")
                if ev.get("reason") == "missing":
                    self.tailer["reading"] = False
                changed = True
            if listed:
                self.recent_events.append(self._row(ev, now))
                changed = True
            if changed:
                self.version += 1
            return changed

    _RESTORE = {"zone": "zone", "in_hideout": "in_hideout", "area_id": "area_id",
                "area_level": "area_level", "zone_entered_at": "zone_entered_at",
                "class": "char_class", "level": "level", "deaths": "deaths",
                "level_ups": "level_ups", "afk": "afk", "dnd": "dnd"}

    def restore(self, fields):
        """LIVE-RESUME: set state fields recovered from the end of Client.txt
        (server/al/resume.py). Nothing is listed. A configured character is
        kept; another character's level, class and counts are ignored.
        Act splits are run-wide and are rebuilt for any character."""
        with self._lock:
            name = fields.get("character")
            other = bool(name) and self.character_fixed and name != self.character
            if name and not self.character_fixed:
                self.character = name
            for key, attr in self._RESTORE.items():
                if other and key in ("class", "level", "deaths", "level_ups"):
                    continue
                if key in fields:
                    setattr(self, attr, fields[key])
            # HUD-ACT-RESUME: rebuild the act splits from the run's area
            # generations (decision 0023); none keeps the current splits.
            rebuilt = acts_mod.ActSplits()
            for a in fields.get("act_areas") or ():
                rebuilt.fold(a.get("area_id"), a.get("at"), a.get("level"))
            if rebuilt.splits:
                self.acts = rebuilt
            self.version += 1
            return True

    @staticmethod
    def _row(ev, now):
        return {"seq": ev.get("seq"), "type": ev.get("type"), "at": now,
                "text": summarize(ev), "trade": bool(ev.get("trade")),
                "whisper": ev.get("type") in ("whisper_in", "whisper_out")}

    # -- read
    def snapshot(self):
        with self._lock:
            now = self._clock()
            self._expire_trades(now)
            return {
                "version": self.version,
                "now": now,
                "session_started_at": self.session_started_at,
                "session_s": max(0.0, now - self.session_started_at),
                "character": self.character,
                "class": self.char_class,
                "level": self.level,
                "zone": self.zone,
                "area_id": self.area_id,
                "area_level": self.area_level,
                "zone_entered_at": self.zone_entered_at,
                "zone_s": (max(0.0, now - self.zone_entered_at)
                           if self.zone_entered_at else None),
                "in_hideout": self.in_hideout,
                "deaths": self.deaths,
                "level_ups": self.level_ups,
                "afk": self.afk,
                "dnd": self.dnd,
                "events_seen": self.events_seen,
                "recent_whispers": list(self.recent_whispers),
                "recent_events": list(self.recent_events),
                "trade_requests": [dict(r, **trade_card_text(r))
                                   for r in self.trade_requests],
                "overlay_layout": dict(self.overlay_layout) if self.overlay_layout else None,
                "tailer": dict(self.tailer),
                "eval": (dict(self.eval, text=eval_card_text(self.eval),
                              expires_at=self.eval["at"] + EVAL_CARD_S)
                         if self.eval else None),
                "price": (dict(self.price, text=price_card_text(self.price),
                               expires_at=price_until(self.price))
                          if self.price else None),
                # The one overlay card chosen at this moment (decision 0016).
                "card": overlay_card(self.eval, self.price, now),
                "build": dict(self.build_info) if self.build_info else None,
                "acts": acts_mod.view(self.acts, self.zone_table, self.area_id,
                                      self.zone, now),
                "maps": self.maps.view(now),
                "death_recap": self.death_log.view(),
                "pace": self.pace.view(now, self.session_started_at),
            }
