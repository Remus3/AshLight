"""PLAY-TD-07A: the Play view, composed and capped at the source.

view(snap) turns one state snapshot into the `play` block of that same
snapshot: the rows of the strip (G), the feed (T), the notices (N) and the
build line (B), each composed under the character budgets of plan 03
section 3.4, so no Play state can add height (G5 word caps per region:
strip 20, feed 50, notices 22, build 16). The renderers print these rows;
they never build Play wording themselves.

Pure: no I/O, no clock read (the snapshot's `now` is the time), no state.
Every field is read defensively (a wrong-typed field reads as missing), so
a malformed snapshot can never break the state push. Names are data and are
never capped: the zone, the character, the class, buyers and items take
the ellipsis in the renderer, with the full text in `title`. A composed row
that does not fit drops its optional parts first (a fixed ladder per row),
then is cut at a word with "...".

Reading and kit state words come from server/al/statuswords.py (F-131);
the build words are the four of design 0001 section 6 (TD-15), the same
table as web/slots.js buildLine. play.context (region C's available modes),
play.item (the item card) and play.kept (the kept checks) come from
server/al/playcards.py (PLAY-TD-07B); play.map_ok stays False until
PLAY-MAP-MODE-ON.
"""

import re
import time

from . import acts
from . import playcards
from . import statuswords
from .text import buildsource as source_words

# -- caps (plan 03 section 3.4, character budgets [D]) -----------------------
CAP_EVENT_SENTENCE = 38
CAP_NOTICE_WORD = 12   # the glyph, one space and the state word
CAP_NOTICE_TITLE = 20
CAP_NOTICE_ACTION = 12
CAP_NOTICE_ROW = 52
NOTICE_ROWS = 2
CAP_BUILD_ROW = 36     # row two of B
# The Zone sub line (20 px / 400) in the narrowest zone cell (compact at
# 1024 px: 452 px) at 0.5em + 0.147em a character: 34 characters.
CAP_STRIP_SUB = 34
# G5 words per region (strip, feed, notices, build). Names are not counted:
# they are data. The strip's labels (4) and numbers (zone timer, level,
# deaths, session timer: 4) and one word of zone name leave 11 composed
# words for the four sub lines; one notice leaves 2 words for "+N more".
WORDS_STRIP = 20
WORDS_FEED = 50
WORDS_NOTICE = 22
WORDS_BUILD = 16
STRIP_SUB_WORDS = 11
NOTICE_ENTRY_WORDS = WORDS_NOTICE - 2

NEW_S = 60  # a feed row says "new" this long after it arrived
ELLIPSIS = "..."

# -- notice kinds (plan 03 section 3.5, web/slots.js noticePick) -------------
KIND_BROKEN = 1     # a part is broken but reading works
KIND_BUILD_Q = 2    # a build question (no snapshot source yet)
KIND_LANGUAGE = 3   # the game-language notice
KIND_SETUP = 4      # "Setup: N steps left"
KIND_DATA = 5       # data notes (game data snapshot, GGG docs flag)
KIND_TIP = 6        # new-character tip (10 min)
KIND_KEY = 7        # key reminder (no snapshot source yet)

# diag check ids that name a part (kind 1 when the check fails) and data
# notes (kind 5); the reading checks (log, consent, reading, last_line)
# are region C's error mode, never a notice.
PART_CHECKS = ("web_data", "prices", "calc", "overlay", "supervisor", "hotkey", "reload")
DATA_CHECKS = ("snapshot", "dev_docs")

ACTION_CHECKS = "Open Checks"
ACTION_SETTINGS = "Settings"

TIP_TITLES = {"start": "New character", "town": "Item check",
              "campaign_death": "Campaign deaths", "first_map": "First map"}
TIP_TITLE = "Tip"

LANGUAGE_TITLE = "Not English"
LANGUAGE_ROW = "AshLight reads only the English game text."

SETUP_STEPS = (("build", "your build"), ("prices", "prices"), ("overlay", "the overlay"))

# -- build line (design 0001 section 6, TD-15; web/slots.js BUILD_STATES) ----
BUILD_WORDS = {
    "fits": ("done", "Build fits"),
    "old": ("needs-operator", "Old build"),
    "wrong_class": ("needs-operator", "Wrong class"),
    "none": ("pending", "No build"),
}
BUILD_FIX = "Copy a PoB code, press the item key."
BUILD_CALC_ON = "Checks use Path of Building numbers."
BUILD_CALC_OFF = "Checks use your stat weights."
# ACTIVE-BUILD-PICK (decision 0096): the build in use and the one switch
# (words in server/al/text/buildsource.py, copy sheet buildsource.md)
BUILD_KINDLER_NAME = source_words.KINDLER_NAME
BUILD_SRC_KINDLER = source_words.SRC_KINDLER
BUILD_SRC_PASTED = source_words.SRC_PASTED
BUILD_USE_KINDLER = source_words.USE_KINDLER
BUILD_USE_PASTED = source_words.USE_PASTED
BUILD_PASTE_TOO = source_words.PASTE_TOO

EVENT_TAGS = {"death": "Death", "level": "Level", "zone": "Zone"}


# -- small readers (FUZZ-3: a wrong type reads as missing) -------------------

def _dict(v):
    return v if isinstance(v, dict) else {}


def _dicts(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, (list, tuple)) else []


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def _int(v):
    n = _num(v)
    if n is None or n != int(n):
        return None
    return int(n)


def _name(v):
    """A name as text, or "" (names are data: never capped here)."""
    return v.strip() if isinstance(v, str) else ""


def words(text):
    """The words of a text as the fit harness counts them (whitespace
    tokens with a letter or digit)."""
    if not isinstance(text, str):
        return 0
    return sum(1 for w in text.split() if re.search(r"[A-Za-z0-9]", w))


def clip(text, cap):
    """text, or its longest whole-word prefix that fits cap with "..."."""
    text = text if isinstance(text, str) else ""
    if len(text) <= cap:
        return text
    room = max(0, cap - len(ELLIPSIS))
    cut = text[:room + 1].rsplit(" ", 1)[0] if " " in text[:room + 1] else text[:room]
    cut = cut[:room].rstrip(" ,;:-")
    return cut + ELLIPSIS


def first_fit(candidates, cap, max_words=None):
    """The first candidate within cap (and max_words), else the last one
    clipped to cap."""
    cands = [c for c in candidates if isinstance(c, str)]
    for c in cands:
        if len(c) <= cap and (max_words is None or words(c) <= max_words):
            return c
    return clip(cands[-1], cap) if cands else ""


def wrap(text, width, rows):
    """Greedy word wrap into at most `rows` lines of `width`; None when it
    does not fit (or a word is wider than a line)."""
    lines = []
    for w in text.split():
        if len(w) > width:
            return None
        if lines and len(lines[-1]) + 1 + len(w) <= width:
            lines[-1] += " " + w
        else:
            lines.append(w)
            if len(lines) > rows:
                return None
    return lines


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def fit_rows(text, width=CAP_NOTICE_ROW, rows=NOTICE_ROWS, max_words=None):
    """Body rows composed at the source: whole sentences while they fit
    `rows` lines of `width` (and max_words), else the first sentence cut at
    a word with "..." on its last line."""
    text = " ".join(text.split()) if isinstance(text, str) else ""
    if not text:
        return []
    parts = _SENTENCE.split(text)
    for k in range(len(parts), 0, -1):
        cand = " ".join(parts[:k])
        lines = wrap(cand, width, rows)
        if lines is not None and (max_words is None or words(cand) <= max_words):
            return lines
    lines = []
    taken = 0
    budget = max_words if max_words is not None else 10 ** 6
    for w in parts[0].split():
        w = w[:width - len(ELLIPSIS)]
        taken += words(w)
        if taken > budget:
            break
        if lines and len(lines[-1]) + 1 + len(w) <= width:
            lines[-1] += " " + w
        elif len(lines) < rows:
            lines.append(w)
        else:
            break
    if not lines:
        return []
    last = lines[-1].rstrip(" .,;:-")
    while len(last) + len(ELLIPSIS) > width and " " in last:
        last = last.rsplit(" ", 1)[0].rstrip(" .,;:-")
    lines[-1] = last[:width - len(ELLIPSIS)] + ELLIPSIS
    return lines


def clock(at):
    """Local wall time "14:02" of an epoch, or "" (display only)."""
    at = _num(at)
    if at is None:
        return ""
    try:
        return time.strftime("%H:%M", time.localtime(at))
    except (OverflowError, OSError, ValueError):
        return ""


def _plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _glyph(kit):
    """The bracket glyph of a kit state, from the one status table (F-131);
    needs-operator ([?]) is the one kit state the table does not use."""
    for row in statuswords.table()["states"].values():
        if row.get("kit") == kit:
            return row["glyph"]
    return "[?]" if kit == "needs-operator" else "[ ]"


# -- G strip -------------------------------------------------------------------

def _zone_tags(snap):
    """The zone sub line's tags in reading order, each with its keep rank
    (lower is kept longer): frozen, AFK, DND, hideout."""
    tags = []
    if snap.get("in_hideout") is True:
        tags.append((3, "hideout"))
    if snap.get("game_idle") is True:
        at = clock(_dict(snap.get("tailer")).get("last_line_at"))
        tags.append((0, f"frozen {at}" if at else "frozen"))
    if snap.get("afk") is True:
        tags.append((1, "AFK"))
    if snap.get("dnd") is True:
        tags.append((2, "DND"))
    return tags


def _zone_place(snap):
    act = acts.act_of(snap.get("area_id"))
    if act:
        return act["label"]
    cur = _dict(_dict(snap.get("maps")).get("current"))
    if cur.get("inside") is True:
        return "Map"
    return ""


def _sub_ladder(snap):
    """The Zone sub line, longest first: act or "Map", area level, tags;
    the act goes first, then the area level, then the tags one by one
    (hideout, DND, AFK, frozen), down to an empty line."""
    place = _zone_place(snap)
    lvl = _int(snap.get("area_level"))
    level = f"area level {lvl}" if lvl is not None else ""
    tags = _zone_tags(snap)

    def join(*parts):
        return " - ".join(p for p in parts if p)
    out = []
    ranks = sorted(rank for rank, _w in tags)
    for keep in range(len(tags), -1, -1):
        kept = ", ".join(w for rank, w in tags if rank in ranks[:keep])
        out += [join(place, level, kept), join(level, kept), join(place, kept), kept]
    out += [level, place, ""]
    seen = []
    for c in out:
        if c not in seen:
            seen.append(c)
    return seen


def _deaths_here(snap):
    """Deaths in this zone stay (this map's while in a map)."""
    cur = _dict(_dict(snap.get("maps")).get("current"))
    if cur.get("inside") is True and _int(cur.get("deaths")) is not None:
        return f"{_int(cur['deaths'])} this map"
    zone = _name(snap.get("zone"))
    if not zone:
        return ""
    since = _num(snap.get("zone_entered_at"))
    recent = _dicts(_dict(snap.get("death_recap")).get("recent"))
    here = [r for r in recent if r.get("zone") == zone
            and (since is None or (_num(r.get("at")) or 0) >= since)]
    n = len(here)
    # the recap keeps the 5 newest: all 5 here means maybe more
    more = "+" if recent and n == len(recent) and n >= 5 else ""
    return f"{n}{more} this zone"


def _session_sub(snap):
    maps = _dict(snap.get("maps"))
    count = _int(maps.get("count")) or 0
    if count > 0:
        text = _plural(count, "map")
        rate = _num(maps.get("per_hour"))
        if rate is not None and rate >= 1:
            text += f", {int(round(rate))}/h"
        return text
    if _int(snap.get("level")) is None:
        return ""
    n = _int(snap.get("level_ups")) or 0
    return _plural(n, "level-up")


def strip_view(snap):
    word = _dict(snap.get("underlevel")).get("word")
    under = word if isinstance(word, str) and word else ""
    level_sub = ""
    if _int(snap.get("level")) is not None:
        # "N lv under" (the overlay's word) while under-levelled, else the
        # class (a name: not counted against the word cap)
        level_sub = under or _name(snap.get("class"))
    deaths_sub = _deaths_here(snap)
    session_sub = _session_sub(snap)
    fixed = sum(words(t) for t in (deaths_sub, session_sub, under))
    sub = first_fit(_sub_ladder(snap), CAP_STRIP_SUB, max(0, STRIP_SUB_WORDS - fixed))
    return {
        "zone": _name(snap.get("zone")) or None,
        "sub": sub,
        "level_sub": level_sub,
        "deaths_sub": deaths_sub,
        "session_sub": session_sub,
        # design 0001 section 6: values look stale while the log is idle
        "fresh": snap.get("game_idle") is not True,
    }


# -- T feed --------------------------------------------------------------------

def _right(at, now, parts):
    age = None if at is None or now is None else now - at
    head = ["new"] if age is not None and 0 <= age < NEW_S else []
    return ", ".join(head + [p for p in parts if p])


def _trade_row(row, now):
    at = _num(row.get("at"))
    lead = row.get("text") if isinstance(row.get("text"), str) else ""
    where = row.get("where") if isinstance(row.get("where"), str) else ""
    age = None if at is None or now is None else max(0.0, now - at)
    age_text = f"{int(age // 60)}m" if age is not None and age >= NEW_S else ""
    return {"id": row.get("id"), "lead": lead, "right": _right(at, now, [where, age_text]),
            "title": lead + (f" ({where})" if where else "")}


def _event(kind, text, title, at, now):
    return {"kind": kind, "tag": EVENT_TAGS[kind], "text": text,
            "right": _right(at, now, [clock(at)]), "title": title, "at": at}


def _latest(rows, types):
    for r in reversed(rows):
        if r.get("type") in types:
            return r
    return None


_LEVEL = re.compile(r"^(.*) reached level (\d+)$")


def _death_event(snap, now):
    recent = _dicts(_dict(snap.get("death_recap")).get("recent"))
    if not recent:
        return None
    d = recent[0]
    who = _name(snap.get("character"))
    zone = _name(d.get("zone"))
    lvl = _int(d.get("level"))
    at_level = f" at level {lvl}" if lvl is not None else ""
    title = (f"{who} died" if who else "Died") + (f" in {zone}" if zone else "") + at_level
    # subject first: over the cap the zone goes before the character name
    cands = []
    if who and zone:
        cands.append(f"{who} died in {zone}")
    if who:
        cands += [f"{who} died{at_level}", f"{who} died"]
    if zone:
        cands.append(f"Died in {zone}")
    cands += [f"Died{at_level}", "Died"]
    return _event("death", first_fit(cands, CAP_EVENT_SENTENCE), title, _num(d.get("at")), now)


def _level_event(rows, now):
    r = _latest(rows, ("level_up",))
    if r is None:
        return None
    text = r.get("text") if isinstance(r.get("text"), str) else ""
    m = _LEVEL.match(text)
    if m:
        who, n = m.group(1), m.group(2)
        cands = [f"{who} reached level {n}", f"Reached level {n}"]
    else:
        cands = [text, "Reached a new level"] if text else ["Reached a new level"]
    return _event("level", first_fit(cands, CAP_EVENT_SENTENCE), text or cands[-1],
                  _num(r.get("at")), now)


def _zone_event(snap, now):
    zone = _name(snap.get("zone"))
    if not zone:
        return None
    full = f"Entered {zone}" + (" (hideout)" if snap.get("in_hideout") is True else "")
    # the zone name is the row's subject: it takes the ellipsis, not a cut
    text = full if len(full) <= CAP_EVENT_SENTENCE else f"Entered {zone}"
    return _event("zone", text, full, _num(snap.get("zone_entered_at")), now)


def feed_view(snap):
    now = _num(snap.get("now"))
    trades = _dicts(snap.get("trade_requests"))
    order = sorted(range(len(trades)),
                   key=lambda i: (_num(trades[i].get("at")) or float("-inf"), i), reverse=True)
    rows = _dicts(snap.get("recent_events"))
    return {
        "trades": [_trade_row(trades[i], now) for i in order],
        "events": {"death": _death_event(snap, now), "level": _level_event(rows, now),
                   "zone": _zone_event(snap, now)},
    }


# -- N notices -------------------------------------------------------------------

def _notice(kind, kit, word, title, text, action, rows=None):
    glyph = _glyph(kit)
    head = f"{glyph} {word}"
    if len(head) > CAP_NOTICE_WORD:
        word = word[:max(0, CAP_NOTICE_WORD - len(glyph) - 1)]
    title = clip(title, CAP_NOTICE_TITLE)
    action = action if len(action) <= CAP_NOTICE_ACTION else ""
    budget = NOTICE_ENTRY_WORDS - words(word) - words(title) - words(action)
    if rows is None:
        rows = fit_rows(text, CAP_NOTICE_ROW, NOTICE_ROWS, max(1, budget))
    rows = [clip(r, CAP_NOTICE_ROW) for r in rows][:NOTICE_ROWS]
    while len(rows) > 1 and sum(words(r) for r in rows) > budget:
        rows = rows[:-1]
    return {"kind": kind, "state": kit, "glyph": glyph, "word": word, "title": title,
            "rows": rows, "action": action}


def _checks(snap):
    return {c.get("id"): c for c in _dicts(_dict(snap.get("diag")).get("checks"))}


def _check_text(c):
    parts = [c.get(k) for k in ("detail", "fix") if isinstance(c.get(k), str) and c.get(k)]
    return " ".join(parts)


def _setup_left(snap, checks):
    left = []
    build = _dict(snap.get("build"))
    if build.get("loaded") is not True:
        left.append("build")
    if _dict(checks.get("web_data")).get("status") == "off":
        left.append("prices")
    if _dict(checks.get("overlay")).get("status") == "off":
        left.append("overlay")
    return left


def _join_and(items):
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def notices_view(snap):
    """Every queued notice, in pick order (kind, then arrival); region N
    shows the first and counts the others (web/slots.js noticePick).

    Order: 1 broken part (only while reading works), 2 build question
    (no source yet), 3 game language, 4 Setup, 5 data notes, 6 new-
    character tip, 7 key reminder (no source yet). One exception: while a
    new-character tip is on show (its 10-minute window, the snapshot
    `hint`), Setup is not queued, so the tip outranks it for that window
    and Setup comes back by itself after it (design review PV-1: Setup
    may never retire for a player who keeps web data off and pastes no
    build). TD-14 renders this list in this order."""
    out = []
    hint = _dict(snap.get("hint"))
    tip = isinstance(hint.get("text"), str) and bool(hint.get("text"))
    tailer = _dict(snap.get("tailer"))
    reading = statuswords.reading_state(tailer) in ("reading", "idle")
    checks = _checks(snap)
    if reading:
        for cid in PART_CHECKS:
            c = _dict(checks.get(cid))
            if c.get("status") == "fail":
                out.append(_notice(KIND_BROKEN, "failed", "Broken",
                                   _name(c.get("label")) or "A part", _check_text(c),
                                   ACTION_CHECKS))
    lang = _dict(snap.get("lang"))
    if lang.get("verdict") == "non_english":
        works = lang.get("works") if isinstance(lang.get("works"), str) else ""
        rows = [LANGUAGE_ROW]
        if works:
            rows.append(clip(works[:1].upper() + works[1:] + " still work.", CAP_NOTICE_ROW))
        out.append(_notice(KIND_LANGUAGE, "needs-operator", "Language", LANGUAGE_TITLE,
                           "", ACTION_CHECKS, rows=rows))
    if tailer.get("consented") is True and not tip:
        # web data off counts as a step left: the snapshot cannot tell a
        # player's choice from the default
        left = _setup_left(snap, checks)
        if left:
            names = dict(SETUP_STEPS)
            n = len(left)
            rows = [clip("Still to set: " + _join_and([names[k] for k in left]) + ".",
                         CAP_NOTICE_ROW),
                    ("It is optional; Settings has the control." if n == 1
                     else "All optional; Settings has the controls.")]
            out.append(_notice(KIND_SETUP, "pending", "Setup",
                               _plural(n, "step") + " left", "", ACTION_SETTINGS, rows=rows))
    for cid in DATA_CHECKS:
        c = _dict(checks.get(cid))
        if c.get("status") in ("fail", "note"):
            out.append(_notice(KIND_DATA, "idle", "Note",
                               _name(c.get("label")) or "Data", _check_text(c), ACTION_CHECKS))
    if tip:
        # Note and Tip are neutral: the kit idle row, no tone (PV-3)
        title = TIP_TITLES.get(hint.get("id"), TIP_TITLE)
        out.append(_notice(KIND_TIP, "idle", "Tip", title, hint["text"], ""))
    out.sort(key=lambda e: e["kind"])  # stable: arrival order within a kind
    return out


# -- B build line ------------------------------------------------------------

def build_view(snap):
    build = _dict(snap.get("build"))
    alert = _dict(snap.get("build_alert"))
    kind = alert.get("kind")
    if build.get("loaded") is not True or kind == "missing":
        state = "none"
    elif kind == "class":
        state = "wrong_class"
    elif kind == "level":
        state = "old"
    else:
        state = "fits"
    kit, word = BUILD_WORDS[state]
    src = _dict(snap.get("build_source"))
    kindler = src.get("use") == "kindler" and state != "none"
    offer = _dict(src.get("offer"))
    row1 = ""
    if state != "none":
        name = _name(build.get("ascendancy")) or _name(build.get("class_name")) or "Build"
        if kindler:
            name = BUILD_KINDLER_NAME + (_name(src.get("label")) or BUILD_SRC_KINDLER)
        lvl = _int(build.get("level"))
        row1 = f"{name}, level {lvl}" if lvl is not None else name
    # ACTIVE-BUILD-PICK (decision 0096): one switch between the pasted
    # build and a Kindler plan, hidden when there is nothing to switch to
    switch = None
    if kindler and src.get("pasted") is True:
        switch = {"label": BUILD_USE_PASTED, "use": "pasted", "id": None}
    elif not kindler and isinstance(offer.get("id"), str):
        switch = {"label": BUILD_USE_KINDLER, "use": "kindler", "id": offer["id"]}
    if state == "fits" and kindler:
        row2 = BUILD_SRC_KINDLER
    elif state == "fits" and switch is not None:
        row2 = BUILD_SRC_PASTED
    elif state == "fits":
        calc = _dict(snap.get("sources")).get("calc_on") is True
        row2 = BUILD_CALC_ON if calc else BUILD_CALC_OFF
    elif state == "none" and switch is not None:
        row2 = BUILD_PASTE_TOO
    else:
        row2 = BUILD_FIX
    return {"state": state, "kit": kit, "glyph": _glyph(kit), "word": word,
            "row1": row1, "row2": clip(row2, CAP_BUILD_ROW),
            "can_paste": state == "none" and switch is None, "switch": switch}


# -- the block -----------------------------------------------------------------

def view(snap):
    """The snapshot's `play` block."""
    snap = _dict(snap)
    item, kept = playcards.check_view(snap)
    return {
        "strip": strip_view(snap),
        "feed": feed_view(snap),
        "notices": notices_view(snap),
        "build": build_view(snap),
        "map_ok": False,
        # PLAY-TD-07B: region C's available modes, the item card, kept checks
        "context": playcards.context_view(snap),
        "item": item,
        "kept": kept,
    }
