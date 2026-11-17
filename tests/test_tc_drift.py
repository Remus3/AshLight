"""TC-DRIFT: tools/tc_drift.py spots a new PoB-PoE2 release, trials the
bridge tests against it unattended, and moves the pin only on a green trial
(decision 0004 item 3, decision 0018, decision 0025). No network: every
request goes through an injected fake transport."""

import json
import sys
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

def test_candidate_pins_validate_and_keep_luajit():
    doc = tc_pin.load_pins()
    cand = tc_drift.candidate(doc, "v0.24.0", NEW_SHA, "b" * 64, 400_000_000, "2026-12-11")
    assert tc_pin.validate_pins(cand) == []
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


def _trial(root, junit, sizes=((400, "c" * 64), (400, "c" * 64)), tmp=None, live=True):
    seen = {"setup": [], "tests": [], "live": []}
    it = iter(sizes)

    def download(url, dest):
        size, sha = next(it)
        return sha, size

    def setup(doc, environ):
        seen["setup"].append(doc["pob2"]["tag"])

    def run_tests(cand_path, junit_path, environ, live=False):
        seen["tests"].append(cand_path)
        seen["live"].append(live)
        assert json.loads(Path(cand_path).read_text(encoding="ascii"))["pob2"]["tag"] == "v0.24.0"
        return tc_drift.parse_junit(junit)
    env = {"AL_SIDECAR_ROOT": str(tmp or root / "sidecar")}
    res = tc_drift.trial(root, "v0.24.0", environ=env, fetch=_fake(), download=download,
                         setup=setup, run_tests=run_tests, today="2026-12-11", live=live)
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
    text = (ROOT / "tools" / "tc_drift.py").read_text(encoding="ascii")
    assert "POESESSID" not in text and "trade" not in text.lower()
    assert tc_drift.API_HOSTS == ("api.github.com",)
