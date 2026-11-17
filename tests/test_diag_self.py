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


def test_consent():
    assert status({}, "consent") == "pass"
    r = row({"consented": False}, "consent")
    assert r["status"] == "fail" and "Allow reading Client.txt" in r["fix"]


def test_reading():
    assert status({}, "reading") == "pass"
    assert status({"reading": False}, "reading") == "fail"
    assert status({"reading": False, "consented": False}, "reading") == "unknown"


def test_last_line():
    assert status({}, "last_line") == "pass"
    assert status({"last_line_at": None}, "last_line") == "unknown"
    r = row({"last_line_at": NOW - 3600}, "last_line")
    assert r["status"] == "unknown" and "may be closed" in r["detail"]


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
    assert r["status"] == "fail" and "-TcCalc" in r["fix"] and "luajit" in r["detail"]
    assert status({"calc_status": None}, "calc") == "unknown"


def test_snapshot():
    assert status({}, "snapshot") == "pass"
    assert status({"snapshot": False}, "snapshot") == "fail"
    assert status({"snapshot": False, "web_data": False}, "snapshot") == "off"
    assert status({"snapshot_at": NOW - 90 * 86400}, "snapshot") == "fail"


def test_overlay_and_supervisor():
    for cid in ("overlay", "supervisor"):
        assert status({}, cid) == "pass"
        r = row({cid: False}, cid)
        assert r["status"] == "fail" and "run.ps1" in r["fix"]
        assert status({cid: None}, cid) == "unknown"


def test_hotkey():
    assert status({}, "hotkey") == "pass"
    assert status({"hotkey": False}, "hotkey") == "fail"
    assert status({"hotkey": None}, "hotkey") == "unknown"


def test_port():
    assert row({}, "port")["detail"] == "127.0.0.1:8960"
    assert status({"port": None}, "port") == "unknown"


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
                 _character="Cinderwisp")
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
