"""DS-NLM: one exact-output assert per summarize template (design 0001
section 9, rule 10). Missing fields read honestly - never "None",
"undefined", "?" or an internal id."""

import pytest

from server.al.state import summarize

TRADE = {"kind": "item", "item": "Plain Belt", "price_amount": 5,
         "price_currency": "exalted", "league": "Standard",
         "stash_tab": "Sale", "left": 3, "top": 7}

CASES = [
    # zone
    ({"type": "scene_changed", "scene": "Clearfell"}, "Entered Clearfell"),
    ({"type": "scene_changed", "scene": "Felled Hideout", "is_hideout": True},
     "Entered Felled Hideout (hideout)"),
    ({"type": "scene_changed", "scene": None}, "Entered an unknown zone"),
    ({"type": "area_entered", "name": "The Riverbank"}, "Entered The Riverbank"),
    ({"type": "area_entered"}, "Entered an unknown zone"),
    ({"type": "area_generated", "area_level": 45, "area_id": "G1_1"},
     "Area level 45"),
    ({"type": "area_generated", "area_id": "G1_1"}, "Area level unknown"),
    # level up
    ({"type": "level_up", "character": "Emberwright", "class": "Witch",
      "level": 12}, "Emberwright reached level 12"),
    ({"type": "level_up", "level": 12}, "Unknown character reached level 12"),
    ({"type": "level_up", "character": "Emberwright"},
     "Emberwright reached a new level (level unknown)"),
    # death
    ({"type": "death", "character": "Emberwright"}, "Emberwright died"),
    ({"type": "death", "character": "Emberwright", "suicide": True},
     "Emberwright died (self-inflicted)"),
    ({"type": "death"}, "Unknown character died"),
    # trade whispers
    ({"type": "whisper_in", "from": "Quietfox", "text": "Hi...", "trade": TRADE},
     "Quietfox wants Plain Belt - 5 exalted"),
    ({"type": "whisper_in", "from": "Quietfox", "text": "Hi...",
      "trade": dict(TRADE, price_amount=None, price_currency=None)},
     "Quietfox wants Plain Belt - no price set"),
    ({"type": "whisper_in", "from": "Coin", "text": "Hi...",
      "trade": {"kind": "exchange", "item": "Chaos Orb", "want_amount": 10,
                "price_amount": 1, "price_currency": "Divine Orb"}},
     "Coin wants 10 Chaos Orb - for 1 Divine Orb"),
    ({"type": "whisper_in", "text": "Hi...", "trade": {"kind": "item"}},
     "Unknown player wants an item - no price set"),
    # plain whispers
    ({"type": "whisper_in", "from": "Quietfox", "text": "hey there"},
     'Quietfox: "hey there"'),
    ({"type": "whisper_in", "from": "Quietfox", "text": ""},
     "Quietfox sent an empty whisper"),
    ({"type": "whisper_in", "text": "hi"}, 'Unknown player: "hi"'),
    ({"type": "whisper_out", "to": "Tradewind", "text": "omw"},
     'To Tradewind: "omw"'),
    ({"type": "whisper_out", "text": "omw"}, 'To unknown player: "omw"'),
    ({"type": "whisper_out", "to": "Tradewind", "text": ""},
     "Sent an empty whisper to Tradewind"),
    # AFK / DND
    ({"type": "afk_changed", "on": True}, "You're AFK"),
    ({"type": "afk_changed", "on": False}, "You're back"),
    ({"type": "dnd_changed", "on": True}, "Do not disturb on"),
    ({"type": "dnd_changed", "on": False}, "Do not disturb off"),
    # party
    ({"type": "player_joined_area", "character": "Partyguy"},
     "Partyguy joined the area"),
    ({"type": "player_left_area", "character": "Partyguy"},
     "Partyguy left the area"),
    ({"type": "player_joined_area"}, "Unknown character joined the area"),
    ({"type": "player_left_area"}, "Unknown character left the area"),
    # trade window
    ({"type": "trade_accepted"}, "Trade accepted"),
    ({"type": "trade_cancelled"}, "Trade cancelled"),
    # session and log state
    ({"type": "session_connect", "host": "1.2.3.4", "port": 6112},
     "Connected to a game server"),
    ({"type": "tailer_started", "path": "x"}, "Reading Client.txt"),
    ({"type": "tailer_reset", "reason": "missing"},
     "Client.txt is missing - waiting for the game"),
    ({"type": "tailer_reset", "reason": "replaced"},
     "Client.txt was replaced - reading the new file"),
    ({"type": "tailer_reset", "reason": "truncated"},
     "Client.txt was cleared - reading from the start"),
    ({"type": "tailer_reset"}, "Client.txt was reset"),
    ({"type": "tailer_reset", "reason": "weird"}, "Client.txt was reset"),
    # fallback: never the raw event type
    ({"type": "unknown_system_line", "body": "x"}, "Something happened in the log"),
    ({"type": "chat", "channel": "global", "character": "A", "text": "b"},
     "Something happened in the log"),
    ({}, "Something happened in the log"),
]


@pytest.mark.parametrize("ev,want", CASES,
                         ids=[f"{i}-{c[0].get('type')}" for i, c in enumerate(CASES)])
def test_exact_output(ev, want):
    assert summarize(ev) == want


@pytest.mark.parametrize("ev", [c[0] for c in CASES])
def test_never_none_or_internal(ev):
    # Missing or None fields everywhere: still honest words.
    blank = {k: None for k in ev if k != "type"}
    blank["type"] = ev.get("type")
    for e in (ev, blank):
        text = summarize(e)
        assert text and text.strip() == text
        for bad in ("None", "undefined", "?", "G1_1", "unknown_system_line",
                    "_changed", "  "):
            assert bad not in text, (e, text)
        text.encode("ascii")


def test_none_died_cannot_happen():
    assert summarize({"type": "death", "character": None}) == "Unknown character died"
    assert summarize({"type": "level_up", "character": None, "level": None}) == \
        "Unknown character reached a new level (level unknown)"
