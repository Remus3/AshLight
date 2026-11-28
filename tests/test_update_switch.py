"""REL-UPDATE-SWITCH (finding F-077, DEP-11): apply-staged, confirm and
rollback (server/al/install/switch.py and its three command modules).

A scratch home under a pytest tmp folder: version OLD active, NEW laid
out beside it with its own MANIFEST.json and runtime folders, and a staged
document for NEW. Every shell effect goes through FakeShell, the one
injected runner, with al_shell.ps1's "is it ours" rule on an in-memory
shell; no PowerShell, registry, shortcut or scheduled task is touched. No
request leaves the process (an autouse fixture fails any socket connect)
and no child process starts (subprocess.Popen and subprocess.run fail the
test). "A core of this home runs" is an injected callable, except where
the default reader is checked on this test process's own pid.
"""

import hashlib
import io
import json
import os
import socket
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from server.al import keepalive as ka
from server.al import paths
from server.al.install import cli, switch
from server.al.install import home as homemod

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "server" / "al" / "install"
WHEN = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
OLD, NEW, NEWER = "1.2.3", "1.3.0", "1.4.0"
PY_OLD, PY_NEW, EL = "python-3.14.10", "python-3.14.11", "electron-45.3.3"


def _under(path, root):
    p = os.path.normcase(os.path.abspath(path)).rstrip("\\/")
    r = os.path.normcase(os.path.abspath(root)).rstrip("\\/")
    return p == r or p.startswith(r + os.sep)


class FakeShell:
    """The runner, with al_shell.ps1's rules on an in-memory shell."""

    def __init__(self, links=None, entry=None, task=None, fail=False):
        self.links = links if links is not None else {"Programs": None, "Desktop": None}
        self.entry = entry
        self.task = task
        self.fail = fail
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        if self.fail:
            from server.al.install import shell
            raise shell.ShellError("al_shell failed: stand-in")
        owner = request["owner_root"]
        want_link = {k: request["shortcut"][k]
                     for k in ("target", "arguments", "workdir", "icon")}
        states = []
        for name in ("Programs", "Desktop"):
            have = self.links.get(name)
            if have is not None and not _under(have["target"], owner):
                states.append("elsewhere")
            elif have == want_link:
                states.append("current")
            else:
                self.links[name] = dict(want_link)
                states.append("written")
        want_entry = dict(request["uninstall"])
        if self.entry == want_entry:
            entry_state = "current"
        else:
            self.entry = want_entry
            entry_state = "written"
        t = request["task"]
        if self.task is None:
            task_state = "absent"
        elif (self.task["execute"], self.task["arguments"], self.task["workdir"]) == \
                (t["execute"], t["arguments"], t["workdir"]):
            task_state = "current"
        else:
            self.task = dict(self.task, execute=t["execute"], arguments=t["arguments"],
                             workdir=t["workdir"])
            task_state = "written"
        return {"shortcuts": states, "uninstall_entry": entry_state,
                "logon_task": task_state}


@pytest.fixture(autouse=True)
def sealed(monkeypatch):
    """No socket connect and no child process in this file."""
    def no_connect(*_a, **_k):
        raise AssertionError("a test of the switch opened a socket")

    def no_child(*_a, **_k):
        raise AssertionError("a test of the switch started a process")
    monkeypatch.setattr(socket.socket, "connect", no_connect)
    monkeypatch.setattr(subprocess, "Popen", no_child)
    monkeypatch.setattr(subprocess, "run", no_child)
    for key in (paths.HOME_ENV, paths.SIDECAR_ENV, paths.RUNTIME_ENV):
        monkeypatch.delenv(key, raising=False)


def _payload(home, version):
    """A laid-out version folder with its own MANIFEST.json."""
    base = Path(home) / "app" / version
    files = {
        "scripts/al_shell.ps1": b"# al_shell\n",
        "scripts/uninstall.ps1": f"# uninstall {version}\n".encode("ascii"),
        "app/assets/icon.ico": b"icon\n",
        "app/main.js": b"'use strict';\n",
        "boot.py": b"# boot\n",
    }
    table = {}
    for rel, body in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        table[rel] = {"sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}
    (base / "MANIFEST.json").write_text(json.dumps({"files": table}) + "\n",
                                        encoding="ascii")
    return base


def _runtime(home, *names):
    for name in names:
        (Path(home) / "runtime" / name).mkdir(parents=True, exist_ok=True)


def _stage(home, version, apply_after, python=PY_NEW, electron=EL):
    manifest = Path(home) / "app" / version / "MANIFEST.json"
    doc = {"schema": 1, "name": "AshLight", "version": version, "from": OLD,
           "published_at": homemod.now_text(apply_after - timedelta(hours=24)),
           "apply_after": homemod.now_text(apply_after),
           "hashes": {"zip": "0" * 64,
                      "manifest": hashlib.sha256(manifest.read_bytes()).hexdigest()},
           "size": 1, "python": python, "electron": electron,
           "staged_at": homemod.now_text(WHEN - timedelta(hours=1))}
    path = Path(home) / "staged" / f"{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc) + "\n", encoding="ascii")
    return path


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "AshLight"
    homemod.make_layout(h, private=lambda p: None)
    _payload(h, OLD)
    _payload(h, NEW)
    _runtime(h, PY_OLD, PY_NEW, EL)
    homemod.write_marker(h, homemod.new_marker(OLD, PY_OLD, EL, now=WHEN))
    (h / "data" / "settings.json").write_text('{"keep": true}\n', encoding="ascii")
    return h


@pytest.fixture
def fake(home):
    """The shell as an install of OLD left it."""
    app = home / "app" / OLD / "app"
    link = {"target": str(home / "runtime" / EL / "electron.exe"),
            "arguments": '"' + str(app) + '" --client', "workdir": str(app),
            "icon": str(app / "assets" / "icon.ico")}
    entry = {"install_location": str(home), "version": OLD,
             "icon": str(app / "assets" / "icon.ico")}
    task = {"execute": str(home / "runtime" / PY_OLD / "pythonw.exe"),
            "arguments": subprocess.list2cmdline(
                [str(home / "app" / OLD / "boot.py"), "server.al.autostart_entry"]),
            "workdir": str(home / "app" / OLD), "user": "player", "delay": "PT30S",
            "description": "AshLight autostart"}
    return FakeShell(links={"Programs": dict(link), "Desktop": dict(link)},
                     entry=dict(entry), task=dict(task))


def _idle(_home):
    return False


def _apply(home, fake, **kw):
    kw.setdefault("now", WHEN)
    kw.setdefault("running", _idle)
    return switch.apply(home, runner=fake, **kw)


def _report(home):
    path = home / "logs" / "reports" / "last-update.json"
    return json.loads(path.read_text(encoding="ascii")) if path.exists() else {}


def _lines(home):
    return _report(home).get("lines", [])


def _points_at(fake, home, version):
    """Every shell entry of the fake names `version`'s folders, and a
    second pass of the runner has nothing left to change."""
    app = str(home / "app" / version / "app")
    for link in fake.links.values():
        assert link["workdir"] == app
    assert fake.entry["version"] == version
    assert fake.task["workdir"] == str(home / "app" / version)
    assert (home / "uninstall.ps1").read_bytes() == \
        f"# uninstall {version}\n".encode("ascii")


# --- apply-staged ----------------------------------------------------------------

def test_apply_staged_with_nothing_staged_returns_in_under_300_ms(home, fake):
    before = (home / "install.json").read_bytes()

    def never(_h):
        raise AssertionError("the no-op path asked whether a core runs")
    best = None
    for _ in range(3):
        t0 = time.perf_counter()
        code, res = switch.apply(home, runner=fake, running=never, now=WHEN)
        took = time.perf_counter() - t0
        best = took if best is None else min(best, took)
        assert (code, res["status"]) == (switch.EXIT_OK, switch.NOTHING)
    assert best < 0.3, best
    assert (home / "install.json").read_bytes() == before
    assert fake.calls == 0
    t0 = time.perf_counter()
    assert cli.main(["apply-staged", "--if-due", "--home", str(home)]) == 0
    assert time.perf_counter() - t0 < 0.3 * 3


def test_a_staged_version_younger_than_apply_after_is_not_applied(home, fake):
    _stage(home, NEW, WHEN + timedelta(hours=3))
    before = (home / "install.json").read_bytes()
    code, res = _apply(home, fake, if_due=True)
    assert (code, res["status"]) == (switch.EXIT_OK, switch.NOT_DUE)
    assert res["apply_after"] == homemod.now_text(WHEN + timedelta(hours=3))
    assert (home / "install.json").read_bytes() == before
    assert (home / "staged" / f"{NEW}.json").exists()
    assert fake.calls == 0


def test_when_due_and_no_core_runs_the_marker_and_shell_entries_switch(home, fake):
    _stage(home, NEW, WHEN - timedelta(minutes=1))
    data_before = {p.name: p.read_bytes() for p in (home / "data").iterdir()}
    asked = []
    code, res = _apply(home, fake, if_due=True,
                       running=lambda h: asked.append(h) or False)
    assert (code, res["status"]) == (switch.EXIT_SWITCHED, switch.SWITCHED), res
    assert asked, "the switch did not ask whether a core of this home runs"
    marker = homemod.read_marker(home)
    assert marker["version"] == NEW and marker["previous"] == OLD
    assert marker["pending_confirm"] is True and marker["start_attempts"] == 0
    assert marker["python"] == PY_NEW and marker["electron"] == EL
    assert marker["previous_runtimes"] == {"python": PY_OLD, "electron": EL}
    # read back: the shortcuts, uninstall entry, uninstall.ps1 and task
    _points_at(fake, home, NEW)
    assert fake.task["execute"] == str(home / "runtime" / PY_NEW / "pythonw.exe")
    assert res["shell"]["uninstall_script"] == "written"
    assert res["shell"]["logon_task"] == "written"
    assert fake.calls == 2  # the write and its read-back pass
    assert not (home / "staged" / f"{NEW}.json").exists()
    assert {p.name: p.read_bytes() for p in (home / "data").iterdir()} == data_before
    assert len(_lines(home)) == 1 and f"to {NEW}" in _lines(home)[0]


def test_apply_without_if_due_is_update_now(home, fake):
    _stage(home, NEW, WHEN + timedelta(hours=20))
    code, res = _apply(home, fake, if_due=False)
    assert code == switch.EXIT_SWITCHED, res
    assert homemod.read_marker(home)["version"] == NEW
    assert cli.main(["apply-staged", "--no-such-flag"]) == 2


def test_never_while_a_core_of_this_home_runs(home, fake):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    before = (home / "install.json").read_bytes()
    code, res = _apply(home, fake, running=lambda h: True)
    assert (code, res["status"]) == (switch.EXIT_BUSY, switch.BUSY)
    assert (home / "install.json").read_bytes() == before
    assert (home / "staged" / f"{NEW}.json").exists() and fake.calls == 0


def test_core_running_reads_only_this_homes_own_files(home):
    assert switch.core_running(home) is False  # no core.alive, no supervisor files
    beat = home / "data" / ka.HEARTBEAT_FILE
    me = os.getpid()
    beat.write_text(json.dumps({"pid": me, "port": 8961, "updated": time.time(),
                                "created": 0}) + "\n", encoding="ascii")
    assert switch.core_running(home) is True  # this python process, proven ours
    beat.write_text(json.dumps({"pid": me, "port": 8961, "updated": time.time(),
                                "created": 1}) + "\n", encoding="ascii")
    assert switch.core_running(home) is False  # a reused pid is not ours
    src = (PKG / "switch.py").read_text(encoding="ascii")
    for word in ("list_processes", "CreateToolhelp32Snapshot", "tasklist",
                 "subprocess", "PathOfExile"):
        assert word not in src, word


def test_a_skipped_or_tampered_version_is_not_applied(home, fake):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    switch.record_skip(home, NEW, "test", now=WHEN)
    before = (home / "install.json").read_bytes()
    code, res = _apply(home, fake)
    assert (code, res["status"]) == (switch.EXIT_OK, switch.NOTHING)
    assert not (home / "staged" / f"{NEW}.json").exists()
    assert (home / "install.json").read_bytes() == before
    (home / "data" / switch.SKIP_NAME).unlink()
    (home / "data" / (switch.SKIP_NAME + ".bak")).unlink()
    _stage(home, NEW, WHEN - timedelta(hours=1))
    (home / "app" / NEW / "boot.py").write_bytes(b"# changed\n")
    code, res = _apply(home, fake)
    assert code == switch.EXIT_FAIL and "MANIFEST" in res["reason"]
    assert (home / "install.json").read_bytes() == before and fake.calls == 0


def test_a_shell_failure_puts_the_old_marker_back(home):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    before = homemod.read_marker(home)
    code, res = _apply(home, FakeShell(fail=True))
    assert code == switch.EXIT_FAIL and "al_shell" in res["reason"]
    assert homemod.read_marker(home) == before


# --- rollback ------------------------------------------------------------------------

def test_the_confirm_waits_180_s_and_three_starts_decide(home):
    # REL-CONFIRM-PATIENCE (research 0066 F12): a slow first start keeps
    # its release
    from server.al.install import confirm as confirm_cmd
    assert switch.CONFIRM_WAIT_S == 180.0
    assert switch.MAX_ATTEMPTS == 3
    seen = {}
    real = switch.confirm

    def spy(h, **kw):
        seen.update(kw)
        return real(h, **kw)
    try:
        switch.confirm = spy
        confirm_cmd.main(["--home", str(home), "--wait"], health=lambda h: OLD,
                         out=io.StringIO())
    finally:
        switch.confirm = real
    assert seen.get("wait_s") == 180.0


def test_a_version_that_never_confirms_is_rolled_back_at_the_third_start(home, fake):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[0] == switch.EXIT_SWITCHED
    # the relaunch from the marker: the first and second starts of NEW count
    code, res = _apply(home, fake)
    assert (code, res["status"]) == (switch.EXIT_OK, switch.STARTED)
    assert homemod.read_marker(home)["start_attempts"] == 1
    code, res = _apply(home, fake)
    assert (code, res["status"]) == (switch.EXIT_OK, switch.STARTED)
    assert homemod.read_marker(home)["start_attempts"] == 2
    lines = len(_lines(home))
    # no health answer came: the third start rolls back by itself
    code, res = _apply(home, fake)
    assert (code, res["status"]) == (switch.EXIT_SWITCHED, switch.ROLLED_BACK), res
    marker = homemod.read_marker(home)
    assert marker["version"] == OLD and marker["previous"] is None
    assert marker["pending_confirm"] is False and marker["start_attempts"] == 0
    assert marker["python"] == PY_OLD and "previous_runtimes" not in marker
    _points_at(fake, home, OLD)
    skip = json.loads((home / "data" / switch.SKIP_NAME).read_text(encoding="ascii"))
    assert [r["version"] for r in skip["versions"]] == [NEW]
    assert skip["versions"][0]["class"] == switch.SKIP_NO_ANSWER
    assert skip["versions"][0]["offers"] == 1
    assert switch.skipped(home, now=WHEN) == {NEW}
    assert len(_lines(home)) == lines + 1
    assert f"from {NEW} to {OLD}" in _lines(home)[-1]
    # NEW is not applied again within the 7 days; a newer release is
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[1]["status"] == switch.NOTHING
    _payload(home, NEWER)
    _stage(home, NEWER, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[0] == switch.EXIT_SWITCHED
    assert homemod.read_marker(home)["version"] == NEWER


def _never_confirms(home, fake, now):
    for _ in range(switch.MAX_ATTEMPTS):
        code, res = _apply(home, fake, now=now)
    assert (code, res["status"]) == (switch.EXIT_SWITCHED, switch.ROLLED_BACK), res


def test_a_no_answer_skip_is_offered_once_more_after_7_days(home, fake):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[0] == switch.EXIT_SWITCHED
    _never_confirms(home, fake, WHEN)
    held = WHEN + timedelta(days=7) - timedelta(seconds=1)
    assert switch.skipped(home, now=held) == {NEW}
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake, now=held)[1]["status"] == switch.NOTHING
    # 7 days on: offered once more and switched to
    later = WHEN + timedelta(days=7)
    assert switch.skipped(home, now=later) == set()
    _stage(home, NEW, later - timedelta(hours=1))
    code, res = _apply(home, fake, now=later)
    assert (code, res["status"]) == (switch.EXIT_SWITCHED, switch.SWITCHED), res
    # no answer again: this time the skip holds for good
    _never_confirms(home, fake, later)
    skip = json.loads((home / "data" / switch.SKIP_NAME).read_text(encoding="ascii"))
    assert [(r["version"], r["class"], r["offers"]) for r in skip["versions"]] == [
        (NEW, switch.SKIP_NO_ANSWER, 2)]
    assert switch.skipped(home, now=later + timedelta(days=400)) == {NEW}


def test_a_confirmed_reoffer_needs_no_skip_and_old_rows_hold(home, fake):
    # a re-offered version that answers is just the active version
    _stage(home, NEW, WHEN - timedelta(hours=1))
    _apply(home, fake)
    _never_confirms(home, fake, WHEN)
    later = WHEN + timedelta(days=8)
    _stage(home, NEW, later - timedelta(hours=1))
    assert _apply(home, fake, now=later)[0] == switch.EXIT_SWITCHED
    code, res = switch.confirm(home, health=lambda h: NEW, now=later)
    assert res["status"] == switch.CONFIRMED
    assert homemod.read_marker(home)["version"] == NEW
    # a row written before the classes (no class) and an unknown class hold
    path = home / "data" / switch.SKIP_NAME
    path.write_text(json.dumps({"schema": 1, "name": "AshLight", "versions": [
        {"version": "2.0.0", "at": homemod.now_text(WHEN),
         "reason": "no health answer after 2 starts"},
        {"version": "2.1.0", "at": homemod.now_text(WHEN), "reason": "x",
         "class": "crash"},
        {"version": "2.2.0", "at": "not a time", "reason": "x",
         "class": switch.SKIP_NO_ANSWER}]}), encoding="ascii")
    assert switch.skipped(home, now=WHEN + timedelta(days=400)) == {
        "2.0.0", "2.1.0", "2.2.0"}
    # a class the caller makes up is stored as manual (holds for good)
    switch.record_skip(home, "2.3.0", "x", now=WHEN, kind="bogus")
    rows = json.loads(path.read_text(encoding="ascii"))["versions"]
    assert rows[-1]["class"] == switch.SKIP_MANUAL


def test_the_core_staged_note_follows_the_reoffer(home, fake):
    from server.al import paths as pathsmod
    _stage(home, NEW, WHEN - timedelta(hours=1))
    _apply(home, fake)
    _never_confirms(home, fake, WHEN)
    doc = json.loads((home / "data" / switch.SKIP_NAME).read_text(encoding="ascii"))
    assert pathsmod.held_skips(doc, WHEN) == {NEW}
    assert pathsmod.held_skips(doc, WHEN + timedelta(days=7)) == set()


def test_rollback_by_hand_restores_n_and_reads_back(home, fake, monkeypatch):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[0] == switch.EXIT_SWITCHED
    real = switch.rollback

    def fake_rollback(h, **kw):
        kw.update(runner=fake, running=_idle, now=WHEN)
        return real(h, **kw)
    monkeypatch.setattr(switch, "rollback", fake_rollback)
    out = io.StringIO()
    assert cli.main(["rollback", "--home", str(home)]) == switch.EXIT_SWITCHED
    marker = homemod.read_marker(home)
    assert marker["version"] == OLD and marker["pending_confirm"] is False
    assert marker["python"] == PY_OLD
    _points_at(fake, home, OLD)
    assert fake.entry["install_location"] == str(home)
    assert switch.skipped(home) == {NEW}
    skip = json.loads((home / "data" / switch.SKIP_NAME).read_text(encoding="ascii"))
    assert skip["versions"][-1]["class"] == switch.SKIP_MANUAL
    # a skip by hand holds for good
    assert switch.skipped(home, now=WHEN + timedelta(days=400)) == {NEW}
    # nothing left to go back to
    code, res = real(home, runner=fake, running=_idle, now=WHEN, out=out)
    assert code == switch.EXIT_FAIL and "no previous version" in res["reason"]


def test_rollback_without_a_runtime_record_reads_the_cached_release(home, fake):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[0] == switch.EXIT_SWITCHED
    marker = homemod.read_marker(home)
    del marker["previous_runtimes"]
    homemod.write_marker(home, marker)
    rel = home / "cache" / "downloads" / OLD / "release.json"
    rel.parent.mkdir(parents=True, exist_ok=True)
    pin = {"sha256": "0" * 64, "size": 1, "licence": "MIT"}
    rel.write_text(json.dumps({"name": "AshLight", "version": OLD, "runtimes": {
        "python": dict(pin, version="3.14.10", url="https://www.python.org/ftp/python/"
                       "3.14.10/python-3.14.10-embed-amd64.zip"),
        "electron": dict(pin, version="45.3.3", url="https://github.com/electron/"
                         "electron/releases/download/v45.3.3/"
                         "electron-v45.3.3-win32-x64.zip")}}), encoding="ascii")
    code, res = switch.rollback(home, runner=fake, running=_idle, now=WHEN)
    assert code == switch.EXIT_SWITCHED, res
    assert homemod.read_marker(home)["python"] == PY_OLD


def test_rollback_never_while_a_core_runs(home, fake):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[0] == switch.EXIT_SWITCHED
    before = (home / "install.json").read_bytes()
    code, res = switch.rollback(home, runner=fake, running=lambda h: True, now=WHEN)
    assert (code, res["status"]) == (switch.EXIT_BUSY, switch.BUSY)
    assert (home / "install.json").read_bytes() == before
    assert not (home / "data" / switch.SKIP_NAME).exists()


# --- confirm ---------------------------------------------------------------------------

def test_confirm_clears_pending_and_removes_what_neither_version_needs(home, fake):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[0] == switch.EXIT_SWITCHED
    _payload(home, "1.0.0")                     # an old version: neither
    _payload(home, NEWER)                       # staged next: kept
    _stage(home, NEWER, WHEN + timedelta(hours=10), python="python-3.14.12")
    _runtime(home, "python-3.13.0", "electron-44.0.0", "python-3.14.12")
    (home / "app" / f"{NEWER}.partial").mkdir()  # not a version folder: left
    asked = []

    def health(h):
        asked.append(h)
        return {"ok": True, "version": NEW, "mode": "installed"}
    code, res = switch.confirm(home, health=health, now=WHEN)
    assert (code, res["status"]) == (switch.EXIT_OK, switch.CONFIRMED), res
    assert asked == [home]
    marker = homemod.read_marker(home)
    assert marker["pending_confirm"] is False and marker["start_attempts"] == 0
    assert marker["version"] == NEW and marker["previous"] == OLD
    assert homemod.version_dirs(home) == [OLD, NEW, NEWER]
    assert (home / "app" / f"{NEWER}.partial").is_dir()
    assert sorted(os.listdir(home / "runtime")) == sorted(
        [PY_OLD, PY_NEW, EL, "python-3.14.12"])
    assert res["removed"] == {"versions": ["1.0.0"],
                              "runtimes": ["electron-44.0.0", "python-3.13.0"]}
    assert "confirmed" in _lines(home)[-1]
    # a confirmed version needs no second confirm, and no rollback follows
    assert switch.confirm(home, health=health)[1]["status"] == switch.CURRENT
    assert _apply(home, fake)[1]["status"] == switch.NOT_DUE


def test_confirm_needs_the_active_versions_own_answer(home, fake):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    assert _apply(home, fake)[0] == switch.EXIT_SWITCHED
    _payload(home, "1.0.0")
    clock = [0.0]

    def tick(s):
        clock[0] += s
    answers = iter([None, {"version": OLD}, RuntimeError("refused")] + [None] * 20)

    def health(_h):
        got = next(answers)
        if isinstance(got, Exception):
            raise got
        return got
    code, res = switch.confirm(home, health=health, wait_s=5, poll_s=1, sleep=tick,
                               clock=lambda: clock[0], now=WHEN)
    assert (code, res["status"]) == (switch.EXIT_FAIL, switch.UNCONFIRMED)
    assert clock[0] >= 5
    assert homemod.read_marker(home)["pending_confirm"] is True
    assert "1.0.0" in homemod.version_dirs(home)
    # the confirm command: --wait polls the injected answer
    from server.al.install import confirm as confirm_cmd
    assert confirm_cmd.main(["--home", str(home)], health=lambda h: NEW,
                            out=io.StringIO()) == 0
    assert homemod.read_marker(home)["pending_confirm"] is False
    assert confirm_cmd.main(["--timeout", "-1"]) == 2


def test_default_health_needs_this_homes_own_core(home):
    assert switch.default_health(home) is None  # no core.alive: no request


# --- shared ----------------------------------------------------------------------------

def test_the_report_and_skip_file_name_no_path(home, fake, tmp_path):
    _stage(home, NEW, WHEN - timedelta(hours=1))
    _apply(home, fake)
    _never_confirms(home, fake, WHEN)  # rolled back
    for path in (home / "logs" / "reports" / "last-update.json",
                 home / "data" / switch.SKIP_NAME):
        text = path.read_text(encoding="ascii")
        for form in (str(tmp_path), str(tmp_path).replace("\\", "/"),
                     json.dumps(str(tmp_path))[1:-1]):
            assert form not in text, path.name


def test_the_three_commands_are_in_the_table_and_refuse_a_game_home(tmp_path):
    for command in ("apply-staged", "rollback", "confirm"):
        assert cli.load(command) is not None, command
    bad = tmp_path / "steamapps" / "common" / "AshLight"
    out = io.StringIO()
    assert switch.apply(bad, out=out)[0] == switch.EXIT_USAGE
    assert switch.rollback(bad, out=out)[0] == switch.EXIT_USAGE
    assert switch.confirm(bad, out=out)[0] == switch.EXIT_USAGE
    assert not bad.exists()


def test_default_idle_reads_only_a_boolean_game_idle(monkeypatch, tmp_path):
    # REL-UPDATE-AUTO-IDLE (research 0066 F4): the automatic update's gate
    # reads this home's own core snapshot; anything but a boolean is unknown
    asked = []
    real = switch._core_doc

    def doc(answer):
        def fake(home, route, max_bytes, timeout):
            asked.append((home, route, max_bytes))
            return answer
        return fake
    for answer, want in (({"game_idle": True}, True), ({"game_idle": False}, False),
                         ({"game_idle": "yes"}, None), ({}, None), (None, None)):
        monkeypatch.setattr(switch, "_core_doc", doc(answer))
        assert switch.default_idle(tmp_path) is want, answer
    assert {a[1] for a in asked} == {"/api/state"}
    assert {a[2] for a in asked} == {switch.MAX_STATE_BYTES}
    # with no heartbeat in the home there is no core to ask: unknown
    monkeypatch.setattr(switch, "_core_doc", real)
    assert switch.default_idle(tmp_path) is None
