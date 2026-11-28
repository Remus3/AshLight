"""PLAY-TD-07A: snapshot()['play'] carries the strip, feed, notices and
build rows, composed and capped at the source (server/al/playview.py).

Exact rows on the evidence-pack states (tests/play_states.py recipes, each
a core pinned to a temp Client.txt on a free test port, never 8960), and
on the long-string fixture no composed row exceeds its cap: event sentence
38, notice word 12 / title 20 / action 12 / rows 52, build row two 36.
Names are data and are never capped: they are left out of the word
counts (G5 per region: strip 20, feed 50, notices 22, build 16).
"""

import json
import math

import pytest

import play_states as ps
from server.al import playview as pv
from server.al import state as state_mod
from server.al.state import SessionState


# -- caps and helpers ----------------------------------------------------------

def test_caps_are_the_plan_figures():
    assert pv.CAP_EVENT_SENTENCE == ps.CAP_EVENT_SENTENCE == 38
    assert pv.CAP_NOTICE_WORD == ps.CAP_NOTICE_WORD == 12
    assert pv.CAP_NOTICE_TITLE == ps.CAP_NOTICE_TITLE == 20
    assert pv.CAP_NOTICE_ACTION == ps.CAP_NOTICE_ACTION == 12
    assert pv.CAP_NOTICE_ROW == ps.CAP_NOTICE_ROW == 52
    assert pv.CAP_BUILD_ROW == ps.CAP_BUILD_ROW == 36
    assert (pv.WORDS_STRIP, pv.WORDS_FEED, pv.WORDS_NOTICE, pv.WORDS_BUILD) == (20, 50, 22, 16)


def test_words_counts_like_the_fit_harness():
    assert pv.words("Act 1 - area level 2") == 5
    assert pv.words("new, tab Sale (1,10)") == 4
    assert pv.words("") == 0 and pv.words(None) == 0


def test_clip_cuts_at_a_word():
    assert pv.clip("short", 10) == "short"
    assert pv.clip("one two three four", 12) == "one two..."
    assert len(pv.clip("x" * 50, 12)) == 12
    for n in range(4, 60):
        assert len(pv.clip(ps.text_at(80), n)) <= n


def test_fit_rows_keeps_whole_sentences_then_cuts():
    assert pv.fit_rows("One. Two.", 52, 2) == ["One. Two."]
    text = "A first sentence here. " + "A long second sentence " * 6
    assert pv.fit_rows(text, 52, 2) == ["A first sentence here."]
    rows = pv.fit_rows("word " * 60, 52, 2)
    assert len(rows) == 2 and all(len(r) <= 52 for r in rows) and rows[-1].endswith("...")
    rows = pv.fit_rows("x" * 200, 52, 2)
    assert rows and all(len(r) <= 52 for r in rows)
    assert pv.words(" ".join(pv.fit_rows("word " * 60, 52, 2, max_words=5))) <= 5
    assert pv.fit_rows("", 52, 2) == [] and pv.fit_rows(None, 52, 2) == []


# -- the block on the core's own snapshot -----------------------------------------

def test_snapshot_carries_the_play_block():
    snap = SessionState().snapshot()
    play = snap["play"]
    assert set(play) == {"strip", "feed", "notices", "build", "map_ok",
                         "context", "item", "kept"}
    assert play["map_ok"] is False
    assert set(play["context"]) == {"setup"} and play["context"]["setup"]["mode"] == "setup"
    assert play["item"] is None and play["kept"] is None
    assert set(play["strip"]) == {"zone", "sub", "level_sub", "deaths_sub",
                                  "session_sub", "fresh"}
    assert set(play["feed"]) == {"trades", "events"}
    assert set(play["feed"]["events"]) == {"death", "level", "zone"}
    assert set(play["build"]) >= {"state", "word", "row1", "row2", "can_paste"}
    json.dumps(play)  # rides the state push as JSON


def test_view_never_raises_on_wrong_types():
    junk = [None, 1, "x", [], {}, {"a": 1}, [None, 1], float("nan"), True]
    keys = ("now", "zone", "area_id", "area_level", "level", "class", "character",
            "deaths", "level_ups", "maps", "underlevel", "death_recap", "recent_events",
            "trade_requests", "tailer", "diag", "lang", "hint", "build", "build_alert",
            "sources", "game_idle", "in_hideout", "afk", "dnd", "zone_entered_at")
    for j in junk:
        assert set(pv.view(j)) >= {"strip", "feed", "notices", "build"}
        for k in keys:
            pv.view({k: j})
            pv.view({k: {"current": j, "recent": [j], "checks": [j], "word": j}})


# -- synthetic rows: every branch ------------------------------------------------

NOW = 1_800_000_000.0


def _snap(**kw):
    base = {"now": NOW, "tailer": {"consented": True, "reading": True, "idle": False},
            "build": {"loaded": True, "class_name": "Ranger", "level": 80},
            "build_alert": None, "trade_requests": [], "recent_events": []}
    base.update(kw)
    return base


def test_strip_rows():
    s = pv.strip_view(_snap(zone="Clearfell", area_id="G1_2", area_level=2, level=4,
                            **{"class": "Sorceress"}, level_ups=1, zone_entered_at=NOW - 30,
                            death_recap={"recent": [{"zone": "Clearfell", "at": NOW - 5},
                                                    {"zone": "Clearfell", "at": NOW - 99}]}))
    assert s == {"zone": "Clearfell", "sub": "Act 1 - area level 2", "level_sub": "Sorceress",
                 "deaths_sub": "1 this zone", "session_sub": "1 level-up", "fresh": True}
    under = pv.strip_view(_snap(zone="Clearfell", level=4, area_level=9,
                                underlevel={"word": "5 lv under"}, **{"class": "Witch"}))
    assert under["level_sub"] == "5 lv under"
    maps = pv.strip_view(_snap(zone="Crypt", area_id="MapCrypt", area_level=65, level=70,
                               maps={"count": 4, "per_hour": 5.2,
                                     "current": {"inside": True, "deaths": 2}}))
    assert maps["deaths_sub"] == "2 this map" and maps["session_sub"] == "4 maps, 5/h"
    assert maps["sub"] == "Map - area level 65"
    five = [{"zone": "Crypt", "at": NOW - i} for i in range(5)]
    assert pv.strip_view(_snap(zone="Crypt", death_recap={"recent": five}))["deaths_sub"] \
        == "5+ this zone"
    idle = pv.strip_view(_snap(zone="Clearfell", area_id="G1_2", area_level=2, level=4,
                               game_idle=True, afk=True, dnd=True,
                               tailer={"consented": True, "idle": True,
                                       "last_line_at": NOW - 1200}))
    assert idle["fresh"] is False
    assert idle["sub"] == f"Act 1 - frozen {pv.clock(NOW - 1200)}, AFK, DND"
    hide = pv.strip_view(_snap(zone="Hideout", area_level=65, in_hideout=True))
    assert hide["sub"] == "area level 65 - hideout"
    empty = pv.strip_view(_snap())
    assert empty == {"zone": None, "sub": "", "level_sub": "", "deaths_sub": "",
                     "session_sub": "", "fresh": True}


def test_feed_rows_newest_trade_first_and_new_for_60_s():
    trades = [{"id": 1, "at": NOW - 200, "text": "A wants X - 5 exalted", "where": "tab S (1,2)"},
              {"id": 2, "at": NOW - 10, "text": "B wants Y - no price set", "where": ""}]
    f = pv.feed_view(_snap(trade_requests=trades))
    assert [t["id"] for t in f["trades"]] == [2, 1]
    assert f["trades"][0] == {"id": 2, "lead": "B wants Y - no price set", "right": "new",
                              "title": "B wants Y - no price set"}
    assert f["trades"][1] == {"id": 1, "lead": "A wants X - 5 exalted",
                              "right": "tab S (1,2), 3m",
                              "title": "A wants X - 5 exalted (tab S (1,2))"}
    assert f["events"] == {"death": None, "level": None, "zone": None}


def test_event_rows_drop_the_name_before_the_cap():
    who = "N" * 40
    snap = _snap(character=who, zone="Clearfell", zone_entered_at=NOW - 120,
                 death_recap={"recent": [{"zone": "Clearfell", "level": 3, "at": NOW - 30}]},
                 recent_events=[{"type": "level_up", "at": NOW - 90,
                                 "text": f"{who} reached level 3"}])
    ev = pv.feed_view(snap)["events"]
    assert ev["death"]["text"] == "Died in Clearfell"
    assert ev["death"]["title"] == f"{who} died in Clearfell at level 3"
    assert ev["death"]["right"] == "new, " + pv.clock(NOW - 30)
    assert ev["level"]["text"] == "Reached level 3"
    assert ev["level"]["right"] == pv.clock(NOW - 90)
    assert ev["zone"] == {"kind": "zone", "tag": "Zone", "text": "Entered Clearfell",
                          "right": pv.clock(NOW - 120), "title": "Entered Clearfell",
                          "at": NOW - 120}
    short = pv.feed_view(_snap(character="Emberdemo", in_hideout=True, zone="Hideout",
                               recent_events=[{"type": "level_up", "at": NOW,
                                               "text": "Emberdemo reached level 9"}]))
    assert short["events"]["level"]["text"] == "Emberdemo reached level 9"
    assert short["events"]["zone"]["text"] == "Entered Hideout (hideout)"


def _check(cid, label, status, detail, fix=None):
    return {"id": cid, "label": label, "status": status, "detail": detail, "fix": fix}


def test_notices_every_kind_in_pick_order():
    snap = _snap(
        build={"loaded": False},
        diag={"checks": [
            _check("log", "Client.txt", "pass", "Found."),
            _check("web_data", "Web data", "off", "Off."),
            _check("hotkey", "Item check hotkey", "fail", "Not registered.",
                   "Another app holds the shortcut."),
            _check("snapshot", "Game data", "fail", "Not fetched yet.",
                   r"Run scripts\build.ps1 -Snapshot to fetch it."),
        ]},
        lang={"verdict": "non_english", "works": "zone, act and map times"})
    got = pv.notices_view(snap)
    assert [n["kind"] for n in got] == [1, 3, 4, 5]
    assert got[0] == {"kind": 1, "state": "failed", "glyph": "[x]", "word": "Broken",
                      "title": "Item check hotkey",
                      "rows": ["Not registered. Another app holds the shortcut."],
                      "action": "Open Checks"}
    assert got[1] == {"kind": 3, "state": "needs-operator", "glyph": "[?]", "word": "Language",
                      "title": "Not English",
                      "rows": ["AshLight reads only the English game text.",
                               "Zone, act and map times still work."],
                      "action": "Open Checks"}
    assert got[2] == {"kind": 4, "state": "pending", "glyph": "[ ]", "word": "Setup",
                      "title": "2 steps left",
                      "rows": ["Still to set: your build and prices.",
                               "All optional; Settings has the controls."],
                      "action": "Settings"}
    assert (got[3]["state"], got[3]["glyph"], got[3]["word"], got[3]["title"]) == (
        "idle", "[-]", "Note", "Game data")
    assert got[3]["rows"] == ["Not fetched yet. Run scripts\\build.ps1 -Snapshot to",
                              "fetch it."]


def test_a_new_character_tip_outranks_setup_for_its_window():
    # PV-1: web data off by default and no build would hold Setup forever;
    # while the tip is on show Setup is not queued, then it comes back
    base = dict(build={"loaded": False},
                diag={"checks": [_check("web_data", "Web data", "off", "Off.")]})
    tip = {"id": "campaign_death", "text": "Deaths in the campaign cost no experience."}
    got = pv.notices_view(_snap(hint=tip, **base))
    assert got == [{"kind": 6, "state": "idle", "glyph": "[-]", "word": "Tip",
                    "title": "Campaign deaths",
                    "rows": ["Deaths in the campaign cost no experience."], "action": ""}]
    after = pv.notices_view(_snap(hint=None, **base))
    assert [(n["kind"], n["word"], n["title"]) for n in after] == [(4, "Setup", "2 steps left")]
    # a real fault still outranks the tip
    broken = dict(base, diag={"checks": [_check("calc", "Calc component", "fail", "Missing.")]})
    assert [n["kind"] for n in pv.notices_view(_snap(hint=tip, **broken))] == [1, 6]


def test_death_sentence_keeps_the_character_before_the_zone():
    # PV-4: subject first; the zone goes before the character name
    snap = _snap(character="Emberwhisperofthe", zone="Clearfell",
                 death_recap={"recent": [{"zone": "The Grelwood Outskirts Far",
                                          "level": 12, "at": NOW}]})
    ev = pv.feed_view(snap)["events"]["death"]
    assert ev["text"] == "Emberwhisperofthe died at level 12"
    assert ev["title"] == "Emberwhisperofthe died in The Grelwood Outskirts Far at level 12"


def test_no_broken_part_notice_while_reading_is_down():
    snap = _snap(tailer={"consented": True, "reading": False, "path": "x"},
                 diag={"checks": [_check("calc", "Calc component", "fail", "Missing.")]})
    assert [n["kind"] for n in pv.notices_view(snap)] == []
    assert pv.notices_view(_snap(tailer={"consented": False})) == []


def test_build_line_states():
    assert pv.build_view(_snap(build={"loaded": False})) == {
        "state": "none", "kit": "pending", "glyph": "[ ]", "word": "No build", "row1": "",
        "row2": "Copy a PoB code, then check it.", "can_paste": True,
        "switch": None}  # ACTIVE-BUILD-PICK: nothing to switch to
    fits = pv.build_view(_snap(sources={"calc_on": True},
                               build={"loaded": True, "class_name": "Ranger",
                                      "ascendancy": "Deadeye", "level": 92}))
    assert (fits["state"], fits["glyph"], fits["word"], fits["row1"], fits["row2"]) == (
        "fits", "[+]", "Build fits", "Deadeye, level 92", "Checks use Path of Building numbers.")
    old = pv.build_view(_snap(build_alert={"kind": "level"}))
    assert (old["state"], old["glyph"], old["word"]) == ("old", "[?]", "Old build")
    wrong = pv.build_view(_snap(build_alert={"kind": "class"}))
    assert (wrong["state"], wrong["word"], wrong["can_paste"]) == ("wrong_class", "Wrong class",
                                                                   False)
    missing = pv.build_view(_snap(build_alert={"kind": "missing"}))
    assert missing["state"] == "none" and missing["can_paste"] is True


def test_build_fix_names_the_bound_item_key():
    # UX-BUILD-FIX-KEY (docs/reviews/ux/2026-11-28.md P2-9): the bound key
    # of the published hotkeys view, else the key-free form
    def row2(hotkeys, **kw):
        snap = _snap(build={"loaded": False}, **kw)
        if hotkeys is not None:
            snap["hotkeys"] = hotkeys
        return pv.build_view(snap)["row2"]

    keyed = row2({"eval": {"key": "Alt+Shift+E", "registered": True}})
    assert keyed == "Copy a PoB code, press Alt+Shift+E."
    assert len(keyed) <= pv.CAP_BUILD_ROW
    assert row2({"eval": {"key": "Ctrl+Alt+F9"}},
                build_alert={"kind": "class"}) == "Copy a PoB code, press Ctrl+Alt+F9."
    plain = "Copy a PoB code, then check it."
    assert pv.BUILD_FIX == plain
    # no view, no eval entry, no key, a bad type or a non-ASCII key
    for hk in (None, {}, {"eval": None}, {"eval": {"key": None}}, {"eval": {"key": ""}},
               {"eval": {"key": 7}}, {"eval": {"key": "Alt+" + chr(0xE9)}}, "Alt+E"):
        assert row2(hk) == plain, hk
    # a key too long for the 36 cap falls back, never clipped
    assert row2({"eval": {"key": "Ctrl+Shift+Alt+F12"}}) == plain


def test_long_text_everywhere_stays_under_the_caps():
    long = ps.text_at(400)
    snap = _snap(
        character=ps.LONG_CHARACTER, zone=ps.LONG_ITEMS[0], level=3, area_level=2,
        area_id="G1_2", game_idle=True, afk=True, dnd=True, in_hideout=True,
        tailer={"consented": True, "reading": True, "idle": True, "last_line_at": NOW},
        underlevel={"word": "12 lv under"}, level_ups=99,
        maps={"count": 999, "per_hour": 99.4, "current": {"inside": True, "deaths": 999}},
        death_recap={"recent": [{"zone": long, "level": 99, "at": NOW}]},
        recent_events=[{"type": "level_up", "at": NOW, "text": long}],
        diag={"checks": [_check(c, long, "fail", long, long) for c in pv.PART_CHECKS]
              + [_check(c, long, "note", long) for c in pv.DATA_CHECKS]},
        lang={"verdict": "non_english", "works": long},
        hint={"id": "x", "text": long},
        build={"loaded": True, "class_name": long, "level": 99},
        build_alert={"kind": "class"})
    play = pv.view(snap)
    _assert_caps(play, names=[long, ps.LONG_ITEMS[0], ps.LONG_CHARACTER])
    ev = play["feed"]["events"]
    assert ev["death"]["text"] == "Died at level 99"
    assert ev["level"]["text"] == "Reached a new level"
    assert [n["kind"] for n in play["notices"]] == [1] * len(pv.PART_CHECKS) + [3, 5, 5, 6]


# -- the evidence-pack states -------------------------------------------------------

def _clock_right(ev):
    return "new, " + pv.clock(ev["at"])


EXPECT = {
    "a": {
        "strip": {"zone": None, "sub": "", "level_sub": "", "deaths_sub": "",
                  "session_sub": "", "fresh": True},
        "trades": [], "events": {"death": None, "level": None, "zone": None},
        "notices": [], "build": ("none", "No build", "", "Copy a PoB code, then check it."),
    },
    "a2": {
        "strip": {"zone": None, "sub": "", "level_sub": "", "deaths_sub": "",
                  "session_sub": "", "fresh": True},
        "trades": [], "events": {"death": None, "level": None, "zone": None},
        "notices": [(4, "[ ]", "Setup", "1 step left",
                     ["Still to set: your build.", "It is optional; Settings has the control."],
                     "Settings")],
        "build": ("none", "No build", "", "Copy a PoB code, then check it."),
    },
    "b": {
        "strip": {"zone": "Clearfell", "sub": "Act 1 - area level 2", "level_sub": "Sorceress",
                  "deaths_sub": "1 this zone", "session_sub": "3 level-ups", "fresh": True},
        "trades": [],
        "events": {"death": "Emberdemo died in Clearfell", "level": "Emberdemo reached level 4",
                   "zone": "Entered Clearfell"},
        "notices": [(6, "[-]", "Tip", "Campaign deaths",
                     ["Campaign deaths cost no experience. The Deaths card",
                      "shows where each one happened."], "")],
        "build": ("none", "No build", "", "Copy a PoB code, then check it."),
    },
}
C_TRADES = [("Secondbuyer_WithALongAccountName wants Example Unique Quarterstaff of Many Words"
             " - 40 exalted", "new, tab Sale (1,10)"),
            ("Firstbuyer wants Grim Bane Ruby Ring - 5 exalted", "new, tab Sale (11,11)")]
CAMPAIGN_TIP = (6, "[-]", "Tip", "Campaign deaths",
                ["Campaign deaths cost no experience. The Deaths card",
                 "shows where each one happened."], "")
WRONG_CLASS = ("wrong_class", "Wrong class", "Ranger, level 80",
               "Copy a PoB code, then check it.")
for _name in ("c", "c2", "d", "c5"):
    EXPECT[_name] = dict(EXPECT["b"], trades=C_TRADES, notices=[CAMPAIGN_TIP],
                         build=WRONG_CLASS)
EXPECT["c5"]["trades"] = [("Fifthbuyer wants Example Iron Ring - 1 exalted", "new, tab Sale (3,5)"),
                          ("Fourthbuyer wants Example Leather Boots - 3 exalted",
                           "new, tab Sale (1,9)"),
                          ("Thirdbuyer wants Example Amber Amulet - 12 exalted",
                           "new, tab Sale (7,1)")] + C_TRADES
EXPECT["d"]["strip"] = dict(EXPECT["b"]["strip"], sub="area level 2 - frozen {last}",
                            fresh=False)
EXPECT["e"] = dict(EXPECT["a"], notices=[
    (4, "[ ]", "Setup", "2 steps left",
     ["Still to set: your build and prices.", "All optional; Settings has the controls."],
     "Settings")])
MAP_STRIP = {"zone": "Sun Temple", "sub": "area level 66", "level_sub": "56 lv under",
             "deaths_sub": "0 this map", "session_sub": "2 maps", "fresh": True}
MAP_EVENTS = {"death": "Ashdemo died in Crypt", "level": "Ashdemo reached level 10",
              "zone": "Entered Sun Temple"}
MAP_TIP = (6, "[-]", "Tip", "First map",
           ["Your first map. Unlike the campaign, deaths in", "endgame maps cost experience."],
           "")
FITS = ("fits", "Build fits", "Ranger, level 80", "Checks use your stat weights.")
EXPECT["f"] = {"strip": MAP_STRIP, "events": MAP_EVENTS, "build": FITS,
               "trades": [("Secondbuyer wants Example Unique - 40 exalted",
                           "new, tab Sale (6,8)")],
               "notices": [MAP_TIP]}
EXPECT["g"] = dict(EXPECT["f"], notices=[MAP_TIP])
EXPECT["map"] = dict(EXPECT["g"], trades=[
    ("Secondbuyer wants Example Unique - 40 exalted", "new, tab Sale (6,8)"),
    ("Firstbuyer wants Grim Bane Ruby Ring - 5 exalted", "new, tab Sale (8,4)")])


def _check_rows(name, snap):
    play = snap["play"]
    want = EXPECT[name]
    strip = dict(want["strip"])
    if "{last}" in strip["sub"]:
        strip["sub"] = strip["sub"].format(last=pv.clock(snap["tailer"]["last_line_at"]))
    assert play["strip"] == strip
    assert [(t["lead"], t["right"]) for t in play["feed"]["trades"]] == want["trades"]
    assert [t["id"] for t in play["feed"]["trades"]] == sorted(
        (r["id"] for r in snap["trade_requests"]), reverse=True)
    events = play["feed"]["events"]
    assert {k: (e["text"] if e else None) for k, e in events.items()} == want["events"]
    for kind, ev in events.items():
        if ev:
            assert ev["tag"] == pv.EVENT_TAGS[kind] and ev["right"] == _clock_right(ev)
    if events["zone"]:
        assert events["zone"]["at"] == snap["zone_entered_at"]
    if events["death"]:
        assert events["death"]["at"] == snap["death_recap"]["recent"][0]["at"]
    got = [(n["kind"], n["glyph"], n["word"], n["title"], n["rows"], n["action"])
           for n in play["notices"]]
    assert got == want["notices"]
    b = play["build"]
    assert (b["state"], b["word"], b["row1"], b["row2"]) == want["build"]
    assert b["can_paste"] is (b["state"] == "none")
    assert play["map_ok"] is False


def _names(snap):
    out = [snap.get("character"), snap.get("zone"), snap.get("class")]
    for r in snap.get("trade_requests") or ():
        out += [r.get("from"), r.get("item"), r.get("stash_tab")]
    for r in (snap.get("death_recap") or {}).get("recent") or ():
        out.append(r.get("zone"))
    b = snap.get("build") or {}
    out += [b.get("class_name"), b.get("ascendancy")]
    return [n for n in out if isinstance(n, str) and n]


def _unnamed(text, names):
    for n in sorted(names, key=len, reverse=True):
        text = text.replace(n, "N")
    return text


def _composed_words(text, names):
    for n in sorted(names, key=len, reverse=True):
        text = text.replace(n, " ")
    return pv.words(text)


def _assert_caps(play, names):
    """Every composed row under its cap; G5 words per region with names
    left out (they are data)."""
    for ev in play["feed"]["events"].values():
        if ev:
            # a name in the sentence takes the ellipsis; the rest fits
            assert len(_unnamed(ev["text"], names)) <= pv.CAP_EVENT_SENTENCE, ev
    for n in play["notices"]:
        assert len(n["glyph"] + " " + n["word"]) <= pv.CAP_NOTICE_WORD, n
        assert len(n["title"]) <= pv.CAP_NOTICE_TITLE, n
        assert len(n["action"]) <= pv.CAP_NOTICE_ACTION, n
        assert len(n["rows"]) <= pv.NOTICE_ROWS, n
        assert all(len(r) <= pv.CAP_NOTICE_ROW for r in n["rows"]), n
        head = [n["word"], n["title"], n["action"]] + n["rows"]
        assert sum(_composed_words(t, names) for t in head) <= pv.WORDS_NOTICE - 2, n
    b = play["build"]
    assert len(b["row2"]) <= pv.CAP_BUILD_ROW, b
    bwords = sum(_composed_words(t, names) for t in (b["word"], b["row1"], b["row2"]))
    assert bwords + (3 if b["can_paste"] else 0) <= pv.WORDS_BUILD, b
    s = play["strip"]
    assert len(s["sub"]) <= pv.CAP_STRIP_SUB, s
    subs = sum(_composed_words(s[k], names)
               for k in ("sub", "level_sub", "deaths_sub", "session_sub"))
    assert subs <= pv.STRIP_SUB_WORDS, s
    feed = play["feed"]
    fwords = 0
    for t in feed["trades"]:
        fwords += 1 + _composed_words(t["lead"], names) + _composed_words(t["right"], names) + 1
    for ev in feed["events"].values():
        if ev and len(feed["trades"]) < 5:
            fwords += 1 + _composed_words(ev["text"], names) + pv.words(ev["right"])
    assert fwords <= pv.WORDS_FEED, fwords


ROW_STATES = tuple(EXPECT)


@pytest.mark.slow  # wave 30 ruling: over the 3 s ceiling under parallel load
@pytest.mark.server
@pytest.mark.parametrize("name", ROW_STATES)
def test_pack_state_rows_are_exact(name, tmp_path):
    with ps.open_state(name, tmp_path / name) as st:
        snap = st.state()
    _check_rows(name, snap)
    _assert_caps(snap["play"], _names(snap))
    assert snap["play"] == pv.view({k: v for k, v in snap.items() if k != "play"})


@pytest.mark.server
def test_long_string_fixture_stays_under_every_cap(tmp_path):
    with ps.open_state("long", tmp_path / "long") as st:
        snap = st.state()
    play = snap["play"]
    _assert_caps(play, _names(snap))
    ev = play["feed"]["events"]
    for e in ev.values():
        assert len(e["text"]) <= ps.CAP_EVENT_SENTENCE, e
    assert ev["death"]["text"] == "Died in Clearfell"
    assert ev["level"]["text"] == "Reached level 3"
    assert ev["death"]["title"].startswith(ps.LONG_CHARACTER)
    trades = play["feed"]["trades"]
    assert len(trades) == ps.LONG_TRADES
    for t, buyer, item in zip(trades, reversed(ps.LONG_BUYERS), reversed(ps.LONG_ITEMS)):
        # names are data: never cut
        assert t["lead"].startswith(f"{buyer} wants {item} - ")
        assert t["right"].startswith("new, tab Sale (")
    assert play["build"]["state"] == "wrong_class"
    assert len(play["build"]["row2"]) <= ps.CAP_BUILD_ROW
    for n in play["notices"]:
        assert all(len(r) <= ps.CAP_NOTICE_ROW for r in n["rows"])
    assert not math.isnan(snap["now"])
    assert state_mod.EVAL_CARD_S == 20
