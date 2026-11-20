"""TC-DRIFT: tools/tc_drift.py spots a new PoB-PoE2 release, trials the
bridge tests against it unattended, and moves the pin only on a green trial
(decision 0004 item 3, decision 0018, decision 0025). No network: every
request goes through an injected fake transport."""

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tc_drift  # noqa: E402
import tc_pin  # noqa: E402

from server.al import paths, webfetch  # noqa: E402

REPO = "PathOfBuildingCommunity/PathOfBuilding-PoE2"
NEW_SHA = "a" * 40
NOW = 1_790_000_000.0


def _root(tmp_path):
    """A minimal tree: the real pin file copied in."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "tc_pins.json").write_bytes(
        (ROOT / "config" / "tc_pins.json").read_bytes())
    return tmp_path


CAND_FILES = {"LICENSE.md": "MIT", "src/HeadlessWrapper.lua": "-- new",
              "src/Data/TradeSiteStats.lua": "return {}"}


def _cand_zip(commit=NEW_SHA, files=None):
    """A candidate commit archive (data only; nothing in it is ever run)."""
    top = f"{REPO.split('/')[1]}-{commit}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in (files or CAND_FILES).items():
            zf.writestr(f"{top}/{name}", data)
    return buf.getvalue()


def _fake(latest="v0.24.0", status=200, headers=None, sha=NEW_SHA, calls=None):
    calls = [] if calls is None else calls

    def fetch(method, url, hdrs, body=None):
        calls.append((method, url, dict(hdrs)))
        if status != 200:
            return status, dict(headers or {}), b"{}"
        if url.endswith("/releases/latest"):
            doc = {"tag_name": latest, "published_at": "2026-12-10T12:00:00Z",
                   "draft": False, "prerelease": False}
            return 200, {}, json.dumps(doc).encode("ascii")
        if "/commits/" in url:
            return 200, {}, sha.encode("ascii")
        return 404, {}, b""
    fetch.calls = calls
    return fetch


# --- tags -------------------------------------------------------------------

def test_parse_and_compare_tags():
    assert tc_drift.parse_tag("v0.23.1") == (0, 23, 1)
    assert tc_drift.parse_tag("v2.49.0-rc1") is None
    assert tc_drift.parse_tag(None) is None
    assert tc_drift.compare("v0.23.1", "v0.23.1") == "current"
    assert tc_drift.compare("v0.23.1", "v0.24.0") == "new"
    assert tc_drift.compare("v0.23.1", "v0.23.10") == "new"  # numeric, not text
    assert tc_drift.compare("v0.23.1", "v0.22.0") == "behind"
    assert tc_drift.compare("v0.23.1", "nightly") == "unknown"


# --- GitHub reads -------------------------------------------------------------

def test_latest_release_sends_truthful_ua_no_cookie_and_only_api_host():
    f = _fake()
    rel = tc_drift.latest_release(REPO, fetch=f)
    assert rel["tag"] == "v0.24.0" and rel["published"] == "2026-12-10T12:00:00Z"
    method, url, hdrs = f.calls[0]
    assert method == "GET"
    assert url == f"https://api.github.com/repos/{REPO}/releases/latest"
    ua = webfetch.header(hdrs, "User-Agent")
    assert ua.startswith("AshLight/") and "drift" in ua
    assert webfetch.header(hdrs, "Cookie") is None
    assert webfetch.header(hdrs, "Authorization") is None


def test_rate_limit_headers_are_obeyed():
    f = _fake(status=403, headers={"X-RateLimit-Remaining": "0",
                                   "X-RateLimit-Reset": str(int(NOW) + 900)})
    with pytest.raises(tc_drift.RateLimited) as e:
        tc_drift.latest_release(REPO, fetch=f, now=NOW)
    assert e.value.until == NOW + 900
    f = _fake(status=429, headers={"Retry-After": "120"})
    with pytest.raises(tc_drift.RateLimited) as e:
        tc_drift.latest_release(REPO, fetch=f, now=NOW)
    assert e.value.until == NOW + 120


def test_resolve_commit_requires_a_full_sha():
    assert tc_drift.resolve_commit(REPO, "v0.24.0", fetch=_fake()) == NEW_SHA
    with pytest.raises(webfetch.FetchError):
        tc_drift.resolve_commit(REPO, "v0.24.0", fetch=_fake(sha="not-a-sha"))
    with pytest.raises(ValueError):
        tc_drift.resolve_commit(REPO, "v0.24.0/../x", fetch=_fake())


# --- candidate pins -----------------------------------------------------------

def test_candidate_pins_validate_and_keep_luajit(tmp_path):
    doc = tc_pin.load_pins()
    archive = tmp_path / "cand.zip"
    archive.write_bytes(_cand_zip())
    cand = tc_drift.candidate(doc, "v0.24.0", NEW_SHA, "b" * 64, 400_000_000, "2026-12-11",
                              archive=archive)
    assert tc_pin.validate_pins(cand) == []
    # TC-CALC-VERIFY-PIN: the candidate carries its own archive's digests
    want = tc_pin.archive_digests(archive, f"PathOfBuilding-PoE2-{NEW_SHA}")
    assert cand["pob2"]["content_sha256"] == want["content_sha256"]
    assert cand["pob2"]["lua_sha256"] == want["lua_sha256"]
    assert cand["pob2"]["content_sha256"] != doc["pob2"]["content_sha256"]
    # without an archive the old digests are dropped, never carried over
    bare = tc_drift.candidate(doc, "v0.24.0", NEW_SHA, "b" * 64, 400, "2026-12-11")
    assert "content_sha256" not in bare["pob2"] and "lua_sha256" not in bare["pob2"]
    assert any("content_sha256" in p for p in tc_pin.validate_pins(bare))
    pob = cand["pob2"]
    assert pob["tag"] == "v0.24.0" and pob["commit"] == NEW_SHA
    assert pob["archive_url"].endswith(f"/archive/{NEW_SHA}.zip")
    assert pob["top_dir"] == f"PathOfBuilding-PoE2-{NEW_SHA}"
    assert pob["verified"] == "2026-12-11"
    assert cand["luajit"] == doc["luajit"]
    assert doc["pob2"]["tag"] == "v0.23.1"  # the input is not mutated


def test_pins_file_env_override(tmp_path):
    alt = tmp_path / "cand.json"
    assert paths.tc_pins_file(environ={}) == ROOT / "config" / "tc_pins.json"
    assert paths.tc_pins_file(environ={tc_drift.PINS_ENV: str(alt)}) == alt


def test_p3_8_pins_env_ignored_outside_a_test_run(tmp_path):
    """AREA-AUDIT P3-8: the core and setup never import pytest, so the env
    var cannot move their trust root; only the trial's pytest child sees it."""
    alt = tmp_path / "cand.json"
    env = {tc_drift.PINS_ENV: str(alt)}
    assert paths.tc_pins_file(environ=env, modules={}) == ROOT / "config" / "tc_pins.json"
    assert paths.tc_pins_file(environ=env, modules={"pytest": object()}) == alt
    import subprocess
    code = ("import sys; from server.al import paths; "
            "print(paths.tc_pins_file(), 'pytest' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True,
                         text=True, env=dict(__import__("os").environ, **env), timeout=60)
    assert out.stdout.split() == [str(ROOT / "config" / "tc_pins.json"), "False"], out


# --- check and the loop hook --------------------------------------------------

def test_check_current_writes_state_and_throttles(tmp_path):
    root = _root(tmp_path)
    f = _fake(latest="v0.23.1")
    st = tc_drift.check(root, NOW, fetch=f)
    assert st["status"] == "current" and st["pinned"] == "v0.23.1"
    assert st["next_check"] == NOW + tc_drift.CHECK_EVERY_S
    assert json.loads(tc_drift.state_file(root).read_text(encoding="ascii"))["status"] == "current"
    # the loop hook does nothing (no request) until the next check is due
    calls_before = len(f.calls)
    assert tc_drift.loop_check(root, NOW + 60, fetch=f) is None
    assert len(f.calls) == calls_before
    line = tc_drift.loop_check(root, NOW + tc_drift.CHECK_EVERY_S, fetch=f)
    assert "current" in line and len(f.calls) == calls_before + 1


def test_loop_check_launches_one_trial_per_new_tag(tmp_path):
    root = _root(tmp_path)
    launched = []
    line = tc_drift.loop_check(root, NOW, fetch=_fake(),
                               launch=lambda r, tag, live=False: launched.append(tag) or 777)
    assert launched == ["v0.24.0"]
    assert "v0.24.0" in line and "trial launched" in line
    st = tc_drift.load_state(root)
    assert st["trial"]["tag"] == "v0.24.0" and st["trial"]["state"] == "launched"
    # a still-running trial is not relaunched before it goes stale
    tc_drift.save_state(root, dict(tc_drift.load_state(root), next_check=0))
    tc_drift.loop_check(root, NOW + 60, fetch=_fake(),
                        launch=lambda r, tag, live=False: launched.append(tag))
    assert launched == ["v0.24.0"]
    # a finished trial for the same tag is never re-run
    st = tc_drift.load_state(root)
    st["trial"] = {"tag": "v0.24.0", "state": "done", "verdict": "red"}
    tc_drift.save_state(root, st)
    line = tc_drift.loop_check(root, NOW + 2 * tc_drift.CHECK_EVERY_S, fetch=_fake(),
                               launch=lambda r, tag, live=False: launched.append(tag))
    assert launched == ["v0.24.0"] and "trial red, hold" in line


def test_loop_check_relaunches_a_dead_trial_a_bounded_number_of_times(tmp_path):
    root = _root(tmp_path)
    launched = []
    t = NOW
    for _ in range(tc_drift.TRIAL_MAX_LAUNCHES + 2):
        tc_drift.loop_check(root, t, fetch=_fake(),
                            launch=lambda r, tag, live=False: launched.append(tag) or 1)
        t += tc_drift.CHECK_EVERY_S  # past TRIAL_STALE_S each time
    assert len(launched) == tc_drift.TRIAL_MAX_LAUNCHES
    assert tc_drift.load_state(root)["trial"]["launches"] == tc_drift.TRIAL_MAX_LAUNCHES


def test_loop_check_without_pins_is_silent(tmp_path):
    f = _fake()
    assert tc_drift.loop_check(tmp_path, NOW, fetch=f) is None
    assert f.calls == []


def test_loop_check_backs_off_on_rate_limit(tmp_path):
    root = _root(tmp_path)
    f = _fake(status=429, headers={"Retry-After": "7200"})
    line = tc_drift.loop_check(root, NOW, fetch=f)
    assert "rate limited" in line
    st = tc_drift.load_state(root)
    assert st["status"] == "rate-limited" and st["next_check"] == NOW + 7200


def test_loop_check_network_failure_retries_later(tmp_path):
    root = _root(tmp_path)

    def broken(method, url, hdrs, body=None):
        raise webfetch.FetchError("network: down")
    line = tc_drift.loop_check(root, NOW, fetch=broken)
    assert "check failed" in line
    st = tc_drift.load_state(root)
    assert st["status"] == "error" and st["next_check"] == NOW + tc_drift.RETRY_S


# --- trial --------------------------------------------------------------------

JUNIT_GREEN = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite tests="3"
 failures="0" errors="0" skipped="0"><testcase classname="tests.test_tc_bridge"
 name="test_lazy_start_then_round_trip"/><testcase classname="tests.test_tc_bridge"
 name="test_live_minimal_build_returns_numeric_outputs"/><testcase
 classname="tests.test_tc_bridge" name="test_live_reload_does_not_leak_state"/>
</testsuite></testsuites>"""

JUNIT_SKIPPED = """<testsuites><testsuite><testcase name="test_lazy_start_then_round_trip"/>
<testcase name="test_live_minimal_build_returns_numeric_outputs"><skipped
 message="absent"/></testcase></testsuite></testsuites>"""

JUNIT_RED = """<testsuites><testsuite><testcase name="test_live_minimal_build_returns_numeric_outputs">
<failure message="boom"/></testcase><testcase name="test_x"><error message="e"/></testcase>
</testsuite></testsuites>"""


def test_parse_junit_counts_live_cases():
    g = tc_drift.parse_junit(JUNIT_GREEN)
    assert g == {"tests": 3, "failures": 0, "errors": 0, "skipped": 0, "live_ran": 2}
    s = tc_drift.parse_junit(JUNIT_SKIPPED)
    assert s["skipped"] == 1 and s["live_ran"] == 0
    r = tc_drift.parse_junit(JUNIT_RED)
    assert r["failures"] == 1 and r["errors"] == 1 and r["live_ran"] == 1


FAKE_LUA = """-- fake data file for tests
return {
\t{
\t\t["id"] = "explicit.stat_1001",
\t\t["text"] = "+# to maximum Life",
\t\t["type"] = "explicit",
\t},
\t{
\t\t["id"] = "explicit.stat_1002",
\t\t["text"] = "#% increased Armour",
\t\t["type"] = "explicit",
\t},
\t{
\t\t["id"] = "implicit.stat_1003",
\t\t["text"] = "#% increased Evasion",
\t\t["type"] = "implicit",
\t},
}
"""
POB_REL = "src/Data/TradeSiteStats.lua"


def _fake_checkout(doc, environ, text=FAKE_LUA, marker_sha=None):
    """What tc_pin.run_setup leaves: the extracted candidate checkout with its
    marker (data only; nothing here is ever run)."""
    co = tc_pin.layout(doc, environ)["pob2_checkout"]
    co.mkdir(parents=True, exist_ok=True)
    (co / tc_pin.MARKER).write_text(json.dumps(
        {"archive_sha256": marker_sha or doc["pob2"]["archive_sha256"]}), encoding="ascii")
    if text is not None:
        f = co.joinpath(*POB_REL.split("/"))
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(text.encode("ascii"))
    return co


def _trial(root, junit, sizes=((400, "c" * 64), (400, "c" * 64)), tmp=None, live=True,
           checkout=_fake_checkout, recycle=None):
    seen = {"setup": [], "tests": [], "live": [], "cand": [], "recycled": []}
    it = iter(sizes)

    def download(url, dest):
        size, sha = next(it)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_cand_zip())  # the digests are read from these bytes
        return sha, size

    def setup(doc, environ):
        seen["setup"].append(doc["pob2"]["tag"])
        if checkout is not None:
            checkout(doc, environ)

    def run_tests(cand_path, junit_path, environ, live=False):
        seen["tests"].append(cand_path)
        seen["live"].append(live)
        cand = json.loads(Path(cand_path).read_text(encoding="ascii"))
        seen["cand"].append(cand)
        assert cand["pob2"]["tag"] == "v0.24.0"
        return tc_drift.parse_junit(junit)

    def fake_recycle(path):
        seen["recycled"].append(Path(path).name)
        return False  # never a real Recycle Bin call from a test
    env = {"AL_SIDECAR_ROOT": str(tmp or root / "sidecar")}
    res = tc_drift.trial(root, "v0.24.0", environ=env, fetch=_fake(), download=download,
                         setup=setup, run_tests=run_tests, today="2026-12-11", live=live,
                         recycle=recycle or fake_recycle)
    return res, seen


def test_trial_green_records_ready_candidate(tmp_path):
    root = _root(tmp_path)
    res, seen = _trial(root, JUNIT_GREEN)
    assert res["verdict"] == "live-green", res
    assert seen["setup"] == ["v0.24.0"] and len(seen["tests"]) == 1
    st = tc_drift.load_state(root)
    assert st["trial"]["verdict"] == "live-green" and st["trial"]["tag"] == "v0.24.0"
    cand = json.loads(Path(st["trial"]["candidate"]).read_text(encoding="ascii"))
    assert cand["pob2"]["archive_sha256"] == "c" * 64 and cand["pob2"]["archive_size"] == 400
    digests = tc_pin.archive_digests(io.BytesIO(_cand_zip()), cand["pob2"]["top_dir"])
    assert cand["pob2"]["content_sha256"] == digests["content_sha256"]
    assert cand["pob2"]["lua_sha256"] == digests["lua_sha256"]


def test_trial_with_an_unreadable_archive_is_an_error(tmp_path):
    root = _root(tmp_path)
    env = {"AL_SIDECAR_ROOT": str(tmp_path / "sidecar")}

    def download(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"not a zip")
        return "c" * 64, 9
    res = tc_drift.trial(root, "v0.24.0", environ=env, fetch=_fake(), download=download,
                         setup=lambda d, e: pytest.fail("no setup without digests"),
                         run_tests=lambda *a, **k: pytest.fail("no tests"),
                         today="2026-12-11", recycle=lambda p: False)
    assert res["verdict"] == "error" and "BadZipFile" in res["detail"]


def test_trial_holds_when_live_tests_skipped(tmp_path):
    root = _root(tmp_path)
    res, _ = _trial(root, JUNIT_SKIPPED)
    assert res["verdict"] == "untested" and "skipped" in res["detail"]


def test_trial_red_holds(tmp_path):
    root = _root(tmp_path)
    res, _ = _trial(root, JUNIT_RED)
    assert res["verdict"] == "red"


def test_trial_refuses_unstable_archive(tmp_path):
    root = _root(tmp_path)
    res, seen = _trial(root, JUNIT_GREEN, sizes=((400, "c" * 64), (400, "d" * 64)))
    assert res["verdict"] == "error" and "differ" in res["detail"]
    assert seen["setup"] == [] and seen["tests"] == []


# --- AUTO-12 (F-064): pob2_files re-hash and candidate prune ------------------

def test_trial_rehashes_pob2_files_and_records_old_new_and_rows(tmp_path):
    import hashlib
    from server.al import tradestats
    root = _root(tmp_path)
    pins_before = (root / "config" / "tc_pins.json").read_bytes()
    pin = json.loads(pins_before)["pob2_files"][POB_REL]
    res, seen = _trial(root, JUNIT_GREEN)
    assert res["verdict"] == "live-green", res
    new_sha = hashlib.sha256(FAKE_LUA.encode("ascii")).hexdigest()
    row = res["pob2_files"][POB_REL]
    assert row == {"old_sha256": pin["sha256"], "old_size": pin["size"],
                   "new_sha256": new_sha, "new_size": len(FAKE_LUA),
                   "rows": 2, "changed": True}
    assert row["rows"] == len(tradestats.parse_pob_trade_stats(FAKE_LUA))
    # the tests ran against a candidate whose pob2_files carry the new hash
    entry = seen["cand"][0]["pob2_files"][POB_REL]
    assert entry == {"sha256": new_sha, "size": len(FAKE_LUA), "commit": NEW_SHA}
    assert seen["cand"][0]["pob2_files"]["_doc"] == json.loads(pins_before)["pob2_files"]["_doc"]
    st = tc_drift.load_state(root)
    assert st["trial"]["pob2_files"][POB_REL]["new_sha256"] == new_sha
    cand = json.loads(Path(st["trial"]["candidate"]).read_text(encoding="ascii"))
    assert cand["pob2_files"][POB_REL]["sha256"] == new_sha
    assert tc_pin.validate_pins(cand) == []
    # the pin is untouched until apply; apply carries the new hash and the
    # review lines name old, new and the parsed row count
    assert (root / "config" / "tc_pins.json").read_bytes() == pins_before
    lines = tc_drift.pob2_files_review(st["trial"])
    assert len(lines) == 1 and pin["sha256"] in lines[0] and new_sha in lines[0]
    assert "2 rows parsed" in lines[0]
    assert tc_drift.apply(root) == "v0.24.0"
    moved = json.loads((root / "config" / "tc_pins.json").read_text(encoding="ascii"))
    assert moved["pob2_files"][POB_REL]["sha256"] == new_sha

    # an unchanged file reads "unchanged"; a missing one keeps the old entry
    # so the static guard reports it, and the review says MISSING
    same = {"pob2_files": {POB_REL: dict(row, old_sha256=new_sha, changed=False)}}
    assert "unchanged" in tc_drift.pob2_files_review(same)[0]
    (tmp_path / "b").mkdir()
    root2 = _root(tmp_path / "b")
    res, seen = _trial(root2, JUNIT_GREEN,
                       checkout=lambda d, e: _fake_checkout(d, e, text=None))
    row = res["pob2_files"][POB_REL]
    assert row["new_sha256"] is None and row["rows"] is None and row["changed"] is True
    assert seen["cand"][0]["pob2_files"][POB_REL]["sha256"] == pin["sha256"]
    assert "MISSING" in tc_drift.pob2_files_review(res)[0]

    # a checkout not extracted from the candidate archive is an error, not a pass
    (tmp_path / "c").mkdir()
    root3 = _root(tmp_path / "c")
    res, seen = _trial(root3, JUNIT_GREEN,
                       checkout=lambda d, e: _fake_checkout(d, e, marker_sha="e" * 64))
    assert res["verdict"] == "error" and "not re-hashed" in res["detail"]
    assert seen["tests"] == []


def test_rehash_refuses_a_path_outside_the_checkout(tmp_path):
    env = {"AL_SIDECAR_ROOT": str(tmp_path / "sidecar")}
    cand = tc_drift.candidate(tc_pin.load_pins(), "v0.24.0", NEW_SHA, "c" * 64, 400,
                              "2026-12-11")
    _fake_checkout(cand, env)
    for bad in ("../outside.lua", "/abs.lua", "src/a:b.lua", "src\\x.lua", ""):
        cand["pob2_files"] = {bad: {"sha256": "0" * 64, "size": 1}}
        with pytest.raises(tc_drift.DriftError):
            tc_drift.rehash_pob2_files(cand, env)


def test_candidates_other_than_pin_and_newest_are_pruned(tmp_path):
    root = _root(tmp_path)
    side = tmp_path / "sidecar"
    env = {"AL_SIDECAR_ROOT": str(side)}
    rt = paths.all_runtime_paths(env)
    pin = tc_pin.load_pins()["pob2"]
    name = pin["repo"].split("/")[1]
    old = "b" * 40
    cache, work = rt["pob2_cache"], rt["build"] / "tc-drift"
    work.mkdir(parents=True)
    keep, gone = [], []
    for commit, bucket in ((pin["commit"], keep), (old, gone), (NEW_SHA, keep)):
        (cache / f"{name}-{commit}" / "src").mkdir(parents=True)
        (cache / f"{name}-{commit}.zip").write_bytes(b"zip")
        bucket += [f"{name}-{commit}", f"{name}-{commit}.zip"]
    for tag, bucket in ((pin["tag"], keep), ("v0.23.5", gone)):
        for suffix in ("pins.json", "junit.xml"):
            (work / f"{tag}-{suffix}").write_text("{}", encoding="ascii")
            bucket.append(f"{tag}-{suffix}")
    # look-alikes that are not candidates stay untouched
    others = [f"{name}-{old}.zip.rejected", "notes.txt", f"{name}-{old}.zip.part"]
    for o in others:
        (cache / o).write_bytes(b"x")
    (work / "v0.23.5-other.json").write_text("{}", encoding="ascii")
    others.append("v0.23.5-other.json")

    recycled = []

    def recycle(path):
        recycled.append(Path(path).name)
        p = Path(path)
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        else:
            p.unlink()
        return True
    res, _ = _trial(root, JUNIT_GREEN, tmp=side, recycle=recycle)
    assert res["verdict"] == "live-green", res
    assert sorted(recycled) == sorted(gone)
    assert sorted(res["prune"]["pruned"]) == sorted(gone) and res["prune"]["left"] == []
    present = {p.name for p in cache.iterdir()} | {p.name for p in work.iterdir()}
    assert set(keep) <= present and set(others) <= present
    assert not (set(gone) & present)
    assert "v0.24.0-pins.json" in present  # the newest candidate stays
    assert tc_drift.load_state(root)["trial"]["prune"]["pruned"] == res["prune"]["pruned"]

    # a recycle that fails leaves the item in place (no direct unlink)
    (cache / f"{name}-{old}.zip").write_bytes(b"zip")
    res, seen = _trial(root, JUNIT_GREEN, tmp=side)
    assert seen["recycled"] == [f"{name}-{old}.zip"]
    assert res["prune"] == {"pruned": [], "left": [f"{name}-{old}.zip"]}
    assert (cache / f"{name}-{old}.zip").is_file()


def test_prune_skipped_before_a_commit_is_known_and_recycle_off_windows(tmp_path, monkeypatch):
    root = _root(tmp_path)
    env = {"AL_SIDECAR_ROOT": str(tmp_path / "sidecar")}
    called = []
    res = tc_drift.trial(root, "v0.24.0", environ=env, fetch=_fake(sha="not-a-sha"),
                         download=lambda u, d: ("c" * 64, 1), setup=lambda d, e: None,
                         run_tests=lambda *a, **k: {}, recycle=lambda p: called.append(p))
    assert res["verdict"] == "error" and "prune" not in res and called == []
    monkeypatch.setattr(tc_drift.os, "name", "posix")
    monkeypatch.setattr(tc_drift.subprocess, "run",
                        lambda *a, **k: pytest.fail("no recycle subprocess off Windows"))
    f = tmp_path / "keep.txt"
    f.write_text("x", encoding="ascii")
    assert tc_drift.recycle_path(f) is False and f.is_file()


# --- apply --------------------------------------------------------------------

def test_apply_moves_pin_only_after_green_trial(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(tc_drift.DriftError):
        tc_drift.apply(root)  # no trial yet
    _trial(root, JUNIT_RED)
    with pytest.raises(tc_drift.DriftError):
        tc_drift.apply(root)
    _trial(root, JUNIT_GREEN)
    tag = tc_drift.apply(root)
    assert tag == "v0.24.0"
    raw = (root / "config" / "tc_pins.json").read_bytes()
    assert raw.isascii() and b"\r\n" not in raw
    moved = json.loads(raw)
    assert tc_pin.validate_pins(moved) == []
    assert moved["pob2"]["tag"] == "v0.24.0" and moved["_doc"].startswith("TC-PIN")
    assert tc_drift.load_state(root)["trial"]["state"] == "applied"


# --- P3-9: unattended trial is static only ---------------------------------

JUNIT_STATIC = """<testsuites><testsuite><testcase name="test_pinned_pob_api_shape"/>
<testcase name="test_pinned_checkout_is_the_pin"/></testsuite></testsuites>"""


def test_p3_9_default_trial_is_static_and_never_applies(tmp_path):
    root = _root(tmp_path)
    res, seen = _trial(root, JUNIT_STATIC, live=False)
    assert seen["live"] == [False]
    assert res["verdict"] == "static-green" and res["live"] is False, res
    with pytest.raises(tc_drift.DriftError):
        tc_drift.apply(root)  # static-green never moves the pin
    assert "--live" in tc_drift.summary(dict(tc_drift.load_state(root), status="new",
                                             latest="v0.24.0"))
    # a static run that somehow executed live tests is an error, not a pass
    res, _ = _trial(root, JUNIT_GREEN, live=False)
    assert res["verdict"] == "error"


def test_p3_9_static_argv_selects_no_luajit_tests(tmp_path):
    argv = tc_drift.trial_argv(tmp_path / "j.xml", live=False)
    assert "-I" in argv
    assert "tests/test_tc_bridge.py" not in argv and "tests/test_tc_delta.py" not in argv
    assert argv[argv.index("-k") + 1] == "not test_live"
    live = tc_drift.trial_argv(tmp_path / "j.xml", live=True)
    assert "tests/test_tc_bridge.py" in live and "-k" not in live


def test_p3_9_loop_launches_live_only_with_local_opt_in(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setenv("TC_DRIFT_LIVE", "1")
    monkeypatch.setenv(tc_drift.LIVE_OPT_IN_KEY, "true")  # env never enables it
    got = []
    tc_drift.loop_check(root, NOW, fetch=_fake(),
                        launch=lambda r, tag, live=False: got.append(live) or 1)
    assert got == [False]
    (root / "config" / "local.json").write_text('{"tc_drift_live_unattended": "true"}',
                                                encoding="ascii")
    assert tc_drift.live_opted_in(root) is False  # a real boolean only
    (root / "config" / "local.json").write_text('{"tc_drift_live_unattended": true}',
                                                encoding="ascii")
    tc_drift.save_state(root, {})
    tc_drift.loop_check(root, NOW, fetch=_fake(),
                        launch=lambda r, tag, live=False: got.append(live) or 1)
    assert got == [False, True]


def test_hold_note_is_dated():
    st = {"checked": "2026-12-11T09:00:00", "pinned": "v0.23.1", "latest": "v0.24.0",
          "trial": {"tag": "v0.24.0", "verdict": "red", "detail": "1 failed"}}
    note = tc_drift.hold_note(st)
    assert note.startswith("2026-12-11 HOLD") and "v0.24.0" in note and "1 failed" in note
    cur = {"checked": "2026-11-17T09:00:00", "pinned": "v0.23.1", "latest": "v0.23.1",
           "status": "current"}
    assert tc_drift.hold_note(cur).startswith("2026-11-17 HOLD")


def test_decision_0004_carries_a_dated_pin_log_line_for_the_current_pin():
    """ACCEPT: pin moved or a dated hold note in decision 0004."""
    import re
    text = (ROOT / "docs" / "decisions" / "0004-scope-theorycraft.md").read_text(
        encoding="ascii")
    assert "## Pin log" in text
    lines = re.findall(r"^- (\d{4}-\d{2}-\d{2}) (HOLD|MOVED)\b.*$", text, re.M)
    assert lines
    tag = tc_pin.load_pins()["pob2"]["tag"]
    log = text.split("## Pin log", 1)[1].split("\n## ", 1)[0]
    assert tag in log


def test_floor_no_trade_or_cookie_paths_in_module():
    import re
    text = (ROOT / "tools" / "tc_drift.py").read_text(encoding="ascii")
    assert "POESESSID" not in text
    # AUTO-12: the one "trade" word allowed is the local data parser module
    # that counts pob2_files rows (decision 0037 amendment); no trade host,
    # path or endpoint
    words = set(re.findall(r"\w*trade\w*", text, re.I))
    assert words <= {"tradestats", "parse_pob_trade_stats"}, words
    assert "pathofexile.com" not in text.lower() and "/trade" not in text.lower()
    assert tc_drift.API_HOSTS == ("api.github.com",)


# --- AUDIT-P6-LOW P6-4: status before the first check ------------------------

def test_status_text_before_first_check_says_so(tmp_path):
    root = _root(tmp_path)
    pinned = tc_pin.load_pins(root / "config" / "tc_pins.json")["pob2"]["tag"]
    assert tc_drift.status_text(root) == (
        f"tc drift: no check run yet; pinned PoB-PoE2 {pinned} "
        "(run `python tools/tc_drift.py check`)")


def test_status_text_after_check_prints_state(tmp_path):
    root = _root(tmp_path)
    tc_drift.check(root, NOW, fetch=_fake(latest="v0.23.1"))
    assert json.loads(tc_drift.status_text(root))["status"] == "current"
