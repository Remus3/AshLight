"""F-131: one status vocabulary. server/al/data/status_words.json is the one
table; each state gives the table's Checks detail and fix through
server/al/diag.py, the two JS copies (web/status.js and
app/shared/render_gate.js) equal it, and the overlay words keep their
caps. The bar, overlay and strip surfaces are fed state by state in
app/test/statuswords.test.js."""

import json
from pathlib import Path

from server.al import diag, statuswords

ROOT = Path(__file__).resolve().parents[1]
NOW = 2_000_000_000.0
FIELDS = {"rank", "kit", "glyph", "bar", "overlay", "overlay_alone", "check_row", "check",
          "next", "fault"}

# Facts (diag.checks) that put the Checks view in each state that has a row.
GREEN = {"log_found": True, "consented": True, "reading": True,
         "last_line_at": NOW - 30, "idle": False, "character_seen": True,
         "lang": "english", "web_data": False, "calc_on": False,
         "snapshot": True, "overlay": True, "supervisor": True, "hotkey": True,
         "port": 8960}
FACTS = {
    "reading": {},
    "off": {"consented": False, "reading": False},
    "idle": {"idle": True, "last_line_at": NOW - 1500},
    "missing": {"log_found": False, "reading": False},
    "path_missing": {"log_found": False, "log_configured": True, "reading": False},
    "stalled": {"reading": False},
    "unreadable": {"unreadable": True, "reading": False},
}


def states():
    return statuswords.table()["states"]


def test_table_is_ascii_and_complete():
    raw = statuswords.PATH.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    doc = json.loads(raw)
    assert doc["schema"] == 1 and doc["_README"]
    kit = json.loads((ROOT / "ops" / "fleet_kit" / "tokens.json").read_text())["states"]
    for sid, s in doc["states"].items():
        assert set(s) == FIELDS, sid
        assert s["glyph"] == kit[s["kit"]]["row"], sid
        assert isinstance(s["rank"], int), sid
        # "fix" only for faults: a fault names its check and its next step
        if s["fault"]:
            assert s["check_row"] and s["check"] and s["next"], sid
        assert (s["check_row"] is None) == (s["check"] is None), sid


def test_overlay_words_fit_beside_the_level_or_alone():
    doc = statuswords.table()
    for sid, s in doc["states"].items():
        w = s["overlay"]
        if w is None:
            continue
        cap = doc["overlay_alone_max"] if s["overlay_alone"] else doc["overlay_beside_max"]
        assert len(w) <= cap, (sid, w)
    assert doc["overlay_beside_max"] == 15 and doc["overlay_alone_max"] == 27


def test_js_copies_equal_the_json_source():
    want = statuswords.copy_doc()
    assert "_README" not in want
    for rel in statuswords.JS_COPIES:
        text = (ROOT / rel).read_text(encoding="ascii")
        assert text.count(statuswords.BEGIN) == 1 and text.count(statuswords.END) == 1, rel
        assert statuswords.js_copy(text) == want, rel
        # the block is pasted as the module prints it
        assert statuswords.js_block() in text, rel


def test_js_copy_reader_refuses_a_file_without_markers():
    assert statuswords.js_copy("var x = 1;") is None


def test_checks_detail_is_the_tables_for_every_state_with_a_row():
    named = {sid for sid, s in states().items() if s["check_row"]}
    assert named == set(FACTS)
    for sid, facts in FACTS.items():
        s = states()[sid]
        rows = {r["id"]: r for r in diag.checks(dict(GREEN, **facts), NOW)}
        r = rows[s["check_row"]]
        assert r["detail"].endswith(s["check"]), sid
        if s["fault"]:
            assert r["status"] == diag.FAIL and r["fix"] == s["next"], sid
        else:
            assert r["status"] != diag.FAIL and r["fix"] is None, sid


def test_view_never_counts_a_pending_choice_or_a_quiet_log_as_a_fix():
    for sid in ("off", "idle"):
        v = diag.view(dict(GREEN, **FACTS[sid]), "1", now=NOW)
        assert v["failed"] == 0, sid


def test_diag_fix_texts_are_the_tables_next_steps():
    assert diag.FIX_START_GAME == statuswords.next_step("missing")
    assert diag.FIX_LOG_PATH == statuswords.next_step("path_missing")
    assert diag.FIX_RUN == statuswords.next_step("stalled")


def test_reading_state_matches_the_dashboard_rule():
    rs = statuswords.reading_state
    assert rs(None) == "unknown"
    assert rs({"consented": True, "reading": True}, live=False) == "unknown"
    assert rs({"consented": True, "reading": True, "idle": True}) == "idle"
    assert rs({"consented": True, "reading": True}) == "reading"
    assert rs({"consented": True, "reading": False, "path": "x"}) == "waiting"
    assert rs({"consented": True, "reading": False, "path": None}) == "missing"
    assert rs({"consented": False, "idle": True}) == "off"
    # every reading state has a bar word; all but unknown have an overlay word
    for sid in ("unknown", "idle", "reading", "waiting", "missing", "off"):
        assert statuswords.bar(sid), sid
        assert (statuswords.overlay(sid) is None) == (sid == "unknown"), sid


def test_idle_words_share_one_root_and_name_no_fixed_time():
    # research 0042 F10 / F20 f: one root, no constant "20 min"
    idle = states()["idle"]
    assert idle["bar"].startswith(idle["overlay"])
    for w in (idle["bar"], idle["overlay"], idle["check"]):
        assert "20" not in w


def test_unreadable_state_is_one_word_for_bar_overlay_and_checks(monkeypatch):
    # RUN-UNREADABLE-WORD (review SRW-1): the file is there but can't be
    # read; the table names it once and diag.check_reading takes it from
    # the table through _state_check
    s = states()["unreadable"]
    assert s["kit"] == "blocked" and s["glyph"] == "[#]"
    assert s["bar"] == "can't read Client.txt"
    assert s["overlay"] and not s["overlay_alone"]
    assert len(s["overlay"]) <= statuswords.table()["overlay_beside_max"] == 15
    assert s["fault"] and s["check_row"] == "reading"
    assert diag.UNREADABLE_DETAIL == s["check"]
    assert diag.FIX_UNREADABLE == s["next"]
    seen = []
    real = diag._state_check

    def spy(cid, label, sid, **kw):
        seen.append((cid, sid))
        return real(cid, label, sid, **kw)

    monkeypatch.setattr(diag, "_state_check", spy)
    for reading in (True, False):
        seen.clear()
        r = diag.check_reading(dict(GREEN, unreadable=True, reading=reading))
        assert seen == [("reading", "unreadable")], reading
        assert r["status"] == diag.FAIL
        assert (r["detail"], r["fix"]) == (s["check"], s["next"])
