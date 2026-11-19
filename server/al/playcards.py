"""PLAY-TD-07B: the Play view's context modes, item card and kept checks.

Three more parts of the snapshot's `play` block, composed and capped at the
source like the rest of server/al/playview.py (plan 03 section 3.4):

- context_view(snap) -> play.context: one block per AVAILABLE mode of
  region C (setup, idle, map, town, guide), keyed by mode, or None when no
  mode is available. web/slots.js contextMode picks the one shown (first
  match); error and none are the renderer's own states. A block is
  {"mode", "title", "full", "rows", "facts"}: a title of at most 38
  characters ("full" holds it uncut when a name had to be cut), at most 7
  body rows of at most 52 characters, each {"kind", "text", ...}, and a
  facts row of at most 52. G5: at most 52 composed words a block (names
  are data and are not counted).
- check_view(snap) -> (play.item, play.kept). The item card of the last
  press (None before the first press): the verdict word and glyph, the
  item name (data, never cut), a sentence of 2 rows of at most 36, ONE
  compare slot with exactly 5 rows of at most 36, a price row and at most
  2 links; 60 words. The kept checks (None before BUILD-LIVE has a list):
  the 3 best upgrades among this character's checks against the current
  build, best first, each row at most 42 characters (the item name takes
  the "..."); 24 words.

Sources, all already in the snapshot, no new read: tailer and diag (setup),
session_summary (idle), maps and the last waystone check (map), in_town /
in_hideout and zone_guide / zone_note (town), zone_guide, campaign and
underlevel (guide), eval / price with their text (item; eval_card_text
and price_card_text are not changed here) and upgrades (kept: BUILD-LIVE,
memory only, decision 0045 and Q-26 b). The build's search strings
(decision 0030) are read from build.search_strings when the snapshot
carries them; the Copy itself is the player's click (decision 0014).

Pure: no I/O, no clock read, every field read defensively (FUZZ-3).
"""

import re

from . import playview as pv
from . import runs
from . import zoneguide

# -- caps (plan 03 section 3.4) ------------------------------------------------
CAP_TITLE = 38
CAP_ROW = 52
CONTEXT_ROWS = 7
WORDS_CONTEXT = 52
CAP_SENTENCE = 36
SENTENCE_ROWS = 2
COMPARE_ROWS = 5
CAP_COMPARE = 36
CAP_PRICE = 36
MAX_LINKS = 2
WORDS_ITEM = 60
CAP_KEPT = 42
KEPT_ROWS = 3
WORDS_KEPT = 24
SEARCH_MAX = 250        # decision 0030: the game's search box limit
SAME_PRESS_S = 2.0      # state.SAME_PRESS_S: eval and price of one press
TOWN_GUIDE_ROWS = 4
LAYOUT_ROWS = 2
BONUS_ROWS = 2

MODES = ("setup", "idle", "map", "town", "guide")

# -- words (design 0001 section 9) -----------------------------------------------
SETUP_TITLE = "Set up AshLight"
SETUP_ASK = "Let AshLight read the game's log, read only:"
SETUP_NO_PATH = "Client.txt not found yet. Start the game once."
SETUP_BUTTON = "Allow reading Client.txt"  # the floor's opt-in words, unchanged
SETUP_PROMISE = "Read only. AshLight never touches the game."
SETUP_STEPS = (
    ("build", "Your build", "loaded", "not set, optional"),
    ("prices", "Prices", "on", "off, optional"),
    ("overlay", "Overlay", "on", "off, optional"),
)
SETUP_NOT_SEEN = "not running, optional"  # overlay check neither on nor off
IDLE_TITLE = "Last session"
TOWN_TITLE = "In town"
HIDEOUT_TITLE = "In your hideout"
BETWEEN_TITLE = "Between maps"
ADVICE_SHORT = {"clear": "Under-levelled: clear it fully for experience.",
                "push": "Over-levelled: move on once your goal is done.",
                "fit": "Your level fits: clear what is on your way."}

# verdict word -> kit state of its glyph (plan 03 section 3.4: "[+] Upgrade",
# "[-] Sidegrade", "[-] Downgrade", "[?] Risky", "[-] Not an item")
WORD_KIT = {"Upgrade": "done", "Sidegrade": "idle", "Downgrade": "idle",
            "Risky": "needs-operator", "No risky mods": "done", "Not checked": "idle"}
NO_PRICE = "No price for this check"
NO_SENTENCE = "AshLight could not check this item."  # state EVAL_ERROR_TEXT default
TRADE_LINK = "Trade search"
UPGRADE_LINK = "Upgrade search"
KEPT_WORD = "Upgrade"
KEPT_NO_BUILD = "Load a build to rank your checks."
KEPT_NONE = "None of your checks is an upgrade now."


# playview's readers (FUZZ-3: a wrong type reads as missing); called through
# the module, so either module may be imported first
def _dict(v):
    return pv._dict(v)


def _dicts(v):
    return pv._dicts(v)


def _num(v):
    return pv._num(v)


def _int(v):
    return pv._int(v)


def _name(v):
    return pv._name(v)


# -- small helpers --------------------------------------------------------------

def _text(v):
    return " ".join(v.split()) if isinstance(v, str) else ""


def _named_words(text, names):
    """Composed words of a text: names are data and are not counted."""
    for n in sorted((n for n in names if n), key=len, reverse=True):
        text = text.replace(n, " ")
    return pv.words(text)


def _row(text, kind="text", names=(), **extra):
    """An internal row: the public dict plus its composed word count."""
    r = {"kind": kind, "text": text}
    r.update(extra)
    return r, _named_words(text, names)


def _block(mode, title, rows, facts="", full=None, title_names=(), facts_names=()):
    """A public block from internal rows, under the row, character and
    word caps; rows are dropped from the end while the words run over."""
    title_text = title if len(title) <= CAP_TITLE else pv.clip(title, CAP_TITLE)
    rows = [(dict(r, text=pv.clip(r["text"], CAP_ROW)), w) for r, w in rows][:CONTEXT_ROWS]
    facts = pv.clip(facts, CAP_ROW) if facts else ""
    fixed = _named_words(title_text, title_names) + _named_words(facts, facts_names)
    while rows and fixed + sum(w for _r, w in rows) > WORDS_CONTEXT:
        rows.pop()
    return {"mode": mode, "title": title_text,
            "full": full if full is not None else title,
            "rows": [r for r, _w in rows], "facts": facts}


def _plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _deaths(n):
    return "no deaths" if not n else _plural(n, "death")


def _clip_left(text, cap):
    """A path keeps its end (the file name) when it is cut."""
    return text if len(text) <= cap else pv.ELLIPSIS + text[-(cap - len(pv.ELLIPSIS)):]


def _checks(snap):
    return {c.get("id"): c for c in _dicts(_dict(snap.get("diag")).get("checks"))}


def _search_strings(snap):
    """The build's search strings (decision 0030), only with a build and
    only within the game's 250-character limit."""
    build = _dict(snap.get("build"))
    if build.get("loaded") is not True:
        return []
    out = []
    for s in _dicts(build.get("search_strings")):
        text, label = s.get("text"), _text(s.get("label"))
        if isinstance(text, str) and text and len(text) <= SEARCH_MAX and label:
            out.append(s)
    return out


def _copy_row(s):
    """The search string row: a plain name with Copy (F-124); the string
    itself is copied only on the player's click (decision 0014)."""
    label = _text(s.get("label"))
    return _row(pv.clip(label, CAP_ROW), kind="copy", copy=s["text"],
                id=s.get("id"), full=_text(s.get("why")) or label)


# -- C: setup --------------------------------------------------------------------

def setup_block(snap):
    """F-069: before consent, the 4 steps with state glyphs."""
    tailer = snap.get("tailer")
    if not isinstance(tailer, dict) or tailer.get("consented") is not False:
        return None
    path = _name(tailer.get("path"))
    checks = _checks(snap)
    done = {
        "build": _dict(snap.get("build")).get("loaded") is True,
        "prices": _dict(checks.get("web_data")).get("status") == "pass",
        "overlay": _dict(checks.get("overlay")).get("status") == "pass",
    }
    rows = [_row(SETUP_ASK, kind="step", state="pending", glyph=pv._glyph("pending"),
                 step="log")]
    if path:
        rows.append(_row(_clip_left(path, CAP_ROW), kind="path", names=(path,), full=path))
    else:
        rows.append(_row(SETUP_NO_PATH, kind="path", full=SETUP_NO_PATH))
    rows.append(_row(SETUP_BUTTON, kind="button", action="consent"))
    overlay_off = _dict(checks.get("overlay")).get("status") == "off"
    for key, label, yes, no in SETUP_STEPS:
        kit = "done" if done[key] else "pending"
        if key == "overlay" and not done[key] and not overlay_off:
            no = SETUP_NOT_SEEN
        rows.append(_row(f"{label}: {yes if done[key] else no}", kind="step", state=kit,
                         glyph=pv._glyph(kit), step=key))
    return _block("setup", SETUP_TITLE, rows, SETUP_PROMISE)


# -- C: idle ---------------------------------------------------------------------

def _mover_row(lines):
    for line in lines:
        if isinstance(line, str) and line.startswith("Price movers: "):
            return line.rstrip(".")
    return ""


def idle_block(snap):
    """Decision 0029: the game may be closed; "Last session" from the
    session summary card, else from the live counters."""
    if snap.get("game_idle") is not True:
        return None
    card = _dict(snap.get("session_summary"))
    rows = []
    if card:
        played = _num(card.get("played_s"))
        if played is not None:
            rows.append(_row(f"Played: {runs.clock_text(played)}"))
        lv_from, lv_to = _int(card.get("level_from")), _int(card.get("level_to"))
        if lv_to is not None:
            text = (f"Level: {lv_from} to {lv_to}"
                    if lv_from is not None and lv_from != lv_to else f"Level: {lv_to}")
            rows.append(_row(text))
        rate = _num(card.get("per_hour"))
        if rate is not None:
            rows.append(_row(f"Pace: {rate:.1f} levels an hour"))
        rows.append(_row(f"Maps: {_int(card.get('maps')) or 0}"))
        rows.append(_row(f"Deaths: {_int(card.get('deaths')) or 0}"))
        movers = _mover_row([x for x in card.get("lines") or () if isinstance(x, str)]
                            if isinstance(card.get("lines"), list) else [])
        if movers:
            # item names are data: the row takes the "..." at its cap
            rows.append(_row(pv.clip(movers, CAP_ROW), names=(movers[len("Price movers: "):],),
                             full=movers))
        at = pv.clock(card.get("ended_at"))
        why = _text(card.get("reason_text"))
        facts = (f"Ended {at} {why}" if at and why else f"Ended {at}" if at else "")
    else:
        lvl = _int(snap.get("level"))
        if lvl is not None:
            rows.append(_row(f"Level: {lvl}"))
        rows.append(_row(f"Maps: {_int(_dict(snap.get('maps')).get('count')) or 0}"))
        rows.append(_row(f"Deaths: {_int(snap.get('deaths')) or 0}"))
        at = pv.clock(_dict(snap.get("tailer")).get("last_line_at"))
        facts = f"Last log line at {at}" if at else ""
    if len(facts) > CAP_ROW:
        facts = f"Ended {at}" if at else ""
    return _block("idle", IDLE_TITLE, rows, facts)


# -- C: map ----------------------------------------------------------------------

def _waystone_row(snap):
    ev = _dict(snap.get("eval"))
    if not _dict(ev.get("waystone")):
        return None
    head = _text(_dict(ev.get("text")).get("head"))
    return _row(f"Last waystone: {head}") if head else None


def map_block(snap):
    """F-068: in a map, or in the hideout after a map this game run."""
    maps = _dict(snap.get("maps"))
    cur = _dict(maps.get("current"))
    count = _int(maps.get("count")) or 0
    inside = cur.get("inside") is True
    hideout = snap.get("in_hideout") is True and count > 0
    if not (inside or hideout):
        return None
    rows = []
    name = ""
    if inside:
        name = _name(cur.get("name")) or "Map"
        lvl = _int(cur.get("area_level"))
        full = title = f"{name}, level {lvl}" if lvl is not None else name
        if len(title) > CAP_TITLE:
            title = name
        time_s = _num(cur.get("time_s"))
        rows.append(_row(f"This map: {runs.clock_text(time_s)}, "
                         f"{_deaths(_int(cur.get('deaths')) or 0)}"))
    else:
        full = title = BETWEEN_TITLE
        last = next(iter(_dicts(maps.get("recent"))), None)
        if last:
            lname = _name(last.get("name")) or "Map"
            text = (f"Last map: {lname}, {runs.clock_text(_num(last.get('time_s')))}, "
                    f"{_deaths(_int(last.get('deaths')) or 0)}")
            rows.append(_row(text, names=(lname,), full=text))
    text = f"Maps this session: {count}"
    rate = _num(maps.get("per_hour"))
    if rate is not None:
        text += f", {rate:.1f} an hour"
    rows.append(_row(text))
    avg = _num(maps.get("avg_s"))
    if avg is not None:
        rows.append(_row(f"Average map: {runs.clock_text(avg)}"))
    ws = _waystone_row(snap)
    if ws:
        rows.append(ws)
    if not inside:
        strings = _search_strings(snap)
        pick = next((s for s in strings if s.get("id") == "waystone"),
                    strings[0] if strings else None)
        if pick:
            rows.append(_copy_row(pick))
    facts = _text(maps.get("deaths_text"))
    return _block("map", title, rows, facts, full=full, title_names=(name,))


# -- C: town ---------------------------------------------------------------------

def _guide_rows(text, width=CAP_ROW, rows=2, names=(), kind="text"):
    """A text as at most `rows` rows (whole sentences, else cut with "...")."""
    return [_row(r, kind=kind, names=names) for r in pv.fit_rows(text, width, rows)]


def town_block(snap):
    """F-124: a campaign town or the hideout: the top search string by a
    plain name with Copy (only with a build), then up to 4 guide rows."""
    hideout = snap.get("in_hideout") is True
    town = snap.get("in_town") is True or (
        isinstance(snap.get("area_id"), str) and "_town" in snap["area_id"].lower())
    if not (hideout or town):
        return None
    rows = []
    strings = _search_strings(snap)
    if strings:
        rows.append(_copy_row(strings[0]))
    guide = []
    zg = _dict(snap.get("zone_guide"))
    if zg.get("kind") == "campaign" and not hideout:
        obj = _text(zg.get("objective"))
        if obj:
            guide += _guide_rows(obj)
        nxt = _name(zg.get("next"))
        if nxt:
            guide.append(_row(f"Next: {nxt}.", kind="next", names=(nxt,)))
    if not guide and not hideout:
        note = _text(_dict(snap.get("zone_note")).get("text"))
        if note:
            guide += _guide_rows(note)
    rows += guide[:TOWN_GUIDE_ROWS]
    return _block("town", HIDEOUT_TITLE if hideout else TOWN_TITLE, rows)


# -- C: guide --------------------------------------------------------------------

def _wrap_title(text):
    """(title, rest): the objective's first words within the title cap; the
    rest continues in the body rows."""
    if len(text) <= CAP_TITLE:
        return text, ""
    words = text.split()
    title = ""
    for i, w in enumerate(words):
        cand = (title + " " + w).strip()
        if len(cand) > CAP_TITLE:
            if not title:
                return pv.clip(text, CAP_TITLE), ""
            return title, " ".join(words[i:])
        title = cand
    return title, ""


def _need_rows(text, width=CAP_ROW):
    """How many rows a text needs, wrapped at a word (no cut)."""
    lines = []
    for w in text.split():
        if lines and len(lines[-1]) + 1 + len(w) <= width:
            lines[-1] += " " + w
        else:
            lines.append(w)
    return len(lines)


_NEAR_LEAD = zoneguide.WAYPOINT_NEAR.split("{zone}")[0]


def _next_row(zg):
    nxt = _name(zg.get("next"))
    wp = _text(zg.get("waypoint"))
    if not nxt and not wp:
        return None
    cands = []
    if nxt and wp:
        cands.append(f"Next: {nxt}. {wp}")
        if wp.startswith(_NEAR_LEAD):
            near = wp[len(_NEAR_LEAD):].rstrip(".")
            cands.append(f"Next: {nxt}. Nearest waypoint: {near}.")
    if nxt:
        cands.append(f"Next: {nxt}.")
    if wp:
        cands.append(wp)
    text = pv.first_fit(cands, CAP_ROW)
    return _row(text, kind="next", names=(nxt,), full=cands[0])


def guide_items(zg):
    """The parts of a guide entry that need body rows, uncut, in display
    order: [(part, priority, text)]; a lower priority is kept longer. The
    data test checks every bundled entry needs at most 7 rows."""
    zg = _dict(zg)
    obj = _text(zg.get("objective"))
    _title, rest = _wrap_title(obj)
    items = []
    if rest:
        items.append(("objective", 0, rest))
    for i, o in enumerate(_dicts(zg.get("optional"))):
        t = _text(o.get("text"))
        if t:
            # the guide's bonus lines start with the reward; the row kind
            # "bonus" marks them (no prefix: Clearfell would need 8 rows)
            items.append(("bonus", 2 if i == 0 else 6, t))
    lay = _text(zg.get("layout"))
    if lay:
        items.append(("layout", 4, lay))
    nr = _next_row(zg)
    if nr:
        items.append(("next", 1, nr[0]["text"]))
    return items


def guide_rows_needed(zg):
    """Body rows the entry itself needs at the 52-character row width
    (objective overflow, bonus lines, layout, next zone and waypoint)."""
    return sum(_need_rows(t) for _part, _prio, t in guide_items(zg))


_BOSS_EL = re.compile(r"mostly (\w+) damage")
_BOSS_RES = re.compile(r"has (-?\d+)% ")


def _boss_text(h):
    """The boss hint in one row (ruling H, decision 0039): the element and
    the build's resistance, from the campaign hint's own words."""
    text = _text(h.get("text"))
    el = _BOSS_EL.search(text)
    if not el:
        return pv.first_fit(pv.fit_rows(text, CAP_ROW, 1) or [""], CAP_ROW)
    el = el.group(1)
    res = _BOSS_RES.search(text)
    if res:
        return f"Boss: {el} damage. Your {el} res: {res.group(1)}%."
    return f"Boss: {el} damage. Your {el} res: unknown."


def _advice_facts(snap, zg):
    under = _text(_dict(snap.get("underlevel")).get("text"))
    if under and len(under) <= CAP_ROW:
        return under
    adv = _dict(zg.get("advice"))
    text = _text(adv.get("text"))
    if text and len(text) <= CAP_ROW:
        return text
    return ADVICE_SHORT.get(adv.get("mode"), "")


def guide_block(snap):
    """A campaign zone with a guide entry (decision 0043): the objective is
    the title; then bonus, boss and resist, flask / boots, layout (2), next
    zone and waypoint; the facts row is the level advice. Over 7 rows or
    52 words, the lowest-priority parts leave first."""
    zg = _dict(snap.get("zone_guide"))
    if zg.get("kind") != "campaign" or snap.get("in_hideout") is True:
        return None
    obj = _text(zg.get("objective"))
    title, _rest = _wrap_title(obj) if obj else (_name(zg.get("zone")) or "Zone guide", "")
    parts = []  # (order, priority, [internal rows])
    order = 0
    hints = _dicts(_dict(snap.get("campaign")).get("hints"))
    boss = [h for h in hints if h.get("id") == "boss"]
    gear = [h for h in hints if h.get("id") != "boss"]
    for part, prio, text in guide_items(zg):
        if part == "objective":
            rows = _guide_rows(text, rows=2, kind="objective")
        elif part == "bonus":
            rows = _guide_rows(text, rows=BONUS_ROWS, kind="bonus")
        elif part == "layout":
            rows = _guide_rows(text, rows=LAYOUT_ROWS, kind="layout")
        else:
            rows = [_next_row(zg)]
        slot = {"objective": 0, "bonus": 1, "layout": 4, "next": 5}[part]
        parts.append((slot, order, prio, rows))
        order += 1
    for h in boss:
        parts.append((2, order, 3, [_row(_boss_text(h), kind="hint")]))
        order += 1
    for h in gear:
        parts.append((3, order, 7, _guide_rows(_text(h.get("text")), rows=1, kind="hint")))
        order += 1
    facts = _advice_facts(snap, zg)

    def total(ps):
        return sum(len(p[3]) for p in ps)

    def wsum(ps):
        return sum(w for p in ps for _r, w in p[3])
    fixed = pv.words(title) + pv.words(facts)
    while parts and (total(parts) > CONTEXT_ROWS or fixed + wsum(parts) > WORDS_CONTEXT):
        drop = max(parts, key=lambda p: (p[2], p[1]))
        parts.remove(drop)
    parts.sort(key=lambda p: (p[0], p[1]))
    rows = [r for p in parts for r in p[3]]
    return _block("guide", title, rows, facts, full=obj or title)


# -- C: all available modes -----------------------------------------------------

BUILDERS = (("setup", setup_block), ("idle", idle_block), ("map", map_block),
            ("town", town_block), ("guide", guide_block))


def context_view(snap):
    """play.context: {mode: block} for every available mode, or None."""
    snap = _dict(snap)
    out = {}
    for mode, fn in BUILDERS:
        block = fn(snap)
        if block is not None:
            out[mode] = block
    return out or None


# -- I: the item card -------------------------------------------------------------

def _best(ev):
    comps = _dicts(ev.get("comparisons"))
    slot = ev.get("slot")
    for i, c in enumerate(comps):
        if c.get("slot") == slot:
            return i, c
    return (0, comps[0]) if comps else (None, {})


def _equipped(comp):
    eq = _dict(comp.get("equipped"))
    return _name(eq.get("name")) or _name(eq.get("base"))


def _compare_row(text, value=""):
    text, value = _text(text), _text(value)
    room = CAP_COMPARE - (len(value) + 1 if value else 0)
    return {"text": pv.clip(text, max(4, room)), "value": value}


def _strip_word(sentence, word):
    """The reason first: "Upgrade: 12 points more ..." -> "12 points more ..."."""
    for w in (word, "Downgrade", "Upgrade", "Sidegrade", "Checked"):
        if w and sentence.startswith(w + ": "):
            rest = sentence[len(w) + 2:]
            return rest[:1].upper() + rest[1:]
    return sentence


def _strip_lead(sentence):
    """A waystone sentence without its leading "Tier 15 waystone. "."""
    head, sep, rest = sentence.partition(". ")
    if sep and head.lower().endswith("waystone") and rest:
        return rest
    return sentence


def _price_row(snap, ev):
    price = _dict(snap.get("price"))
    at_e, at_p = _num(ev.get("at")), _num(price.get("at"))
    same = (not ev) or (at_e is not None and at_p is not None
                        and abs(at_p - at_e) < SAME_PRESS_S)
    if not price or not same:
        return {"value": NO_PRICE, "source": ""}, None
    t = _dict(price.get("text"))
    value = _text(t.get("line")) or NO_PRICE
    url = price.get("url")
    link = None
    if price.get("status") == "link" and isinstance(url, str) and url.startswith("https://"):
        link = {"label": TRADE_LINK, "url": url}
    return {"value": pv.clip(value, CAP_PRICE),
            "source": pv.clip(_text(t.get("detail")), CAP_PRICE)}, link


def _item_compare(ev, t):
    """(label, label name, rows) of the ONE compared slot."""
    ws = _dict(ev.get("waystone"))
    if ws:
        rows = []
        rewards = _text(t.get("rewards"))
        if rewards:
            rows += [_compare_row(r) for r in pv.fit_rows(rewards, CAP_COMPARE, 2)]
        for r in _dicts(ws.get("risky")):
            label = _text(r.get("label"))
            if label:
                rows.append(_compare_row(label, "risky"))
        return "Rewards and risky mods", "", rows
    if ev.get("ok") is not True:
        return "", "", []
    i, comp = _best(ev)
    if i is None:
        return "", "", []
    comps = _dicts(ev.get("comparisons"))
    slot = _name(comp.get("slot")) or "its slot"
    name = _equipped(comp)
    label = f"vs empty {slot}" if comp.get("empty") or not name else f"vs {name}"
    others = len(comps) - 1
    if others > 0:
        label += f" (+{_plural(others, 'other slot')})"
    rows = []
    if _dict(ev.get("calc")).get("source") == "pob":
        line = _text(t.get("line"))
        if line.startswith("DPS "):
            rows.append(_compare_row(line))
    tcomps = _dicts(t.get("comparisons"))
    tc = tcomps[i] if i < len(tcomps) else {}
    for s in _dicts(tc.get("stats")):
        rows.append(_compare_row(s.get("text"), s.get("points")))
    if ev.get("unidentified") and not rows:
        rows.append(_compare_row("Mods hidden - identify it first"))
    return label, name if label.startswith("vs " + name) and name else "", rows


def item_view(snap):
    """play.item: the card of the last press, or None before it."""
    ev = _dict(snap.get("eval"))
    price = _dict(snap.get("price"))
    if not ev and not price:
        return None
    t = _dict(ev.get("text"))
    if ev:
        ws = bool(_dict(ev.get("waystone")))
        word = _text(t.get("word")) or "Not checked"
        kind = "waystone" if ws else ("verdict" if ev.get("ok") is True else "error")
        if kind == "error":
            word = _text(t.get("head")) or word
        name = _name(t.get("item")) or "Unnamed item"
        sentence = _text(t.get("sentence"))
        if kind == "verdict":
            sentence = _strip_word(sentence, word)
            eq = _equipped(_best(ev)[1])
            if eq:
                sentence = sentence.replace(f" ({eq})", "")
        elif kind == "waystone":
            sentence = _strip_lead(sentence)
    else:
        # a price without an item check (slots.js has no price kind: the
        # reserved card of a verdict)
        kind, word = "verdict", "Price"
        pt = _dict(price.get("text"))
        name = _name(pt.get("item")) or "Unnamed item"
        sentence = _text(pt.get("sentence"))
    kit = WORD_KIT.get(word, "idle")
    label, label_name, crows = _item_compare(ev, t) if ev else ("", "", [])
    price_row, trade = _price_row(snap, ev)
    links = []
    if trade:
        links.append(trade)
    up = _dict(ev.get("upgrade")).get("url")
    if isinstance(up, str) and up.startswith("https://"):
        links.append({"label": UPGRADE_LINK, "url": up})
    links = links[:MAX_LINKS]
    if not sentence:
        sentence = NO_SENTENCE if kind == "error" else f"{word}."
    sent = pv.fit_rows(sentence, CAP_SENTENCE, SENTENCE_ROWS)
    label = pv.clip(label, CAP_COMPARE) if label else ""
    crows = crows[:COMPARE_ROWS]
    fixed = (pv.words(word) + sum(pv.words(r) for r in sent)
             + _named_words(label, (label_name,))
             + pv.words(price_row["value"]) + pv.words(price_row["source"])
             + sum(pv.words(x["label"]) for x in links))
    while crows and fixed + sum(pv.words(r["text"]) + pv.words(r["value"])
                                for r in crows) > WORDS_ITEM:
        crows.pop()
    while len(crows) < COMPARE_ROWS:
        crows.append({"text": "", "value": ""})
    return {"kind": kind, "state": kit, "glyph": pv._glyph(kit), "word": word,
            "name": name, "sentence": sent, "full": sentence,
            "compare": {"label": label, "rows": crows},
            "price": price_row, "links": links,
            "at": _num(ev.get("at")) if ev else _num(price.get("at"))}


# -- U: kept checks ---------------------------------------------------------------

def _gain(n):
    d = _num(n.get("score_delta"))
    d = 0.0 if d is None else round(float(d), 1)
    if d == 0:
        d = 0.0
    num = str(int(d)) if d.is_integer() else str(d)
    num = num if num.startswith("-") else "+" + num
    if n.get("source") in ("pob", "pob_cached"):
        return num + "%"
    return num + (" point" if num in ("+1", "-1") else " points")


def _kept_row(n):
    glyph = pv._glyph("done")
    item = _name(n.get("name")) or _name(n.get("base")) or "Unnamed item"
    slot = _name(n.get("slot"))
    at = pv.clock(n.get("at"))
    lead = f"{glyph} {KEPT_WORD} {_gain(n)}, "
    tails = []
    if slot and at:
        tails.append(f", {slot}, {at}")
    if slot:
        tails.append(f", {slot}")
    tails.append("")
    # the whole item name first (time, then slot leave), else the name
    # takes the "..." beside the slot
    text = next((lead + item + tail for tail in tails
                 if len(lead + item + tail) <= CAP_KEPT), "")
    if not text:
        tail = f", {slot}" if slot else ""
        room = CAP_KEPT - len(lead) - len(tail)
        text = (lead + pv.clip(item, room) + tail if room >= 8
                else pv.clip(lead + item, CAP_KEPT))
    return {"glyph": glyph, "word": KEPT_WORD, "gain": _gain(n), "item": item,
            "slot": slot, "at": _num(n.get("at")), "text": text,
            "full": f"{KEPT_WORD} {_gain(n)}: {item}" + (f", {slot}" if slot else "")
            + (f", {at}" if at else "")}, _named_words(text, (item, slot))


def kept_view(snap):
    """play.kept: the best 3 upgrades now (decision 0045), or None before
    BUILD-LIVE has a list."""
    up = snap.get("upgrades")
    if not isinstance(up, dict):
        return None
    loaded = up.get("build_loaded") is not False and \
        _dict(snap.get("build")).get("loaded") is True
    items = [n for n in _dicts(up.get("items")) if _num(n.get("score_delta")) is not None]
    order = sorted(range(len(items)),
                   key=lambda i: (-_num(items[i]["score_delta"]),
                                  -(_num(items[i].get("at")) or float("-inf")), i))
    rows = [_kept_row(items[i]) for i in order[:KEPT_ROWS]] if loaded else []
    while rows and sum(w for _r, w in rows) > WORDS_KEPT:
        rows.pop()
    empty = "" if rows else (KEPT_NONE if loaded else KEPT_NO_BUILD)
    return {"rows": [r for r, _w in rows], "empty": empty,
            "checked": _int(up.get("checked")) or 0}


def check_view(snap):
    """(play.item, play.kept)."""
    snap = _dict(snap)
    return item_view(snap), kept_view(snap)
