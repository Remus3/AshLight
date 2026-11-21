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
import subprocess
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
        "app/package.json", "app/package-lock.json")
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
def standin_needle(monkeypatch):
    monkeypatch.setenv("AL_LEAK_NEEDLES", NEEDLE)


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
        "clean", "version", "suite", "node", "builds", "sweep"]
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
    detail = rep["steps"][-1]["detail"]
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
