"""TC-EVAL-UI: exact output of every item check template (design 0001
section 9 rule 10) and the live state wiring (TC-VIEW build summary, last
item check re-scored on a weights or build change)."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al.core import Core
from server.al.http import serve
from server.al.state import (EVAL_CARD_S, SessionState, build_alert_text, eval_card_text,
                             stat_delta_text)
from server.al.theorycraft import codec, live
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, RARE_GLOVES


def test_stat_delta_text():
    assert stat_delta_text("+# to maximum Life", 30) == "+30 to maximum Life"
    assert stat_delta_text("+#% to Lightning Resistance", -10) == "-10% to Lightning Resistance"
    assert stat_delta_text("#% increased Attack Speed", 12) == "+12% increased Attack Speed"
    assert stat_delta_text("#% increased Attack Speed", -12.25) == "-12.2% increased Attack Speed"
    assert stat_delta_text("Adds # to # Lightning Damage to Attacks", 21) == \
        "+21 average Lightning Damage to Attacks"
    assert stat_delta_text("Cannot be Example Frozen", 1) == "Gains: Cannot be Example Frozen"
    assert stat_delta_text("Cannot be Example Frozen", -1) == "Loses: Cannot be Example Frozen"
    assert stat_delta_text(None, 0) == "Gains: an unknown stat"


def comp(slot, verdict, delta, name="Weak Loop", empty=False, stats=()):
    return {"slot": slot, "verdict": verdict, "score_delta": delta, "empty": empty,
            "equipped": None if empty else {"name": name, "base": "Example Ring"},
            "stats": list(stats)}


LIFE = {"key": "+# to maximum Life", "delta": 35, "score_delta": 35, "weighted": True}
ODD = {"key": "Some odd stat #", "delta": 4, "score_delta": 0, "weighted": False}


# TC-VERDICT-CAVEAT (F-042): the no-build sentence names the item-key load
NO_BUILD_SENTENCE = ("No build loaded yet. Paste a Path of Building code under Build, "
                     "or copy the code in Path of Building and press the item key, "
                     "then check the item again.")
# the three build alerts (buildlive.alert findings) and their short heads
ALERTS = (
    ({"kind": "missing", "character": "Sable"}, "No build for Sable"),
    ({"kind": "class", "character": "Sable", "build_class": "Ranger",
      "log_class": "Witch"}, "Build is for a Ranger"),
    ({"kind": "level", "character": "Sable", "build_level": 62, "level": 70},
     "Build is from level 62"),
)


def card(**kw):
    base = {"ok": True, "error": None, "verdict": "upgrade", "slot": "Ring 1",
            "score_delta": 47.5, "unidentified": False,
            "item": {"name": "Storm Loop", "base": "Example Ring"},
            "comparisons": [comp("Ring 1", "upgrade", 47.5, stats=[ODD, LIFE]),
                            comp("Ring 2", "downgrade", -1, name="Strong Loop")]}
    base.update(kw)
    return base


def test_upgrade_card_text():
    t = eval_card_text(card())
    assert t["head"] == "Upgrade +47.5 vs Ring 1"
    assert t["item"] == "Storm Loop"
    assert t["line"] == "+35 to maximum Life"
    assert t["sentence"] == "Upgrade: 47.5 points more than your Ring 1 (Weak Loop)."
    assert t["comparisons"][1]["sentence"] == \
        "Downgrade: 1 point less than your Ring 2 (Strong Loop)."
    assert t["comparisons"][0]["stats"] == [
        {"text": "+Some odd stat 4", "points": "not counted"},
        {"text": "+35 to maximum Life", "points": "+35 points"}]
    # TC-CARD-PARTS: the mark's word and tone; no part notes without parts
    assert (t["notes"], t["word"], t["tone"], t["answers"]) == ([], "Upgrade", "upgrade", False)


def test_sidegrade_empty_slot_and_unidentified():
    side = card(verdict="sidegrade", slot="Belt", score_delta=0.4,
                comparisons=[comp("Belt", "sidegrade", 0.4, name="Cord")])
    t = eval_card_text(side)
    assert t["head"] == "Sidegrade +0.4 vs Belt"
    assert t["sentence"] == "Sidegrade: about the same as your Belt (Cord), +0.4 points."
    assert t["line"] == "No counted stat changes"
    assert (t["notes"], t["word"], t["tone"]) == ([], "Sidegrade", "sidegrade")
    empty = card(slot="Boots", score_delta=45,
                 comparisons=[comp("Boots", "upgrade", 45, empty=True, stats=[LIFE])])
    one = card(verdict="sidegrade", slot="Belt", score_delta=1,
               comparisons=[comp("Belt", "sidegrade", 1, name="Cord",
                                 stats=[dict(LIFE, delta=1, score_delta=-1)])])
    t = eval_card_text(one)
    assert t["sentence"] == "Sidegrade: about the same as your Belt (Cord), +1 point."
    assert t["comparisons"][0]["stats"][0]["points"] == "-1 point"
    t = eval_card_text(empty)
    assert t["head"] == "Upgrade +45 - Boots empty"
    assert t["sentence"] == "Upgrade: your build has nothing in Boots (+45 points)."
    t = eval_card_text(card(unidentified=True, item={"name": None, "base": "Example Ring"}))
    assert t["item"] == "Example Ring (unidentified)"
    assert t["line"] == "Mods hidden: identify it"


def test_delta_head_drops_the_slot_name_over_26():
    """CARD-LINE-LIMIT-COPY: the item check head keeps the verdict and the
    number whole; over 26 characters the slot name drops (the dashboard
    sentence still names it)."""
    t = eval_card_text(card(slot="Body Armour", score_delta=-1234.5, verdict="downgrade",
                            comparisons=[comp("Body Armour", "downgrade", -1234.5)]))
    assert t["head"] == "Downgrade -1234.5"
    assert "Body Armour" in t["sentence"]
    t = eval_card_text(card(slot="Body Armour", score_delta=12,
                            comparisons=[comp("Body Armour", "upgrade", 12)]))
    assert t["head"] == "Upgrade +12 vs Body Armour" and len(t["head"]) == 26
    t = eval_card_text(card(slot="Body Armour", score_delta=12,
                            comparisons=[comp("Body Armour", "upgrade", 12, empty=True)]))
    assert t["head"] == "Upgrade +12 - slot empty"
    t = eval_card_text(card(slot="Gloves", score_delta=5,
                            comparisons=[comp("Gloves", "upgrade", 5, empty=True)]))
    assert t["head"] == "Upgrade +5 - Gloves empty"
    t = eval_card_text(card(slot="Weapon 1", score_delta=123.5,
                            comparisons=[comp("Weapon 1", "upgrade", 123.5, empty=True)]))
    assert t["head"] == "Upgrade +123.5"
    for slot in ("Weapon 1", "Body Armour", "Charm 3"):
        for verdict, delta in (("upgrade", 99999.5), ("sidegrade", -0.5), ("downgrade", -12.5)):
            for empty in (False, True):
                c = card(verdict=verdict, slot=slot, score_delta=delta,
                         comparisons=[comp(slot, verdict, delta, empty=empty)])
                assert len(eval_card_text(c)["head"]) <= 26, (slot, delta, empty)


def test_error_card_text():
    t = eval_card_text({"ok": False, "error": "no build loaded",
                        "item": {"name": "Grim Clutch"}})
    assert (t["head"], t["item"], t["line"]) == \
        ("No build loaded", "Grim Clutch", "Paste a build first")
    assert t["sentence"] == NO_BUILD_SENTENCE
    assert (t["notes"], t["word"], t["tone"], t["answers"]) == (
        [], "Not checked", "note", False)
    # RUN-NO-DEAD-ENDS (research 0042 F20 d): a press with no item names none
    t = eval_card_text({"ok": False, "error": "not an item", "item": {}})
    assert (t["head"], t["item"], t["line"]) == \
        ("Not an item", "", "Copy an item in game first")
    t = eval_card_text({"ok": False, "error": "no gear slot for this item class"})
    assert (t["head"], t["line"]) == ("Can't compare this", "Only gear is compared")
    # OVL-COPY-FIRST (F-054): a press before the game wrote the clipboard
    t = eval_card_text({"ok": False, "error": "empty clipboard", "item": {}})
    assert (t["head"], t["item"], t["line"]) ==         ("Copy the item first", "", "Hover it, press Ctrl+C")
    assert t["sentence"] == ("The clipboard was empty when you pressed the hotkey. Hover "
                             "an item in game, press Ctrl+C, then press the hotkey again.")
    assert (t["notes"], t["word"], t["tone"], t["answers"]) == (
        [], "Not checked", "note", False)
    t = eval_card_text({"ok": False, "error": "something new"})
    assert (t["head"], t["line"]) == ("Can't check this item", "See the dashboard")
    for t in (eval_card_text(None), eval_card_text({})):
        assert "None" not in str(t) and "undefined" not in str(t)


def test_every_mark_has_a_word():
    """TC-CARD-PARTS (F-043): every verdict mark is paired with a word."""
    down = eval_card_text(card(verdict="downgrade", score_delta=-3))
    assert (down["word"], down["tone"]) == ("Downgrade", "downgrade")
    odd = eval_card_text(card(verdict=None))
    assert (odd["word"], odd["tone"]) == ("Checked", "")
    risky = {"ok": False, "error": "no gear slot for this item class",
             "waystone": {"tier": 5, "risky": [{"label": "Monsters fire extra projectiles",
                                                "short": "Extra projectiles"}]}}
    t = eval_card_text(risky)
    assert (t["word"], t["tone"], t["notes"]) == ("Risky", "risky", [])
    t = eval_card_text(dict(risky, waystone={"tier": 5, "risky": []}))
    assert (t["word"], t["tone"]) == ("No risky mods", "note")
    t = eval_card_text(dict(risky, waystone={"tier": 5, "unidentified": True,
                                             "risky": risky["waystone"]["risky"]}))
    assert (t["word"], t["tone"]) == ("Not checked", "note")
    for t in (eval_card_text(None), eval_card_text({})):
        assert (t["notes"], t["word"], t["tone"], t["answers"]) == (
            [], "Not checked", "note", False)


def test_overlay_lines_fit_the_card():
    """Section 9 rule 6: the head and line of the common cases fit 34;
    CARD-LINE-LIMIT-COPY: without an alert they are worded to fit 26."""
    for c in (card(), card(slot="Body Armour", score_delta=-1234.5, verdict="downgrade"),
              card(unidentified=True),
              {"ok": False, "error": "no build loaded"},
              {"ok": False, "error": "no gear slot for this item class"},
              {"ok": False, "error": "empty clipboard"}):
        t = eval_card_text(c)
        assert len(t["head"]) <= 26 and len(t["line"]) <= 26, t
        # TC-VERDICT-CAVEAT: with any build alert, worst cases included
        long_name = "Q" * 23
        for alert in [a for a, _short in ALERTS] + [
                {"kind": "missing", "character": long_name},
                {"kind": "class", "character": long_name,
                 "build_class": "Acolyte of Chayula", "log_class": "Witch"},
                {"kind": "class", "build_class": "X" * 40},
                {"kind": "level", "build_level": 10 ** 40, "level": 1}]:
            t = eval_card_text(c, alert)
            assert len(t["head"]) <= 34 and len(t["line"]) <= 34, (t, alert)


def test_alert_head_takes_line3():
    """TC-VERDICT-CAVEAT (F-043): while a build alert is set, a compared
    item's line 3 is the alert's short head (exact, at most 34) and the
    alert sentence is the first dashboard note; the verdict stays."""
    for alert, short in ALERTS:
        words = build_alert_text(alert)
        assert words["short"] == short and len(short) <= 26
        t = eval_card_text(card(), alert)
        assert (t["head"], t["item"], t["line"]) == (
            "Upgrade +47.5 vs Ring 1", "Storm Loop", short)
        assert t["notes"] == [words["text"]]
        assert (t["word"], t["tone"]) == ("Upgrade", "upgrade")
    assert eval_card_text(card(), None) == eval_card_text(card())
    # articles and fallbacks for long names and classes
    assert build_alert_text({"kind": "class", "build_class": "Invoker",
                             "log_class": "Ranger"})["short"] == "Build is for an Invoker"
    # CARD-LINE-LIMIT-COPY2: shorts fit 26 (a 13-character name just fits)
    assert build_alert_text({"kind": "missing"})["short"] == "No build saved"
    assert build_alert_text({"kind": "missing", "character": "Q" * 13})["short"] ==         "No build for " + "Q" * 13
    assert build_alert_text({"kind": "missing", "character": "Q" * 14})["short"] ==         "No build saved"
    assert build_alert_text({"kind": "class", "build_class": "X" * 40})["short"] ==         "Build is for another class"
    assert build_alert_text({"kind": "class"})["short"] == "Build is for another class"
    assert build_alert_text({"kind": "level", "build_level": 10 ** 40})["short"] ==         "Build is for a lower level"
    # an unidentified item keeps naming the input it lacks; the note stays
    alert = ALERTS[0][0]
    t = eval_card_text(card(unidentified=True), alert)
    assert t["line"] == "Mods hidden: identify it"
    assert t["notes"] == [build_alert_text(alert)["text"]]
    # error and waystone cards are left as they are
    for c in ({"ok": False, "error": "no build loaded"},
              {"ok": False, "error": "not an item"},
              {"ok": True, "waystone": {"tier": 5, "risky": []}}):
        assert eval_card_text(c, alert) == eval_card_text(c)
    # junk alerts change nothing
    for junk in ({}, {"kind": "new"}, "missing", 5):
        assert eval_card_text(card(), junk) == eval_card_text(card())


def test_state_eval_and_build_fields():
    now = [1000.0]
    st = SessionState(clock=lambda: now[0])
    snap = st.snapshot()
    assert snap["eval"] is None and snap["build"] is None
    v = snap["version"]
    st.set_eval(live.compact({"ok": False, "error": "not an item"}))
    snap = st.snapshot()
    assert snap["version"] == v + 1
    assert snap["eval"]["at"] == 1000.0 and snap["eval"]["expires_at"] == 1000.0 + EVAL_CARD_S
    assert snap["eval"]["text"]["head"] == "Not an item"
    now[0] = 1005.0
    st.set_eval(live.compact({"ok": False, "error": "no build loaded"}), keep_time=True)
    assert st.snapshot()["eval"]["at"] == 1000.0
    st.set_eval(live.compact({"ok": False, "error": "no build loaded"}))
    assert st.snapshot()["eval"]["at"] == 1005.0
    st.set_build_info(live.build_info(None))
    v = st.snapshot()["version"]
    st.set_build_info(live.build_info(None))
    assert st.snapshot()["version"] == v  # unchanged info: no push


def test_compact_trims_and_never_raises():
    assert live.compact(None)["ok"] is False
    rows = [{"key": f"k{i}", "delta": 1, "score_delta": 1, "weighted": True} for i in range(20)]
    rows.append({"key": "same", "delta": 0, "score_delta": 0, "weighted": True})
    c = live.compact({"ok": True, "comparisons": [{"slot": "Belt", "stats": rows}] * 5,
                      "unweighted": [str(i) for i in range(30)]})
    assert len(c["comparisons"]) == live.MAX_COMPARISONS
    assert len(c["comparisons"][0]["stats"]) == live.MAX_STATS
    assert all(s["key"] != "same" for s in c["comparisons"][0]["stats"])
    assert len(c["unweighted"]) == live.MAX_LIST


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    yield c
    c.close()


def test_core_rescores_on_weights_and_build_change(core):
    assert core.state.snapshot()["build"]["loaded"] is False
    core.last_eval.run(ADVANCED_RING)
    first = core.state.snapshot()["eval"]
    assert first["error"] == "no build loaded"
    core.builds.load_code(codec.encode(EVAL_BUILD_XML))
    snap = core.state.snapshot()
    assert snap["build"] == {"loaded": True, "rev": 1, "class_name": "Ranger",
                             "ascendancy": None, "level": 80, "character": None}
    assert snap["eval"]["ok"] and snap["eval"]["verdict"] == "upgrade"
    assert snap["eval"]["at"] == first["at"]  # a re-score keeps the card time
    core.weights.put({"weights": {"+# to maximum Life": 0}})
    core.last_eval.rerun()
    assert core.state.snapshot()["eval"]["score"] == 0


@pytest.mark.server
def test_api_eval_publishes_and_put_weights_rescores(tmp_path):
    root = Path(__file__).resolve().parents[1]
    token = "d" * 48
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    srv = serve(c, token, port=0, web_root=root / "web",
                tokens_css=root / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()

    def call(method, path, body):
        conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        conn.request(method, path, body=json.dumps(body).encode("ascii"),
                     headers={"Host": f"127.0.0.1:{srv.port}", "X-AL-Token": token,
                              "Content-Type": "application/json"})
        r = conn.getresponse()
        data = json.loads(r.read())
        conn.close()
        return r.status, data
    try:
        # OVL-COPY-FIRST: an empty clipboard at the hotkey press reads "Copy
        # the item first" and asks for no price check
        status, doc = call("POST", "/api/eval", {"item": ""})
        assert status == 200 and doc["error"] == "empty clipboard"
        assert c.state.snapshot()["eval"]["text"]["head"] == "Copy the item first"
        assert c.state.snapshot()["price"] is None
        call("POST", "/api/build-code", {"code": codec.encode(EVAL_BUILD_XML)})
        call("POST", "/api/eval", {"item": RARE_GLOVES})
        before = c.state.snapshot()["eval"]["score"]
        status, _ = call("PUT", "/api/weights", {"weights": {"+# to maximum Life": 10}})
        assert status == 200
        after = c.state.snapshot()["eval"]["score"]
        assert before != after and after == 700
    finally:
        srv.stop()
        c.close()


def test_blank_press_is_the_copy_first_card_and_asks_no_price(core):
    """OVL-COPY-FIRST (F-054): a blank or whitespace-only press publishes
    the "empty clipboard" status card, asks for no price check and leaves
    no item to re-score; an item press after it is checked as usual."""
    prices = []
    real = core.price.request
    core.price.request = lambda text, at=None: prices.append(text) or real(text, at=at)
    for blank in ("", "  \r\n\t "):
        doc = core.eval_press(blank)
        assert (doc["ok"], doc["error"]) == (False, "empty clipboard")
        ev = core.state.snapshot()["eval"]
        assert ev["error"] == "empty clipboard"
        assert (ev["text"]["head"], ev["text"]["line"]) == (
            "Copy the item first", "Hover it, press Ctrl+C")
        assert core.state.snapshot()["card"]["head"] == "Copy the item first"
    assert prices == [] and core.state.price is None
    assert core.last_eval.rerun() is None  # nothing to re-score
    assert core.state.snapshot()["eval"]["error"] == "empty clipboard"
    core.eval_press(RARE_GLOVES)
    assert prices == [RARE_GLOVES]
    assert core.state.snapshot()["eval"]["error"] == "no build loaded"


def test_blank_press_cancels_an_older_press_s_pending_stages(core):
    """OVL-COPY-FIRST: the blank press is a new press generation, so an
    older press's later stages publish nothing over its card."""
    gen = core.last_eval._gen
    core.eval_press("")
    assert core.last_eval._gen == gen + 1
    assert not core.last_eval.current(gen)


def test_rerun_without_an_item_is_a_no_op(core):
    assert core.last_eval.rerun() is None
    assert core.state.snapshot()["eval"] is None
    core.last_eval.run(RARE_GLOVES, "Gloves")
    assert core.state.snapshot()["eval"]["slot"] is None  # no build yet


def test_no_build_keep_part_words():
    """TC-CAMPAIGN-KEEP (decision 0057): with no build, the keep part of a
    gear card gives the Keep / Vendor word, head and notes; the overlay
    line keeps the build next step and the dashboard sentence stays."""
    keep = {"status": "keep", "level": 24, "need": 2, "of": 5, "count": 2, "missed": [],
            "met": [{"label": "life", "min": 25, "have": 31},
                    {"label": "fire res", "min": 12, "have": 14}]}
    base = {"ok": False, "error": "no build loaded", "item": {"name": "Grim Clutch"}}
    t = eval_card_text(dict(base, parts={"keep": keep}))
    assert (t["word"], t["tone"], t["answers"]) == ("Keep", "upgrade", True)
    assert (t["head"], t["item"], t["line"]) == (
        "Keep - 2 of 5 met, Lv 24", "Grim Clutch", "Paste a build first")
    assert t["sentence"] == NO_BUILD_SENTENCE
    assert t["notes"] == [
        "Worth keeping: it meets 2 of 5 levelling thresholds for level 24.",
        "Thresholds met: life 25+, fire res 12+."]
    vendor = dict(keep, status="vendor", count=0, met=[])
    t = eval_card_text(dict(base, parts={"keep": vendor}))
    assert (t["word"], t["tone"], t["head"]) == ("Vendor", "note",
                                                 "Vendor - 0 of 5 met, Lv 24")
    assert t["notes"] == [
        "Vendor: it meets 0 of 5 levelling thresholds for level 24, and 2 are needed."]
    t = eval_card_text(dict(base, parts={"keep": {"status": "no_level"}}))
    assert (t["word"], t["head"], t["answers"]) == ("Not checked", "No build loaded", False)
    assert t["notes"] == ["Keep or vendor needs your character level from Client.txt."]
