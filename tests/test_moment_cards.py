"""OVL-ZONE-CARD: the zone moment card in the one card slot and the HUD
guide-line fields of the snapshot's "overlay" dict (server/al/overlayview.py).

- a replayed log entering a guided campaign zone publishes one card of
  kind zone, 3 lines of at most 34 characters, for 12 s;
- an open trade request, a press card or the sample takes the slot first,
  and the zone card never waits or returns;
- re-entry in the same game run shows nothing; a new game run shows it
  again;
- parts.moment off or zone_guide "never" shows nothing;
- every shipped guide entry's lines fit the clip or are clipped (a long
  bonus at a whole word); a short with nothing to add makes no card;
- the overlay view carries guide_short and calm_at, never the
  120-character guide line.

The log lines are invented fixtures fed through the parser; no game file
is read and nothing is sent.
"""

import pytest

from server.al import layout, overlayview, parser, zoneguide
from server.al.overlayview import MOMENT_CARD_S, zone_lines
from server.al.state import SessionState
from server.al.text.common import CARD_LINE

T0 = 70000.0
SHIPPED = zoneguide.load()
RIVERBANK_SHORT = SHIPPED["acts"]["G1"]["zones"]["The Riverbank"]["short"]

OPEN = "2026/11/16 20:00:00 ***** LOG FILE OPENING *****"
LEVEL = ("2026/11/16 20:00:01 900 1a2b3c4d [INFO Client 4242] : "
         "Emberwright (Witch) is now level 2")
DEATH = "2026/11/16 20:00:01 950 1a2b3c4d [INFO Client 4242] : Emberwright has been slain."
TRADE = ("2026/11/16 20:00:02 1000 1a2b3c4d [INFO Client 4242] @From Tradewind: Hi, I "
         "would like to buy your Grim Bane Ruby Ring listed for 5 exalted in Standard "
         "(stash tab \"Sale\"; position: left 3, top 7)")
ACCEPTED = "2026/11/16 20:00:03 1100 1a2b3c4d [INFO Client 4242] : Trade accepted."


def _gen(area_id, level=1):
    return (f"2026/11/16 20:00:04 1200 2b3c4d5e [DEBUG Client 4242] Generating level "
            f"{level} area \"{area_id}\" with seed 1234567")


def _scene(name):
    return f"2026/11/16 20:00:05 1300 2b3c4d5e [INFO Client 4242] [SCENE] Set Source [{name}]"


ZONES = {"The Riverbank": "G1_1", "Clearfell": "G1_2",
         "Felled Hideout": "HideoutFelled"}


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def _state(guide=SHIPPED):
    clock = Clock()
    st = SessionState(clock=clock)
    st.set_zone_guide(guide=guide)
    return st, clock


def _feed(st, clock, *lines, at=None):
    """Replay log lines through the parser at time `at` (default: now)."""
    if at is not None:
        clock.t = at
    for line in lines:
        ev = parser.parse_line(line)
        assert ev is not None, line
        ev["recv_ts"] = clock.t
        st.apply(ev)


def _enter(st, clock, zone, at=None):
    _feed(st, clock, _gen(ZONES[zone]), _scene(zone), at=at)


def _card(st, at):
    st._clock.t = at
    return st.snapshot()["card"]


def test_first_entry_of_a_guided_zone_shows_the_zone_card_for_12_s():
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL)
    _enter(st, clock, "The Riverbank", at=T0)
    card = _card(st, T0)
    assert card is not None and card["kind"] == "zone"
    assert set(card) == {"kind", "head", "line2", "line3", "verdict", "expires_at"}
    assert card["head"] == RIVERBANK_SHORT
    assert card["line2"] == "Bonus: Uncut skill gem"
    assert card["line3"] == overlayview.FIT_LINE  # level 2 in a level 1 zone
    assert card["verdict"] == ""  # neutral edge
    assert card["expires_at"] == T0 + MOMENT_CARD_S == T0 + 12
    for key in ("head", "line2", "line3"):
        assert card[key].isascii() and len(card[key]) <= CARD_LINE == 34, (key, card[key])
    assert _card(st, T0 + MOMENT_CARD_S - 0.01) == card
    assert _card(st, T0 + MOMENT_CARD_S) is None
    assert st.overlay.moment is None  # gone for good
    # the card enters no event list
    assert all(r.get("text") != card["head"] for r in st.snapshot()["recent_events"])


def test_an_open_trade_request_takes_the_slot_and_the_zone_card_never_returns():
    # a trade open at entry: no zone card, not even once the trade closes
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, TRADE, at=T0 - 1)
    _enter(st, clock, "The Riverbank", at=T0)
    assert _card(st, T0) is None
    _feed(st, clock, ACCEPTED, at=T0 + 2)
    assert not st.trade_requests
    assert _card(st, T0 + 3) is None
    # a trade that arrives while the zone card shows drops it for good
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0 - 1)
    _enter(st, clock, "The Riverbank", at=T0)
    assert _card(st, T0)["kind"] == "zone"
    _feed(st, clock, TRADE, at=T0 + 1)
    assert _card(st, T0 + 1) is None
    _feed(st, clock, ACCEPTED, at=T0 + 2)
    assert _card(st, T0 + 3) is None


def test_a_trade_with_the_trade_part_off_does_not_take_the_slot():
    st, clock = _state()
    off = layout.normalize({"parts": {"trade": False}})
    st.set_overlay_layout(off)
    _feed(st, clock, OPEN, LEVEL, TRADE, at=T0 - 1)
    _enter(st, clock, "The Riverbank", at=T0)
    assert _card(st, T0)["kind"] == "zone"


def test_a_press_card_takes_the_slot_and_the_zone_card_never_waits():
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0)
    st.set_eval({"ok": False, "error": "no build loaded"}, at=T0)
    # entry while the press card is still fresh (it lasts 20 s)
    _enter(st, clock, "The Riverbank", at=T0 + 15)
    assert _card(st, T0 + 15)["kind"] == "eval"
    # the press card left inside the zone card's 12 s: nothing comes back
    assert _card(st, T0 + 21) is None
    # a press while the zone card shows drops it at once
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0)
    _enter(st, clock, "The Riverbank", at=T0)
    assert _card(st, T0)["kind"] == "zone"
    st.set_eval({"ok": False, "error": "no build loaded"}, at=T0 + 1)
    assert st.overlay.moment is None
    assert _card(st, T0 + 1)["kind"] == "eval"


def test_re_entry_in_the_same_game_run_shows_nothing():
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0)
    _enter(st, clock, "The Riverbank", at=T0)
    assert _card(st, T0)["kind"] == "zone"
    _enter(st, clock, "Clearfell", at=T0 + 60)
    clear = _card(st, T0 + 60)
    assert clear["kind"] == "zone" and clear["head"] != RIVERBANK_SHORT
    # leaving drops the old zone's card at once
    _enter(st, clock, "The Riverbank", at=T0 + 65)
    assert _card(st, T0 + 65) is None
    _enter(st, clock, "Clearfell", at=T0 + 120)
    assert _card(st, T0 + 120) is None
    # a new game run: every zone shows once more
    _feed(st, clock, OPEN, at=T0 + 200)
    _enter(st, clock, "The Riverbank", at=T0 + 210)
    assert _card(st, T0 + 210)["head"] == RIVERBANK_SHORT


def test_hideout_endgame_and_a_zone_without_short_show_nothing():
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0)
    _enter(st, clock, "Felled Hideout", at=T0)
    assert _card(st, T0) is None
    doc = {"acts": {"G1": {"zones": {"The Riverbank": {"objective": "Go on.",
                                                       "next": "Clearfell"}}}},
           "endgame": {"objective": "Kill the map boss.", "short": "Map boss"}}
    st, clock = _state(doc)
    _feed(st, clock, OPEN, LEVEL, at=T0)
    _enter(st, clock, "The Riverbank", at=T0)
    assert st.snapshot()["zone_guide"]["kind"] == "campaign"
    assert _card(st, T0) is None  # no short, no card
    assert zone_lines({"kind": "endgame", "short": "Map boss"}) is None


@pytest.mark.parametrize("lay", [{"parts": {"moment": False}}, {"zone_guide": "never"}])
def test_layout_switches_hide_the_zone_card(lay):
    st, clock = _state()
    st.set_overlay_layout(layout.normalize(lay))
    _feed(st, clock, OPEN, LEVEL, at=T0)
    _enter(st, clock, "The Riverbank", at=T0)
    assert _card(st, T0) is None
    # switched back on inside the 12 s: it does not come back
    st.set_overlay_layout(layout.normalize({}))
    assert _card(st, T0 + 1) is None


def test_every_shipped_guide_entry_fits_or_clips():
    advice = [None, {"mode": "fit", "text": zoneguide.FIT_TEXT},
              {"mode": "clear", "text": zoneguide.CLEAR_TEXT.format(n=12, lv="levels")},
              {"mode": "push", "text": zoneguide.RUSH_TEXT.format(n=1, lv="level")},
              {"mode": "clear", "text": zoneguide.CLEAR_TEXT.format(n=199, lv="levels")}]
    shown = 0
    for act in SHIPPED["acts"].values():
        for name, z in act.get("zones", {}).items():
            for adv in advice:
                for boss in (None, zoneguide._boss(z), "lightning"):
                    guide = {"kind": "campaign", "zone": name,
                             "short": zoneguide._clean(z.get("short"), zoneguide.MAX_SHORT),
                             "optional": zoneguide._optional(z),
                             "next": zoneguide._clean(z.get("next")),
                             "advice": adv, "boss": boss}
                    lines = zone_lines(guide)
                    if not guide["short"]:
                        assert lines is None, name
                        continue
                    if lines is None:  # nothing to add to the short
                        assert boss is None and adv is None, name
                        continue
                    shown += 1
                    assert len(lines) == 3 and lines[0] == guide["short"], name
                    for line in lines:
                        assert isinstance(line, str) and line.isascii(), (name, line)
                        assert len(line) <= CARD_LINE, (name, line)
                    assert lines[1] or not lines[2], (name, lines)  # no gap
    assert shown > 0


def test_zone_lines_words():
    base = {"kind": "campaign", "short": "Short words", "optional": [], "next": None,
            "advice": None, "boss": None}
    # nothing to add to the short: no card
    assert zone_lines(base) is None
    assert zone_lines(dict(base, advice={"mode": "fit", "text": zoneguide.FIT_TEXT})) == (
        "Short words", "Your level fits this zone", "")
    clear = {"mode": "clear", "text": zoneguide.CLEAR_TEXT.format(n=1, lv="level")}
    g = dict(base, next="Clearfell", advice=clear)
    assert zone_lines(g) == ("Short words", "Next: Clearfell", "You are 1 level under: clear it")
    # the boss element outranks the level advice
    g = dict(base, next="Clearfell", boss="fire", advice=clear)
    assert zone_lines(g) == ("Short words", "Next: Clearfell", "Boss deals mostly fire damage")
    g = dict(base, advice={"mode": "fit", "text": zoneguide.FIT_TEXT}, boss="cold")
    assert zone_lines(g) == ("Short words", "Boss deals mostly cold damage", "")
    g = dict(base, optional=[{"kind": "resist", "text": "+10% cold resistance - near the middle."}],
             next="Clearfell", advice={"mode": "push",
                                       "text": zoneguide.RUSH_TEXT.format(n=7, lv="levels")})
    assert zone_lines(g) == ("Short words", "Bonus: +10% cold resistance",
                             "You are 7 levels over: move on")
    # a next zone the short already names gives no line
    g = dict(base, short="Next: Clearfell", next="Clearfell")
    assert zone_lines(g) is None
    # a bonus that would be cut gives way to the next zone
    g = dict(base, optional=[{"kind": "other", "text": "A permanent bonus of your choice"}],
             next="Qimah")
    assert zone_lines(g)[1] == "Next: Qimah"
    # with no next zone a long bonus is cut at a whole word
    g = dict(base, optional=[{"kind": "other", "text": "A permanent bonus of your choice"}])
    assert zone_lines(g)[1] == "Bonus: A permanent bonus of..."
    g = dict(base, optional=[{"kind": "charm", "text": "A charm bonus of your choice"}])
    assert zone_lines(g)[1] == "Bonus: A charm bonus of your..."
    assert overlayview.clip_words("x" * 40) == "x" * 31 + "..."


def test_overlay_view_carries_the_guide_short_never_the_guide_line():
    st, clock = _state()
    assert st.snapshot()["overlay"] == {"guide_short": "", "calm_at": None}
    _feed(st, clock, OPEN, LEVEL, at=T0)
    _enter(st, clock, "The Riverbank", at=T0)
    snap = st.snapshot()
    ov = snap["overlay"]
    assert set(ov) == {"guide_short", "calm_at"}
    assert ov["guide_short"] == RIVERBANK_SHORT and len(ov["guide_short"]) <= CARD_LINE
    line = snap["zone_guide"]["line"]
    assert line and line not in ov.values() and len(line) > CARD_LINE
    # the hideout and a new game run carry no short
    _enter(st, clock, "Felled Hideout", at=T0 + 30)
    assert st.snapshot()["overlay"]["guide_short"] == ""
    _enter(st, clock, "Clearfell", at=T0 + 40)
    assert st.snapshot()["overlay"]["guide_short"]
    _feed(st, clock, OPEN, at=T0 + 50)
    assert st.snapshot()["overlay"]["guide_short"] == ""


def test_calm_at_follows_the_last_death_or_level_up():
    st, clock = _state()
    _feed(st, clock, OPEN, at=T0)
    assert st.snapshot()["overlay"]["calm_at"] is None
    _feed(st, clock, LEVEL, at=T0 + 5)
    assert st.snapshot()["overlay"]["calm_at"] == T0 + 5 + overlayview.CALM_S == T0 + 25
    _feed(st, clock, DEATH, at=T0 + 40)
    assert st.snapshot()["overlay"]["calm_at"] == T0 + 60
    # another player's death is not the player's
    _feed(st, clock, "2026/11/16 20:00:09 990 1a2b3c4d [INFO Client 4242] : "
          "Otherguy has been slain.", at=T0 + 70)
    assert st.snapshot()["overlay"]["calm_at"] == T0 + 60


def test_the_moment_card_survives_a_store_round_trip_untouched():
    # the zone entries stay in memory: the store document is unchanged
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0)
    _enter(st, clock, "The Riverbank", at=T0)
    assert st.overlay.to_doc() == {"schema": overlayview.SCHEMA}
