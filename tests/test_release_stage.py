"""Release stage (DEP-12, F-074): tools/rel_stage.py, `release.py stage`.

Git is a fresh scratch repo under tmp_path (the real ship list, pins and
lockfile, the real VERSION, a stand-in notes file and payload), the suite
and node runner is a recorder, and the clock is fixed. Every build points
its cache check at a folder under tmp_path, and the leak sweep gets a
stand-in needle through AL_LEAK_NEEDLES, so nothing reads the operator's
sidecar or needle config. Nothing here runs the real suite or npm.
"""
import datetime
import functools
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import zipfile
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WHEN = "2026-11-19T10:20:30Z"
WHEN_TS = int(datetime.datetime(2026, 11, 19, 10, 20, 30,
                                tzinfo=datetime.timezone.utc).timestamp())
NEEDLE = "zqxstandinneedle"


def _load(name):
    spec = importlib.util.spec_from_file_location(
        "stage_test_" + name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rs = _load("rel_stage")
VERSION = rs.rv.source_version(ROOT)

_GIT = ["git", "-c", "core.hooksPath=", "-c", "user.name=t",
        "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]


def _git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE=WHEN, GIT_COMMITTER_DATE=WHEN)
    proc = subprocess.run(_GIT + list(args), cwd=str(cwd), env=env,
                          capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


REAL = ("config/ship_list.json", "config/runtime_pins.json",
        "config/electron_pin.json", "config/tc_pins.json",
        "app/package.json", "app/package-lock.json",
        "scripts/install.ps1", "server/al/ports.py")
FILES = {
    "server/al/__init__.py": "\"\"\"AshLight core.\"\"\"\n\nVERSION = \"%s\"\n"
                             % VERSION,
    "server/al/core.py": "\"\"\"Stand-in core.\"\"\"\nVALUE = 1\n",
    "web/index.html": "<!doctype html><title>AshLight</title>\n",
    "app/main.js": "'use strict';\n",
    "README.md": "# AshLight\n",
    "LICENSE": "licence\n",
    "boot.py": "# boot\n",
    "docs/releases/%s.md" % VERSION:
        "## [%s] - 2026-11-19\n\nStand-in notes.\n" % VERSION,
}


@pytest.fixture(autouse=True)
def standin_needle(monkeypatch, tmp_path):
    monkeypatch.setenv("AL_LEAK_NEEDLES", NEEDLE)
    # the round trip's scratch and runtime cache resolve under tmp_path
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(tmp_path / "sidecar"))


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q")
    for rel in REAL:
        dst = path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ROOT / rel).read_bytes())
    for rel, text in FILES.items():
        dst = path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(text.encode("ascii"))
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "chore: scratch")
    return path


class Runner:
    """Records every argv; exit codes by a predicate on the argv."""

    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        return 1 if self.fail and self.fail(argv) else 0


def _builder(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir(exist_ok=True)
    return functools.partial(rs.rb.build, cache_dir=cache)


def _stage(repo, tmp_path, version=VERSION, run=None, build=None, **kw):
    run = run if run is not None else Runner()
    if "roundtrip" not in kw:
        kw["roundtrip"] = FakeFactory(tmp_path)
    rep = rs.stage(version, run=run, now=lambda: WHEN_TS, root=repo,
                   out=tmp_path / "out", owner="sess.agent",
                   build=build or _builder(tmp_path), **kw)
    return rep, run


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").decode("ascii").strip()


def _status(repo):
    return _git(repo, "status", "--porcelain=v1", "--untracked-files=all")


def _statuses(rep):
    return {r["name"]: r["status"] for r in rep["steps"]}


def _detail(rep, name):
    return [r for r in rep["steps"] if r["name"] == name][0]["detail"]


# --- the round trip's stand-in effects ---------------------------------------

def _write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(doc, indent=1) + "\n").encode("ascii"))


class FakeEffects(rs.RoundTripEffects):
    """The real scratch layout, N-1 build, env and cleanup; the installer,
    update, switch and uninstall children are stand-ins that make the same
    file changes in the scratch home and under the scratch shell root.
    Nothing outside the scratch base is written."""

    def __init__(self, ctx, base, log, web_data=False, leave_link=False,
                 snapshots=None):
        super().__init__(ctx, base)
        self.log = log
        self.web_data = web_data
        self.leave_link = leave_link
        self.snapshots = snapshots
        self.envs = []
        if snapshots is not None:
            self.snapshot = lambda: self.snapshots.pop(0)

    def runtimes(self, release):
        self.log.append(("runtimes", sorted(release["runtimes"])))
        return []

    def previous(self, version):
        prev, assets = super().previous(version)
        self.log.append(("previous", prev))
        return prev, assets

    def _set_links(self, present):
        for sub in ("Programs", "Desktop"):
            link = self.shell / sub / rs.LINK_NAME
            if present:
                link.parent.mkdir(parents=True, exist_ok=True)
                link.write_bytes(b"link")
            elif link.exists() and not (self.leave_link and sub == "Desktop"):
                link.unlink()

    def _marker(self):
        return json.loads((self.home / "install.json").read_bytes())

    def install(self, folder, version):
        self.envs.append(self.env())
        assert (folder / rs.rb.zip_name(version)).is_file()
        assert (folder / rs.INSTALLER_PS1).is_file()
        self.log.append(("install", version))
        _write_json(self.home / "install.json", {
            "schema": 1, "name": "AshLight", "version": version,
            "previous": None, "pending_confirm": False})
        local = self.home / "data" / "local.json"
        if not local.exists():
            _write_json(local, {"web_data": self.web_data})
        (self.home / "app" / version).mkdir(parents=True, exist_ok=True)
        (self.home / "uninstall.ps1").write_bytes(b"# stand-in\n")
        self._set_links(True)
        return 0

    def installer(self, command, *args):
        self.envs.append(self.env())
        self.log.append(("installer", command))
        marker = self._marker()
        if command == "update":
            zip_path = Path(str(args[list(args).index("--zip") + 1]))
            assert zip_path.is_file()
            new = zip_path.name[len("AshLight-"):-len("-app.zip")]
            _write_json(self.home / "staged" / (new + ".json"), {"version": new})
            return 0
        if command == "apply-staged":
            new = sorted(p.stem for p in (self.home / "staged").iterdir())[0]
            marker.update(previous=marker["version"], version=new,
                          pending_confirm=True)
            _write_json(self.home / "install.json", marker)
            return rs.EXIT_SWITCHED
        if command == "rollback":
            left = marker["version"]
            marker.update(version=marker["previous"], previous=None,
                          pending_confirm=False)
            _write_json(self.home / "install.json", marker)
            _write_json(self.home / "data" / "update_skip.json",
                        {"versions": [{"version": left}]})
            return rs.EXIT_SWITCHED
        return 2

    def uninstall(self, purge):
        self.envs.append(self.env())
        self.log.append(("uninstall", purge))
        for item in list(self.home.iterdir()):
            if item.name == "data" and not purge:
                continue
            if item.is_dir():
                shutil.rmtree(str(item))
            else:
                item.unlink()
        if purge:
            self.home.rmdir()
        self._set_links(False)
        return 0

    def cleanup(self):
        self.log.append(("cleanup",))
        super().cleanup()


class FakeFactory:
    """roundtrip(ctx) -> FakeEffects in a fresh base under the tmp sidecar."""

    def __init__(self, tmp_path, **kw):
        self.tmp_path = tmp_path
        self.kw = kw
        self.log = []
        self.made = []

    def __call__(self, ctx):
        base = self.tmp_path / "sidecar" / "Temp" / ("rt%d" % len(self.made))
        base.mkdir(parents=True)
        fx = FakeEffects(ctx, base, self.log, **self.kw)
        self.made.append(fx)
        return fx


def _assert_nothing_changed(repo, tmp_path, rep, head, status, failed):
    """A refusal: FAIL at `failed`, later steps skipped, the tree as it was,
    no release asset written, only stage.json in the release folder."""
    assert rep["verdict"] == "FAIL"
    names = [r["name"] for r in rep["steps"]]
    statuses = _statuses(rep)
    assert statuses[failed] == "fail"
    for name in names[names.index(failed) + 1:]:
        assert statuses[name] == "skipped"
    for name in names[:names.index(failed)]:
        assert statuses[name] == "pass"
    assert rep["assets"] == [] and rep["sums_sha256"] is None
    assert _head(repo) == head
    assert _status(repo) == status
    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == ["stage.json"]
    doc = json.loads((out / "stage.json").read_bytes().decode("ascii"))
    assert doc["verdict"] == "FAIL"


# --- PASS ------------------------------------------------------------------

def test_pass_writes_stage_json_with_every_field(repo, tmp_path):
    head = _head(repo)
    rep, run = _stage(repo, tmp_path)
    assert rep["verdict"] == "PASS", rep["steps"]
    assert [r["name"] for r in rep["steps"]] == [
        "clean", "version", "suite", "node", "builds", "sweep", "roundtrip"]
    assert set(_statuses(rep).values()) == {"pass"}
    out = tmp_path / "out"
    doc = json.loads((out / "stage.json").read_bytes().decode("ascii"))
    for key in ("version", "commit", "verdict", "steps", "assets",
                "sums_sha256", "created", "sandbox"):
        assert key in doc
    assert doc["version"] == VERSION
    assert doc["commit"] == head
    assert doc["created"] == WHEN
    assert doc["sandbox"] is False
    names = sorted(e["name"] for e in doc["assets"])
    assert "AshLight-%s-app.zip" % VERSION in names
    assert "SHA256SUMS.txt" not in names
    for entry in doc["assets"]:
        data = (out / entry["name"]).read_bytes()
        assert entry == {"name": entry["name"], "size": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()}
    sums = (out / "SHA256SUMS.txt").read_bytes()
    assert doc["sums_sha256"] == hashlib.sha256(sums).hexdigest()
    assert not (out / rs.SCRATCH_NAME).exists()
    assert _status(repo) == b""
    assert len(run.calls) == 2


def test_suite_runs_through_the_suite_gate(repo, tmp_path):
    _rep, run = _stage(repo, tmp_path)
    suite = run.calls[0]
    assert suite[1] == "ops/fleet_kit/fleet_suite_gate.py"
    assert suite[2:6] == ["run", "--owner", "sess.agent", "--"]
    assert suite[-1] == "tools/suite_run.py"
    assert run.calls[1] == ["npm", "test", "--prefix", "app"]
    assert rs.suite_argv("x.y")[1:] == [
        "ops/fleet_kit/fleet_suite_gate.py", "run", "--owner", "x.y", "--",
        sys.executable, "tools/suite_run.py"]


def test_sandbox_is_recorded(repo, tmp_path):
    rep, _run = _stage(repo, tmp_path, sandbox=True)
    doc = json.loads((tmp_path / "out" / "stage.json").read_bytes())
    assert doc["sandbox"] is True and rep["sandbox"] is True
    assert any("sandbox" in n for n in doc["notes"])


def test_steps_are_an_append_point(repo, tmp_path):
    seen = []

    def extra(ctx):
        seen.append(ctx["version"])
        raise rs.StepFail("extra step refused")
    rep, _run = _stage(repo, tmp_path,
                       steps=list(rs.STEPS) + [("roundtrip", extra)])
    assert seen == [VERSION]
    assert rep["verdict"] == "FAIL"
    assert _statuses(rep)["roundtrip"] == "fail"
    assert rep["assets"] == []


# --- refusals of steps 1 to 5: nothing changed -----------------------------

def test_step1_dirty_tree_refuses(repo, tmp_path):
    (repo / "stray.txt").write_bytes(b"left over\n")
    head, status = _head(repo), _status(repo)
    rep, run = _stage(repo, tmp_path)
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "clean")
    assert run.calls == []
    assert (repo / "stray.txt").read_bytes() == b"left over\n"


def test_step2_version_mismatch_refuses(repo, tmp_path):
    head, status = _head(repo), _status(repo)
    rep, run = _stage(repo, tmp_path, version="9.9.9")
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "version")
    assert run.calls == []
    assert "9.9.9" in rep["steps"][1]["detail"]


def test_step2_inconsistent_version_places_refuse(repo, tmp_path):
    pkg = json.loads((repo / "app/package.json").read_bytes())
    pkg["version"] = "0.0.1"
    (repo / "app/package.json").write_bytes(
        (json.dumps(pkg, indent=2) + "\n").encode("ascii"))
    _git(repo, "commit", "-q", "-am", "chore: drift")
    head, status = _head(repo), _status(repo)
    rep, _run = _stage(repo, tmp_path)
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "version")


def test_step3_suite_failure_refuses(repo, tmp_path):
    head, status = _head(repo), _status(repo)
    run = Runner(fail=lambda argv: "tools/suite_run.py" in argv)
    rep, _run = _stage(repo, tmp_path, run=run)
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "suite")
    assert len(run.calls) == 1


def test_step4_node_failure_refuses(repo, tmp_path):
    head, status = _head(repo), _status(repo)
    run = Runner(fail=lambda argv: argv[0] == "npm")
    rep, _run = _stage(repo, tmp_path, run=run)
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "node")
    assert len(run.calls) == 2


def test_step4_runner_that_cannot_start_refuses(repo, tmp_path):
    head, status = _head(repo), _status(repo)

    def run(argv, cwd):
        if argv[0] == "npm":
            raise FileNotFoundError("npm")
        return 0
    rep, _run = _stage(repo, tmp_path, run=run)
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "node")


def test_step5_build_refusal_refuses(repo, tmp_path):
    head, status = _head(repo), _status(repo)

    def build(root, out):
        raise rs.rb.BuildError("stand-in refusal")
    rep, _run = _stage(repo, tmp_path, build=build)
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "builds")
    detail = [r for r in rep["steps"] if r["name"] == "builds"][0]["detail"]
    assert "stand-in refusal" in detail


def test_step5_two_builds_that_differ_fail(repo, tmp_path):
    head, status = _head(repo), _status(repo)
    real = _builder(tmp_path)
    count = []

    def build(root, out):
        res = real(root=root, out=out)
        count.append(out)
        if len(count) == 2:
            zip_path = res["zip"]
            zip_path.write_bytes(zip_path.read_bytes() + b"\0")
        return res
    rep, _run = _stage(repo, tmp_path, build=build)
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "builds")
    detail = [r for r in rep["steps"] if r["name"] == "builds"][0]["detail"]
    assert "differ" in detail and "AshLight-%s-app.zip" % VERSION in detail
    assert len(count) == 2


# --- step 6: the leak sweep of the staged tree -----------------------------

def test_sweep_of_the_staged_tree_refuses_a_needle(repo, tmp_path):
    real = _builder(tmp_path)

    def build(root, out):
        res = real(root=root, out=out)
        (Path(out) / "extra.txt").write_bytes(("x %s\n" % NEEDLE).encode("ascii"))
        return res
    head, status = _head(repo), _status(repo)
    rep, _run = _stage(repo, tmp_path, build=build)
    _assert_nothing_changed(repo, tmp_path, rep, head, status, "sweep")
    detail = _detail(rep, "sweep")
    assert NEEDLE not in detail and "extra.txt" in detail


def test_staged_tree_holds_zip_members_and_assets(repo, tmp_path):
    out = tmp_path / "one"
    _builder(tmp_path)(root=repo, out=out)
    assets = {p.name: p.read_bytes() for p in out.iterdir()}
    tree = rs.staged_tree(assets, "AshLight-%s-app.zip" % VERSION)
    top = "AshLight-%s/" % VERSION
    assert top + "server/al/core.py" in tree
    assert top + "MANIFEST.json" in tree
    assert "release/SHA256SUMS.txt" in tree
    assert not any(n.endswith("-app.zip") for n in tree)


# --- step 7 (plan step 6): the scratch-home round trip -----------------------

PREV = rs.previous_version(VERSION)


def test_round_trip_steps_and_order(repo, tmp_path):
    fac = FakeFactory(tmp_path)
    rep, _run = _stage(repo, tmp_path, roundtrip=fac)
    assert rep["verdict"] == "PASS", rep["steps"]
    assert _statuses(rep)["roundtrip"] == "pass"
    assert fac.log == [
        ("runtimes", ["electron", "python"]),
        ("previous", PREV),
        ("install", PREV),
        ("installer", "update"),
        ("installer", "apply-staged"),
        ("installer", "rollback"),
        ("uninstall", False),
        ("install", VERSION),
        ("uninstall", True),
        ("cleanup",),
    ]
    detail = _detail(rep, "roundtrip")
    assert "install %s, update to %s" % (PREV, VERSION) in detail
    # the scratch base (home, releases, the N-1 clone) is gone afterwards
    assert not fac.made[0].base.exists()
    # the stage's own repository is untouched by the N-1 clone
    assert _status(repo) == b""
    assert _git(repo, "tag", "--list") == b""


def test_round_trip_synthetic_previous_version():
    assert rs.previous_version("0.1.0") == "0.0.0"
    assert rs.previous_version("1.2.3") == "1.2.2"
    assert rs.previous_version("1.2.0") == "1.1.0"
    assert rs.previous_version("2.0.0") == "1.0.0"
    assert rs.previous_version("1.0.0-rc.2") == "1.0.0-rc.1"
    assert rs.previous_version("1.0.0-rc.0") == "0.0.0"
    assert rs.previous_version("0.0.0") is None
    for v in ("0.1.0", "1.2.3", "1.0.0-rc.2"):
        assert rs.rv.compare(rs.previous_version(v), v) < 0


def test_round_trip_refuses_a_step_that_does_not_read_back(repo, tmp_path):
    fac = FakeFactory(tmp_path, leave_link=True)
    rep, _run = _stage(repo, tmp_path, roundtrip=fac)
    assert rep["verdict"] == "FAIL" and rep["assets"] == []
    assert "uninstall: left behind: Desktop/AshLight.lnk" in _detail(rep, "roundtrip")
    assert fac.log[-1] == ("cleanup",)
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["stage.json"]


def test_round_trip_writes_no_real_shell_entry(repo, tmp_path, monkeypatch):
    for key in ("AL_HOME", "AL_PORT", "AL_UNINSTALL_FAKE", "AL_DEV"):
        monkeypatch.setenv(key, "x")
    before = rs.real_shell_snapshot()
    fac = FakeFactory(tmp_path)
    rep, _run = _stage(repo, tmp_path, roundtrip=fac)
    assert rep["verdict"] == "PASS", rep["steps"]
    assert rs.real_shell_snapshot() == before
    fx = fac.made[0]
    sidecar_temp = (tmp_path / "sidecar" / "Temp").resolve()
    assert fx.base.resolve().parent == sidecar_temp
    assert len(fx.envs) == 7
    for env in fx.envs:
        assert env["AL_SHELL_ROOT"] == str(fx.shell)
        assert env["TEMP"] == env["TMP"] == str(fx.temp)
        for key in ("AL_HOME", "AL_PORT", "AL_UNINSTALL_FAKE", "AL_DEV"):
            assert key not in env
    # the real snapshot reads AshLight's own names only
    snap = rs.real_shell_snapshot()
    assert sorted(snap) == ["desktop", "logon_task", "start_menu", "uninstall_key"]
    assert rs.REAL_UNINSTALL_KEY.endswith(r"\Uninstall\AshLight")
    # a real entry that changes during the round trip fails the step
    real = {"start_menu": None, "desktop": None, "uninstall_key": None,
            "logon_task": None}
    moved = dict(real, desktop=[1, 2, "ab"])
    fac2 = FakeFactory(tmp_path / "two", snapshots=[real, moved])
    (tmp_path / "two").mkdir()
    rep2, _run = _stage(repo, tmp_path, roundtrip=fac2)
    assert rep2["verdict"] == "FAIL"
    assert _detail(rep2, "roundtrip") == "the real shell entries changed: desktop"


def test_round_trip_scratch_key_id_matches_al_shell(tmp_path):
    # al_shell.ps1 Get-AlShellPlaces: SHA-256 of the lower-cased full root
    # path (UTF-8, no trailing separator), first 8 bytes as hex
    root = os.path.abspath(str(tmp_path / "Shell"))
    want = hashlib.sha256(root.lower().encode("utf-8")).hexdigest()[:16]
    assert rs.scratch_key_id(root + os.sep) == want
    text = (ROOT / "scripts" / "al_shell.ps1").read_text(encoding="ascii")
    assert "ToLowerInvariant()" in text and "$bytes[0..7]" in text


def _zip_with_ports(line):
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("AshLight-%s/server/al/ports.py" % VERSION, line + "\n")
    return buf.getvalue()


def test_round_trip_demo_cores_use_selftest_ports_and_web_data_off(repo, tmp_path):
    # the shipped self-test block is 8970-8975, never the core's 8960
    out = tmp_path / "one"
    _builder(tmp_path)(root=repo, out=out)
    zip_bytes = (out / ("AshLight-%s-app.zip" % VERSION)).read_bytes()
    assert rs.selftest_ports(zip_bytes) == (8970, 8975)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from server.al import ports
    from server.al.install import selftest
    import inspect
    assert ports.SELFTEST_PORTS == rs.SELFTEST_BLOCK
    assert inspect.signature(selftest.run).parameters["ports"].default \
        == ports.SELFTEST_PORTS
    if os.name == "nt":
        assert selftest.child_flags() & rs.CREATE_NO_WINDOW
    # a payload whose self-test could bind the core port is refused first
    for bad in ("SELFTEST_PORTS = (8960, 8965)", "SELFTEST_PORTS = (8970, 8979)",
                "PORTS = 1"):
        log = []
        ctx = {"staged": {"release.json": b"{}", "z.zip": _zip_with_ports(bad)},
               "version": VERSION, "zip_name": "z.zip",
               "roundtrip": lambda c: log.append("effects")}
        with pytest.raises(rs.StepFail) as err:
            rs.step_roundtrip(ctx)
        assert "8970-8975" in str(err.value) and log == []
    # web data on in the scratch home fails the step after the install
    fac = FakeFactory(tmp_path, web_data=True)
    rep, _run = _stage(repo, tmp_path, roundtrip=fac)
    assert rep["verdict"] == "FAIL"
    assert _detail(rep, "roundtrip") == \
        "install: web data is not off in the scratch home"
    assert ("installer", "update") not in fac.log
    assert fac.log[-1] == ("cleanup",)


def test_round_trip_skips_cleanly_without_cached_runtimes(repo, tmp_path,
                                                          monkeypatch):
    import socket
    import urllib.request

    def no_network(*_a, **_k):
        raise AssertionError("the round trip made a network request")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    # a cached file with the right name but the wrong bytes is not a hit
    cache = tmp_path / "sidecar" / "Cache" / "runtimes"
    cache.mkdir(parents=True)
    pins = json.loads((ROOT / "config" / "runtime_pins.json").read_bytes())
    py_file = pins["runtimes"]["python"]["file"]
    (cache / py_file).write_bytes(b"not the pinned zip")
    rep = rs.stage(VERSION, run=Runner(), now=lambda: WHEN_TS, root=repo,
                   out=tmp_path / "out", owner="sess.agent",
                   build=_builder(tmp_path))
    assert rep["verdict"] == "FAIL"
    assert _statuses(rep)["roundtrip"] == "fail"
    detail = _detail(rep, "roundtrip")
    assert detail.startswith("runtimes not cached: ")
    assert "never downloads" in detail
    assert str(tmp_path) not in detail
    assert rep["assets"] == []
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["stage.json"]
    # the default scratch folder under <sidecar>/Temp is removed again
    temp = tmp_path / "sidecar" / "Temp"
    assert not [p for p in temp.iterdir() if p.name.startswith(rs.RT_PREFIX)]


def test_find_runtimes_matches_size_and_hash(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    data = b"publisher zip bytes"
    (b / "rt.zip").write_bytes(data)
    (a / "rt.zip").write_bytes(b"other bytes of a size")
    pin = {"url": "https://example.invalid/x/rt.zip", "size": len(data),
           "sha256": hashlib.sha256(data).hexdigest()}
    found = rs.find_runtimes({"runtimes": {"python": pin}}, [a, b])
    assert found == {"rt.zip": b / "rt.zip"}
    with pytest.raises(rs.StepFail) as err:
        rs.find_runtimes({"runtimes": {"python": pin}}, [a])
    assert "runtimes not cached: rt.zip" in str(err.value)
    with pytest.raises(rs.StepFail):
        rs.find_runtimes({"runtimes": {}}, [a])


# --- dispatcher ------------------------------------------------------------

def test_release_dispatcher_loads_stage():
    rel = _load("release")
    assert rel.module_path("stage").name == "rel_stage.py"
    assert rel.load("stage") is not None
    assert rel.main(["stage", "--help"]) == 0


def test_cli_fail_exit_code(repo, tmp_path, monkeypatch):
    (repo / "stray.txt").write_bytes(b"x\n")
    monkeypatch.setattr(rs, "default_run", Runner())
    code = rs.main("stage", ["--root", str(repo), "--out", str(tmp_path / "out"),
                             "--owner", "sess.agent"])
    assert code == 1
    doc = json.loads((tmp_path / "out" / "stage.json").read_bytes())
    assert doc["verdict"] == "FAIL" and doc["version"] == VERSION


# --- floor: the release tools never look for the game ----------------------

_FLOOR = re.compile(
    r"tasklist|get-process|psutil|process_iter|toolhelp32|enumprocesses|"
    r"wmic|win32_process|enumwindows|findwindow|getforegroundwindow|"
    r"getwindowtext|client\.txt", re.I)


def test_release_tools_never_look_for_the_game():
    files = sorted((ROOT / "tools").glob("rel_*.py")) + [ROOT / "tools/release.py"]
    assert ROOT / "tools/rel_stage.py" in files
    for path in files:
        text = path.read_text(encoding="utf-8")
        hit = _FLOOR.search(text)
        assert hit is None, "%s: %s" % (path.name, hit.group(0))


def test_the_loop_never_publishes_or_tags():
    for rel in ("tools/al_loop.py", "tools/al_lane.py", "tools/loop_prompts.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "release.py publish" not in text, rel
        assert "git tag" not in text, rel
