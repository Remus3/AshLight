"""REL-INSTALL-CMD (finding F-050, DEP-09): the installer's `install` and
`repair` commands (server/al/install/install.py and repair.py).

A scratch home with fakes: the app zips are built by tools/rel_build.py
from a scratch git repo under a pytest tmp folder (two versions, for the
upgrade), the runtime zips are small stand-ins placed from a -RuntimeDir
folder with pins made to match, the self-test is a fake (or the real one
with a fake child that fails its code check), the shell runner is a fake
that keeps nothing outside the process, the data ACL and the client start
are injected. No request leaves the process (an autouse fixture fails any
socket connect) and no real child process starts (subprocess.Popen and
subprocess.run fail the test).
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
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import NAME, paths, pinfetch, snapstart  # noqa: E402
from server.al.install import cli, firstrun, install, payload, repair  # noqa: E402
from server.al.install import home as homemod  # noqa: E402
from server.al.install import selftest as selftestmod  # noqa: E402
from server.al.theorycraft import datacredit  # noqa: E402

VER_A = "1.2.3"
VER_B = "1.3.0"
WHEN = "2026-11-19T10:20:30Z"
STAMP = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
SRC_INSTALL = ROOT / "server" / "al" / "install" / "install.py"
SRC_REPAIR = ROOT / "server" / "al" / "install" / "repair.py"

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
EL_ZIP = _runtime_zip({"electron.exe": b"stand-in electron\n", "LICENSE": b"MIT\n"})
PY_URL = "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip"
EL_URL = ("https://github.com/electron/electron/releases/download/v45.3.3/"
          "electron-v45.3.3-win32-x64.zip")
PY_RT = "python-3.14.10"
EL_RT = "electron-45.3.3"


def _pin(url, data, version, licence):
    return {"version": version, "file": url.rsplit("/", 1)[-1], "url": url,
            "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
            "licence": licence}


def _release_doc(version):
    return {"name": NAME, "version": version, "runtimes": {
        "python": _pin(PY_URL, PY_ZIP, "3.14.10", "PSF-2.0"),
        "electron": _pin(EL_URL, EL_ZIP, "45.3.3", "MIT")}}


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(
        "installer_test_" + name, str(ROOT / "tools" / (name + ".py")))
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
    """{version: {zip, sums, release, dir}} for VER_A and VER_B, plus 'rt':
    a -RuntimeDir folder with both stand-in publisher zips."""
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
    for version in (VER_A, VER_B):
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
    (rt / PY_URL.rsplit("/", 1)[-1]).write_bytes(PY_ZIP)
    (rt / EL_URL.rsplit("/", 1)[-1]).write_bytes(EL_ZIP)
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


class FakeRunner:
    """The shell runner: 'written' for a request it has not seen, then
    'current'; the logon task is absent. Nothing outside the process."""

    def __init__(self):
        self.requests = []
        self.seen = []

    def __call__(self, request):
        self.requests.append(json.loads(json.dumps(request)))
        state = "current" if request in self.seen else "written"
        self.seen.append(json.loads(json.dumps(request)))
        return {"shortcuts": [state, state], "uninstall_entry": state,
                "logon_task": "absent"}


class FakeSpawn:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((list(cmd), kw))
        return object()


class FakeSelftest:
    def __init__(self, status=selftestmod.PASSED):
        self.status = status
        self.calls = []

    def __call__(self, home, version):
        self.calls.append(version)
        return selftestmod.Result(status=self.status, version=version,
                                  stage="health", reason="answered")


class Kit:
    """The injected effects of one test home."""

    def __init__(self, tmp_path):
        self.home = tmp_path / "home"
        self.effects = tmp_path / "effects"
        self.runner = FakeRunner()
        self.spawn = FakeSpawn()
        self.selftest = FakeSelftest()
        self.acl = []

    def private(self, path):
        self.acl.append(Path(path))
        return None

    def run(self, rel, start=True, selftest=None, **kw):
        out = io.StringIO()
        code, report = install.run(
            rel["zip"], self.home, runtime_dir=kw.pop("runtime_dir", None),
            start=start, selftest=selftest or self.selftest, runner=self.runner,
            spawn=self.spawn, private=self.private, effect_root=self.effects,
            environ={"PATH": "x", "AL_RUNTIME_DIR": "elsewhere", "AL_PORT": "1",
                     "ELECTRON_RUN_AS_NODE": "1"},
            now=STAMP, out=out, **kw)
        self.lines = out.getvalue().splitlines()
        return code, report


@pytest.fixture
def kit(tmp_path):
    return Kit(tmp_path)


def _installed(kit, releases, version=VER_A, **kw):
    code, report = kit.run(releases[version], runtime_dir=releases["rt"], **kw)
    assert code == install.EXIT_OK, report
    return report


def _report_text(home):
    return (home / "logs" / "reports" / install.REPORT_NAME).read_text(encoding="ascii")


def _nothing_installed(home):
    assert not (home / "install.json").exists()
    for name in ("app", "runtime", "data"):
        folder = home / name
        assert not folder.exists() or os.listdir(folder) == [], name


# --- a clean install -------------------------------------------------------------------

def test_clean_install_lays_out_marker_code_data_and_runtime(kit, releases, tmp_path):
    report = _installed(kit, releases)
    home = kit.home
    marker = homemod.read_marker(home)
    assert marker["version"] == VER_A and marker["previous"] is None
    assert marker["python"] == PY_RT and marker["electron"] == EL_RT
    assert marker["pending_confirm"] is False and marker["start_attempts"] == 0
    assert payload.check_manifest(home / "app" / VER_A) == []
    assert payload.verify_active(home)["ok"] is True
    for folder in (PY_RT, EL_RT):
        assert (home / "runtime" / folder / pinfetch.RUNTIME_MARKER).is_file()
    cfg = json.loads((home / "data" / "local.json").read_text(encoding="ascii"))
    assert cfg == firstrun.first_run_config() and cfg["web_data"] is False
    assert not (home / "data" / "consent.json").exists()
    assert kit.acl == [home / "data"]
    cached = home / "cache" / "downloads" / VER_A
    assert (cached / ("%s-%s-app.zip" % (NAME, VER_A))).read_bytes() == \
        releases[VER_A]["zip"].read_bytes()
    assert (cached / "SHA256SUMS.txt").is_file() and (cached / "release.json").is_file()
    assert (home / "uninstall.ps1").read_bytes() == b"# stand-in uninstall\n"
    assert report["status"] == "installed" and report["version"] == VER_A
    assert list(report["steps"]) == list(install.STEPS)
    assert report["steps"]["selftest"] == "passed" and report["steps"]["marker"] == "written"
    assert kit.selftest.calls == [VER_A]
    on_disk = json.loads(_report_text(home))
    assert on_disk["status"] == "installed" and on_disk["kind"] == "install"
    assert os.listdir(home / "logs" / "reports") == [install.REPORT_NAME]


def test_the_order_is_fixed_and_the_marker_comes_after_the_self_test(kit, releases,
                                                                     monkeypatch):
    seen = []
    for mod, name in ((install, "verify"), (homemod, "make_layout"),
                      (install, "lay_out"), (payload, "place_runtimes"),
                      (firstrun, "write_first_run"), (install, "set_marker"),
                      (install.shell, "rewrite"), (install, "start_client")):
        real = getattr(mod, name)

        def spy(*a, _real=real, _name=name, **k):
            seen.append(_name)
            return _real(*a, **k)
        monkeypatch.setattr(mod, name, spy)
    real_test = kit.selftest

    def selftest(home, version):
        seen.append("selftest")
        assert homemod.read_marker(home) is None  # no marker before the test
        return real_test(home, version)
    _installed(kit, releases, selftest=selftest)
    assert seen == ["verify", "make_layout", "lay_out", "place_runtimes",
                    "write_first_run", "selftest", "set_marker", "rewrite",
                    "start_client"]


def test_the_client_starts_with_the_shortcut_command_and_a_clean_env(kit, releases):
    _installed(kit, releases)
    home = kit.home
    assert len(kit.spawn.calls) == 1
    cmd, kw = kit.spawn.calls[0]
    app_dir = home / "app" / VER_A / "app"
    assert cmd == [str(home / "runtime" / EL_RT / "electron.exe"), str(app_dir), "--client"]
    assert kw["cwd"] == str(app_dir)
    env = kw["env"]
    assert env[paths.HOME_ENV] == str(home)
    for key in ("AL_RUNTIME_DIR", "AL_PORT", "ELECTRON_RUN_AS_NODE"):
        assert key not in env
    req = kit.runner.requests[0]
    assert req["shortcut"]["target"] == cmd[0]
    assert req["shortcut"]["arguments"] == '"%s" --client' % app_dir


def test_no_start_starts_nothing(kit, releases):
    report = _installed(kit, releases, start=False)
    assert kit.spawn.calls == []
    assert report["steps"]["start"] == "not started"
    assert homemod.read_marker(kit.home)["version"] == VER_A


def test_every_shell_effect_goes_through_the_injected_runner(kit, releases):
    _installed(kit, releases)
    assert len(kit.runner.requests) == 2  # the rewrite and its read-back pass
    for req in kit.runner.requests:
        assert req["effect_root"] == str(kit.effects)
        assert req["owner_root"] == str(kit.home)
        assert req["version"] == VER_A
    assert not kit.effects.exists()  # the fake wrote nothing there


# --- nothing installed ------------------------------------------------------------------

def _copy_release(releases, tmp_path, version=VER_A, zip_bytes=None, sums=None):
    folder = tmp_path / "dl"
    folder.mkdir()
    src = releases[version]
    data = src["zip"].read_bytes() if zip_bytes is None else zip_bytes
    (folder / src["zip"].name).write_bytes(data)
    (folder / "SHA256SUMS.txt").write_bytes(
        src["sums"].read_bytes() if sums is None else sums)
    (folder / "release.json").write_bytes(src["release"].read_bytes())
    return {"zip": folder / src["zip"].name}


def test_tampered_zip_installs_nothing(kit, releases, tmp_path):
    data = bytearray(releases[VER_A]["zip"].read_bytes())
    data[len(data) // 2] ^= 1
    rel = _copy_release(releases, tmp_path, zip_bytes=bytes(data))
    code, report = kit.run(rel, runtime_dir=releases["rt"])
    assert code == install.EXIT_FAIL
    assert report["stage"] == "verify" and "HashMismatch" in report["reason"]
    _nothing_installed(kit.home)
    assert kit.runner.requests == [] and kit.spawn.calls == [] and kit.acl == []
    assert kit.selftest.calls == []
    assert json.loads(_report_text(kit.home))["status"] == "failed"


def test_missing_hash_line_installs_nothing(kit, releases, tmp_path):
    other = ("%s  something-else.zip\n" % ("0" * 64)).encode("ascii")
    rel = _copy_release(releases, tmp_path, sums=other)
    code, report = kit.run(rel, runtime_dir=releases["rt"])
    assert code == install.EXIT_FAIL and report["stage"] == "verify"
    assert "SumsError" in report["reason"]
    _nothing_installed(kit.home)
    assert kit.spawn.calls == []


def test_a_missing_runtime_installs_no_marker(kit, releases, tmp_path):
    rt = tmp_path / "rt-empty"
    rt.mkdir()
    code, report = kit.run(releases[VER_A], runtime_dir=rt)
    assert code == install.EXIT_FAIL and report["stage"] == "runtimes"
    assert not (kit.home / "install.json").exists()
    assert kit.selftest.calls == [] and kit.spawn.calls == []


def test_a_home_in_a_game_folder_is_refused_with_nothing_written(tmp_path, releases):
    kit = Kit(tmp_path / "steamapps" / "common")
    code, report = kit.run(releases[VER_A], runtime_dir=releases["rt"])
    assert code == install.EXIT_USAGE and report["status"] == "refused"
    assert not (tmp_path / "steamapps").exists()


class FailProc:
    """A self-test child whose code check exits 1."""

    def __init__(self, *_a, **_k):
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


def test_failed_self_test_leaves_no_marker_and_one_report(kit, releases, tmp_path):
    spawned = []

    def selftest(home, version):
        def spawn(cmd, **kw):
            spawned.append(cmd)
            return FailProc()
        return selftestmod.run(home, version, clicked=True, spawn=spawn)
    code, report = kit.run(releases[VER_A], runtime_dir=releases["rt"],
                           selftest=selftest)
    home = kit.home
    assert code == install.EXIT_FAIL
    assert len(spawned) == 1 and "--check" in spawned[0]
    assert not (home / "install.json").exists()
    assert not (home / "install.json.bak").exists()
    assert not (home / "app" / VER_A).exists()
    assert (home / "temp" / ("failed-" + VER_A)).is_dir()
    assert os.listdir(home / "logs" / "reports") == [install.REPORT_NAME]
    doc = json.loads(_report_text(home))
    assert doc["status"] == "failed" and doc["stage"] == "selftest"
    assert doc["selftest"]["stage"] == "check" and doc["selftest"]["exit_code"] == 1
    assert doc["selftest"]["report"]["kind"] == "selftest"
    assert kit.runner.requests == [] and kit.spawn.calls == []


def test_the_report_names_no_path(kit, releases, tmp_path, monkeypatch):
    _installed(kit, releases)
    text = _report_text(kit.home)
    for needle in (str(tmp_path), str(tmp_path).replace("\\", "/"),
                   str(tmp_path).replace("\\", "\\\\")):
        assert needle not in text

    def boom(*_a, **_k):
        raise OSError("cannot write %s" % (kit.home / "data" / "x"))
    monkeypatch.setattr(firstrun, "write_first_run", boom)
    other = Kit(tmp_path / "second")
    code, report = other.run(releases[VER_A], runtime_dir=releases["rt"])
    assert code == install.EXIT_FAIL and report["stage"] == "config"
    text = _report_text(other.home)
    assert str(tmp_path) not in text and str(tmp_path).replace("\\", "\\\\") not in text
    assert "<path>" in report["reason"] or "<home>" in report["reason"]


def test_scrub_replaces_absolute_paths():
    drive = "Q" + ":" + "\\"  # built here: no drive path literal in the file
    assert install.scrub(drive + "data\\x\\f.txt is bad") == "<path> is bad"
    assert install.scrub("open /home/x/file failed") == "open <path> failed"
    assert install.scrub("changed: server/al/core.py") == "changed: server/al/core.py"


# --- a re-run --------------------------------------------------------------------------------

def test_rerun_restores_a_deleted_shipped_file(kit, releases):
    _installed(kit, releases)
    shipped = kit.home / "app" / VER_A / "server" / "al" / "core.py"
    want = shipped.read_bytes()
    shipped.unlink()
    report = _installed(kit, releases)
    assert shipped.read_bytes() == want
    assert report["steps"]["extract"] == "restored"
    assert report["steps"]["selftest"] == "skipped"  # the active version
    assert report["steps"]["marker"] == "current"
    assert kit.selftest.calls == [VER_A]
    assert payload.check_manifest(kit.home / "app" / VER_A) == []
    assert not [n for n in os.listdir(kit.home / "temp") if n.startswith("repair-")]


def test_rerun_of_an_intact_install_changes_nothing(kit, releases):
    _installed(kit, releases)
    before = (kit.home / "install.json").read_bytes()
    report = _installed(kit, releases)
    assert report["steps"]["extract"] == "current"
    assert report["steps"]["config"] == "kept"
    assert (kit.home / "install.json").read_bytes() == before


def test_rerun_keeps_the_players_local_json(kit, releases):
    _installed(kit, releases)
    cfg = kit.home / "data" / "local.json"
    cfg.write_text('{"web_data": true}\n', encoding="ascii")
    _installed(kit, releases, VER_B)
    assert cfg.read_text(encoding="ascii") == '{"web_data": true}\n'


def test_rerun_with_a_newer_release_upgrades_the_older_marker(kit, releases):
    _installed(kit, releases, VER_A)
    report = _installed(kit, releases, VER_B)
    marker = homemod.read_marker(kit.home)
    assert marker["version"] == VER_B and marker["previous"] == VER_A
    assert marker["pending_confirm"] is True and marker["start_attempts"] == 0
    assert report["steps"]["marker"] == "switched"
    assert kit.selftest.calls == [VER_A, VER_B]
    assert homemod.version_dirs(kit.home) == [VER_A, VER_B]
    cmd, _kw = kit.spawn.calls[-1]
    assert cmd[1] == str(kit.home / "app" / VER_B / "app")
    assert kit.runner.requests[-1]["version"] == VER_B


# --- the start-time snapshot in an installed copy (DATA-SNAP-AT-START, Q-04) -------

class FakePopen:
    def __init__(self):
        self.calls = []
        self.pid = 4242

    def __call__(self, cmd, **kw):
        self.calls.append((list(cmd), kw))
        return self


def test_installed_start_runs_the_snapshot_tool_through_boot_py_under_home_cache(
        kit, releases, monkeypatch):
    _installed(kit, releases, start=False)
    home = kit.home
    monkeypatch.setenv(paths.HOME_ENV, str(home))
    for key in (paths.SIDECAR_ENV, paths.RUNTIME_ENV, snapstart.OPT_OUT_ENV):
        monkeypatch.delenv(key, raising=False)
    env = dict(os.environ)
    runtime = paths.runtime_dir()
    assert runtime == home / "data"
    assert datacredit.cache_dir(env) == home / "cache" / "gamedata"
    root = home / "app" / VER_A
    popen = FakePopen()
    # web data off (the first-run config): nothing starts
    assert snapstart.tick(runtime, 1.0e9, environ=env, popen=popen, root=root) is None
    assert popen.calls == []
    cfg = home / "data" / "local.json"
    doc = json.loads(cfg.read_text(encoding="ascii"))
    doc["web_data"] = True
    cfg.write_text(json.dumps(doc) + "\n", encoding="ascii")
    pid = snapstart.tick(runtime, 1.0e9, environ=env, popen=popen, root=root)
    assert pid == 4242 and len(popen.calls) == 1
    cmd, kw = popen.calls[0]
    assert cmd[0] == str(home / "runtime" / PY_RT / "pythonw.exe")
    assert cmd[1:] == [str(root / "boot.py"), snapstart.MODULE]
    assert kw["cwd"] == str(root)
    assert (home / "data" / snapstart.PID_FILE).is_file()
    assert (home / "logs" / snapstart.LOG_NAME).is_file()


# --- repair ---------------------------------------------------------------------------------------

def _repair(kit, **kw):
    out = io.StringIO()
    code, res = repair.run(kit.home, runner=kit.runner, effect_root=kit.effects,
                           out=out, **kw)
    return code, res, out.getvalue().splitlines()


def test_repair_of_an_intact_install_is_ok(kit, releases):
    _installed(kit, releases)
    code, res, lines = _repair(kit)
    assert code == repair.EXIT_OK and res["status"] == "ok"
    assert lines[-1] == "repair: ok (%s)" % VER_A


def test_repair_re_extracts_a_changed_file_from_the_cached_zip(kit, releases):
    _installed(kit, releases)
    shipped = kit.home / "app" / VER_A / "web" / "index.html"
    want = shipped.read_bytes()
    shipped.write_bytes(b"changed\n")
    (kit.home / "app" / VER_A / "extra.txt").write_bytes(b"x\n")
    code, res, lines = _repair(kit)
    assert code == repair.EXIT_OK and res["status"] == "repaired", lines
    assert "repair: changed: web/index.html" in lines
    assert shipped.read_bytes() == want
    assert not (kit.home / "app" / VER_A / "extra.txt").exists()
    assert payload.verify_active(kit.home)["ok"] is True
    assert not [n for n in os.listdir(kit.home / "temp") if n.startswith("repair-")]
    assert not [ln for ln in lines if str(kit.home) in ln]


def test_repair_without_a_cached_zip_fails_and_moves_nothing(kit, releases):
    _installed(kit, releases)
    zip_path = kit.home / "cache" / "downloads" / VER_A / releases[VER_A]["zip"].name
    zip_path.unlink()
    shipped = kit.home / "app" / VER_A / "web" / "index.html"
    shipped.write_bytes(b"changed\n")
    code, res, lines = _repair(kit)
    assert code == repair.EXIT_FAIL and res["stage"] == "code"
    assert "no cached zip" in lines[-1]
    assert shipped.read_bytes() == b"changed\n"


def test_repair_with_a_tampered_cached_zip_keeps_the_folder(kit, releases):
    _installed(kit, releases)
    zip_path = kit.home / "cache" / "downloads" / VER_A / releases[VER_A]["zip"].name
    data = bytearray(zip_path.read_bytes())
    data[len(data) // 2] ^= 1
    zip_path.write_bytes(bytes(data))
    (kit.home / "app" / VER_A / "README.md").unlink()
    code, _res, _lines = _repair(kit)
    assert code == repair.EXIT_FAIL
    assert (kit.home / "app" / VER_A / "web" / "index.html").is_file()


def test_reextract_moves_the_old_folder_back_when_the_extract_fails(kit, releases,
                                                                    monkeypatch):
    _installed(kit, releases)
    shipped = kit.home / "app" / VER_A / "web" / "index.html"
    shipped.write_bytes(b"changed\n")

    def boom(*_a, **_k):
        raise payload.PayloadError("extract failed")
    monkeypatch.setattr(payload, "extract", boom)
    with pytest.raises(payload.PayloadError):
        repair.reextract(kit.home, VER_A, b"unused")
    assert shipped.read_bytes() == b"changed\n"
    assert not [n for n in os.listdir(kit.home / "temp") if n.startswith("repair-")]


def test_repair_places_a_missing_runtime_again(kit, releases):
    _installed(kit, releases)
    import shutil
    shutil.rmtree(kit.home / "runtime" / EL_RT)
    code, res, lines = _repair(kit, runtime_dir=releases["rt"])
    assert code == repair.EXIT_OK, lines
    assert res["steps"]["runtimes"] == "placed"
    assert (kit.home / "runtime" / EL_RT / "electron.exe").is_file()


def test_repair_without_a_marker_fails(kit):
    code, res, lines = _repair(kit)
    assert code == repair.EXIT_FAIL and res["version"] is None
    assert "no valid install marker" in lines[-1]


# --- the command table and static checks --------------------------------------------------

def test_the_command_table_finds_install_and_repair():
    assert cli.load("install") is install
    assert cli.load("repair") is repair


def test_install_needs_a_zip_argument():
    assert install.main([], out=io.StringIO()) == install.EXIT_USAGE


def test_home_resolution_takes_the_argument_then_al_home(tmp_path):
    assert install.resolve_home(str(tmp_path / "h"), {}) == tmp_path / "h"
    assert install.resolve_home(None, {paths.HOME_ENV: str(tmp_path / "e")}) == \
        tmp_path / "e"
    assert install.resolve_home(None, {"LOCALAPPDATA": str(tmp_path)}) == \
        tmp_path / "Programs" / "AshLight"


ELEVATION = re.compile(r"runas|ShellExecute|IsUserAnAdmin|"
                       r"Start-Process|-Verb\b|elevat|UAC\b", re.I)


@pytest.mark.parametrize("src", [SRC_INSTALL, SRC_REPAIR], ids=["install", "repair"])
def test_no_elevation_call(src):
    text = src.read_text(encoding="ascii")
    assert not ELEVATION.search(text)
    assert "winreg" not in text and "steamapps" not in text.lower()
