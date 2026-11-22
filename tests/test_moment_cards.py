"""OVL-ZONE-CARD and OVL-ACT-CARD: the zone and act moment cards in the one card slot and the HUD
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
  120-character guide line;
- an act split closing shows kind act for 12 s: 'Act <n> done', the split
  time and the gap to the saved best of the run history view (time only
  without a best, for a partial split or with history off), never over a
  press card or an open trade, off with parts.moment only, and it holds
  the slot over the zone card of the same entry.

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


def test_card_copy_lives_in_the_text_module_and_is_re_exported():
    # OVL-ZONE-CARD fix round: the copy and pure builders sit under the
    # design gate (server/al/text/); overlayview re-exports the same objects
    from server.al.text import overlaycard
    for name in ("MOMENT_CARD_S", "BONUS_TEXT", "NEXT_TEXT", "CLEAR_LINE",
                 "PUSH_LINE", "FIT_LINE", "BOSS_LINE", "_LEVELS", "clip",
                 "clip_words", "_lv", "_plain", "zone_lines"):
        assert getattr(overlayview, name) is getattr(overlaycard, name), name


# -- OVL-ACT-CARD: the act moment card ---------------------------------------

ZONES.update({"Vastiri Outskirts": "G2_1"})
ACT1_S = 600.0


def _act_run(at_close=T0 + ACT1_S, first="The Riverbank"):
    """A run that enters Act 1 at T0 and Act 2 at `at_close`."""
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0 - 1)
    _enter(st, clock, first, at=T0)
    _enter(st, clock, "Vastiri Outskirts", at=at_close)
    return st, clock


def _history(best_s, **row):
    return {"on": True, "runs": 2, "deaths_by_zone": [],
            "best": [dict({"key": "G1", "label": "Act 1", "best_s": best_s,
                           "best_text": "", "delta_s": None}, **row)]}


def _lines_fit(card):
    for key in ("head", "line2", "line3"):
        assert isinstance(card[key], str) and card[key].isascii(), (key, card[key])
        assert len(card[key]) <= CARD_LINE, (key, card[key])


def test_a_closed_act_without_a_saved_best_shows_the_time_only_for_12_s():
    st, clock = _act_run()
    at = T0 + ACT1_S
    card = _card(st, at)
    assert card is not None and card["kind"] == "act"
    assert set(card) == {"kind", "head", "line2", "line3", "verdict", "expires_at"}
    assert card["head"] == "Act 1 done"
    assert card["line2"] == "Act time 10:00"
    assert card["line3"] == ""
    assert card["verdict"] == ""
    assert card["expires_at"] == at + 12
    _lines_fit(card)
    assert _card(st, at + 11.99) == card
    assert _card(st, at + 12) is None
    assert st.overlay.moment is None  # gone for good
    # the zone card of the act's first zone was dropped, not queued
    assert _card(st, at + 13) is None
    assert ("Act 2", "Vastiri Outskirts") in st.overlay.seen


@pytest.mark.parametrize("best,line3", [
    (540.0, "1:00 behind your best"),
    (725.0, "New best by 2:05"),
    (600.4, "Ties your best"),
    (60.0, "9:00 behind your best"),
])
def test_a_closed_act_with_a_saved_best_shows_the_gap(best, line3):
    st, clock = _act_run()
    st.set_run_history(_history(best))
    card = _card(st, T0 + ACT1_S + 1)
    assert card["kind"] == "act" and card["head"] == "Act 1 done"
    assert card["line2"] == "Act time 10:00"
    assert card["line3"] == line3
    _lines_fit(card)


def test_the_gap_follows_a_history_view_that_lands_after_the_close():
    st, clock = _act_run()
    assert _card(st, T0 + ACT1_S)["line3"] == ""
    st.set_run_history(_history(540.0))
    assert _card(st, T0 + ACT1_S + 1)["line3"] == "1:00 behind your best"


@pytest.mark.parametrize("view", [
    None,
    {"on": False, "runs": 0, "best": [], "deaths_by_zone": []},
    _history(540.0, this_run=True),  # the best is this run's own split
    _history(540.0, key="G2"),  # no saved best for this act
    _history("540"),  # a broken value is no best
])
def test_no_usable_best_shows_no_gap(view):
    st, clock = _act_run()
    st.set_run_history(view)
    card = _card(st, T0 + ACT1_S)
    assert card["kind"] == "act" and card["line3"] == ""


def test_a_partial_act_says_so_and_shows_no_gap():
    # the run did not start at the first zone: the split is partial
    st, clock = _act_run(first="Clearfell")
    st.set_run_history(_history(540.0))
    card = _card(st, T0 + ACT1_S)
    assert card["head"] == "Act 1 done"
    assert card["line2"] == "Act time 10:00, partial"
    assert card["line3"] == ""


def test_long_acts_read_in_hours_and_fit():
    st, clock = _act_run(at_close=T0 + 2 * 3600 + 5)
    st.set_run_history(_history(5.0))
    card = _card(st, T0 + 2 * 3600 + 5)
    assert card["line2"] == "Act time 2:00:05"
    assert card["line3"] == "2:00:00 behind your best"
    _lines_fit(card)


def test_an_open_trade_or_a_press_card_takes_the_slot_from_the_act_card():
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0 - 1)
    _enter(st, clock, "The Riverbank", at=T0)
    _feed(st, clock, TRADE, at=T0 + ACT1_S - 1)
    _enter(st, clock, "Vastiri Outskirts", at=T0 + ACT1_S)
    assert _card(st, T0 + ACT1_S) is None
    _feed(st, clock, ACCEPTED, at=T0 + ACT1_S + 1)
    assert _card(st, T0 + ACT1_S + 2) is None  # never returns
    # a press while the act card shows drops it at once
    st, clock = _act_run()
    assert _card(st, T0 + ACT1_S)["kind"] == "act"
    st.set_eval({"ok": False, "error": "no build loaded"}, at=T0 + ACT1_S + 1)
    assert st.overlay.moment is None
    assert _card(st, T0 + ACT1_S + 1)["kind"] == "eval"
    assert _card(st, T0 + ACT1_S + 30) is None
    # an act closing while a press card is fresh: the press card stays
    st, clock = _state()
    _feed(st, clock, OPEN, LEVEL, at=T0 - 1)
    _enter(st, clock, "The Riverbank", at=T0)
    st.set_eval({"ok": False, "error": "no build loaded"}, at=T0 + ACT1_S - 5)
    _enter(st, clock, "Vastiri Outskirts", at=T0 + ACT1_S)
    assert _card(st, T0 + ACT1_S)["kind"] == "eval"
    assert _card(st, T0 + ACT1_S + 16) is None


def test_parts_moment_turns_the_act_card_off_but_zone_guide_never_does_not():
    st, clock = _state()
    st.set_overlay_layout(layout.normalize({"parts": {"moment": False}}))
    _feed(st, clock, OPEN, LEVEL, at=T0 - 1)
    _enter(st, clock, "The Riverbank", at=T0)
    _enter(st, clock, "Vastiri Outskirts", at=T0 + ACT1_S)
    assert _card(st, T0 + ACT1_S) is None
    st, clock = _state()
    st.set_overlay_layout(layout.normalize({"zone_guide": "never"}))
    _feed(st, clock, OPEN, LEVEL, at=T0 - 1)
    _enter(st, clock, "The Riverbank", at=T0)
    _enter(st, clock, "Vastiri Outskirts", at=T0 + ACT1_S)
    assert _card(st, T0 + ACT1_S)["kind"] == "act"


def test_the_next_zone_entry_drops_the_act_card_and_reentry_shows_none():
    st, clock = _act_run()
    assert _card(st, T0 + ACT1_S)["kind"] == "act"
    # back to an Act 1 zone: the split stays open in Act 2, no new card
    _enter(st, clock, "Clearfell", at=T0 + ACT1_S + 5)
    card = _card(st, T0 + ACT1_S + 5)
    assert card is None or card["kind"] == "zone"
    _enter(st, clock, "Vastiri Outskirts", at=T0 + ACT1_S + 60)
    assert _card(st, T0 + ACT1_S + 60) is None


def test_entering_endgame_closes_the_last_act_with_its_card():
    st, clock = _act_run()
    _feed(st, clock, _gen("MapCrypt", 65), at=T0 + 2 * ACT1_S)
    card = _card(st, T0 + 2 * ACT1_S)
    assert card["kind"] == "act" and card["head"] == "Act 2 done"
    assert card["line2"] == "Act time 10:00"


def test_the_act_card_names_the_acts_card_as_twin_and_stays_out_of_events():
    holder = next(h for h in overlayview.CARD_HOLDERS if h["kind"] == "moment")
    assert "act" in holder["cards"] and "actsbox" in holder["twin"]
    st, clock = _act_run()
    card = _card(st, T0 + ACT1_S)
    assert all(r.get("text") != card["head"] for r in st.snapshot()["recent_events"])
    assert st.overlay.to_doc() == {"schema": overlayview.SCHEMA}
    for name in ("ACT_HEAD", "ACT_TIME", "ACT_TIME_PARTIAL", "ACT_FASTER",
                 "ACT_SLOWER", "ACT_SAME"):
        text = getattr(overlayview, name)
        assert text.isascii() and len(text.format(label="Cruel Act 99", time="99:59:59",
                                                  gap="99:59:59")) <= CARD_LINE, name
