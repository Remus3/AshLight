"""Client.txt parser: prefix, every event type, anti-spoofing."""

from pathlib import Path

from server.al import parser

FIXTURE = Path(__file__).parent / "fixtures" / "client_sample.txt"
P = "2026/11/16 20:00:00 1000 1a2b3c4d [INFO Client 4242] "


def _events():
    return parser.parse_lines(FIXTURE.read_text(encoding="ascii").splitlines())


def _one(body):
    return parser.parse_line(P + body)


def test_prefix_fields():
    ev = _one(": Trade accepted.")
    assert ev["type"] == "trade_accepted"
    assert ev["ts_local"] == "2026-11-16T20:00:00"
    assert ev["counter"] == 1000
    assert ev["pid"] == 4242
    assert ev["level_tag"] == "INFO"
    assert ev["source"] == "client_log"
    assert "raw" not in ev
    assert parser.parse_line(P + ": Trade accepted.", keep_raw=True)["raw"].startswith("2026")


def test_no_prefix_is_ignored():
    assert parser.parse_line("this line has no prefix") is None
    assert parser.parse_line("") is None


def test_crlf_tolerated():
    assert _one(": Trade accepted.\r\n")["type"] == "trade_accepted"


def test_scene_changed_null_and_hideout():
    ev = _one("[SCENE] Set Source [(null)]")
    assert ev["type"] == "scene_changed" and ev["is_null"] and ev["scene"] is None
    assert not ev["is_hideout"]
    ev = _one("[SCENE] Set Source [Felled Hideout]")
    assert ev["scene"] == "Felled Hideout" and ev["is_hideout"] and not ev["is_null"]
    ev = _one("[SCENE] Set Source [The Riverbank]")
    assert ev["scene"] == "The Riverbank" and not ev["is_hideout"]
    assert _one("[SCENE] Load Source [Clearfell]")["scene"] == "Clearfell"
    assert _one("[RENDER] Shader uses incorrect vertex layout") is None


def test_area_generated():
    ev = _one('Generating level 12 area "G1_4" with seed 99887766')
    assert ev == {**ev, "type": "area_generated", "area_level": 12,
                  "area_id": "G1_4", "seed": "99887766"}


def test_area_entered():
    ev = _one(": You have entered The Riverbank.")
    assert ev["type"] == "area_entered" and ev["name"] == "The Riverbank"


def test_level_up():
    ev = _one(": Emberwright (Witch) is now level 3")
    assert (ev["type"], ev["character"], ev["class"], ev["level"]) == (
        "level_up", "Emberwright", "Witch", 3)
    ev = _one(": Odd (Name) Here (Mercenary) is now level 40")
    assert ev["character"] == "Odd (Name) Here" and ev["class"] == "Mercenary"


def test_death_and_suicide():
    ev = _one(": Emberwright has been slain.")
    assert ev["type"] == "death" and ev["character"] == "Emberwright" and not ev["suicide"]
    ev = _one(": Emberwright has committed suicide.")
    assert ev["type"] == "death" and ev["suicide"]


def test_whisper_in_with_guild_and_trade():
    ev = _one('@From <GLD> Tradewind: Hi, I would like to buy your Grim Bane Ruby Ring '
              'listed for 5 exalted in Standard (stash tab "Sale"; position: left 3, top 7)')
    assert ev["type"] == "whisper_in" and ev["from"] == "Tradewind"
    assert ev["guild_tag"] == "GLD"
    tr = ev["trade"]
    assert tr["item"] == "Grim Bane Ruby Ring"
    assert tr["price_amount"] == 5 and tr["price_currency"] == "exalted"
    assert tr["league"] == "Standard" and tr["stash_tab"] == "Sale"
    assert (tr["left"], tr["top"]) == (3, 7)


def test_whisper_trade_unpriced_and_exchange():
    ev = _one('@From Quietfox: Hi, I would like to buy your Plain Belt in Standard '
              '(stash tab "Dump"; position: left 1, top 2)')
    assert ev["trade"]["item"] == "Plain Belt" and ev["trade"]["price_amount"] is None
    ev = _one("@From Coinmonger: Hi, I'd like to buy your 10 Chaos Orb for my 1 Divine Orb "
              "in Standard.")
    tr = ev["trade"]
    assert tr["kind"] == "exchange" and tr["item"] == "Chaos Orb"
    assert tr["want_amount"] == 10 and tr["price_amount"] == 1
    assert tr["price_currency"] == "Divine Orb" and tr["league"] == "Standard"


def test_plain_whisper_and_out():
    ev = _one("@From Pal: hey there")
    assert ev["type"] == "whisper_in" and "trade" not in ev and ev["text"] == "hey there"
    ev = _one("@To Tradewind: omw")
    assert ev["type"] == "whisper_out" and ev["to"] == "Tradewind" and ev["text"] == "omw"


def test_chat_channels():
    got = {_one(b)["channel"] for b in ("#A: x", "$B: x", "%C: x", "&D: x")}
    assert got == {"global", "trade", "party", "guild"}
    ev = _one("$<MKT> Merchant: WTS stuff")
    assert ev["guild_tag"] == "MKT" and ev["character"] == "Merchant"


def test_chat_cannot_spoof_system_events():
    ev = _one("%Partyguy: Emberwright (Witch) is now level 99")
    assert ev["type"] == "chat"
    assert _one("Tradewind has joined the area.") is None


def test_afk_dnd():
    ev = _one(': AFK mode is now ON. Autoreply "back soon"')
    assert ev["type"] == "afk_changed" and ev["on"] and "back soon" in ev["autoreply"]
    assert _one(": AFK mode is now OFF.")["on"] is False
    assert _one(": DND mode is now ON.")["type"] == "dnd_changed"
    assert _one(": DND mode is now OFF.")["on"] is False


def test_join_leave_trade_accepted_unknown():
    assert _one(": Tradewind has joined the area.")["type"] == "player_joined_area"
    assert _one(": Tradewind has left the area.")["character"] == "Tradewind"
    assert _one(": Trade accepted.")["type"] == "trade_accepted"
    ev = _one(": Some brand new system message")
    assert ev == {**ev, "type": "unknown_system_line", "body": "Some brand new system message"}


def test_session_connect():
    ev = _one("Connecting to instance server at 10.0.0.1:6112")
    assert ev["type"] == "session_connect" and ev["port"] == 6112


def test_fixture_covers_every_event_type():
    types = {e["type"] for e in _events()}
    want = {"session_connect", "scene_changed", "area_generated", "area_entered",
            "level_up", "death", "whisper_in", "whisper_out", "chat", "afk_changed",
            "dnd_changed", "player_joined_area", "player_left_area", "trade_accepted",
            "unknown_system_line"}
    assert want <= types, want - types


def test_fixture_is_ascii_lf():
    data = FIXTURE.read_bytes()
    data.decode("ascii")
    assert b"\r" not in data


# --- LIVE-1 (2026-11-16): shapes seen in a real PoE2 Client.txt. The fixture
# is synthetic and anonymised (made-up names, TEST-NET addresses, fake seeds);
# only the line SHAPES come from the live log.
LIVE = Path(__file__).parent / "fixtures" / "client_live_shapes.txt"


def _live():
    return parser.parse_lines(LIVE.read_text(encoding="ascii").splitlines())


def test_live_fixture_is_ascii_lf():
    data = LIVE.read_bytes()
    data.decode("ascii")
    assert b"\r" not in data


def test_live_unknown_scene_is_transient_not_a_zone():
    # "(unknown)" is the login / character-select / full-screen panel scene.
    ev = _one("[SCENE] Set Source [(unknown)]")
    assert ev["type"] == "scene_changed" and ev["is_transient"]
    assert ev["scene"] is None and not ev["is_null"] and not ev["is_hideout"]


def test_live_act_scene_is_transient_not_a_zone():
    # "Act <N>" shows for a few seconds (world map) and the same zone returns.
    ev = _one("[SCENE] Set Source [Act 1]")
    assert ev["is_transient"] and ev["scene"] == "Act 1" and not ev["is_null"]
    assert not _one("[SCENE] Set Source [The Riverbank]")["is_transient"]
    assert not _one("[SCENE] Set Source [(null)]")["is_transient"]
    assert not _one("[SCENE] Set Source [Actor Hideout]")["is_transient"]


def test_live_debug_level_and_short_hex_prefix():
    line = '2026/11/16 21:00:01 59200 2a3b4c5 [DEBUG Client 5150] Generating level 1 area "G1_1" with seed 1'
    ev = parser.parse_line(line)
    assert ev["type"] == "area_generated" and ev["level_tag"] == "DEBUG"


def test_live_trade_cancelled():
    assert _one(": Trade cancelled.")["type"] == "trade_cancelled"


def test_live_npc_dialogue_and_engine_lines_ignored():
    assert _one("Riverside Miller: Grind you down!") is None
    assert _one("[WINDOW] Gained focus") is None
    # UTIL-SESSION-SUMMARY: the run marker is the only non-prefixed line
    # parsed (a new game run; the previous game closed)
    assert parser.parse_line("2026/11/16 21:00:00 ***** LOG FILE OPENING *****") == {
        "type": "game_started", "ts_local": "2026-11-16T21:00:00", "source": "client_log"}
    assert parser.parse_line("2026/11/16 21:00:00 ***** LOG FILE OPENING ***** x") is None


def test_live_fixture_event_types():
    evs = _live()
    types = [e["type"] for e in evs]
    for t in ("scene_changed", "session_connect", "area_generated", "level_up", "chat",
              "unknown_system_line", "trade_cancelled"):
        assert t in types, t
    lv = [e for e in evs if e["type"] == "level_up"][0]
    assert (lv["character"], lv["class"], lv["level"]) == ("Cinderwisp", "Sorceress", 2)
    chans = sorted(e["channel"] for e in evs if e["type"] == "chat")
    assert chans == ["global", "trade"]
    areas = [(e["area_level"], e["area_id"]) for e in evs if e["type"] == "area_generated"]
    assert areas == [(1, "G1_1"), (15, "G1_town")]
    assert "area_entered" not in types  # PoE2 does not log "You have entered"
