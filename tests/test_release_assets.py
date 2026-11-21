"""Release assets (REL-BUILD-ASSETS, decision 0064): tools/rel_assets.py,
called once from tools/rel_build.py build().

The scratch repos are fresh git repos under tmp_path holding the real ship
list, the real runtime / Electron / calc pins and npm lockfile, a notes file
and small stand-in payload files, committed at a fixed time. Every build
points its cache check at a folder under tmp_path, and the leak sweep gets
a stand-in needle through AL_LEAK_NEEDLES, so nothing reads the operator's
sidecar or needle config.
"""
import datetime
import hashlib
import importlib.util
import json
import os
import random
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al.install import payload  # noqa: E402

WHEN = "2026-11-19T10:20:30Z"
WHEN_TS = int(datetime.datetime(2026, 11, 19, 10, 20, 30,
                                tzinfo=datetime.timezone.utc).timestamp())
NEEDLE = "zqxstandinneedle"


def _load(name):
    spec = importlib.util.spec_from_file_location(
        "assets_test_" + name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rb = _load("rel_build")
ra = _load("rel_assets")

_GIT = ["git", "-c", "core.hooksPath=", "-c", "user.name=t",
        "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
        "-c", "tag.gpgsign=false"]


def _git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE=WHEN, GIT_COMMITTER_DATE=WHEN)
    proc = subprocess.run(_GIT + list(args), cwd=str(cwd), env=env,
                          capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


NOTES = ("## [1.2.3] - 2026-11-19\n\nStand-in release notes.\n\n"
         "### Added\n- One thing (X-1)\n")
INSTALLER = ("# AshLight bootstrap (stand-in)\n"
             "$AlVersion = '__AL_VERSION__'\n"
             "$Ua = 'AshLight/__AL_VERSION__ (installer)'\n")
NINJA_OFF = ("\"\"\"Stand-in poe.ninja client.\"\"\"\n"
             "RELEASE_POLLING = False\nREASON_RELEASE = \"release build\"\n")
NINJA_ON = NINJA_OFF.replace("RELEASE_POLLING = False", "RELEASE_POLLING = True")
YES_DECISION = ("# 9001 - poe.ninja answered\n\n"
                "Release polling: allowed by poe.ninja's written yes.\n")

FILES = {
    "server/al/core.py": "\"\"\"Stand-in core.\"\"\"\nVALUE = 1\n",
    "web/index.html": "<!doctype html><title>AshLight</title>\n",
    "app/main.js": "'use strict';\n",
    "tools/tc_pin.py": "# pin tool\n",
    "README.md": "# AshLight\n",
    "LICENSE": "licence\n",
    "boot.py": "# boot\n",
    "docs/releases/1.2.3.md": NOTES,
}
REAL = ("config/ship_list.json", "config/runtime_pins.json",
        "config/electron_pin.json", "config/tc_pins.json",
        "app/package-lock.json")


def _write(repo, rel, text):
    dst = repo / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(text.encode("ascii") if isinstance(text, str) else text)


def _init_text(version):
    return "\"\"\"AshLight core.\"\"\"\n\nVERSION = \"%s\"\n" % version


def _scratch(tmp_path, version="1.2.3", extra=None, drop=(), name="repo"):
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    for rel in REAL:
        if rel not in drop:
            _write(repo, rel, (ROOT / rel).read_bytes())
    _write(repo, "server/al/__init__.py", _init_text(version))
    for rel, text in FILES.items():
        if rel not in drop:
            _write(repo, rel, text)
    for rel, text in (extra or {}).items():
        _write(repo, rel, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: scratch")
    return repo


def _cache(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir(exist_ok=True)
    return cache


def _build(repo, tmp_path, out_name, **kw):
    kw.setdefault("cache_dir", _cache(tmp_path))
    return rb.build(root=repo, out=tmp_path / out_name, **kw)


def _refuse(repo, tmp_path, match, **kw):
    out = tmp_path / "refused"
    with pytest.raises(rb.BuildError, match=match):
        rb.build(root=repo, out=out, cache_dir=_cache(tmp_path), **kw)
    assert not out.exists()


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").decode("ascii").strip()


@pytest.fixture(autouse=True)
def standin_needle(monkeypatch):
    monkeypatch.setenv("AL_LEAK_NEEDLES", NEEDLE)


class _NetSpy:
    def __init__(self, monkeypatch):
        self.calls = []

        def refuse(*a, **_k):
            self.calls.append(a)
            raise OSError("network blocked in this test")
        monkeypatch.setattr(socket.socket, "connect", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        monkeypatch.setattr(socket, "getaddrinfo", refuse)


# --- release.json ----------------------------------------------------------

def test_release_json_carries_the_fields_pins_and_asset_list(tmp_path,
                                                             monkeypatch):
    net = _NetSpy(monkeypatch)
    repo = _scratch(tmp_path, extra={"scripts/install.ps1": INSTALLER})
    res = _build(repo, tmp_path, "out")
    out = res["out"]
    doc = json.loads((out / "release.json").read_bytes().decode("ascii"))
    assert doc["name"] == "AshLight"
    assert doc["version"] == "1.2.3"
    assert doc["channel"] == "stable"
    assert doc["commit"] == _head(repo)
    assert doc["created"] == WHEN
    assert doc["bootstrap_protocol"] == 1
    assert "tag" not in doc
    runtime = json.loads((ROOT / "config/runtime_pins.json").read_bytes())
    py = runtime["runtimes"]["python"]
    assert doc["runtimes"]["python"] == {
        k: py[k] for k in ("version", "file", "url", "sha256", "size", "licence")}
    el = json.loads((ROOT / "config/electron_pin.json").read_bytes())
    x64 = el["arch"]["x64"]
    assert doc["runtimes"]["electron"] == {
        "version": el["version"], "file": x64["zip_name"], "url": x64["zip_url"],
        "sha256": x64["zip_sha256"], "size": x64["zip_size"],
        "licence": runtime["runtimes"]["electron"]["licence"]}
    # the installer reads the same pins from this file
    pins = payload.pins_from_release(doc, "1.2.3")
    assert pins["python"]["sha256"] == py["sha256"]
    listed = {e["name"]: e for e in doc["assets"]}
    assert sorted(listed) == sorted([
        "AshLight-1.2.3-app.zip", "install.ps1", "AshLight-1.2.3-notes.md",
        "AshLight-1.2.3.sbom.json"])
    assert [e["name"] for e in doc["assets"]] == sorted(listed)
    for name, entry in listed.items():
        data = (out / name).read_bytes()
        assert entry == {"name": name, "size": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()}
    assert net.calls == []


def test_rc_version_is_the_rc_channel(tmp_path):
    repo = _scratch(tmp_path, version="1.2.3-rc.1",
                    extra={"docs/releases/1.2.3-rc.1.md": NOTES})
    res = _build(repo, tmp_path, "out")
    doc = json.loads((res["out"] / "release.json").read_bytes())
    assert doc["channel"] == "rc" and doc["version"] == "1.2.3-rc.1"


# --- install.ps1 -----------------------------------------------------------

def test_install_ps1_is_the_tracked_bootstrap_with_the_version_stamped(tmp_path):
    repo = _scratch(tmp_path, extra={"scripts/install.ps1": INSTALLER})
    res = _build(repo, tmp_path, "out")
    got = (res["out"] / "install.ps1").read_bytes()
    assert got == INSTALLER.replace("__AL_VERSION__", "1.2.3").encode("ascii")
    assert b"__AL_VERSION__" not in got
    assert "install.ps1" in res["assets"]


def test_install_ps1_absent_gives_a_clear_note(tmp_path, capsys):
    repo = _scratch(tmp_path)
    res = _build(repo, tmp_path, "out")
    assert not (res["out"] / "install.ps1").exists()
    assert any("scripts/install.ps1 does not exist" in n for n in res["notes"])
    assert "scripts/install.ps1 does not exist" in capsys.readouterr().err
    doc = json.loads((res["out"] / "release.json").read_bytes())
    assert "install.ps1" not in [e["name"] for e in doc["assets"]]


def test_install_ps1_without_a_stamp_point_refuses(tmp_path):
    repo = _scratch(tmp_path, extra={"scripts/install.ps1": "# no stamp\n"})
    _refuse(repo, tmp_path, "no version stamp point")


def test_stamp_marker_lines_must_hold_the_version():
    marker = b"al-version-" + b"stamp"  # split: rel_version scans tracked files
    good = b"$v = '1.2.3'  # " + marker + b"\n"
    assert ra.stamp_installer(good, "1.2.3") == good
    with pytest.raises(ra.AssetError, match="does not hold 1.2.3"):
        ra.stamp_installer(b"$v = '1.2.2'  # " + marker + b"\n", "1.2.3")


# --- notes and SBOM --------------------------------------------------------

def test_notes_equal_the_docs_releases_file(tmp_path):
    repo = _scratch(tmp_path)
    res = _build(repo, tmp_path, "out")
    assert ((res["out"] / "AshLight-1.2.3-notes.md").read_bytes()
            == NOTES.encode("ascii"))


def test_missing_notes_refuse(tmp_path):
    repo = _scratch(tmp_path, drop=("docs/releases/1.2.3.md",))
    _refuse(repo, tmp_path, "docs/releases/1.2.3.md is missing")


def test_sbom_is_the_sbom_tool_output(tmp_path):
    repo = _scratch(tmp_path)
    res = _build(repo, tmp_path, "out")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "sbom.py"), "--commit", "HEAD",
         "--root", str(repo)], capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert (res["out"] / "AshLight-1.2.3.sbom.json").read_bytes() == proc.stdout
    sbom = json.loads(proc.stdout)
    assert sbom["metadata"]["timestamp"] == WHEN


# --- SHA256SUMS.txt and reproducibility ------------------------------------

def test_sums_have_one_sorted_line_per_file(tmp_path):
    repo = _scratch(tmp_path, extra={"scripts/install.ps1": INSTALLER})
    res = _build(repo, tmp_path, "out")
    out = res["out"]
    lines = (out / "SHA256SUMS.txt").read_text("ascii").splitlines()
    names = [ln.split("  ", 1)[1] for ln in lines]
    assert names == sorted(names)
    assert sorted(names) == sorted(p.name for p in out.iterdir()
                                   if p.name != "SHA256SUMS.txt")
    assert names == res["assets"]
    for ln in lines:
        digest, name = ln.split("  ", 1)
        assert digest == hashlib.sha256((out / name).read_bytes()).hexdigest()


def test_two_builds_give_identical_sums(tmp_path, monkeypatch):
    repo = _scratch(tmp_path, extra={"scripts/install.ps1": INSTALLER})
    net = _NetSpy(monkeypatch)
    first = _build(repo, tmp_path, "out1")
    monkeypatch.setattr(time, "time", lambda: 4102444800.0)
    monkeypatch.setattr(time, "time_ns", lambda: 4102444800 * 10 ** 9)
    monkeypatch.setattr(socket, "gethostname", lambda: "another-host")
    monkeypatch.setattr(os, "urandom", lambda n: b"\x07" * n)
    monkeypatch.setattr(random, "random", lambda: 0.123)
    second = _build(repo, tmp_path, "out2")
    one = (first["out"] / "SHA256SUMS.txt").read_bytes()
    assert one == (second["out"] / "SHA256SUMS.txt").read_bytes()
    for name in first["assets"]:
        assert ((first["out"] / name).read_bytes()
                == (second["out"] / name).read_bytes()), name
    assert net.calls == []


def test_cli_builds_twice_with_identical_sums(tmp_path):
    repo = _scratch(tmp_path)
    env = dict(os.environ, AL_SIDECAR_ROOT=str(tmp_path / "sidecar"),
               AL_LEAK_NEEDLES=NEEDLE)
    outs = []
    for name in ("c1", "c2"):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "release.py"), "build",
             "--root", str(repo), "--ref", "HEAD", "--out", str(tmp_path / name)],
            cwd=str(ROOT), env=env, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        outs.append((tmp_path / name / "SHA256SUMS.txt").read_bytes())
    assert outs[0] == outs[1]
    assert len(outs[0].splitlines()) == 4


# --- refusals of the staged tree -------------------------------------------

def test_leak_sweep_needle_hit_refuses(tmp_path):
    repo = _scratch(tmp_path, extra={
        "web/app.js": "// built for %s\n" % NEEDLE})
    _refuse(repo, tmp_path, "leak sweep: 1 finding.*web/app.js:1 needle-slot-0")


def test_leak_sweep_structural_hit_refuses(tmp_path):
    drive = "Q" + ":" + "\\" + "private" + "\\" + "notes.txt"
    repo = _scratch(tmp_path, extra={"server/al/where.py": "P = %r\n" % drive})
    _refuse(repo, tmp_path, "leak sweep.*server/al/where.py:1 drive-path")


def test_leak_sweep_finding_never_prints_the_needle(tmp_path):
    repo = _scratch(tmp_path, extra={"web/app.js": "// %s\n" % NEEDLE})
    with pytest.raises(rb.BuildError) as info:
        _build(repo, tmp_path, "out")
    assert NEEDLE not in str(info.value)


def test_ninja_release_switch_on_without_a_decision_refuses(tmp_path):
    repo = _scratch(tmp_path, extra={"server/al/ninja.py": NINJA_ON})
    _refuse(repo, tmp_path, "RELEASE_POLLING = True and no decision")


def test_ninja_release_switch_on_with_a_recorded_yes_builds(tmp_path):
    repo = _scratch(tmp_path, extra={
        "server/al/ninja.py": NINJA_ON,
        "docs/decisions/9001-poe-ninja-yes.md": YES_DECISION})
    res = _build(repo, tmp_path, "out")
    assert (res["out"] / "release.json").is_file()


def test_ninja_release_switch_off_builds(tmp_path):
    repo = _scratch(tmp_path, extra={"server/al/ninja.py": NINJA_OFF})
    res = _build(repo, tmp_path, "out")
    assert (res["out"] / "release.json").is_file()


def test_real_ninja_holds_the_release_constant():
    # The constant exists (DATA-PRICE-CADENCE), so the gate reads it for real.
    data = (ROOT / "server" / "al" / "ninja.py").read_text(encoding="utf-8")
    assert ra.release_polling(data) is False


def test_ninja_gate_rules():
    off = {ra.NINJA_REL: NINJA_OFF.encode("ascii")}
    on = {ra.NINJA_REL: NINJA_ON.encode("ascii")}
    notes = []
    assert ra.ninja_gate({}, {}, notes) is None and notes
    assert ra.ninja_gate(off, {}) is False
    with pytest.raises(ra.AssetError, match="no decision records"):
        ra.ninja_gate(on, {"docs/decisions/0072-x.md": "RELEASE_POLLING = True\n"})
    prose = {"docs/decisions/9001-x.md":
             "We hope for Release polling: allowed by poe.ninja's written yes.\n"}
    with pytest.raises(ra.AssetError):
        ra.ninja_gate(on, prose)
    assert ra.ninja_gate(on, {"docs/decisions/9001-x.md": YES_DECISION}) is True
    for bad in ("X = 1\n", "RELEASE_POLLING = False\nRELEASE_POLLING = True\n",
                "RELEASE_POLLING = 1\n", "RELEASE_POLLING = bool(1)\n"):
        with pytest.raises(ra.AssetError):
            ra.ninja_gate({ra.NINJA_REL: bad.encode("ascii")}, {})


# --- the release inputs ----------------------------------------------------

def test_stand_in_tree_builds_only_the_zip_and_sums(tmp_path):
    repo = _scratch(tmp_path, drop=("config/runtime_pins.json",
                                    "config/electron_pin.json",
                                    "app/package-lock.json"))
    res = _build(repo, tmp_path, "out")
    assert sorted(p.name for p in res["out"].iterdir()) == [
        "AshLight-1.2.3-app.zip", "SHA256SUMS.txt"]
    assert any("release assets skipped" in n for n in res["notes"])


def test_partial_release_inputs_refuse(tmp_path):
    repo = _scratch(tmp_path, drop=("config/electron_pin.json",))
    _refuse(repo, tmp_path, "incomplete release inputs.*electron_pin.json")


def test_ref_and_tag_builds_have_identical_assets(tmp_path):
    repo = _scratch(tmp_path)
    _git(repo, "tag", "-a", "v1.2.3", "-m", "release v1.2.3")
    by_ref = _build(repo, tmp_path, "ref", ref="HEAD")
    by_tag = _build(repo, tmp_path, "tag", tag="v1.2.3")
    assert by_ref["assets"] == by_tag["assets"]
    for name in by_ref["assets"] + ["SHA256SUMS.txt"]:
        assert ((by_ref["out"] / name).read_bytes()
                == (by_tag["out"] / name).read_bytes()), name
    assert b"v1.2.3" not in (by_tag["out"] / "release.json").read_bytes()
