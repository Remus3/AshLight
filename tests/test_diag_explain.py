"""RUN-EXPLAIN-ROWS (F-129): the five cause rows of server/al/plug/explain.py
(overlay on screen, last item check, calc in use, log lines understood,
restarts), each from seeded files or counters in a tmp runtime dir."""

import datetime
import json
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace

from server.al import diag, keepalive, logshapes, metrics, parser, plug
from server.al.plug import explain

ROOT = Path(__file__).resolve().parents[1]
P = "2026/11/17 10:00:00 1 abc [INFO Client 1] "
BLANK = chr(13) + chr(10)  # an empty log line


def _core(tmp_path, wire=None):
    rt = tmp_path / "runtime"
    rt.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(runtime=rt, ledger_wire=wire)


def _iso(at):
    return datetime.datetime.fromtimestamp(at, datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z")


def _overlay_file(core, state, at):
    doc = {"schema": 1, "updated": _iso(at), "period_s": 60, "processes": 4,
           "working_set_kb": 1000, "private_kb": 900, "cpu_pct": 0.5,
           "by_type": {}, "overlay_shown": state == "shown",
           "companion_open": False, "overlay_state": state}
    (Path(core.runtime) / explain.OVERLAY_FILE).write_text(json.dumps(doc),
                                                           encoding="ascii")


def test_overlay_row_each_of_four_states_from_seeded_file(tmp_path):
    now = time.time()
    want = {"shown": "pass", "hidden_user": "off", "hidden_idle": "note",
            "starting": "unknown"}
    for i, (state, status) in enumerate(want.items()):
        core = _core(tmp_path / str(i))
        _overlay_file(core, state, now - 30)
        f = explain.facts(core, now)
        assert f["explain_overlay"]["state"] == state
        row = explain.overlay_row(f["explain_overlay"], now)
        assert row["id"] == "overlay_screen" and row["status"] == status
        assert row["detail"] == explain.OVERLAY_WORDS[state][1]
        assert "fix" not in row
    # no file, a stale file, a malformed file: no row (the Overlay row says it)
    core = _core(tmp_path / "none")
    assert explain.facts(core, now)["explain_overlay"] is None
    _overlay_file(core, "shown", now - 600)
    assert explain.facts(core, now)["explain_overlay"] is None
    (Path(core.runtime) / explain.OVERLAY_FILE).write_text("{not json", encoding="ascii")
    assert explain.overlay_fact(core, now) is None
    # a start that lasts 2 minutes is a fix row
    core = _core(tmp_path / "stuck")
    _overlay_file(core, "starting", now)
    assert explain.overlay_row(explain.overlay_fact(core, now), now)["status"] == "unknown"
    later = now + explain.STARTING_STUCK_S
    _overlay_file(core, "starting", later)
    os.utime(Path(core.runtime) / explain.OVERLAY_FILE, ns=(1, 1))
    row = explain.overlay_row(explain.overlay_fact(core, later), later)
    assert row["status"] == "fail" and row["fix"] == explain.STUCK_FIX


def test_overlay_words_are_the_gate_hints_word_for_word():
    js = (ROOT / "app" / "overlay_gate.js").read_text(encoding="ascii")
    block = js[js.index("const HINTS = {"):js.index("};", js.index("const HINTS = {"))]
    hints = {}
    for m in re.finditer(r"(\w+):\s*((?:\"[^\"]*\"\s*\+?\s*)+)", block):
        hints[m.group(1)] = "".join(re.findall(r"\"([^\"]*)\"", m.group(2)))
    assert set(hints) == set(explain.OVERLAY_WORDS)
    for state, (_, text) in explain.OVERLAY_WORDS.items():
        assert text == hints[state], state


def test_item_key_row_last_press_age_and_outcome(tmp_path):
    core = _core(tmp_path)
    explain.attach(core)
    assert explain.facts(core, time.time())["explain_press"] is None
    assert explain.press_row(None, time.time()) is None
    rec = metrics.emit("press", outcome="item", ms=12.5)
    f = explain.facts(core, rec["t"])
    assert f["explain_press"]["outcome"] == "item"
    t = f["explain_press"]["t"]
    row = explain.press_row(f["explain_press"], t + 60)
    assert row == {"id": "item_key_press", "label": "Last item check", "status": "pass",
                   "detail": "Pressed under 5 min ago. The item was checked."}
    assert explain.press_row(f["explain_press"], t + 17 * 60)["detail"].startswith(
        "Pressed 15 min ago.")
    assert explain.press_row(f["explain_press"], t + 3 * 3600 + 5)["detail"].startswith(
        "Pressed 3 h ago.")
    want = {"build": "pass", "unscored": "note", "empty": "note", "error": "fail"}
    for outcome, status in want.items():
        metrics.emit("press", outcome=outcome, ms=1.0)
        row = explain.press_row(explain.last("press"), time.time())
        assert row["status"] == status
        assert row["detail"].endswith(explain.PRESS_WORDS[outcome][1])
        assert ("fix" in row) == (status == "fail")
    # the age moves in steps, so an idle minute changes nothing
    assert explain.age_words(301) == explain.age_words(359) == "5 min ago"
    # a new core starts with no press; a calc emit is not a press
    explain.attach(core)
    metrics.emit("calc", cmd="calc", outcome="ok", ms=3.0)
    assert explain.last("press") is None


def test_calc_run_time_row(tmp_path):
    core = _core(tmp_path)
    explain.attach(core)
    metrics.emit("calc", cmd="calc", outcome="ok", ms=840.0)
    f = explain.facts(core, time.time())
    assert explain.calc_row(f["explain_calc"], False) is None  # the calc is off
    assert explain.calc_row(None, True) is None                # no calculation yet
    row = explain.calc_row(f["explain_calc"], True)
    assert row == {"id": "calc_run", "label": "Calc in use", "status": "pass",
                   "detail": "Working. The last calculation took 0.8 s."}
    for outcome, status in (("timeout", "fail"), ("crash", "fail"),
                            ("unavailable", "fail"), ("error", "note")):
        metrics.emit("calc", cmd="calc", outcome=outcome, ms=5.0)
        row = explain.calc_row(explain.last("calc"), True)
        assert row["status"] == status, outcome
        assert row.get("fix") == explain.CALC_FIX.get(outcome)
    assert explain.FIX_CALC_SETUP == diag.FIX_CALC
    # through the plug seam with the built-in calc_on fact
    rows = explain.rows({"calc_on": True, "explain_calc": explain.last("calc")}, time.time())
    assert [r["id"] for r in rows] == ["calc_run"]


def _feed(wire, line):
    wire.counters.observe(line, parser.parse_line(line))


def test_500_lines_0_events_fails_the_understood_row(tmp_path):
    wire = SimpleNamespace(counters=logshapes.Counters())
    core = _core(tmp_path, wire)
    assert explain.lines_row(explain.lines_fact(core)) is None  # nothing read yet
    _feed(wire, P + 'Generating level 3 area "G1_2" with seed 5')
    assert explain.lines_row(explain.lines_fact(core))["status"] == "pass"
    for _ in range(499):
        _feed(wire, P + "[ENGINE] synthetic engine noise line")
    for _ in range(300):  # NPC and local speech never count toward the run
        _feed(wire, P + "Someone: hello there")
        _feed(wire, BLANK)
    row = explain.lines_row(explain.lines_fact(core))
    assert row["status"] == "pass"
    _feed(wire, P + "[ENGINE] synthetic engine noise line")
    row = explain.lines_row(explain.lines_fact(core))
    assert row["id"] == "log_understood" and row["status"] == "fail"
    assert "500 game log lines" in row["detail"] and row["fix"] == explain.LINES_FIX
    # one understood line starts a new run
    _feed(wire, P + ": Emberwright (Witch) is now level 3")
    assert explain.lines_row(explain.lines_fact(core))["status"] == "pass"
    # a log with no event at all from the first line
    wire2 = SimpleNamespace(counters=logshapes.Counters())
    core2 = _core(tmp_path / "b", wire2)
    for _ in range(499):
        _feed(wire2, P + "[ENGINE] synthetic engine noise line")
    assert explain.lines_row(explain.lines_fact(core2)) is None
    _feed(wire2, "garbled line with no prefix")
    assert explain.lines_row(explain.lines_fact(core2))["status"] == "fail"
    # no ledger wire: no row
    assert explain.lines_fact(_core(tmp_path / "c")) is None


_STAMP = [10**18]


def _keepalive(core, at, reason="hung"):
    path = Path(core.runtime) / keepalive.STATE_FILE
    doc = {"status": "ok", "restarts": 1, "port": 8961, "updated": at,
           "last_restart": {"at": at, "reason": reason}}
    path.write_text(json.dumps(doc), encoding="ascii")
    _STAMP[0] += 10**9  # a new mtime for every write (the facts re-read on a change)
    os.utime(path, ns=(_STAMP[0], _STAMP[0]))


def test_restarts_row_only_after_3_in_a_day(tmp_path):
    now = time.time()
    core = _core(tmp_path)
    assert explain.restarts_row(explain.restarts_fact(core, now)) is None
    _keepalive(core, now - 3 * 3600)
    assert explain.restarts_fact(core, now)["count"] == 1
    # each restart is seen by the next core, which reads the history file
    core = _core(tmp_path)
    _keepalive(core, now - 2 * 3600, "crash")
    f = explain.restarts_fact(core, now)
    assert f["count"] == 2 and explain.restarts_row(f) is None
    core = _core(tmp_path)
    _keepalive(core, now - 60, "start-timeout")
    f = explain.restarts_fact(core, now)
    assert f["count"] == 3
    row = explain.restarts_row(f, localtime=time.gmtime)
    clock = time.strftime("%H:%M", time.gmtime(now - 60))
    assert row == {"id": "restarts", "label": "Restarts", "status": "fail",
                   "detail": ("AshLight restarted its core 3 times in the last 24 "
                              f"hours, last at {clock} (it did not finish starting)."),
                   "fix": explain.RESTARTS_FIX}
    # the same record read again is not a new restart
    core = _core(tmp_path)
    assert explain.restarts_fact(core, now)["count"] == 3
    # a day later the oldest restarts drop out
    assert explain.restarts_fact(core, now + 22.5 * 3600)["count"] == 1
    # the history file stays bounded and holds times and reason codes only
    doc = json.loads((Path(core.runtime) / explain.HISTORY_FILE).read_text("ascii"))
    assert set(doc) == {"schema", "at", "reasons"} and len(doc["at"]) <= explain.MAX_RESTARTS
    for i in range(explain.MAX_RESTARTS + 4):
        _keepalive(core, now - 1000 + i)
        explain.restarts_fact(core, now)
    doc = json.loads((Path(core.runtime) / explain.HISTORY_FILE).read_text("ascii"))
    assert len(doc["at"]) == explain.MAX_RESTARTS


def test_rows_pass_the_plug_row_shape(tmp_path):
    core = _core(tmp_path)
    explain.attach(core)
    now = time.time()
    _overlay_file(core, "hidden_idle", now)
    metrics.emit("press", outcome="error", ms=2.0)
    f = dict(explain.facts(core, now), calc_on=False)
    got = explain.rows(f, now)
    assert [r["id"] for r in got] == ["overlay_screen", "item_key_press"]
    assert all(plug._row(r) == dict(r, fix=r.get("fix")) for r in got)
    # nothing in the facts: no row
    assert explain.rows({}, now) == []


def test_player_sentences_live_in_the_text_module_and_copy_sheet():
    from server.al.text import explain as text
    from tests import test_structure
    root = Path(__file__).resolve().parent.parent
    plug_path = root / "server" / "al" / "plug" / "explain.py"
    assert test_structure.sentence_count(plug_path) < test_structure.SENTENCE_MIN
    for name in ("OVERLAY_WORDS", "PRESS_WORDS", "CALC_WORDS", "CALC_FIX",
                 "STUCK_FIX", "LINES_FIX", "RESTARTS_FIX", "age_words"):
        assert getattr(explain, name) is getattr(text, name)
    sheet = " ".join((root / "docs" / "design" / "copy" / "explain.md")
                     .read_text("ascii").split())
    sheet = sheet.replace("` `", " ")
    words = [t for _, t in text.OVERLAY_WORDS.values()]
    words += [t for _, t in text.PRESS_WORDS.values()]
    words += [t.replace(" " + text.FALLBACK, "") for _, t in text.CALC_WORDS.values()]
    words += [text.FALLBACK, text.STUCK_TEXT, text.STUCK_FIX, text.PRESS_FIX,
              text.FIX_CALC_SLOW, text.FIX_CALC_SETUP, text.LINES_PASS,
              text.LINES_FIX, text.RESTARTS_FIX, text.LABEL_OVERLAY,
              text.LABEL_PRESS, text.LABEL_CALC, text.LABEL_LINES,
              text.LABEL_RESTARTS, text.AGE_UNDER_5]
    for w in words:
        assert w.replace("{sec}", "<sec>") in sheet, w
