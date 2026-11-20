"""Release build tool (DEP-08, decision 0064): tools/rel_build.py.

The scratch repos here are fresh git repos under tmp_path holding the real
config/ship_list.json plus small stand-in files, committed at a fixed time.
Every build points its cache check at a folder under tmp_path, so nothing
reads the operator's sidecar.
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
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "tools" / "release.py"
WHEN = "2026-11-19T10:20:30Z"
WHEN_TS = int(datetime.datetime(2026, 11, 19, 10, 20, 30,
                                tzinfo=datetime.timezone.utc).timestamp())


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rb = _load("rel_build")
release = _load("release")

_GIT = ["git", "-c", "core.hooksPath=", "-c", "user.name=t",
        "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
        "-c", "tag.gpgsign=false"]


def _git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE=WHEN, GIT_COMMITTER_DATE=WHEN)
    proc = subprocess.run(_GIT + list(args), cwd=str(cwd), env=env,
                          capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


CORE = ("\"\"\"Stand-in core module for the release build test.\"\"\"\n"
        + "".join("VALUE_%02d = %d  # padding so the file is not tiny\n" % (i, i)
                  for i in range(12)))

FILES = {
    "server/al/core.py": CORE,
    "server/al/data/zone_notes.json": "{\"zones\": []}\n",
    "web/index.html": "<!doctype html><title>AshLight</title>\n",
    "app/main.js": "'use strict';\n",
    "app/package.json": "{\"version\": \"1.2.3\"}\n",
    "app/test/main.test.js": "// test\n",
    "scripts/run.ps1": "# run\n",
    "scripts/brand_render.js": "// dev only\n",
    "config/tc_pins.json": "{}\n",
    "config/local.example.json": "{}\n",
    "tools/tc_pin.py": "# pin tool\n",
    "tools/leak_sweep.py": "# dev tool\n",
    "tests/test_x.py": "# test\n",
    "docs/x.md": "# doc\n",
    "ops/loop/gates.txt": "gate\n",
    "ops/fleet_kit/tokens.css": ":root{}\n",
    "ops/fleet_kit/fleet_hook.sh": "# kit\n",
    ".claude/settings.json": "{}\n",
    ".githooks/pre-push": "# hook\n",
    "ROADMAP.md": "# roadmap\n",
    "CLAUDE.md": "# rules\n",
    "AL-NEXT-SESSION.txt": "hand-off\n",
    "README.md": "# AshLight\n",
    "LICENSE": "licence\n",
    "boot.py": "# boot\n",
}


def _write(repo, rel, text):
    dst = repo / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(text.encode("ascii") if isinstance(text, str) else text)


def _init_text(version):
    return "\"\"\"AshLight core.\"\"\"\n\nVERSION = \"%s\"\n" % version


def _scratch(tmp_path, version="1.2.3", extra=None, name="repo"):
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    _write(repo, "config/ship_list.json",
           (ROOT / "config" / "ship_list.json").read_bytes())
    _write(repo, "server/al/__init__.py", _init_text(version))
    for rel, text in FILES.items():
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


def _members(zip_path):
    with zipfile.ZipFile(str(zip_path)) as zf:
        return {i.filename: (i, zf.read(i)) for i in zf.infolist()}


class _NetSpy:
    def __init__(self, monkeypatch):
        self.calls = []

        def refuse(*a, **_k):
            self.calls.append(a)
            raise OSError("network blocked in this test")
        monkeypatch.setattr(socket.socket, "connect", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        monkeypatch.setattr(socket, "getaddrinfo", refuse)


def test_two_builds_are_byte_identical_with_clock_host_and_random_changed(
        tmp_path, monkeypatch):
    repo = _scratch(tmp_path)
    net = _NetSpy(monkeypatch)
    first = _build(repo, tmp_path, "out1")
    monkeypatch.setattr(time, "time", lambda: 4102444800.0)
    monkeypatch.setattr(time, "time_ns", lambda: 4102444800 * 10 ** 9)
    monkeypatch.setattr(socket, "gethostname", lambda: "another-host")
    monkeypatch.setattr(os, "urandom", lambda n: b"\x07" * n)
    monkeypatch.setattr(random, "random", lambda: 0.123)
    monkeypatch.setattr(random, "getrandbits", lambda k: 5)
    second = _build(repo, tmp_path, "out2")
    assert first["sha256"] == second["sha256"]
    assert first["zip"].read_bytes() == second["zip"].read_bytes()
    assert ((first["out"] / rb.SUMS_NAME).read_bytes()
            == (second["out"] / rb.SUMS_NAME).read_bytes())
    sums = (first["out"] / rb.SUMS_NAME).read_text("ascii")
    assert sums == "%s  AshLight-1.2.3-app.zip\n" % first["sha256"]
    assert net.calls == []


def test_entries_come_from_git_blobs_sorted_at_the_commit_time(tmp_path):
    repo = _scratch(tmp_path)
    # A working-copy change is not shipped: the bytes come from the blob.
    _write(repo, "web/index.html", "changed in the working copy\n")
    res = _build(repo, tmp_path, "out", check_clean=False)
    names = [i.filename for i in zipfile.ZipFile(str(res["zip"])).infolist()]
    assert names == sorted(names)
    assert all(n.startswith("AshLight-1.2.3/") for n in names)
    members = _members(res["zip"])
    want_time = time.gmtime(WHEN_TS)[:6]
    for name, (info, data) in members.items():
        rel = name.split("/", 1)[1]
        assert info.date_time == want_time
        if rel in rb.GENERATED:
            continue
        assert data == _git(repo, "cat-file", "blob", "HEAD:" + rel)
    assert members["AshLight-1.2.3/web/index.html"][1].startswith(b"<!doctype")
    build = json.loads(members["AshLight-1.2.3/BUILD"][1].decode("ascii"))
    head = _git(repo, "rev-parse", "HEAD").decode("ascii").strip()
    assert build == {"commit": head[:12], "created": WHEN, "version": "1.2.3"}
    manifest = json.loads(members["AshLight-1.2.3/MANIFEST.json"][1])
    assert sorted(manifest["files"]) == sorted(
        n.split("/", 1)[1] for n in names if not n.endswith("/MANIFEST.json"))
    assert rb.verify_zip(res["zip"]) == []


def test_scratch_ship_list_keeps_only_the_payload(tmp_path):
    repo = _scratch(tmp_path)
    shipped = rb.ship("HEAD", repo)
    assert shipped == [
        "LICENSE", "README.md", "app/main.js", "app/package.json", "boot.py",
        "config/tc_pins.json", "ops/fleet_kit/tokens.css", "scripts/run.ps1",
        "server/al/__init__.py", "server/al/core.py",
        "server/al/data/zone_notes.json", "tools/tc_pin.py", "web/index.html"]


def _real_files():
    spec = rb.parse_ship_list((ROOT / "config" / "ship_list.json").read_bytes())
    head = rb._rev(ROOT, "HEAD^{commit}")
    return spec, head, rb.assemble(ROOT, head, spec, "0.0.0", WHEN_TS,
                                   cache_dir=None)


def test_real_ship_list_leaves_out_dev_files():
    _spec, _head, files = _real_files()
    shipped = sorted(set(files) - set(rb.GENERATED))
    for path in shipped:
        assert not path.startswith(("ops/loop/", "tests/", "docs/", "app/test/",
                                    ".claude/", ".githooks/", ".github/")), path
        if path.startswith("tools/"):
            assert path == "tools/tc_pin.py"
        if path.startswith("ops/"):
            assert path.startswith("ops/fleet_kit/")
    for path in ("config/local.example.json", "config/ship_list.json",
                 "ROADMAP.md", "CLAUDE.md", "AL-NEXT-SESSION.txt"):
        assert path not in shipped
    for path in ("server/al/__init__.py", "boot.py", "README.md", "LICENSE",
                 "ops/fleet_kit/tokens.css", "app/main.js", "web/index.html",
                 "tools/tc_pin.py"):
        assert path in shipped


def test_real_zip_is_under_two_megabytes():
    spec, _head, files = _real_files()
    blob = rb.write_zip(files, "AshLight-0.0.0", WHEN_TS, spec["compression"],
                        spec["compresslevel"])
    assert spec["max_zip_bytes"] <= 2000000
    assert len(blob) < 2000000


def test_manifest_check_catches_changed_missing_and_unsafe(tmp_path):
    repo = _scratch(tmp_path)
    res = _build(repo, tmp_path, "out")
    lay = tmp_path / "laid"
    with zipfile.ZipFile(str(res["zip"])) as zf:
        zf.extractall(str(lay))
    folder = lay / "AshLight-1.2.3"
    assert rb.verify_tree(folder) == []
    (folder / "web" / "index.html").write_bytes(b"tampered\n")
    assert rb.verify_tree(folder) == ["changed: web/index.html"]
    (folder / "app" / "main.js").unlink()
    assert "missing: app/main.js" in rb.verify_tree(folder)
    manifest = json.loads((folder / "MANIFEST.json").read_bytes())
    manifest["files"]["../outside.txt"] = {"sha256": "0" * 64, "size": 1}
    assert "unsafe path: '../outside.txt'" in rb.verify_tree(folder, manifest)
    (folder / "extra.txt").write_bytes(b"x")
    assert "unlisted: extra.txt" in rb.verify_tree(folder)
    for bad in ("../x", "/abs", "a\\b", "C" + ":/x", "a/./b", "con.py", "a/aux",
                "web/a b.js", "trail.", ""):
        assert not rb.safe_path(bad), bad


def test_zip_check_catches_a_tampered_member(tmp_path):
    repo = _scratch(tmp_path)
    res = _build(repo, tmp_path, "out")
    members = _members(res["zip"])
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(str(bad), "w") as zf:
        for name, (_info, data) in sorted(members.items()):
            if name.endswith("/app/main.js"):
                data = b"tampered\n"
            zf.writestr(name, data)
    assert rb.verify_zip(bad) == ["changed: app/main.js"]
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(str(evil), "w") as zf:
        zf.writestr("AshLight-1.2.3/../../evil.txt", b"x")
    assert rb.verify_zip(evil)[0].startswith("unsafe member")


def _tag(repo, tag, annotated=True):
    if annotated:
        _git(repo, "tag", "-a", tag, "-m", "release " + tag)
    else:
        _git(repo, "tag", tag)


def _refuse(repo, tmp_path, match, **kw):
    out = tmp_path / "refused"
    with pytest.raises(rb.BuildError, match=match):
        rb.build(root=repo, out=out, **kw)
    assert not out.exists()


def test_dirty_tree_refuses_with_nothing_written(tmp_path):
    repo = _scratch(tmp_path)
    _write(repo, "web/index.html", "edited\n")
    _refuse(repo, tmp_path, "dirty", cache_dir=_cache(tmp_path))


def test_untracked_file_refuses_with_nothing_written(tmp_path):
    repo = _scratch(tmp_path)
    _write(repo, "web/new.js", "new\n")
    _refuse(repo, tmp_path, "dirty", cache_dir=_cache(tmp_path))


def test_missing_tag_refuses_with_nothing_written(tmp_path):
    repo = _scratch(tmp_path)
    _refuse(repo, tmp_path, "no tag v1.2.3", tag="v1.2.3",
            cache_dir=_cache(tmp_path))
    _refuse(repo, tmp_path, "not v<version>", tag="1.2.3",
            cache_dir=_cache(tmp_path))


def test_tag_that_differs_from_version_refuses(tmp_path):
    repo = _scratch(tmp_path)
    _tag(repo, "v1.2.4")
    _refuse(repo, tmp_path, "differs from v1.2.3", tag="v1.2.4",
            cache_dir=_cache(tmp_path))


def test_sidecar_cache_file_refuses_with_nothing_written(tmp_path):
    repo = _scratch(tmp_path)
    cache = _cache(tmp_path)
    (cache / "gamedata").mkdir()
    (cache / "gamedata" / "snapshot.py").write_bytes(CORE.encode("ascii"))
    _refuse(repo, tmp_path, "sidecar cache file.*server/al/core.py",
            cache_dir=cache)


def test_cache_shaped_path_refuses_with_nothing_written(tmp_path):
    repo = _scratch(tmp_path, extra={
        "server/al/data/gamedata/base_items.json": "{}\n"})
    _refuse(repo, tmp_path, "sidecar cache file.*gamedata",
            cache_dir=_cache(tmp_path))


def test_unsafe_shipped_path_refuses(tmp_path):
    repo = _scratch(tmp_path, extra={"web/a b.js": "x\n"})
    _refuse(repo, tmp_path, "unsafe path", cache_dir=_cache(tmp_path))


def test_ref_builds_any_version_untagged(tmp_path):
    repo = _scratch(tmp_path, version="2.0.0-rc.1")
    _write(repo, "server/al/__init__.py", _init_text("2.0.0"))
    _git(repo, "commit", "-q", "-am", "chore: final")
    newest = _build(repo, tmp_path, "a", ref="HEAD")
    older = _build(repo, tmp_path, "b", ref="HEAD~1")
    assert newest["version"] == "2.0.0"
    assert older["version"] == "2.0.0-rc.1"
    assert newest["zip"].name == "AshLight-2.0.0-app.zip"
    assert older["zip"].name == "AshLight-2.0.0-rc.1-app.zip"
    assert _git(repo, "tag", "--list") == b""


@pytest.mark.parametrize("annotated", [True, False])
def test_ref_and_tag_builds_of_one_commit_are_identical(tmp_path, annotated):
    repo = _scratch(tmp_path)
    _tag(repo, "v1.2.3", annotated)
    by_ref = _build(repo, tmp_path, "ref", ref="HEAD")
    by_tag = _build(repo, tmp_path, "tag", tag="v1.2.3")
    assert by_ref["zip"].read_bytes() == by_tag["zip"].read_bytes()
    assert ((by_ref["out"] / rb.SUMS_NAME).read_bytes()
            == (by_tag["out"] / rb.SUMS_NAME).read_bytes())
    members = _members(by_tag["zip"])
    for name in ("BUILD", "MANIFEST.json"):
        data = members["AshLight-1.2.3/" + name][1]
        assert b"v1.2.3" not in data
        assert "tag" not in json.loads(data)
    rel = by_tag["out"] / "release.json"
    if rel.exists():  # written by REL-BUILD-ASSETS
        assert "tag" not in json.loads(rel.read_bytes())


def test_both_ref_and_tag_is_a_refusal(tmp_path):
    repo = _scratch(tmp_path)
    _refuse(repo, tmp_path, "not both", ref="HEAD", tag="v1.2.3",
            cache_dir=_cache(tmp_path))


def _cli(repo, tmp_path, *args):
    env = dict(os.environ, AL_SIDECAR_ROOT=str(tmp_path / "sidecar"))
    return subprocess.run(
        [sys.executable, str(RELEASE), "build", "--root", str(repo), *args],
        cwd=str(ROOT), env=env, capture_output=True, text=True, check=False)


def test_cli_builds_twice_with_one_sha_and_refuses_cleanly(tmp_path):
    repo = _scratch(tmp_path)
    one = _cli(repo, tmp_path, "--ref", "HEAD", "--out", str(tmp_path / "c1"))
    two = _cli(repo, tmp_path, "--ref", "HEAD", "--out", str(tmp_path / "c2"))
    assert one.returncode == 0 and two.returncode == 0, one.stderr + two.stderr
    sha = [ln for ln in one.stdout.splitlines() if "sha256" in ln]
    assert sha and sha == [ln for ln in two.stdout.splitlines() if "sha256" in ln]
    digest = hashlib.sha256(
        (tmp_path / "c1" / "AshLight-1.2.3-app.zip").read_bytes()).hexdigest()
    assert digest in sha[0]
    bad = _cli(repo, tmp_path, "--tag", "v9.9.9", "--out", str(tmp_path / "c3"))
    assert bad.returncode == 1 and "refused" in bad.stderr
    assert not (tmp_path / "c3").exists()
    both = _cli(repo, tmp_path, "--ref", "HEAD", "--tag", "v1.2.3")
    assert both.returncode == 2
    assert release.COMMANDS["build"] == "build"
    assert release.load("build") is not None


def test_default_out_is_the_sidecar_build_release_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(tmp_path / "sc"))
    assert rb.default_out("1.2.3") == (tmp_path / "sc").resolve() / "Build" / \
        "release" / "1.2.3"
