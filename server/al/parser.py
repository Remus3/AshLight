"""Client.txt line parser -> event dicts (schema: docs/research/0002-client-log.md).

Only the line text is read. Anti-spoofing rule from the research: game events
(level-up, death, AFK, joins) are trusted ONLY from system lines (body starts
with ": "); player chat carries a channel prefix and can never fake them.

Patterns the research marked UNVERIFIED for PoE2 carry an "UNVERIFIED" comment;
ROADMAP row LIVE-1 confirms or corrects them against a real log.
"""

import re

# Prefix: date time counter hex [LEVEL Client pid] body
PREFIX = re.compile(
    r"^(\d{4})/(\d{2})/(\d{2}) (\d{2}:\d{2}:\d{2}) (\d+) ([0-9a-fA-F]+) "
    r"\[(\w+) Client (\d+)\] ?(.*)$")

# [SCENE] Set Source [<name>] - confirmed in PoE2 logs.
# "Load Source" is UNVERIFIED (search snippet only).
SCENE = re.compile(r"^\[SCENE\] (?:Set|Load) Source \[(.*)\]\s*$")
# Generating level <N> area "<id>" with seed <N> - from EE2 client strings (MIT).
AREA_GEN = re.compile(r'^Generating level (\d+) area "(.*)" with seed (\d+)\s*$')
# Connecting to instance server at <host>:<port> - UNVERIFIED (search snippet).
INSTANCE = re.compile(r"^Connecting to instance server at ([^\s:]+):(\d+)\s*$")

# System-line bodies (after the leading ": ").
# You have entered <Zone>. - PoE1-confirmed, UNVERIFIED for PoE2.
ENTERED = re.compile(r"^You have entered (.+?)\.?\s*$")
# <Name> (<Class>) is now level <N> - EE2 client strings (MIT).
LEVEL_UP = re.compile(r"^(.+) \((.+)\) is now level (\d+)\s*$")
# <Name> has been slain. / has committed suicide. - UNVERIFIED for PoE2.
DEATH = re.compile(r"^(.+?) has (been slain|committed suicide)\.?\s*$")
# AFK mode is now ON. <autoreply> - PoE2 sample seen; OFF form inferred.
AFK = re.compile(r"^AFK mode is now (ON|OFF)\.?\s*(.*)$")
# DND mode is now ON/OFF - wording UNVERIFIED.
DND = re.compile(r"^DND mode is now (ON|OFF)\.?\s*(.*)$")
# <Name> has joined / has left the area. - UNVERIFIED for PoE2.
JOINED = re.compile(r"^(.+?) has joined the area\.?\s*$")
LEFT = re.compile(r"^(.+?) has left the area\.?\s*$")
# Trade accepted. - PoE2 sample seen.
TRADE_ACCEPTED = re.compile(r"^Trade accepted\.?\s*$")
# Trade cancelled. - seen in a live PoE2 log (LIVE-1, 2026-11-16).
TRADE_CANCELLED = re.compile(r"^Trade cancelled\.?\s*$")

# Whispers - EE2 client strings (MIT).
WHISPER_IN = re.compile(r"^@From (?:<(.+?)> )?(.+?): (.*)$")
WHISPER_OUT = re.compile(r"^@To (?:<(.+?)> )?(.+?): (.*)$")
# Chat channels: # global, $ trade, % party, & guild.
CHAT = re.compile(r"^([#$%&])(?:<(.+?)> )?(.+?): (.*)$")
CHANNELS = {"#": "global", "$": "trade", "%": "party", "&": "guild"}

# Trade whisper templates - exact PoE2 wording UNVERIFIED (research 0002 4).
_STASH = r'\(stash tab "(.*)"; position: left (\d+), top (\d+)\)'
TRADE_PRICED = re.compile(
    r"^Hi, I would like to buy your (.+) listed for ([\d.]+) (.+?) in (.+?) "
    + _STASH + r"\s*(.*)$")
TRADE_UNPRICED = re.compile(
    r"^Hi, I would like to buy your (.+) in (.+?) " + _STASH + r"\s*(.*)$")
TRADE_EXCHANGE = re.compile(
    r"^Hi, I'd like to buy your ([\d.]+) (.+?) for my ([\d.]+) (.+?) in (.+?)\.\s*(.*)$")

# FUZZ-1 (TEST-FUZZ): the whisper / chat / level-up patterns backtrack
# quadratically and the trade templates cubically on crafted text (a 10 KB
# whisper took 4 s on the tailer thread). No real Client.txt line AshLight
# reads is near these sizes (chat messages are short), so longer lines are
# ignored and longer whisper bodies are never matched as trade templates.
MAX_LINE_CHARS = 8192
MAX_TRADE_TEXT = 1024

HIDEOUT_WORD = "hideout"  # substring match on the scene name - UNVERIFIED

# Scenes that are not zones (LIVE-1, live PoE2 log 2026-11-16): "(unknown)"
# is the login / character select / full-screen panel scene, and "Act <N>"
# shows for a few seconds (world map) before the same zone returns. Both are
# reported as transient so the current zone and its timer are kept.
# "scene" is None for "(unknown)" (no name) and keeps "Act <N>" (a real act
# label); consumers decide on is_transient, never on the scene text.
UNKNOWN_SCENE = "(unknown)"
ACT_SCENE = re.compile(r"^Act \d+$")


def _num(text):
    try:
        f = float(text)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def parse_trade(text):
    """Trade fields from a whisper body, or None when it is not a buy template."""
    if len(text) > MAX_TRADE_TEXT:
        return None
    m = TRADE_PRICED.match(text)
    if m:
        return {"kind": "item", "item": m.group(1), "price_amount": _num(m.group(2)),
                "price_currency": m.group(3), "league": m.group(4),
                "stash_tab": m.group(5), "left": int(m.group(6)),
                "top": int(m.group(7)), "note": m.group(8) or ""}
    m = TRADE_UNPRICED.match(text)
    if m:
        return {"kind": "item", "item": m.group(1), "price_amount": None,
                "price_currency": None, "league": m.group(2),
                "stash_tab": m.group(3), "left": int(m.group(4)),
                "top": int(m.group(5)), "note": m.group(6) or ""}
    m = TRADE_EXCHANGE.match(text)
    if m:
        return {"kind": "exchange", "item": m.group(2), "want_amount": _num(m.group(1)),
                "price_amount": _num(m.group(3)), "price_currency": m.group(4),
                "league": m.group(5), "note": m.group(6) or ""}
    return None


def is_hideout(scene):
    return HIDEOUT_WORD in scene.lower()


def _system(body):
    """Event fields for a system line body (without the ": "), or None."""
    m = LEVEL_UP.match(body)
    if m:
        return {"type": "level_up", "character": m.group(1), "class": m.group(2),
                "level": int(m.group(3))}
    m = DEATH.match(body)
    if m:
        return {"type": "death", "character": m.group(1),
                "suicide": m.group(2) == "committed suicide"}
    m = ENTERED.match(body)
    if m:
        return {"type": "area_entered", "name": m.group(1)}
    m = AFK.match(body)
    if m:
        ev = {"type": "afk_changed", "on": m.group(1) == "ON"}
        if m.group(2):
            ev["autoreply"] = m.group(2)
        return ev
    m = DND.match(body)
    if m:
        ev = {"type": "dnd_changed", "on": m.group(1) == "ON"}
        if m.group(2):
            ev["autoreply"] = m.group(2)
        return ev
    m = JOINED.match(body)
    if m:
        return {"type": "player_joined_area", "character": m.group(1)}
    m = LEFT.match(body)
    if m:
        return {"type": "player_left_area", "character": m.group(1)}
    if TRADE_ACCEPTED.match(body):
        return {"type": "trade_accepted"}
    if TRADE_CANCELLED.match(body):
        return {"type": "trade_cancelled"}
    return {"type": "unknown_system_line", "body": body}


def parse_body(body):
    """Event fields for a line body, or None for lines AshLight ignores."""
    if body.startswith(": "):
        return _system(body[2:].strip())
    if body.startswith("[SCENE]"):
        m = SCENE.match(body)
        if m:
            scene = m.group(1)
            null = scene in ("(null)", "")
            unknown = scene == UNKNOWN_SCENE
            transient = unknown or bool(ACT_SCENE.match(scene))
            return {"type": "scene_changed",
                    "scene": None if (null or unknown) else scene,
                    "is_null": null, "is_transient": transient,
                    "is_hideout": not (null or transient) and is_hideout(scene)}
        return None
    m = AREA_GEN.match(body)
    if m:
        return {"type": "area_generated", "area_level": int(m.group(1)),
                "area_id": m.group(2), "seed": m.group(3)}
    if body.startswith("@From "):
        m = WHISPER_IN.match(body)
        if m:
            ev = {"type": "whisper_in", "from": m.group(2), "text": m.group(3)}
            if m.group(1):
                ev["guild_tag"] = m.group(1)
            trade = parse_trade(m.group(3))
            if trade:
                ev["trade"] = trade
            return ev
        return None
    if body.startswith("@To "):
        m = WHISPER_OUT.match(body)
        if m:
            return {"type": "whisper_out", "to": m.group(2), "text": m.group(3)}
        return None
    if body[:1] in CHANNELS:
        m = CHAT.match(body)
        if m:
            ev = {"type": "chat", "channel": CHANNELS[m.group(1)],
                  "character": m.group(3), "text": m.group(4)}
            if m.group(2):
                ev["guild_tag"] = m.group(2)
            return ev
        return None
    m = INSTANCE.match(body)
    if m:
        return {"type": "session_connect", "host": m.group(1), "port": int(m.group(2))}
    return None


def parse_line(line, keep_raw=False):
    """One event dict for a Client.txt line, or None.

    Every event carries ts_local (ISO 8601, no zone), counter, level, pid and
    source; the bus adds seq and recv_ts.
    """
    if len(line) > MAX_LINE_CHARS + 2:  # FUZZ-1
        return None
    m = PREFIX.match(line.rstrip("\r\n"))
    if not m:
        return None
    ev = parse_body(m.group(9))
    if ev is None:
        return None
    ev["ts_local"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}"
    ev["counter"] = int(m.group(5))
    ev["level_tag"] = m.group(7)
    ev["pid"] = int(m.group(8))
    ev["source"] = "client_log"
    if keep_raw:
        ev["raw"] = line
    return ev


def parse_lines(lines, keep_raw=False):
    out = []
    for line in lines:
        ev = parse_line(line, keep_raw)
        if ev is not None:
            out.append(ev)
    return out
