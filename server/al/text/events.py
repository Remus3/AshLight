"""Event sentences (design 0001 section 9; FS-STATE-TEXT).

Moved byte for byte out of server/al/state.py (RUN-ZONE-RESET, folded
TEST-STATE-TEXT-1); state.py re-exports every name, so state.<name> is
the same object. summarize() stays the only place event wording is
made. Pure functions and constants; stdlib only.
"""

from .common import _amount, _dict, _text


FALLBACK_TEXT = "Something happened in the log"
UNKNOWN_CHARACTER = "Unknown character"
UNKNOWN_PLAYER = "Unknown player"
UNKNOWN_ZONE = "an unknown zone"

# tailer_reset reasons, as plain sentences (design 0001 section 9).
RESET_TEXT = {
    "missing": "Client.txt is missing - waiting for the game",
    "replaced": "Client.txt was replaced - reading the new file",
    "truncated": "Client.txt was cleared - reading from the start",
    "continued": "Client.txt is back - reading on from where it stopped",
}
# RUN-TAIL-HEAL-CORE: after a break the reader says where it reads on
# (the event's "read": start, kept or end; logfile.Tailer._after_break),
# so the sentence is true for each: only "start" reads the file's first
# line again; "end" skips the old lines (the resume scan counts them).
RESET_READ_TEXT = {
    ("replaced", "kept"): "Client.txt was replaced - reading on from where it stopped",
    ("replaced", "end"): "Client.txt was replaced - reading new lines only",
    ("truncated", "kept"): "Client.txt got shorter - reading on from where it stopped",
    ("truncated", "end"): "Client.txt got shorter - reading new lines only",
}


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
    row = _dict(row)
    sender = _text(row.get("from"), UNKNOWN_PLAYER)
    return {"text": _trade_text(sender, row), "where": _trade_where(row)}


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
        reason = ev.get("reason")
        return RESET_READ_TEXT.get((reason, ev.get("read")),
                                   RESET_TEXT.get(reason, "Client.txt was reset"))
    if t == "tailer_unreadable":
        return "Client.txt can't be read right now - trying again"
    if t == "tailer_readable":
        return "Client.txt can be read again"
    if t == "tailer_restarted":
        return "AshLight restarted its log reader"
    return FALLBACK_TEXT
