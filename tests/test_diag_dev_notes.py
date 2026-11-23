"""LOOP-DEV-CHECKS (F-125, AUTO-08, F-130): two Checks notes. A developer
note while the dev loop's last tick (its own status file, never a process
list) is older than 2 hours, and a note for every user while the pinned
Electron line is within 30 days of its end of life or past it, computed
offline from the tracked pin. Both halves are proven with fixtures."""

import ast
import datetime as dt
import json
import socket
import subprocess
import urllib.request
from pathlib import Path

import pytest

from server.al import diag, paths
from server.al.core import Core

REPO = Path(__file__).resolve().parents[1]
STAMP = "2026-11-22T12:00:00+00:00"
AT = dt.datetime.fromisoformat(STAMP).timestamp()
EOL = "2027-04-27"
EOL_AT = dt.datetime(2027, 4, 27, tzinfo=dt.timezone.utc).timestamp()
DAY = 86400.0


def _loop_root(tmp_path, doc):
    f = tmp_path.joinpath(*diag.LOOP_STATUS_PARTS)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return tmp_path


def _pin_root(tmp_path, doc):
    f = tmp_path.joinpath(*diag.ELECTRON_PIN_PARTS)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return tmp_path


def _rows(facts, now):
    return {r["id"]: r for r in diag.checks(facts, now)}


def _real_core(tmp_path, monkeypatch, root):
    """A test core that takes the real core's branch for the two keys,
    with the repository root pointed at a fixture folder."""
    core = Core(runtime=tmp_path / "rt", tail=False)
    core._real = True
    monkeypatch.setattr(paths, "repo_root", lambda: root)
    monkeypatch.setattr(paths, "runtime_dir", lambda: tmp_path / "rt")
    return core


def test_tick_older_than_2_h_is_a_dev_note(tmp_path, monkeypatch):
    root = _loop_root(tmp_path / "repo", {"task": "loop", "status": "done",
                                          "updated": STAMP, "checklist": []})
    assert diag.loop_tick_age(root, AT + 600) == 600
    # within 2 hours: no row
    for age in (600, 2 * 3600):
        assert "dev_loop" not in _rows({"loop_tick_age_s": age}, AT + age)
    # older: one developer note, nothing to fix
    now = AT + 3 * 3600
    age = diag.loop_tick_age(root, now)
    r = _rows({"loop_tick_age_s": age}, now)["dev_loop"]
    assert r["status"] == diag.NOTE and r["fix"] is None
    assert r["detail"].startswith("Developer note:") and r["detail"].isascii()
    assert "loop_task.py status" in r["detail"]
    assert r["at"] == AT
    assert diag.render_detail(r, now) == r["detail"].replace(diag.AGO, "3 h ago")
    # RUN-QUIET-FEED: a minute later the published view is the same
    later = AT + 3 * 3600 + 60
    a = diag.view({"loop_tick_age_s": age}, "0", now=now, with_report=False)
    b = diag.view({"loop_tick_age_s": diag.loop_tick_age(root, later)}, "0",
                  now=later, with_report=False)
    assert a == b
    assert "Dev loop" in diag.view({"loop_tick_age_s": age}, "0", now=now)["report"]
    # the core reads the status file under its own root
    core = _real_core(tmp_path, monkeypatch, root)
    facts = core.diag_facts(now)
    assert facts["loop_tick_age_s"] == 3 * 3600
    assert "dev_loop" in _rows(facts, now)


def test_no_loop_status_file_means_no_note(tmp_path, monkeypatch):
    empty = tmp_path / "repo"
    empty.mkdir()
    assert diag.loop_tick_age(empty, AT) is None
    for doc in ("{not json", {"status": "done"}, {"updated": "yesterday"},
                {"updated": 12}, ["updated", STAMP]):
        bad = _loop_root(tmp_path / f"bad{len(str(doc))}", doc)
        assert diag.loop_tick_age(bad, AT + DAY) is None, doc
    # a stamp from the future (clock skew) is not old
    assert diag.loop_tick_age(_loop_root(tmp_path / "skew", {"updated": STAMP}),
                              AT - 600) == 0
    assert "dev_loop" not in _rows({}, AT)
    assert "dev_loop" not in _rows({"loop_tick_age_s": None}, AT)
    # a test core never reads the live status file
    core = Core(runtime=tmp_path / "rt", tail=False)
    facts = core.diag_facts(AT)
    assert facts["loop_tick_age_s"] is None and facts["electron_eol"] is None
    # the real branch with no file reads no note
    core = _real_core(tmp_path, monkeypatch, empty)
    facts = core.diag_facts(AT + DAY)
    assert facts["loop_tick_age_s"] is None
    assert "dev_loop" not in _rows(facts, AT + DAY)


def test_electron_line_inside_30_days_of_eol_is_a_note(tmp_path, monkeypatch):
    root = _pin_root(tmp_path / "repo", {"version": "45.3.3", "eol": EOL})
    pin = diag.electron_eol(root)
    assert pin == {"version": "45.3.3", "eol": EOL}
    # 10 days before: a note naming the date and setup.ps1, nothing to fix
    now = EOL_AT - 10 * DAY
    r = _rows({"electron_eol": pin}, now)["electron_eol"]
    assert r["status"] == diag.NOTE and r["fix"] is None
    assert "Electron 45" in r["detail"] and EOL in r["detail"]
    assert "reaches its end of life" in r["detail"]
    assert "scripts\\setup.ps1" in r["detail"] and r["detail"].isascii()
    # the row does not change from day to day
    assert _rows({"electron_eol": pin}, now + DAY)["electron_eol"] == r
    # exactly 30 days before is inside
    assert "electron_eol" in _rows({"electron_eol": pin}, EOL_AT - 30 * DAY)
    # past it
    r = _rows({"electron_eol": pin}, EOL_AT + DAY)["electron_eol"]
    assert "reached its end of life" in r["detail"] and "scripts\\setup.ps1" in r["detail"]
    # an installed copy updates by itself: no script named
    r = _rows({"electron_eol": pin, "install": {"mode": "installed"}},
              EOL_AT + DAY)["electron_eol"]
    assert "setup.ps1" not in r["detail"] and "by itself" in r["detail"]
    v = diag.view({"electron_eol": pin}, "0", now=now)
    assert "Desktop app runtime" in v["report"]
    assert not any(c["id"] == "electron_eol" and c["status"] == diag.FAIL
                   for c in v["checks"])
    # the core reads the pin under its own root
    core = _real_core(tmp_path, monkeypatch, root)
    assert core.diag_facts(now)["electron_eol"] == pin
    # the tracked pin parses (decision 0068) and names app/package.json's line
    tracked = diag.electron_eol(REPO)
    want = json.loads((REPO / "config" / "electron_pin.json").read_text(encoding="utf-8"))
    assert tracked == {"version": want["version"], "eol": want["eol"]}


def test_no_pin_file_or_far_eol_means_no_note(tmp_path, monkeypatch):
    empty = tmp_path / "repo"
    empty.mkdir()
    assert diag.electron_eol(empty) is None
    for i, doc in enumerate(("{oops", [], {"version": "45.3.3"}, {"eol": EOL},
                             {"version": "v45", "eol": EOL},
                             {"version": "45.3.3", "eol": "2027-13-40"},
                             {"version": "45.3.3", "eol": "April 2027"},
                             {"version": 45, "eol": EOL})):
        assert diag.electron_eol(_pin_root(tmp_path / f"bad{i}", doc)) is None, doc
    pin = {"version": "45.3.3", "eol": EOL}
    assert "electron_eol" not in _rows({"electron_eol": pin}, EOL_AT - 31 * DAY)
    assert "electron_eol" not in _rows({"electron_eol": None}, EOL_AT)
    assert "electron_eol" not in _rows({}, EOL_AT)
    assert "electron_eol" not in _rows({"electron_eol": {"version": "x", "eol": EOL}},
                                       EOL_AT)
    core = _real_core(tmp_path, monkeypatch, empty)
    facts = core.diag_facts(EOL_AT)
    assert facts["electron_eol"] is None
    assert "electron_eol" not in _rows(facts, EOL_AT)


def test_notes_never_reach_the_network(tmp_path, monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("no request and no process from the Checks notes")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    root = _loop_root(tmp_path / "repo", {"updated": STAMP})
    _pin_root(root, {"version": "45.3.3", "eol": "2026-12-01"})
    now = AT + 5 * 3600
    facts = {"loop_tick_age_s": diag.loop_tick_age(root, now),
             "electron_eol": diag.electron_eol(root)}
    v = diag.view(facts, "0", now=now)
    ids = {r["id"] for r in v["checks"]}
    assert {"dev_loop", "electron_eol"} <= ids
    # diag.py imports no network or process module (decision 0013)
    tree = ast.parse((REPO / "server" / "al" / "diag.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names |= {node.module or ""} | {a.name for a in node.names}
    for bad in ("urllib", "http", "socket", "webfetch", "subprocess", "procs"):
        assert not any(bad in n for n in names), bad


@pytest.mark.parametrize("age", [2 * 3600 + 1, 30 * DAY])
def test_old_tick_ages_render_in_words(age):
    r = _rows({"loop_tick_age_s": age}, AT + age)["dev_loop"]
    assert diag.AGO in r["detail"] and "ago" in diag.render_detail(r, AT + age)
