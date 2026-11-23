"""DIAG-SELF (research 0032 section 3, ruling J): one test per check (pass
/ fail / unknown or off), a redaction test on a report built from a seeded
state, and no network module in diag.py."""

import ast
import json
from pathlib import Path

from server.al import diag
from server.al.core import Core

NOW = 2_000_000_000.0
GREEN = {"log_found": True, "consented": True, "reading": True,
         "last_line_at": NOW - 30, "idle": False, "character_seen": True,
         "lang": "english", "web_data": True, "contact_set": True,
         "book_checked_at": NOW - 600, "book_error": None, "calc_on": True,
         "calc_status": {"available": True, "missing": []}, "snapshot": True,
         "snapshot_at": NOW - 86400, "overlay": True, "supervisor": True,
         "hotkey": True, "port": 8960}


def row(facts, cid):
    return {r["id"]: r for r in diag.checks(dict(GREEN, **facts), NOW)}[cid]


def status(facts, cid):
    return row(facts, cid)["status"]


def test_all_green_folds_to_one_line():
    v = diag.view(GREEN, "1.2.3", now=NOW)
    assert v["failed"] == 0 and v["summary"] == "All checks pass."
    assert all(r["fix"] is None for r in v["checks"])


def test_log_found():
    assert status({}, "log") == "pass"
    r = row({"log_found": False}, "log")
    assert r["status"] == "fail" and "Start Path of Exile 2" in r["fix"]
    # SEC-NO-DISCOVERY: a configured path that is missing stays configured
    # and says so, with its own fix (no Steam scan replaces it).
    r = row({"log_found": False, "log_configured": True}, "log")
    assert r["status"] == "fail"
    assert r["detail"] == "The Client.txt path in your settings is missing."
    # RUN-NO-DEAD-ENDS (research 0042 R4): the fix names the dashboard field
    # (SEC-LOG-PATH-FIELD, shown while this row fails), never a file to edit
    assert "Settings, Reading and web data" in r["fix"] and r["fix"] == diag.FIX_LOG_PATH
    assert "local.json" not in r["fix"]
    assert status({"log_configured": True}, "log") == "pass"


def test_consent():
    assert status({}, "consent") == "pass"
    # F-131 (research 0042 F23): a choice not made yet is a note, not a fix
    r = row({"consented": False}, "consent")
    assert r["status"] == "note" and r["fix"] is None
    assert r["detail"] == "Not given yet. Allow it on the Play tab."
    v = diag.view(dict(GREEN, consented=False, reading=False), "1", now=NOW)
    assert v["failed"] == 0 and v["summary"] == "All checks pass."


def test_reading():
    assert status({}, "reading") == "pass"
    assert status({"reading": False}, "reading") == "fail"
    assert status({"reading": False, "consented": False}, "reading") == "unknown"


def test_reading_dead_and_unreadable():
    # RUN-TAIL-HEAL-CORE: a dead reader thread reads as not reading (the
    # core's fact follows the thread), a fix row, never PASS
    r = row({"reading": False}, "reading")
    assert r["status"] == "fail" and r["detail"] == "Not reading Client.txt." and r["fix"]
    # an unreadable file wins over a stale reading flag, with its own words
    for reading in (True, False):
        r = row({"reading": reading, "unreadable": True}, "reading")
        assert r["status"] == "fail" and r["detail"] == diag.UNREADABLE_DETAIL
        assert r["fix"] == diag.FIX_UNREADABLE
        assert "Client.txt" in r["fix"] and "run.ps1" not in r["fix"]
    # no opt-in: nothing is read, so nothing is unreadable
    assert status({"reading": False, "consented": False, "unreadable": True},
                  "reading") == "unknown"


def test_core_reading_fact_follows_the_thread(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    try:
        core.state.set_tailer(consented=True, reading=True)
        facts = core.diag_facts()
        assert facts["reading"] is False and facts["unreadable"] is False

        class Alive:
            running = True

        core.tailer = Alive()
        assert core.diag_facts()["reading"] is True
        Alive.running = False
        assert core.diag_facts()["reading"] is False
        core.tailer = None
    finally:
        core.close()


def test_last_line():
    assert status({}, "last_line") == "pass"
    assert status({"last_line_at": None}, "last_line") == "unknown"
    r = row({"last_line_at": NOW - 3600}, "last_line")
    # RUN-NO-DEAD-ENDS (research 0042 F20 a): a known age is a note, never
    # "not known yet" beside "1 h ago"
    assert r["status"] == "note" and "may be closed" in r["detail"]
    # RUN-QUIET-FEED: the age is written in from "at" (report, dashboard)
    assert r["detail"] == diag.AGO + ". The game may be closed, or you are AFK."
    assert r["at"] == NOW - 3600
    assert diag.render_detail(r, NOW) == "60 min ago. The game may be closed, or you are AFK."
    assert r["fix"] is None


def test_age_rows_carry_an_absolute_time():
    # RUN-QUIET-FEED (F-093): every row with an age holds the absolute time
    # in "at" and the AGO mark in a detail with no time text; the rest have
    # no "at"
    facts = dict(GREEN, started_at=NOW - 120,
                 last_exit={"at": NOW - 200, "reason": "crash", "detail": None},
                 client_exit={"at": NOW - 90, "reason": "relaunch", "detail": None})
    rows = {r["id"]: r for r in diag.checks(facts, NOW)}
    want = {"last_line": NOW - 30, "prices": NOW - 600, "snapshot": NOW - 86400,
            "last_exit": NOW - 200, "client_exit": NOW - 90}
    assert {k: r["at"] for k, r in rows.items() if "at" in r} == want
    for cid in want:
        d = rows[cid]["detail"]
        assert d.count(diag.AGO) == 1, cid
        assert "ago" not in d.replace(diag.AGO, "") and "just now" not in d, cid
    assert diag.render_detail(rows["prices"], NOW) == "Updated 10 min ago."
    assert diag.render_detail(rows["snapshot"], NOW) == "Present, fetched 24 h ago."
    assert diag.render_detail(rows["last_line"], NOW) == "Just now."
    assert diag.render_detail(rows["last_exit"], NOW).startswith(
        "AshLight stopped 3 min ago after")
    # the same facts later: the same rows (no minute in the published view)
    assert diag.checks(facts, NOW + 240) == list(rows.values())
    # the snapshot's copy has no report; the click's copy writes ages in
    assert "report" not in diag.view(facts, "1", now=NOW, with_report=False)
    text = diag.view(facts, "1", now=NOW)["report"]
    assert "[ok] Price book: Updated 10 min ago." in text and diag.AGO not in text


def test_character():
    assert status({}, "character") == "pass"
    assert status({"character_seen": False}, "character") == "unknown"


def test_language():
    assert status({}, "language") == "pass"
    r = row({"lang": "non_english"}, "language")
    assert r["status"] == "note" and r["fix"] is None and "still work" in r["detail"]
    assert status({"lang": "unknown"}, "language") == "unknown"


def test_web_data():
    assert status({}, "web_data") == "pass"
    assert status({"web_data": False}, "web_data") == "off"
    r = row({"contact_set": False}, "web_data")
    assert r["status"] == "fail" and "contact" in r["fix"]
    # DATA-CONTACT-FIELD: the fix and the detail name the dashboard place
    # of the field, never a file path. RUN-NO-DEAD-ENDS: the field sits in
    # the Settings section Reading and web data (an h3 of web/index.html)
    card = "Settings, Reading and web data"
    assert diag.CONTACT_CARD == card and r["fix"] == diag.FIX_CONTACT
    h3 = Path(__file__).resolve().parents[1] / "web" / "index.html"
    page = h3.read_text(encoding="utf-8")
    assert '<h3 id="reading-title" tabindex="-1">Reading and web data</h3>' in page
    assert page.index('id="reading-title"') < page.index('id="webdata-contact"')
    for text in (r["fix"], r["detail"]):
        assert card in text
        assert "local.json" not in text and "config" not in text
        assert "\\" not in text and "/" not in text


def test_price_book():
    assert status({}, "prices") == "pass"
    assert status({"web_data": False}, "prices") == "off"
    assert status({"book_error": "timed out"}, "prices") == "fail"
    assert status({"book_checked_at": NOW - 5 * 3600}, "prices") == "fail"
    assert status({"book_checked_at": None}, "prices") == "unknown"


def test_calc():
    assert status({}, "calc") == "pass"
    assert status({"calc_on": False}, "calc") == "off"
    r = row({"calc_status": {"available": False, "missing": ["luajit"]}}, "calc")
    assert r["status"] == "fail" and "luajit" in r["detail"]
    # TC-CALC-OPTIN: the fix names the one step, which also turns the calc on.
    # RUN-NO-DEAD-ENDS (research 0042 R4, F20 c): the step is the Checks
    # row's button (web/checks.js CALC_BUTTON), never a script, never "again"
    assert r["fix"] == diag.FIX_CALC
    assert '"Set up the calc" under Settings, Checks' in r["fix"] and "turns it on" in r["fix"]
    assert ".ps1" not in r["fix"] and "scripts" not in r["fix"] and "again" not in r["fix"]
    assert "config" not in r["fix"]  # no second edit of local.json asked for
    off = row({"calc_on": False}, "calc")
    assert off["fix"] is None and off["detail"].endswith(
        'press "Set up the calc" under Settings, Checks in the AshLight window.')
    assert status({"calc_status": None}, "calc") == "unknown"


def test_snapshot():
    assert status({}, "snapshot") == "pass"
    assert status({"snapshot": False}, "snapshot") == "fail"
    assert status({"snapshot": False, "web_data": False}, "snapshot") == "off"
    assert status({"snapshot_at": NOW - 90 * 86400}, "snapshot") == "fail"
    # DATA-SNAP-AT-START: AshLight fetches the data by itself, so no fix
    # text names a script
    fixes = [row({"snapshot": False}, "snapshot")["fix"],
             row({"snapshot_at": NOW - 90 * 86400}, "snapshot")["fix"],
             row({"snapshot_at": NOW - 90 * 86400, "web_data": False}, "snapshot")["fix"]]
    assert fixes[0] == fixes[1] == diag.FIX_SNAPSHOT
    assert fixes[2] == diag.FIX_SNAPSHOT_OFF and "Use web data" in fixes[2]
    for fix in fixes:
        assert "by itself" in fix
        assert ".ps1" not in fix and "scripts" not in fix and "build" not in fix
    assert row({"snapshot": False, "web_data": False}, "snapshot")["fix"] is None


def test_overlay_and_supervisor():
    for cid in ("overlay", "supervisor"):
        assert status({}, cid) == "pass"
        r = row({cid: False}, cid)
        # RUN-NO-DEAD-ENDS (research 0042 R4): the player's act, never a script
        assert r["status"] == "fail" and "Start Menu shortcut" in r["fix"]
        assert ".ps1" not in r["fix"] and "scripts" not in r["fix"]
        assert status({cid: None}, cid) == "unknown"


def _hk(eval_=None, toggle=None, overlay_on=True):
    off = {"key": None, "want": None, "registered": None, "fallback": None}
    return {"eval": dict(off, **(eval_ or {})), "toggle": dict(off, **(toggle or {})),
            "overlay_on": overlay_on}


def test_hotkey():
    # no runtime file: the item check row reads the overlay log verdict
    assert status({}, "hotkey") == "pass"
    assert status({"hotkey": False}, "hotkey") == "fail"
    assert status({"hotkey": None}, "hotkey") == "unknown"
    assert status({}, "hotkey_toggle") == "unknown"
    # HOTKEYS-LIVE (OVL-KEYS-CORE): two rows, one per shortcut
    ok = {"key": "Alt+Shift+E", "want": "Alt+Shift+E", "registered": True,
          "fallback": False}
    tog = {"key": "Alt+Shift+A", "want": "Alt+Shift+A", "registered": True,
           "fallback": False}
    hk = _hk(ok, tog)
    rows = [r for r in diag.checks(dict(GREEN, hotkeys=hk), NOW)
            if r["id"] in ("hotkey", "hotkey_toggle", "overlay_off")]
    assert [(r["id"], r["label"], r["status"]) for r in rows] == [
        ("hotkey", "Item check hotkey", "pass"),
        ("hotkey_toggle", "Overlay hotkey", "pass")]
    assert rows[0]["detail"] == "Registered: Alt+Shift+E."
    # the view wins over the log verdict
    assert status({"hotkeys": hk, "hotkey": False}, "hotkey") == "pass"
    # a fallback: a note naming both keys, nothing to fix
    fb = row({"hotkeys": _hk(dict(ok, key="Ctrl+Shift+F9", fallback=True), tog)}, "hotkey")
    assert fb["status"] == "note" and fb["fix"] is None
    assert fb["detail"] == "Alt+Shift+E is taken by another app, so AshLight uses Ctrl+Shift+F9."
    # nothing bound: a fix naming the in-app field, never a script
    bad = row({"hotkeys": _hk(ok, {"want": "Alt+Shift+A", "registered": False,
                                   "fallback": False})}, "hotkey_toggle")
    assert bad["status"] == "fail" and bad["fix"] == diag.FIX_TOGGLE_KEY
    assert bad["detail"] == "Not registered: another app holds Alt+Shift+A."
    assert "overlay key" in bad["fix"] and ".ps1" not in bad["fix"]
    bad = row({"hotkeys": _hk({"want": "Alt+Shift+E", "registered": False}, tog)}, "hotkey")
    assert bad["fix"] == diag.FIX_HOTKEY and "item check key" in bad["fix"]
    assert "Overlay position and size" in diag.FIX_HOTKEY
    # unknown parts read unknown
    assert status({"hotkeys": _hk()}, "hotkey") == "unknown"
    # the overlay process is not running: keys unknown, no note
    assert status({"hotkeys": hk, "overlay": False}, "hotkey") == "unknown"
    assert status({"hotkey": True, "overlay": False}, "hotkey") == "unknown"
    ids = [r["id"] for r in diag.checks(dict(GREEN, overlay=False,
                                             hotkeys=_hk(ok, tog, overlay_on=False)), NOW)]
    assert "overlay_off" not in ids


def test_hotkey_overlay_off_note():
    tog = {"key": "Ctrl+Shift+F10", "want": "Alt+Shift+A", "registered": True,
           "fallback": True}
    r = row({"hotkeys": _hk(None, tog, overlay_on=False)}, "overlay_off")
    assert r["status"] == "note" and r["fix"] is None
    assert r["detail"] == "You switched the overlay off. Press Ctrl+Shift+F10 to show it."
    r = row({"hotkeys": _hk(None, {"registered": False}, overlay_on=False)}, "overlay_off")
    assert r["detail"] == "You switched the overlay off. Show it again from the tray icon."
    for on in (True, None):
        ids = [x["id"] for x in diag.checks(dict(GREEN, hotkeys=_hk(overlay_on=on)), NOW)]
        assert "overlay_off" not in ids
    v = diag.view(dict(GREEN, hotkeys=_hk(None, tog, overlay_on=False)), "1", now=NOW)
    assert v["failed"] == 0 and "[note] Overlay switched off:" in v["report"]


def test_core_facts_take_the_runtime_file(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    (tmp_path / "overlay.log").write_text("t overlay started\n", encoding="ascii")
    core.procs_status = lambda: {"overlay": {"live": True}}
    f = core.diag_facts()
    assert f["hotkeys"] is None and f["hotkey"] is True  # no file: the log
    (tmp_path / "hotkeys.json").write_text(json.dumps(
        {"keys": {"eval": {"want": "Alt+Shift+E", "bound": "Ctrl+Shift+F9",
                           "registered": True, "fallback": True}},
         "overlay": {"user_on": False}}), encoding="ascii")
    f = core.diag_facts()
    assert f["hotkey"] is None and f["hotkeys"]["eval"]["key"] == "Ctrl+Shift+F9"
    assert f["hotkeys"]["overlay_on"] is False
    core.close()


def test_port():
    assert row({}, "port")["detail"] == "127.0.0.1:8960"
    assert status({"port": None}, "port") == "unknown"


def test_private_files_row():
    # SEC-ACL-CHECK: no row while nothing is open or the audit has not run
    ids = [r["id"] for r in diag.checks(GREEN, NOW)]
    assert "private" not in ids
    assert diag.check_private({"acl_open": None}) is None
    assert diag.check_private({"acl_open": []}) is None
    assert diag.check_private({"acl_open": ["elsewhere"]}) is None
    r = row({"acl_open": ["app"]}, "private")
    assert r["status"] == "fail" and r["label"] == "Private files"
    assert r["detail"] == ("Other accounts on this computer can change files in "
                           "the AshLight folder.")
    # NDE-1: a player-level fix in plain words, never a command line
    assert r["fix"] == diag.FIX_PRIVATE_APP
    assert "Properties" in r["fix"] and "Security" in r["fix"]
    for name in ("runtime", "sidecar"):
        r = row({"acl_open": [name]}, "private")
        assert r["fix"] == diag.FIX_PRIVATE_SETUP and "AshLight's setup again" in r["fix"]
        assert ".ps1" not in r["fix"] and "scripts" not in r["fix"]
    r = row({"acl_open": ["sidecar", "app", "runtime"]}, "private")
    assert r["detail"].endswith("in AshLight's runtime folder, the AshLight folder "
                                "and AshLight's sidecar folder.")
    assert r["fix"] == diag.FIX_PRIVATE_BOTH
    assert len(r["fix"].splitlines()) == 1
    v = diag.view(dict(GREEN, acl_open=["runtime"]), "1", now=NOW)
    assert v["failed"] == 1 and v["checks"][-1]["id"] == "private"


def test_no_fix_text_holds_a_command_line():
    # NDE-1 (wave 28 design finding): a Checks fix is for players, so no fix
    # text tells them to type a python command line.
    texts = [v for k, v in vars(diag).items()
             if k.startswith("FIX_") and isinstance(v, str)]
    assert texts
    combos = (["app"], ["runtime"], ["sidecar"], ["app", "runtime"],
              ["app", "sidecar", "runtime"])
    texts += [diag.check_private({"acl_open": c})["fix"] for c in combos]
    for t in texts:
        assert "python -m" not in t, t
        assert "python " not in t.lower(), t


def test_summary_counts_fixes():
    v = diag.view(dict(GREEN, overlay=False, reading=False), "1", now=NOW)
    assert v["failed"] == 2 and v["summary"] == "2 checks need a fix."
    assert "[FIX] Overlay: The overlay is not running. Fix:" in v["report"]


def test_hotkey_from_the_overlay_log(tmp_path):
    log = tmp_path / "overlay.log"
    assert diag.hotkey_registered(log) is None
    log.write_text("t overlay started; port 8960\n", encoding="ascii")
    assert diag.hotkey_registered(log) is True
    log.write_text("t overlay started\nt item check shortcut not available: Alt+E\n"
                   "t overlay started\n", encoding="ascii")
    assert diag.hotkey_registered(log) is False
    log.write_text("t item check shortcut not available: Alt+E\nt overlay started\n"
                   "t overlay started\n", encoding="ascii")
    assert diag.hotkey_registered(log) is True


def test_report_redacts_a_seeded_state(tmp_path):
    # built at run time so the leak sweep sees no machine path or address
    c, e, sep = "C" + ":", "E" + ":", "\\"
    home = sep.join([c, "Users", "SecretUser"])
    mail = "me" + "@" + "mail.example"
    facts = dict(GREEN, book_error="open " + home + sep + "x failed for " + mail,
                 log_found=False, _repo=e + sep + "SecretRepo",
                 _sidecar=sep.join([e, "Sidecars", "AL"]),
                 _log_path=sep.join([home, "Games", "Client.txt"]), _contact=mail,
                 _character="Cinderwisp", acl_open=["runtime", "app", "sidecar"])
    env = {"USERPROFILE": home, "USERNAME": "SecretUser"}
    pairs = diag.secrets(facts, environ=env)
    rows = diag.checks(facts, NOW)
    rows.append({"id": "x", "label": "Seed", "status": "fail",
                 "detail": ("Cinderwisp at " + e + "/SecretRepo/ops and "
                            + sep.join([e, "Sidecars", "AL", "Logs"])),
                 "fix": "ask secretuser"})
    text = diag.report(rows, "1.0", NOW, pairs)
    for leak in ("SecretUser", "secretuser", "SecretRepo", "Sidecars", "mail.example",
                 "Cinderwisp", c + sep, e + sep, e + "/"):
        assert leak not in text, leak
    assert "<character>" in text and "<repo>" in text
    # SEC-ACL-CHECK: the private files row names folders, never a path
    priv = [ln for ln in text.splitlines() if ln.startswith("[FIX] Private files:")]
    assert len(priv) == 1 and "<path>" not in priv[0] and "<repo>" not in priv[0]
    assert "<sidecar>" not in priv[0] and "<home>" not in priv[0]
    text.encode("ascii")
    assert "\r" not in text


def test_core_view_has_no_secret(tmp_path):
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps({"web_data": True, "contact": "me" + "@" + "mail.example"}),
                   encoding="ascii")
    core = Core(runtime=tmp_path, tail=False, config_path=cfg, character="Cinderwisp")
    core.tick_diag(force=True)
    d = core.state.snapshot()["diag"]
    blob = json.dumps(d)
    assert "mail.example" not in blob and "Cinderwisp" not in blob
    assert str(tmp_path) not in blob and str(tmp_path).replace("\\", "/") not in blob
    ids = [r["id"] for r in d["checks"]]
    assert ids[:3] == ["log", "consent", "reading"] and "language" in ids
    # a test core reads no process list: overlay / keepalive stay unknown
    assert {r["id"]: r["status"] for r in d["checks"]}["overlay"] == "unknown"


def test_tick_is_throttled(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    core.tick_diag(force=True)
    calls = []
    core.procs_status = lambda: calls.append(1)
    core.tick_diag()
    assert calls == []


def test_diag_module_makes_no_request():
    src = (Path(__file__).resolve().parents[1] / "server" / "al" / "diag.py").read_text()
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names |= {node.module or ""} | {a.name for a in node.names}
    for bad in ("webfetch", "urllib", "http", "socket", "ninja", "subprocess"):
        assert not any(bad in n for n in names), bad


# -- OBS-CRASH (F-105): the last unclean exit of the core and the client

START = NOW - 120


def _exit_ids(facts):
    return [r["id"] for r in diag.checks(dict(GREEN, started_at=START, **facts), NOW)
            if r["id"] in ("last_exit", "client_exit")]


def test_unclean_core_exit_row():
    for reason, word in (("crash", "unexpected error"), ("signal", "closed from outside"),
                         ("supervisor-kill", "stopped responding")):
        rec = {"at": START - 30, "pid": 7, "reason": reason, "detail": "ValueError: x"}
        r = row({"started_at": START, "last_exit": rec}, "last_exit")
        assert r["status"] == "note" and r["fix"] is None
        assert word in r["detail"] and "(ValueError: x)" in r["detail"]
        assert r["label"] == "Last stop"
    # a worker thread's crash: the core may still run
    rec = {"at": NOW - 30, "reason": "crash", "detail": "thread al-tail: KeyError: x"}
    r = row({"started_at": START, "last_exit": rec}, "last_exit")
    assert r["detail"].startswith("Part of AshLight stopped")
    # a note, never a fix: the summary still says all pass
    v = diag.view(dict(GREEN, started_at=START,
                       last_exit={"at": START - 5, "reason": "crash", "detail": None}),
                  "1", now=NOW)
    assert v["failed"] == 0 and "[note] Last stop: AshLight stopped" in v["report"]


def test_client_crash_or_relaunch_row():
    for reason, word in (("crash", "unexpected error"), ("relaunch", "restarted itself")):
        rec = {"at": NOW - 60, "pid": None, "reason": reason, "detail": None}
        r = row({"started_at": START, "client_exit": rec}, "client_exit")
        assert r["status"] == "note" and word in r["detail"]
        assert r["detail"].startswith("The desktop app") and "()" not in r["detail"]


def test_no_exit_row_after_a_clean_stop():
    assert _exit_ids({}) == []
    for reason in ("stop", "reload"):
        assert _exit_ids({"last_exit": {"at": START - 5, "reason": reason}}) == []
    assert _exit_ids({"client_exit": {"at": NOW - 5, "reason": "quit"}}) == []
    # an unclean exit long before this start did not lead to it
    old = START - diag.EXIT_WINDOW_S - 1
    assert _exit_ids({"last_exit": {"at": old, "reason": "crash"},
                      "client_exit": {"at": old, "reason": "crash"}}) == []
    both = _exit_ids({"last_exit": {"at": START - 5, "reason": "crash"},
                      "client_exit": {"at": NOW - 5, "reason": "relaunch"}})
    assert both == ["last_exit", "client_exit"]


def test_exit_detail_is_redacted_in_the_report(monkeypatch):
    c, sep = "C" + ":", "\\"
    home = sep.join([c, "Users", "SecretUser"])
    monkeypatch.setenv("USERNAME", "SecretUser")
    monkeypatch.setenv("USERPROFILE", home)
    facts = dict(GREEN, started_at=START, _character="Cinderwisp",
                 last_exit={"at": START - 5, "reason": "crash",
                            "detail": "KeyError: Cinderwisp in " + home + sep + "x.py"},
                 client_exit={"at": NOW - 5, "reason": "crash",
                              "detail": "Error: SecretUser"})
    v = diag.view(facts, "1", now=NOW)
    blob = json.dumps(v)
    for leak in ("Cinderwisp", "SecretUser", c + sep):
        assert leak not in v["report"], leak
    assert "Cinderwisp" not in blob
    assert "<character>" in v["report"]


def test_core_facts_read_both_exit_records(tmp_path):
    from server.al import exitrecord
    core = Core(runtime=tmp_path, tail=False)
    f = core.diag_facts()
    assert f["last_exit"] is None and f["client_exit"] is None
    assert f["started_at"] == core.started_at
    exitrecord.write(tmp_path, "crash", "ValueError: boom", now=core.started_at - 10)
    (tmp_path / exitrecord.CLIENT_FILE).write_text(
        json.dumps({"at": core.started_at + 1, "reason": "relaunch", "detail": None}),
        encoding="ascii")
    core.tick_diag(force=True)
    ids = {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}
    assert "ValueError: boom" in ids["last_exit"]["detail"]
    assert "restarted itself" in ids["client_exit"]["detail"]
    exitrecord.write(tmp_path, "stop", now=core.started_at - 10)
    (tmp_path / exitrecord.CLIENT_FILE).write_text(
        json.dumps({"at": core.started_at + 1, "reason": "quit"}), encoding="ascii")
    core.tick_diag(force=True)
    ids = {r["id"] for r in core.state.snapshot()["diag"]["checks"]}
    assert "last_exit" not in ids and "client_exit" not in ids
