"""DEP-11 (finding F-077, local half): `installer update --zip FILE`
(server/al/install/update.py stage_from_zip).

A scratch home: three app zips built by tools/rel_build.py from a scratch
git repo under a pytest tmp folder, version N installed by install.run
with fakes (self-test, shell runner, client start, data ACL), then N to
N+1 and N+1 to N+2 staged from the local zips. The self-test is a fake, or
the real selftest.run with a fake child. No request leaves the process (an
autouse fixture fails any socket connect) and no real child process starts
(subprocess.Popen and subprocess.run fail the test).

DEP-17 (the network half, stage_from_release and `update --yes`): a fake
GitHub on loopback. FakeGitHub is a local HTTP server; LoopbackOpener is
the request opener handed to the installer's real fetch
(payload.installer_stream), so the host allow-list, the redirect hops,
the User-Agent and the size caps run for real and only the socket goes to
127.0.0.1 (the connect guard allows loopback and nothing else).
"""

import hashlib
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import NAME, pinfetch  # noqa: E402
from server.al.install import cli, install, payload, update  # noqa: E402
from server.al.install import home as homemod  # noqa: E402
from server.al.install import selftest as selftestmod  # noqa: E402
from server.al.install import switch as switchmod  # noqa: E402
from server.al import updates  # noqa: E402

_REAL_CONNECT = socket.socket.connect
_REAL_CREATE = socket.create_connection

VER_N = "1.2.3"
VER_N1 = "1.3.0"
VER_N2 = "1.4.0"
WHEN = "2026-11-19T10:20:30Z"
STAMP = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
SRC_UPDATE = ROOT / "server" / "al" / "install" / "update.py"

_GIT = ["git", "-c", "core.hooksPath=", "-c", "user.name=t",
        "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]

FILES = {
    "server/al/core.py": "\"\"\"Stand-in core.\"\"\"\nVALUE = 1\n",
    "server/al/data/selftest/client_selftest.txt": "2026/11/19 10:00:00 stand-in\n",
    "web/index.html": "<!doctype html><title>AshLight</title>\n",
    "app/main.js": "'use strict';\n",
    "config/tc_pins.json": "{}\n",
    "tools/tc_pin.py": "# pin tool\n",
    "scripts/al_shell.ps1": "# stand-in al_shell\n",
    "scripts/uninstall.ps1": "# stand-in uninstall\n",
    "README.md": "# AshLight\n",
    "LICENSE": "licence\n",
    "boot.py": "# boot\n",
}


def _runtime_zip(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return out.getvalue()


PY_ZIP = _runtime_zip({"python.exe": b"stand-in python\n",
                       "pythonw.exe": b"stand-in pythonw\n",
                       "python314._pth": b".\n"})
PY2_ZIP = _runtime_zip({"python.exe": b"stand-in python 2\n",
                        "pythonw.exe": b"stand-in pythonw 2\n",
                        "python314._pth": b".\n"})
EL_ZIP = _runtime_zip({"electron.exe": b"stand-in electron\n", "LICENSE": b"MIT\n"})
PY_URL = "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip"
PY2_URL = "https://www.python.org/ftp/python/3.14.11/python-3.14.11-embed-amd64.zip"
EL_URL = ("https://github.com/electron/electron/releases/download/v45.3.3/"
          "electron-v45.3.3-win32-x64.zip")
PY_RT = "python-3.14.10"
PY2_RT = "python-3.14.11"
EL_RT = "electron-45.3.3"


def _pin(url, data, version, licence):
    return {"version": version, "file": url.rsplit("/", 1)[-1], "url": url,
            "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
            "licence": licence}


def _release_doc(version, py=(PY_URL, PY_ZIP, "3.14.10")):
    return {"name": NAME, "version": version, "runtimes": {
        "python": _pin(py[0], py[1], py[2], "PSF-2.0"),
        "electron": _pin(EL_URL, EL_ZIP, "45.3.3", "MIT")}}


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(
        "updater_test_" + name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE=WHEN, GIT_COMMITTER_DATE=WHEN)
    proc = subprocess.run(_GIT + list(args), cwd=str(cwd), env=env,
                          capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr


@pytest.fixture(scope="module")
def releases(tmp_path_factory):
    """{version: {zip, sums, release, dir}} for N, N+1 and N+2, plus 'rt':
    a -RuntimeDir folder with the stand-in publisher zips."""
    base = tmp_path_factory.mktemp("rel")
    repo = base / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for rel, text in FILES.items():
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(text.encode("ascii"))
    (repo / "config" / "ship_list.json").write_bytes(
        (ROOT / "config" / "ship_list.json").read_bytes())
    (base / "cache").mkdir()
    rb = _load_tool("rel_build")
    out = {}
    for version in (VER_N, VER_N1, VER_N2):
        init = repo / "server" / "al" / "__init__.py"
        init.write_bytes(("\"\"\"AshLight.\"\"\"\n\nVERSION = \"%s\"\n" % version)
                         .encode("ascii"))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "chore: scratch %s" % version)
        folder = base / ("out-" + version)
        res = rb.build(root=repo, ref="HEAD", out=folder, cache_dir=base / "cache")
        rel = folder / "release.json"
        rel.write_text(json.dumps(_release_doc(version), indent=1) + "\n",
                       encoding="ascii")
        out[version] = {"zip": res["zip"], "sums": folder / rb.SUMS_NAME,
                        "release": rel, "dir": folder}
    rt = base / "rt"
    rt.mkdir()
    for url, data in ((PY_URL, PY_ZIP), (PY2_URL, PY2_ZIP), (EL_URL, EL_ZIP)):
        (rt / url.rsplit("/", 1)[-1]).write_bytes(data)
    out["rt"] = rt
    return out


@pytest.fixture(autouse=True)
def sealed(monkeypatch, releases):
    """No network and no real child process during a test."""
    def refuse(*_a, **_k):
        raise AssertionError("a test tried to open a network connection")

    def no_child(*_a, **_k):
        raise AssertionError("a test tried to start a real process")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(subprocess, "Popen", no_child)
    monkeypatch.setattr(subprocess, "run", no_child)


class FakeSelftest:
    def __init__(self, status=selftestmod.PASSED):
        self.status = status
        self.calls = []

    def __call__(self, home, version):
        self.calls.append(version)
        return selftestmod.Result(status=self.status, version=version,
                                  stage="health", reason="answered")


class FakePriority:
    """The priority class setter: records every class set."""

    def __init__(self, start=0x20):
        self.current = start
        self.calls = []

    def __call__(self, cls):
        self.calls.append(cls)
        old, self.current = self.current, cls
        return old


class ShellRunner:
    """The shell runner: 'written' for a request it has not seen, then
    'current' (the read-back pass); the logon task is absent."""

    def __init__(self):
        self.seen = []

    def __call__(self, request):
        state = "current" if request in self.seen else "written"
        self.seen.append(json.loads(json.dumps(request)))
        return {"shortcuts": [state, state], "uninstall_entry": state,
                "logon_task": "absent"}


@pytest.fixture
def home(tmp_path, releases):
    """A home with version N installed (no client start)."""
    h = tmp_path / "home"
    code, report = install.run(
        releases[VER_N]["zip"], h, runtime_dir=releases["rt"], start=False,
        selftest=FakeSelftest(), runner=ShellRunner(), spawn=None,
        private=lambda _p: None, effect_root=tmp_path / "effects",
        environ={"PATH": "x"}, now=STAMP, out=io.StringIO())
    assert code == install.EXIT_OK, (report["stage"], report["reason"])
    data = h / "data"
    (data / "local.json").write_text('{"web_data": false, "mine": 1}\n',
                                     encoding="ascii")
    (data / "run_history.json").write_bytes(b'{"schema": 2, "runs": []}\n')
    (data / "sub").mkdir()
    (data / "sub" / "notes.bin").write_bytes(bytes(range(256)))
    return h


def _tree(folder, skip=()):
    out = {}
    for path in sorted(Path(folder).rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if rel in skip:
            continue
        out[rel] = path.read_bytes() if path.is_file() else None
    return out


def _stage(home, rel, **kw):
    kw.setdefault("clicked", True)
    kw.setdefault("selftest", FakeSelftest())
    kw.setdefault("priority", FakePriority())
    kw.setdefault("now", STAMP)
    out = kw.pop("out", None) or io.StringIO()
    code, report = update.stage_from_zip(home, rel["zip"], out=out, **kw)
    return code, report


def _report_doc(home):
    return json.loads((home / "logs" / "reports" / update.REPORT_NAME)
                      .read_text(encoding="ascii"))


def _copy_release(releases, tmp_path, version, zip_bytes=None, release_doc=None):
    folder = tmp_path / ("dl-" + version)
    folder.mkdir()
    src = releases[version]
    data = src["zip"].read_bytes() if zip_bytes is None else zip_bytes
    (folder / src["zip"].name).write_bytes(data)
    (folder / "SHA256SUMS.txt").write_bytes(src["sums"].read_bytes())
    if release_doc is None:
        (folder / "release.json").write_bytes(src["release"].read_bytes())
    else:
        (folder / "release.json").write_text(json.dumps(release_doc) + "\n",
                                             encoding="ascii")
    return {"zip": folder / src["zip"].name}


# --- N to N+1 to N+2 ------------------------------------------------------------------

def test_n_to_n1_to_n2_from_local_zips_keeps_data_byte_for_byte(home, releases):
    data_before = _tree(home / "data")
    marker_n = (home / "install.json").read_bytes()

    code, report = _stage(home, releases[VER_N1])
    assert code == update.EXIT_OK, report
    assert report["status"] == "staged" and report["from"] == VER_N
    assert report["version"] == VER_N1
    assert (home / "install.json").read_bytes() == marker_n  # never the marker
    assert payload.check_manifest(home / "app" / VER_N1) == []
    assert payload.check_manifest(home / "app" / VER_N, ignore_bytecode=True) == []
    assert update.staged_versions(home) == [VER_N1]
    assert _tree(home / "data") == data_before

    # the switch is apply-staged's (REL-UPDATE-SWITCH); stand in for it here
    homemod.switch_marker(home, VER_N1)
    code, report = _stage(home, releases[VER_N2])
    assert code == update.EXIT_OK, report
    assert report["from"] == VER_N1 and report["version"] == VER_N2
    assert report["superseded"] == [VER_N1]
    assert update.staged_versions(home) == [VER_N2]
    assert homemod.read_marker(home)["version"] == VER_N1
    assert homemod.version_dirs(home) == [VER_N, VER_N1, VER_N2]
    assert _tree(home / "data") == data_before
    cached = home / "cache" / "downloads" / VER_N2
    assert (cached / releases[VER_N2]["zip"].name).read_bytes() == \
        releases[VER_N2]["zip"].read_bytes()


def test_staged_file_holds_version_published_at_hashes_and_apply_after(home, releases):
    rel = releases[VER_N1]
    code, _report = _stage(home, rel, published_at="2026-11-19T10:00:00Z")
    assert code == update.EXIT_OK
    doc = json.loads((home / "staged" / (VER_N1 + ".json")).read_text(encoding="ascii"))
    assert doc["version"] == VER_N1 and doc["from"] == VER_N
    assert doc["published_at"] == "2026-11-19T10:00:00Z"
    assert doc["apply_after"] == "2026-11-20T10:00:00Z"
    zip_bytes = rel["zip"].read_bytes()
    assert doc["hashes"]["zip"] == hashlib.sha256(zip_bytes).hexdigest()
    assert doc["hashes"]["sums"] == hashlib.sha256(rel["sums"].read_bytes()).hexdigest()
    assert doc["hashes"]["release"] == \
        hashlib.sha256(rel["release"].read_bytes()).hexdigest()
    manifest = home / "app" / VER_N1 / payload.MANIFEST_NAME
    assert doc["hashes"]["manifest"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert doc["size"] == len(zip_bytes)
    assert doc["python"] == PY_RT and doc["electron"] == EL_RT
    assert doc["staged_at"] == "2026-11-20T12:00:00Z"
    assert update.read_staged(home, VER_N1) == doc


def test_published_at_defaults_to_release_json_then_now(home, releases, tmp_path):
    code, _r = _stage(home, releases[VER_N1])  # release.json has no time: now
    assert code == update.EXIT_OK
    doc = update.read_staged(home, VER_N1)
    assert doc["published_at"] == "2026-11-20T12:00:00Z"
    assert doc["apply_after"] == "2026-11-21T12:00:00Z"
    rdoc = _release_doc(VER_N2)
    rdoc["published_at"] = "2026-11-01T08:30:00Z"
    rel = _copy_release(releases, tmp_path, VER_N2, release_doc=rdoc)
    code, _r = _stage(home, rel)
    assert code == update.EXIT_OK
    assert update.read_staged(home, VER_N2)["apply_after"] == "2026-11-02T08:30:00Z"


def test_a_rerun_of_a_staged_version_changes_nothing(home, releases):
    test = FakeSelftest()
    assert _stage(home, releases[VER_N1], selftest=test)[0] == update.EXIT_OK
    staged = (home / "staged" / (VER_N1 + ".json")).read_bytes()
    code, report = _stage(home, releases[VER_N1], selftest=test)
    assert code == update.EXIT_OK and report["status"] == "staged"
    assert report["steps"]["selftest"] == "current" and test.calls == [VER_N1]
    assert (home / "staged" / (VER_N1 + ".json")).read_bytes() == staged


# --- refused, failed, deferred ---------------------------------------------------------------

def test_a_tampered_zip_is_refused_with_nothing_changed(home, releases, tmp_path):
    data = bytearray(releases[VER_N1]["zip"].read_bytes())
    data[len(data) // 2] ^= 1
    rel = _copy_release(releases, tmp_path, VER_N1, zip_bytes=bytes(data))
    report_rel = "logs/reports/" + update.REPORT_NAME
    before = _tree(home, skip={report_rel})
    test = FakeSelftest()
    code, report = _stage(home, rel, selftest=test)
    assert code == update.EXIT_FAIL
    assert report["stage"] == "verify" and "HashMismatch" in report["reason"]
    assert _tree(home, skip={report_rel}) == before
    assert test.calls == []
    assert _report_doc(home)["status"] == "failed"


def test_an_older_or_equal_version_is_refused(home, releases):
    code, report = _stage(home, releases[VER_N])
    assert code == update.EXIT_FAIL and report["stage"] == "verify"
    assert "not newer" in report["reason"]
    assert not (home / "staged").exists()


def test_no_install_means_no_update(tmp_path, releases):
    h = tmp_path / "empty"
    h.mkdir()
    code, report = _stage(h, releases[VER_N1])
    assert code == update.EXIT_FAIL and "no install" in report["reason"]
    assert not (h / "app").exists() and not (h / "staged").exists()


class FailProc:
    """A self-test child whose code check exits 1."""

    def __init__(self):
        self.returncode = None
        self.stdout = None
        self.pid = 0

    def wait(self, timeout=None):
        self.returncode = 1
        return 1

    def poll(self):
        return self.wait()

    def terminate(self):
        pass

    def kill(self):
        pass


def test_a_failed_self_test_leaves_the_marker_on_n_with_exit_1_and_one_report(
        home, releases):
    marker_n = (home / "install.json").read_bytes()
    reports_before = set(os.listdir(home / "logs" / "reports"))
    spawned = []

    def spawn(cmd, **kw):
        spawned.append((cmd, kw))
        return FailProc()
    code, report = _stage(home, releases[VER_N1], selftest=None, spawn=spawn)
    assert code == update.EXIT_FAIL
    assert report["stage"] == "selftest" and report["status"] == "failed"
    assert (home / "install.json").read_bytes() == marker_n
    assert homemod.read_marker(home)["version"] == VER_N
    assert not (home / "app" / VER_N1).exists()
    assert (home / "temp" / ("failed-" + VER_N1)).is_dir()
    assert not (home / "staged").exists()
    reports = set(os.listdir(home / "logs" / "reports")) - reports_before
    assert reports == {update.REPORT_NAME}
    doc = _report_doc(home)
    assert doc["status"] == "failed" and doc["selftest"]["stage"] == "check"
    assert doc["selftest"]["exit_code"] == 1
    assert doc["selftest"]["report"]["kind"] == "selftest"
    assert len(spawned) == 1 and "--check" in spawned[0][0]
    if os.name == "nt":  # the child runs hidden at below-normal priority
        assert spawned[0][1]["creationflags"] & update.BELOW_NORMAL


def test_the_work_runs_at_below_normal_priority_and_restores_it(home, releases,
                                                                monkeypatch):
    prio = FakePriority(start=0x20)
    seen = []
    real = install.lay_out

    def lay_out(*a, **k):
        seen.append(prio.current)
        return real(*a, **k)
    monkeypatch.setattr(install, "lay_out", lay_out)
    test = FakeSelftest()

    def selftest(h, v):
        seen.append(prio.current)
        return test(h, v)
    code, _r = _stage(home, releases[VER_N1], priority=prio, selftest=selftest)
    assert code == update.EXIT_OK
    assert seen == [update.BELOW_NORMAL, update.BELOW_NORMAL]
    assert prio.calls == [update.BELOW_NORMAL, 0x20] and prio.current == 0x20


@pytest.mark.skipif(os.name != "nt", reason="priority classes are a Windows call")
def test_the_real_priority_setter_lowers_and_restores_this_process():
    with update.below_normal() as old:
        assert old is not None
        inside = update.set_priority(update.BELOW_NORMAL)
        assert inside == update.BELOW_NORMAL
    after = update.set_priority(old)
    assert after == old


def test_it_waits_while_game_idle_is_false(home, releases, monkeypatch):
    answers = [False, None, False, True]
    asked = []

    def idle():
        asked.append(1)
        return answers.pop(0) if answers else True
    slept = []
    order = []
    real = install.lay_out

    def lay_out(*a, **k):
        order.append(len(asked))
        return real(*a, **k)
    monkeypatch.setattr(install, "lay_out", lay_out)
    code, report = _stage(home, releases[VER_N1], clicked=False, idle=idle,
                          sleep=slept.append, poll_s=5.0)
    assert code == update.EXIT_OK, report
    assert slept == [5.0, 5.0, 5.0] and report["waited"] == 3
    assert order == [4]  # the extract ran only after game_idle answered true
    assert report["steps"]["gate"] == "idle"


def test_never_idle_defers_with_nothing_laid_out(home, releases):
    report_rel = "logs/reports/" + update.REPORT_NAME
    before = _tree(home, skip={report_rel})
    prio = FakePriority()
    test = FakeSelftest()
    code, report = _stage(home, releases[VER_N1], clicked=False,
                          idle=lambda: False, max_wait_s=0, sleep=lambda _s: None,
                          priority=prio, selftest=test)
    assert code == update.EXIT_DEFERRED
    assert report["status"] == "deferred" and report["stage"] == "gate"
    assert _tree(home, skip={report_rel}) == before
    assert prio.calls == [] and test.calls == []
    code, report = _stage(home, releases[VER_N1], clicked=False, idle=None)
    assert code == update.EXIT_DEFERRED and report["reason"]


def test_a_deferred_self_test_stages_nothing(home, releases):
    code, report = _stage(home, releases[VER_N1],
                          selftest=FakeSelftest(selftestmod.DEFERRED))
    assert code == update.EXIT_DEFERRED and report["stage"] == "selftest"
    assert not (home / "staged").exists()
    assert homemod.read_marker(home)["version"] == VER_N


# --- runtimes ------------------------------------------------------------------------------------

def test_a_changed_runtime_pin_needs_the_runtime_folder(home, releases, tmp_path):
    rdoc = _release_doc(VER_N1, py=(PY2_URL, PY2_ZIP, "3.14.11"))
    rel = _copy_release(releases, tmp_path, VER_N1, release_doc=rdoc)
    code, report = _stage(home, rel)
    assert code == update.EXIT_FAIL and report["stage"] == "runtimes"
    assert "--runtime-dir" in report["reason"]
    assert not (home / "app" / VER_N1).exists()
    assert not (home / "runtime" / PY2_RT).exists()
    code, report = _stage(home, rel, runtime_dir=releases["rt"])
    assert code == update.EXIT_OK, report
    assert report["steps"]["runtimes"] == "placed"
    assert (home / "runtime" / PY2_RT / pinfetch.RUNTIME_MARKER).is_file()
    assert (home / "runtime" / PY_RT / pinfetch.RUNTIME_MARKER).is_file()
    assert update.read_staged(home, VER_N1)["python"] == PY2_RT
    assert homemod.read_marker(home)["python"] == PY_RT


# --- the report ------------------------------------------------------------------------------------

def _no_path(text, tmp_path):
    for needle in (str(tmp_path), str(tmp_path).replace("\\", "/"),
                   str(tmp_path).replace("\\", "\\\\")):
        assert needle not in text


def test_the_report_shows_no_path(home, releases, tmp_path, monkeypatch):
    code, _r = _stage(home, releases[VER_N1])
    assert code == update.EXIT_OK
    report_file = home / "logs" / "reports" / update.REPORT_NAME
    _no_path(report_file.read_text(encoding="ascii"), tmp_path)

    def boom(*_a, **_k):
        raise OSError("cannot write %s" % (home / "app" / "x"))
    monkeypatch.setattr(install, "cache_release", boom)
    out = io.StringIO()
    code, report = _stage(home, releases[VER_N2], out=out)
    assert code == update.EXIT_FAIL and report["stage"] == "extract"
    _no_path(report_file.read_text(encoding="ascii"), tmp_path)
    _no_path(out.getvalue(), tmp_path)
    assert "<home>" in report["reason"] or "<path>" in report["reason"]


# --- the command ----------------------------------------------------------------------------------

def test_the_command_table_finds_update():
    assert cli.load("update") is update


def test_update_needs_a_zip_and_a_valid_time():
    assert update.main([], out=io.StringIO()) == update.EXIT_USAGE
    assert update.main(["--zip", "x.zip", "--published-at", "soon"],
                       out=io.StringIO()) == update.EXIT_USAGE


def test_the_update_line_is_the_players_click(home, releases, monkeypatch):
    seen = []

    def run(h, version, **kw):
        seen.append(kw.get("clicked"))
        return selftestmod.Result(status=selftestmod.PASSED, version=version)
    monkeypatch.setattr(selftestmod, "run", run)
    monkeypatch.setattr(update, "set_priority", lambda _cls: None)
    out = io.StringIO()
    code = update.main(["--zip", str(releases[VER_N1]["zip"]), "--home", str(home),
                        "--published-at", "2026-11-19T00:00:00Z"], out=out)
    assert code == update.EXIT_OK and seen == [True]
    assert update.read_staged(home, VER_N1)["apply_after"] == "2026-11-20T00:00:00Z"
    assert out.getvalue().startswith("update: verify ok")


# --- static ------------------------------------------------------------------------------------------

def test_the_update_module_writes_no_marker_and_asks_no_network():
    text = SRC_UPDATE.read_text(encoding="ascii")
    for word in ("write_marker", "switch_marker", "urllib", "socket", "winreg",
                 "installer_fetch", "http.client"):
        assert word not in text, word
    assert "steamapps" not in text.lower()
    assert not re.search(r"runas|ShellExecute|IsUserAnAdmin|elevat", text, re.I)
    assert not re.search(r"tasklist|EnumProcesses|CreateToolhelp32Snapshot|"
                         r"OpenProcess|FindWindow", text)


# === DEP-17: the network half (stage_from_release, update --yes) ==================

REPO = "al-test/AshLight"
API_PUBLISHED = "2026-11-19T10:00:00Z"
GH_HOSTS = {"api.github.com", "github.com", "release-assets.githubusercontent.com",
            "objects.githubusercontent.com"}
EL2_ZIP = _runtime_zip({"electron.exe": b"stand-in electron 2\n", "LICENSE": b"MIT\n"})
EL2_URL = ("https://github.com/electron/electron/releases/download/v45.3.4/"
           "electron-v45.3.4-win32-x64.zip")
EL2_RT = "electron-45.3.4"


class FakeGitHub:
    """A loopback HTTP server standing in for github.com and its asset
    hosts: routes by (host, path); records (host, path, headers) of every
    request it got."""

    def __init__(self):
        self.routes = {}
        self.seen = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                host = self.headers.get("X-Fake-Host", "")
                hdrs = {k.lower(): v for k, v in self.headers.items()
                        if k.lower() != "x-fake-host"}
                owner.seen.append((host, self.path, hdrs))
                status, headers, body = owner.routes.get(
                    (host, self.path), (404, {}, b"not found"))
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def serve(self, url, body, status=200, headers=None):
        parts = urllib.parse.urlsplit(url)
        self.routes[(parts.hostname, parts.path)] = (status, headers or {}, body)

    def via_cdn(self, url, body, host="release-assets.githubusercontent.com"):
        """github.com answers 302 to an asset host that serves the bytes."""
        cdn = "https://%s/production/%s" % (host, url.rsplit("/", 1)[-1])
        self.serve(url, b"", 302, {"Location": cdn})
        self.serve(cdn, body)

    def opener(self, on_open=None):
        return LoopbackOpener(self, on_open)


class LoopbackOpener:
    """The request opener handed to payload.installer_stream: the https URL
    that passed the installer's host check goes to the loopback server
    with its host in X-Fake-Host; redirects come back as HTTPError for the
    installer's own hop check."""

    def __init__(self, gh, on_open=None):
        self.gh = gh
        self.on_open = on_open
        self.urls = []
        self.inner = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                 pinfetch._NoRedirect())

    def open(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        if self.on_open is not None:
            self.on_open(url)
        parts = urllib.parse.urlsplit(url)
        assert parts.scheme == "https"
        headers = dict(req.header_items())
        headers["X-Fake-Host"] = parts.hostname
        local = urllib.request.Request("http://127.0.0.1:%d%s" % (self.gh.port, parts.path),
                                       headers=headers, method="GET")
        return self.inner.open(local, timeout=timeout)


@pytest.fixture
def gh(sealed, monkeypatch):
    """The fake GitHub; sockets may connect to 127.0.0.1 and nowhere else."""
    def connect(sock, address):
        if not (isinstance(address, tuple) and address[0] == "127.0.0.1"):
            raise AssertionError("a test tried to open a non-loopback connection")
        return _REAL_CONNECT(sock, address)

    def create(address, *a, **k):
        if address[0] != "127.0.0.1":
            raise AssertionError("a test tried to open a non-loopback connection")
        return _REAL_CREATE(address, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create)
    server = FakeGitHub()
    yield server
    server.close()


def _web_on(home, ack=updates.WORDING_VERSION, on=True):
    doc = {"web_data": on, "mine": 1}
    if ack is not None:
        doc[update.ACK_KEY] = ack
    (home / "data" / "local.json").write_text(json.dumps(doc) + "\n", encoding="ascii")


@pytest.fixture
def web_home(home):
    """The home with web data on and the update wording acknowledged."""
    _web_on(home)
    return home


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _gh_url(version, name, repo=REPO):
    return "https://github.com/%s/releases/download/v%s/%s" % (repo, version, name)


def _publish(gh, releases, version, zip_bytes=None, listed_zip=None, release_doc=None,
             listed_release=None, digest=True, digests=None, sizes=None, urls=None,
             published_at=API_PUBLISHED, tag=None, prerelease=False):
    """Serve the three assets of `version` (github.com redirecting to an
    asset host) and return the cached answer updates.py keeps for them:
    a raw releases/latest document through updates._parse_release."""
    src = releases[version]
    real_zip = src["zip"].read_bytes()
    data = real_zip if zip_bytes is None else zip_bytes
    rel_b = (json.dumps(release_doc or _release_doc(version), indent=1) + "\n").encode("ascii")
    zname = src["zip"].name
    listed = {zname: listed_zip if listed_zip is not None else real_zip,
              "release.json": listed_release if listed_release is not None else rel_b}
    sums = "".join("%s  %s\n" % (_sha(listed[n]), n) for n in sorted(listed)).encode("ascii")
    files = {"release.json": rel_b, "SHA256SUMS.txt": sums, zname: data}
    assets = []
    for name, body in files.items():
        url = (urls or {}).get(name) or _gh_url(version, name)
        if url.startswith("https://github.com/" + REPO + "/"):
            gh.via_cdn(url, body)
        raw = {"name": name, "size": (sizes or {}).get(name, len(body)),
               "browser_download_url": url}
        if digest:
            raw["digest"] = "sha256:" + (digests or {}).get(name, _sha(body))
        assets.append(raw)
    raw_doc = {"tag_name": tag or "v" + version, "draft": False, "prerelease": prerelease,
               "published_at": published_at,
               "html_url": "https://github.com/%s/releases/tag/v%s" % (REPO, version),
               "assets": assets}
    return updates._parse_release(json.dumps(raw_doc).encode("ascii"))


def _rstage(home, answer, gh, **kw):
    kw.setdefault("idle", lambda: True)
    kw.setdefault("selftest", FakeSelftest())
    kw.setdefault("priority", FakePriority())
    kw.setdefault("now", STAMP)
    kw.setdefault("repo", REPO)
    if "opener" not in kw:
        kw["opener"] = gh.opener()
    out = kw.pop("out", None) or io.StringIO()
    return update.stage_from_release(home, answer, out=out, **kw)


def _nothing_staged(home, version=VER_N1):
    assert not (home / "staged").exists() or update.staged_versions(home) == []
    assert not (home / "app" / version).exists()
    assert not (home / "cache" / "downloads" / version).exists()
    assert homemod.read_marker(home)["version"] == VER_N


def test_release_n_to_n1_needs_no_click_and_stays_on_the_github_hosts(
        web_home, releases, gh):
    answer = _publish(gh, releases, VER_N1)
    opener = gh.opener()
    code, report = _rstage(web_home, answer, gh, clicked=False, opener=opener)
    assert code == update.EXIT_OK, report
    assert report["status"] == "staged" and report["source"] == "release"
    assert report["steps"]["gate"] == "idle" and report["steps"]["download"] == "ok"
    assert report["digest"] == "checked"
    doc = update.read_staged(web_home, VER_N1)
    assert doc["published_at"] == API_PUBLISHED
    assert doc["hashes"]["zip"] == _sha(releases[VER_N1]["zip"].read_bytes())
    assert payload.check_manifest(web_home / "app" / VER_N1) == []
    assert homemod.read_marker(web_home)["version"] == VER_N
    hosts = {urllib.parse.urlsplit(u).hostname for u in opener.urls}
    assert hosts <= GH_HOSTS and {"github.com"} <= hosts
    assert {h for h, _p, _hd in gh.seen} == hosts
    for _host, _path, headers in gh.seen:
        assert headers["user-agent"] == payload.user_agent()
        assert "cookie" not in headers and "authorization" not in headers
    assert len(gh.seen) == 6  # three assets, each one github.com hop and one asset host
    cached = web_home / "cache" / "downloads" / VER_N1
    assert (cached / releases[VER_N1]["zip"].name).read_bytes() == \
        releases[VER_N1]["zip"].read_bytes()


@pytest.mark.parametrize("case", ["size", "sha256", "digest", "release-sums"])
def test_a_size_sha256_or_digest_mismatch_stages_nothing(web_home, releases, gh, case):
    real = releases[VER_N1]["zip"].read_bytes()
    zname = releases[VER_N1]["zip"].name
    tampered = bytearray(real)
    tampered[len(tampered) // 2] ^= 1
    kw = {}
    if case == "size":
        kw["sizes"] = {zname: len(real) + 1}
    elif case == "sha256":
        kw["zip_bytes"] = bytes(tampered)  # its API digest matches; SHA256SUMS does not
    elif case == "digest":
        kw["digests"] = {zname: _sha(bytes(tampered))}
    else:
        kw["listed_release"] = b"{}\n"
    answer = _publish(gh, releases, VER_N1, **kw)
    test = FakeSelftest()
    code, report = _rstage(web_home, answer, gh, selftest=test)
    assert code == update.EXIT_FAIL, report
    assert report["stage"] == "verify" and report["status"] == "failed"
    words = {"size": "the release lists", "sha256": "SHA256SUMS",
             "digest": "release digest", "release-sums": "release.json"}
    assert words[case] in report["reason"]
    assert test.calls == []
    _nothing_staged(web_home)
    assert _report_doc(web_home)["status"] == "failed"


def test_a_release_younger_than_24_h_is_staged_with_the_hold(web_home, releases, gh):
    answer = _publish(gh, releases, VER_N1, published_at="2026-11-20T10:00:00Z")
    code, report = _rstage(web_home, answer, gh)
    assert code == update.EXIT_OK, report
    doc = update.read_staged(web_home, VER_N1)
    assert doc["published_at"] == "2026-11-20T10:00:00Z"
    assert doc["apply_after"] == "2026-11-21T10:00:00Z"
    assert update.parse_time(doc["apply_after"]) > STAMP  # not due yet
    assert homemod.read_marker(web_home)["version"] == VER_N


def test_a_version_in_update_skip_is_never_staged_again(web_home, releases, gh):
    switchmod.record_skip(web_home, VER_N1, "rolled back", now=STAMP)
    answer = _publish(gh, releases, VER_N1)
    opener = gh.opener()
    code, report = _rstage(web_home, answer, gh, clicked=True, opener=opener)
    assert code == update.EXIT_OK and report["status"] == "skipped"
    assert opener.urls == [] and gh.seen == []
    _nothing_staged(web_home)
    newer = _publish(gh, releases, VER_N2)  # a newer release is offered
    code, report = _rstage(web_home, newer, gh)
    assert code == update.EXIT_OK and report["status"] == "staged"
    assert report["version"] == VER_N2


def test_a_changed_runtime_pin_is_fetched_in_the_installer_process(web_home, releases, gh):
    rdoc = _release_doc(VER_N1)
    rdoc["runtimes"]["electron"] = _pin(EL2_URL, EL2_ZIP, "45.3.4", "MIT")
    gh.via_cdn(EL2_URL, EL2_ZIP, host="objects.githubusercontent.com")
    answer = _publish(gh, releases, VER_N1, release_doc=rdoc)
    opener = gh.opener()
    code, report = _rstage(web_home, answer, gh, opener=opener)
    assert code == update.EXIT_OK, report
    assert report["steps"]["runtimes"] == "placed"
    assert EL2_URL in opener.urls
    assert all(urllib.parse.urlsplit(u).hostname in GH_HOSTS for u in opener.urls)
    for _host, _path, headers in gh.seen:
        assert headers["user-agent"] == payload.user_agent()
        assert "cookie" not in headers
    rt = web_home / "runtime" / EL2_RT
    assert pinfetch.runtime_ready("electron", rdoc["runtimes"]["electron"], rt)
    assert (rt / "electron.exe").read_bytes() == b"stand-in electron 2\n"
    assert update.read_staged(web_home, VER_N1)["electron"] == EL2_RT
    assert homemod.read_marker(web_home)["electron"] == EL_RT


def test_a_runtime_that_fails_its_new_pin_stages_nothing(web_home, releases, gh):
    rdoc = _release_doc(VER_N1)
    rdoc["runtimes"]["electron"] = _pin(EL2_URL, EL2_ZIP, "45.3.4", "MIT")
    gh.via_cdn(EL2_URL, b"x" * len(EL2_ZIP))
    answer = _publish(gh, releases, VER_N1, release_doc=rdoc)
    code, report = _rstage(web_home, answer, gh)
    assert code == update.EXIT_FAIL and report["stage"] == "runtimes", report
    assert "HashMismatch" in report["reason"]
    assert not (web_home / "runtime" / EL2_RT).exists()
    assert not (web_home / "staged").exists()


def test_download_runs_below_normal_and_only_after_the_gate(web_home, releases, gh):
    answer = _publish(gh, releases, VER_N1)
    prio = FakePriority(start=0x20)
    seen = []
    code, report = _rstage(web_home, answer, gh, priority=prio,
                           opener=gh.opener(lambda _u: seen.append(prio.current)))
    assert code == update.EXIT_OK, report
    assert seen and set(seen) == {update.BELOW_NORMAL}
    assert prio.calls == [update.BELOW_NORMAL, 0x20]

    answers = [False, None, True]
    asked = []

    def idle():
        asked.append(1)
        return answers.pop(0) if answers else True
    first = []
    answer = _publish(gh, releases, VER_N2)
    code, report = _rstage(web_home, answer, gh, idle=idle, sleep=lambda _s: None,
                           opener=gh.opener(lambda _u: first.append(len(asked))))
    assert code == update.EXIT_OK, report
    assert first and min(first) == 3 and report["waited"] == 2


def test_never_idle_defers_with_no_request(web_home, releases, gh):
    answer = _publish(gh, releases, VER_N1)
    opener = gh.opener()
    prio = FakePriority()
    code, report = _rstage(web_home, answer, gh, idle=lambda: False, max_wait_s=0,
                           sleep=lambda _s: None, priority=prio, opener=opener)
    assert code == update.EXIT_DEFERRED and report["stage"] == "gate"
    assert opener.urls == [] and gh.seen == [] and prio.calls == []
    code, report = _rstage(web_home, answer, gh, idle=None, opener=opener)
    assert code == update.EXIT_DEFERRED and opener.urls == []
    code, report = _rstage(web_home, answer, gh, idle=None, clicked=True, opener=opener)
    assert code == update.EXIT_OK and report["steps"]["gate"] == "clicked"


def test_an_answer_without_digest_is_recorded_and_sha256sums_decides(
        web_home, releases, gh):
    answer = _publish(gh, releases, VER_N1, digest=False)
    assert all(a["digest"] is None for a in answer["assets"])
    code, report = _rstage(web_home, answer, gh)
    assert code == update.EXIT_OK, report
    assert report["digest"] == "absent"
    assert set(report["digests"].values()) == {"absent"}
    assert _report_doc(web_home)["digest"] == "absent"

    real = releases[VER_N2]["zip"].read_bytes()
    tampered = bytearray(real)
    tampered[10] ^= 1
    answer = _publish(gh, releases, VER_N2, digest=False, zip_bytes=bytes(tampered))
    code, report = _rstage(web_home, answer, gh)
    assert code == update.EXIT_FAIL and report["stage"] == "verify"
    assert "SHA256SUMS" in report["reason"]
    assert update.staged_versions(web_home) == [VER_N1]


def test_web_data_off_or_unacknowledged_makes_no_request(home, releases, gh):
    answer = _publish(gh, releases, VER_N1)
    for setup in (lambda: None, lambda: _web_on(home, ack=None),
                  lambda: _web_on(home, ack=0), lambda: _web_on(home, on=False)):
        setup()
        opener = gh.opener()
        code, report = _rstage(home, answer, gh, clicked=True, opener=opener)
        assert code == update.EXIT_FAIL and report["stage"] == "web_data"
        assert "nothing was requested" in report["reason"]
        assert opener.urls == [] and gh.seen == []
    _nothing_staged(home)
    assert update.web_data_allowed(home) is False
    _web_on(home)
    assert update.web_data_allowed(home) is True


def test_a_foreign_address_or_redirect_is_refused(web_home, releases, gh):
    zname = releases[VER_N1]["zip"].name
    opener = gh.opener()
    answer = _publish(gh, releases, VER_N1,
                      urls={zname: "https://example.com/x/" + zname})
    code, report = _rstage(web_home, answer, gh, opener=opener)
    assert code == update.EXIT_FAIL and report["stage"] == "release"
    assert opener.urls == []
    answer = _publish(gh, releases, VER_N1)
    code, report = _rstage(web_home, answer, gh, repo="someone/else", opener=opener)
    assert code == update.EXIT_FAIL and report["stage"] == "release"
    assert opener.urls == []

    answer = _publish(gh, releases, VER_N1)
    gh.serve(_gh_url(VER_N1, zname), b"", 302,
             {"Location": "https://downloads.example.net/" + zname})
    code, report = _rstage(web_home, answer, gh, opener=opener)
    assert code == update.EXIT_FAIL and report["stage"] == "download", report
    assert "UrlNotAllowed" in report["reason"]
    assert all(urllib.parse.urlsplit(u).hostname in GH_HOSTS for u in opener.urls)
    _nothing_staged(web_home)


def test_not_newer_or_prerelease_is_nothing_to_do_with_no_request(web_home, releases, gh):
    opener = gh.opener()
    for answer, status in (
            (_publish(gh, releases, VER_N), "current"),
            (_publish(gh, releases, VER_N1, prerelease=True), "skipped"),
            (_publish(gh, releases, VER_N1, tag="v1.3.0-rc.1"), "skipped")):
        code, report = _rstage(web_home, answer, gh, opener=opener)
        assert code == update.EXIT_OK and report["status"] == status, report
    assert opener.urls == []
    code, report = _rstage(web_home, None, gh, opener=opener)
    assert code == update.EXIT_FAIL and report["stage"] == "release"
    _nothing_staged(web_home)


def test_a_staged_release_is_current_with_no_new_download(web_home, releases, gh):
    answer = _publish(gh, releases, VER_N1)
    test = FakeSelftest()
    assert _rstage(web_home, answer, gh, selftest=test)[0] == update.EXIT_OK
    staged = (web_home / "staged" / (VER_N1 + ".json")).read_bytes()
    opener = gh.opener()
    code, report = _rstage(web_home, answer, gh, selftest=test, opener=opener)
    assert code == update.EXIT_OK and report["steps"]["download"] == "current"
    assert opener.urls == [] and test.calls == [VER_N1]
    assert (web_home / "staged" / (VER_N1 + ".json")).read_bytes() == staged


def test_the_yes_line_reads_the_cached_answer_and_stages(web_home, releases, gh,
                                                        monkeypatch):
    seen = []

    def run(h, version, **kw):
        seen.append(kw.get("clicked"))
        return selftestmod.Result(status=selftestmod.PASSED, version=version)
    monkeypatch.setattr(selftestmod, "run", run)
    monkeypatch.setattr(update, "set_priority", lambda _cls: None)
    answer = _publish(gh, releases, VER_N1)
    cache = update.cache_path(web_home)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"repo": REPO, "latest": answer, "etag": None,
                                 "checked_at": 1.0, "next_at": 2.0}) + "\n",
                     encoding="ascii")
    opener = gh.opener()
    out = io.StringIO()
    code = update.main(["--yes", "--home", str(web_home)], out=out, opener=opener)
    assert code == update.EXIT_OK, out.getvalue()
    assert seen == [True] and update.staged_versions(web_home) == [VER_N1]
    assert update.read_staged(web_home, VER_N1)["apply_after"] == "2026-11-20T10:00:00Z"
    assert "staged " + VER_N1 in out.getvalue()


def test_the_yes_line_with_web_data_off_requests_nothing(home, releases, gh):
    answer = _publish(gh, releases, VER_N1)
    cache = update.cache_path(home)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"repo": REPO, "latest": answer}) + "\n", encoding="ascii")
    opener = gh.opener()
    code = update.main(["--yes", "--home", str(home)], out=io.StringIO(), opener=opener)
    assert code == update.EXIT_FAIL
    assert opener.urls == [] and gh.seen == []
    assert _report_doc(home)["stage"] == "web_data"


def test_the_yes_line_usage():
    for argv in (["--yes", "--zip", "x.zip"], ["--yes", "--runtime-dir", "rt"],
                 ["--yes", "--published-at", "2026-11-19T00:00:00Z"],
                 ["--zip", "x.zip", "--release-cache", "c.json"]):
        assert update.main(argv, out=io.StringIO()) == update.EXIT_USAGE, argv


def test_release_hosts_and_ack_key_match_their_sources():
    from server.al import core
    assert set(update.RELEASE_HOSTS) == GH_HOSTS
    assert update.ACK_KEY == core.ACK_KEY
    assert set(update.RELEASE_HOSTS) - {updates.API_HOST} <= set(pinfetch.RUNTIME_HOSTS)
