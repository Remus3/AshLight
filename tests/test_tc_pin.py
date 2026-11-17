"""TC-PIN: pin validation, hash-mismatch refusal, re-run no-op, opt-in gate,
archive path guard. No network: every fetch is a fake."""

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tc_pin  # noqa: E402

from server.al import paths  # noqa: E402

POB_COMMIT = "a" * 40
LJ_COMMIT = "b" * 40


def _zip(top, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(top + "/", "")
        for name, data in files.items():
            zf.writestr(f"{top}/{name}", data)
    return buf.getvalue()


def _spec(repo, commit, blob, **extra):
    spec = {
        "repo": repo, "commit": commit,
        "archive_url": f"https://github.com/{repo}/archive/{commit}.zip",
        "archive_sha256": hashlib.sha256(blob).hexdigest(),
        "archive_size": len(blob),
        "top_dir": f"{repo.split('/')[1]}-{commit}",
    }
    spec.update(extra)
    return spec


@pytest.fixture
def world(tmp_path):
    pob_top = f"PathOfBuilding-PoE2-{POB_COMMIT}"
    lj_top = f"LuaJIT-{LJ_COMMIT}"
    blobs = {
        "pob2": _zip(pob_top, {"LICENSE.md": "MIT", "src/HeadlessWrapper.lua": "-- x"}),
        "luajit": _zip(lj_top, {"COPYRIGHT": "MIT", "src/msvcbuild.bat": "rem x"}),
    }
    doc = {
        "schema": 1,
        "pob2": _spec("PathOfBuildingCommunity/PathOfBuilding-PoE2", POB_COMMIT,
                      blobs["pob2"], tag="v0.23.1"),
        "luajit": _spec("LuaJIT/LuaJIT", LJ_COMMIT, blobs["luajit"], version="2.1.1"),
    }
    calls = []

    def fetch(url, max_bytes):
        calls.append(url)
        blob = blobs["pob2"] if "PathOfBuilding" in url else blobs["luajit"]
        for i in range(0, len(blob), 7):
            yield blob[i:i + 7]

    env = {paths.SIDECAR_ENV: str(tmp_path / "AL")}
    return {"doc": doc, "blobs": blobs, "fetch": fetch, "calls": calls, "env": env,
            "root": tmp_path / "AL"}


def _which_cl(name):
    return "cl.exe" if name == "cl" else None


def _no_compiler(name):
    return None


def _fake_build(lay):
    def run(cmd, cwd=None, env=None, capture_output=None, timeout=None):
        assert Path(cwd) == lay["luajit_source"] / "src"
        lay["luajit_exe"].write_bytes(b"fake")

        class R:
            returncode = 0
        return R()
    return run


def test_real_pin_file_is_complete_and_well_formed():
    doc = tc_pin.load_pins()
    assert doc["pob2"]["tag"] == "v0.23.1"
    assert doc["luajit"]["version"].startswith("2.1.")
    assert tc_pin.validate_pins(doc) == []
    text = paths.tc_pins_file().read_text(encoding="ascii")
    assert ":\\" not in text and "Users" not in text  # no absolute paths
    assert tc_pin.main(["check"]) == 0


@pytest.mark.parametrize("mutate", [
    lambda d: d["pob2"].pop("archive_sha256"),
    lambda d: d["luajit"].__setitem__("archive_sha256", "0" * 63),
    lambda d: d["pob2"].__setitem__("commit", "HEAD"),
    lambda d: d["pob2"].__setitem__("archive_url", "https://example.com/x.zip"),
    lambda d: d["luajit"].__setitem__("archive_size", 0),
    lambda d: d["luajit"].pop("version"),
    lambda d: d["pob2"].pop("tag"),
    lambda d: d.pop("luajit"),
    lambda d: d["pob2"].__setitem__("top_dir", "../escape"),
])
def test_missing_or_malformed_pin_refuses(world, tmp_path, monkeypatch, mutate):
    doc = json.loads(json.dumps(world["doc"]))
    mutate(doc)
    assert tc_pin.validate_pins(doc)
    bad = tmp_path / "pins.json"
    bad.write_text(json.dumps(doc), encoding="ascii")
    with pytest.raises(tc_pin.PinError):
        tc_pin.load_pins(bad)
    monkeypatch.setattr(paths, "tc_pins_file", lambda: bad)
    assert tc_pin.main(["setup", "--opt-in"]) == tc_pin.RC_REFUSED


def test_download_hash_mismatch_refuses_and_quarantines(world):
    doc = world["doc"]
    doc["pob2"]["archive_sha256"] = "f" * 64
    with pytest.raises(tc_pin.HashMismatch):
        tc_pin.run_setup(doc, environ=world["env"], fetch=world["fetch"], which=_no_compiler)
    lay = tc_pin.layout(doc, world["env"])
    assert not lay["pob2_archive"].exists()
    assert lay["pob2_archive"].with_name(lay["pob2_archive"].name + ".part.rejected").exists()
    assert not lay["pob2_checkout"].exists()
    assert not lay["stamp"].exists()


def test_oversize_download_refuses(world):
    doc = world["doc"]
    doc["luajit"]["archive_size"] -= 1
    with pytest.raises(tc_pin.HashMismatch):
        tc_pin.run_setup(doc, environ=world["env"], fetch=world["fetch"], which=_no_compiler)
    assert not tc_pin.layout(doc, world["env"])["luajit_archive"].exists()


def test_tampered_cached_archive_refuses(world):
    doc, env = world["doc"], world["env"]
    lay = tc_pin.layout(doc, env)
    tc_pin.run_setup(doc, environ=env, fetch=world["fetch"], which=_which_cl,
                     run=_fake_build(lay))
    lay["stamp"].unlink()  # force a re-check of the cache
    blob = bytearray(lay["luajit_archive"].read_bytes())
    blob[-1] ^= 0xFF
    lay["luajit_archive"].write_bytes(bytes(blob))
    (lay["luajit_source"] / tc_pin.MARKER).unlink()  # tree no longer vouched for
    with pytest.raises(tc_pin.HashMismatch):
        tc_pin.run_setup(doc, environ=env, fetch=world["fetch"], which=_which_cl,
                         run=_fake_build(lay))
    assert lay["luajit_archive"].with_name(lay["luajit_archive"].name + ".rejected").exists()


def test_full_run_then_rerun_is_a_noop(world):
    doc, env = world["doc"], world["env"]
    lay = tc_pin.layout(doc, env)
    status = tc_pin.run_setup(doc, environ=env, fetch=world["fetch"], which=_which_cl,
                              run=_fake_build(lay))
    assert status == "ready"
    assert len(world["calls"]) == 2
    assert (lay["pob2_checkout"] / "src" / "HeadlessWrapper.lua").is_file()
    assert (lay["luajit_source"] / "COPYRIGHT").is_file()
    stamp = json.loads(lay["stamp"].read_text(encoding="ascii"))
    assert stamp["status"] == "ready" and stamp["pins_sha256"] == tc_pin.pins_digest(doc)

    def no_net(url, max_bytes):
        raise AssertionError("re-run must not fetch")

    def no_build(*a, **k):
        raise AssertionError("re-run must not build")

    before = sorted(p.relative_to(world["root"]) for p in world["root"].rglob("*"))
    assert tc_pin.run_setup(doc, environ=env, fetch=no_net, which=_which_cl,
                            run=no_build) == "noop"
    after = sorted(p.relative_to(world["root"]) for p in world["root"].rglob("*"))
    assert before == after


def test_pin_change_invalidates_the_noop(world):
    doc, env = world["doc"], world["env"]
    lay = tc_pin.layout(doc, env)
    tc_pin.run_setup(doc, environ=env, fetch=world["fetch"], which=_which_cl,
                     run=_fake_build(lay))
    assert tc_pin.is_noop(doc, lay)
    doc["pob2"]["tag"] = "v0.23.2"
    assert not tc_pin.is_noop(doc, lay)


def test_no_compiler_is_source_only_and_rerun_does_not_refetch(world):
    doc, env = world["doc"], world["env"]
    assert tc_pin.run_setup(doc, environ=env, fetch=world["fetch"],
                            which=_no_compiler) == "source-only"
    assert len(world["calls"]) == 2

    def no_net(url, max_bytes):
        raise AssertionError("archives are cached and verified; no fetch")

    assert tc_pin.run_setup(doc, environ=env, fetch=no_net, which=_no_compiler) == "source-only"


def test_build_plan_prefers_msvc_then_mingw():
    assert tc_pin.build_plan(_which_cl)[-2:] == ["msvcbuild.bat", "static"]
    both = {"mingw32-make": "m", "gcc": "g"}
    assert tc_pin.build_plan(both.get) == ["m", "BUILDMODE=static"]  # the resolved path (AUDIT-EXE-PATH)
    assert tc_pin.build_plan(_no_compiler) is None


@pytest.mark.parametrize("name", ["../evil.txt", "{top}/../../evil.txt", "/abs.txt",
                                  "{top}/" + "C" + ":" + "/x.txt", "other-top/x.txt"])
def test_unsafe_archive_member_refuses(world, name):
    doc, env = world["doc"], world["env"]
    top = doc["luajit"]["top_dir"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(top + "/ok.txt", "ok")
        zf.writestr(name.format(top=top), "bad")
    blob = buf.getvalue()
    doc["luajit"]["archive_sha256"] = hashlib.sha256(blob).hexdigest()
    doc["luajit"]["archive_size"] = len(blob)
    world["blobs"]["luajit"] = blob
    with pytest.raises(tc_pin.UnsafeArchive):
        tc_pin.run_setup(doc, environ=env, fetch=world["fetch"], which=_no_compiler)
    assert not (world["root"] / "evil.txt").exists()
    assert not tc_pin.layout(doc, env)["luajit_source"].exists()


def test_off_by_default_fetches_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "AL"))
    monkeypatch.setattr(paths, "load_local_config", lambda: {})

    def boom(*a, **k):
        raise AssertionError("off by default: no setup work")

    monkeypatch.setattr(tc_pin, "run_setup", boom)
    assert tc_pin.main(["setup"]) == 0
    assert not (tmp_path / "AL").exists()


def test_opt_in_needs_a_real_true():
    assert tc_pin.opted_in(True, {})
    assert tc_pin.opted_in(False, {"tc_calc": True})
    assert not tc_pin.opted_in(False, {})
    assert not tc_pin.opted_in(False, {"tc_calc": "true"})
    assert not tc_pin.opted_in(False, {"tc_calc": 1})


def test_main_maps_mismatch_to_refused(monkeypatch):
    monkeypatch.setattr(paths, "load_local_config", lambda: {"tc_calc": True})

    def mismatch(doc):
        raise tc_pin.HashMismatch("x")

    monkeypatch.setattr(tc_pin, "run_setup", mismatch)
    assert tc_pin.main(["setup"]) == tc_pin.RC_REFUSED


def test_http_stream_refuses_a_host_off_the_allowlist():
    with pytest.raises(tc_pin.webfetch.UrlNotAllowed):
        next(tc_pin.http_stream("https://example.com/x.zip", 10))
    with pytest.raises(tc_pin.webfetch.UrlNotAllowed):
        next(tc_pin.http_stream("http://github.com/x.zip", 10))


# --- decision 0027: the optional pinned portable toolchain ------------------

TC_TAG = "16.2.0posix-14.0.0-ucrt-r9"
TC_ASSET = "winlibs-x86_64-test.zip"


def _toolchain(world):
    blob = _zip("mingw64", {"bin/mingw32-make.exe": "m", "bin/gcc.exe": "g",
                            "COPYING": "GPL"})
    repo = "brechtsanders/winlibs_mingw"
    world["doc"]["toolchain"] = {
        "repo": repo, "tag": TC_TAG, "asset": TC_ASSET,
        "archive_url": f"https://github.com/{repo}/releases/download/{TC_TAG}/{TC_ASSET}",
        "archive_sha256": hashlib.sha256(blob).hexdigest(),
        "archive_size": len(blob), "top_dir": "mingw64",
    }
    return blob


def test_real_pin_file_toolchain_entry_is_well_formed():
    doc = tc_pin.load_pins()
    tc = doc["toolchain"]
    assert tc_pin._validate_toolchain(tc) == []
    assert tc["archive_url"].startswith("https://github.com/brechtsanders/winlibs_mingw/"
                                        "releases/download/")
    assert tc["asset"].endswith(".zip")  # stdlib zipfile only, never 7z / sfx


@pytest.mark.parametrize("mutate", [
    lambda t: t.__setitem__("archive_url", "https://example.com/x.zip"),
    lambda t: t.__setitem__("asset", "x.7z"),
    lambda t: t.__setitem__("asset", "../x.zip"),
    lambda t: t.__setitem__("top_dir", "../escape"),
    lambda t: t.pop("archive_sha256"),
    lambda t: t.__setitem__("archive_size", -1),
])
def test_malformed_toolchain_pin_refuses(world, mutate):
    _toolchain(world)
    mutate(world["doc"]["toolchain"])
    assert any(p.startswith("toolchain:") for p in tc_pin.validate_pins(world["doc"]))


def test_no_system_compiler_builds_with_the_pinned_toolchain(world, monkeypatch):
    blob = _toolchain(world)
    doc, env = world["doc"], world["env"]
    lay = tc_pin.layout(doc, env)
    tc_calls, seen = [], {}
    monkeypatch.setenv("MSYSTEM", "MINGW64")  # must not leak into the build env

    def tc_fetch(url, max_bytes):
        tc_calls.append(url)
        yield blob

    def run(cmd, cwd=None, env=None, capture_output=None, timeout=None):
        seen["cmd"], seen["env"] = cmd, env
        lay["luajit_exe"].write_bytes(b"fake")

        class R:
            returncode = 0
        return R()

    assert tc_pin.run_setup(doc, environ=env, fetch=world["fetch"], which=_no_compiler,
                            run=run, toolchain_fetch=tc_fetch) == "ready"
    assert tc_calls == [doc["toolchain"]["archive_url"]]
    assert Path(seen["cmd"][0]) == lay["toolchain_bin"] / "mingw32-make.exe"
    assert seen["cmd"][1:] == ["BUILDMODE=static"]
    assert seen["env"]["PATH"].split(";")[0] == str(lay["toolchain_bin"])
    assert "MSYSTEM" not in seen["env"] and "TERM" not in seen["env"]
    # everything inside the AL sidecar Cache
    assert lay["toolchain_root"].is_relative_to(world["root"] / "Cache")
    # a second toolchain use is a no-op (marker), no refetch
    assert tc_pin.ensure_toolchain(doc, lay, fetch=None) == lay["toolchain_bin"]


def test_p3_10_tampered_toolchain_tree_is_reextracted_before_the_build(world):
    """AREA-AUDIT P3-10: the marker alone no longer vouches for the tree; a
    file changed after extraction is caught by the re-hash and the tree is
    re-extracted from the hash-verified archive before any build uses it."""
    blob = _toolchain(world)
    doc = world["doc"]
    lay = tc_pin.layout(doc, world["env"])
    fetched = []

    def tc_fetch(url, max_bytes):
        fetched.append(url)
        yield blob
    tc_pin.ensure_toolchain(doc, lay, fetch=tc_fetch)
    gcc = lay["toolchain_bin"] / "gcc.exe"
    assert gcc.read_text() == "g"
    marker = tc_pin.read_marker(lay["toolchain_root"])
    assert marker["tree_sha256"] == tc_pin.tree_digest(lay["toolchain_root"])
    gcc.write_text("planted")  # same marker, different compiler
    (lay["toolchain_bin"] / "extra.dll").write_text("x")  # an added file counts too
    tc_pin.ensure_toolchain(doc, lay, fetch=tc_fetch)
    assert gcc.read_text() == "g"
    assert not (lay["toolchain_bin"] / "extra.dll").exists()
    assert fetched == [doc["toolchain"]["archive_url"]]  # cached archive re-verified
    # an old marker without a tree digest is not trusted either
    m = lay["toolchain_root"] / tc_pin.MARKER
    old = json.loads(m.read_text(encoding="ascii"))
    old.pop("tree_sha256")
    m.write_text(json.dumps(old), encoding="ascii")
    tc_pin.ensure_toolchain(doc, lay, fetch=tc_fetch)
    assert "tree_sha256" in tc_pin.read_marker(lay["toolchain_root"])


def test_system_compiler_wins_over_the_pinned_toolchain(world):
    _toolchain(world)
    doc, env = world["doc"], world["env"]
    lay = tc_pin.layout(doc, env)

    def no_tc(url, max_bytes):
        raise AssertionError("system compiler present; toolchain never fetched")

    assert tc_pin.run_setup(doc, environ=env, fetch=world["fetch"], which=_which_cl,
                            run=_fake_build(lay), toolchain_fetch=no_tc) == "ready"


def test_toolchain_hosts_only_widen_for_the_toolchain():
    with pytest.raises(tc_pin.webfetch.UrlNotAllowed):
        next(tc_pin.http_stream("https://release-assets.githubusercontent.com/x", 10))
    assert "release-assets.githubusercontent.com" in tc_pin.TOOLCHAIN_HOSTS


def test_setup_ps1_wires_the_opt_in_step():
    text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="ascii")
    assert "[switch]$TcCalc" in text
    assert "tools\\tc_pin.py" in text
