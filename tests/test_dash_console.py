"""UX-REGRESSION-SWEEP: the dashboard loads with no console error, no
uncaught exception, no failed load and no CSP violation.

A real core and HTTP / SSE server on a free test port, a temp runtime, a
synthetic session from tools/synth_client.py (campaign, maps, deaths,
trades), a local mock poe.ninja behind the core's web transport (the
test_fullstack mock), a loaded build and three item checks (gear, waystone,
a weapon into an empty slot). app/test/cdp/dash_console.mjs then drives
headless Chrome over the DevTools protocol at 360 / 1440 / 768 px (dark,
light, forced colours) with every fold open, and this test fails on any
issue it reports. RUN-P8-6-CONSOLE: a second run adds the Checks view
(tick_diag), a new-character tip and the all-sessions map ladder, and checks
their painters left rows on the page. Skips when Chrome (or Edge) or node is
missing.
"""

import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import synth_client  # noqa: E402
from browser_util import find_browser  # noqa: E402
import tc_eval_fixtures as fx  # noqa: E402
import test_fullstack as fs  # noqa: E402
from ci_timing import ci_scale  # noqa: E402
from tc_live_util import lease_port  # noqa: E402

from server.al import ninja, playview  # noqa: E402
from server.al.core import Core  # noqa: E402
from server.al.http import serve  # noqa: E402
from server.al.theorycraft import codec  # noqa: E402

pytestmark = pytest.mark.server
SCRIPT = ROOT / "app" / "test" / "cdp" / "dash_console.mjs"
TOKEN = "c" * 48


@pytest.fixture
def stack(tmp_path):
    rt = tmp_path / "rt"
    rt.mkdir()
    cfg = rt / "local.json"
    cfg.write_text(json.dumps({"contact": fs.CONTACT}), encoding="ascii")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    mock = fs.MockNinja()
    core = Core(runtime=rt, log_path=str(log), poll_s=0.02, config_path=cfg,
                web_fetch=fs.Transport(mock))
    port, release = lease_port()
    server = serve(core, TOKEN, port=port, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    st = fs.Stack.__new__(fs.Stack)  # its req / state / wait_for helpers only
    st.core, st.server, st.port = core, server, port
    try:
        yield st, log
    finally:
        server.stop()
        release()
        core.close()
        mock.close()


def _busy_session(st, log, monkeypatch):
    """The synthetic session, the price book, the build and three checks."""
    monkeypatch.setattr(fs, "TOKEN", TOKEN)
    assert st.req("POST", "/api/consent", {"consent": True})[0] == 200
    st.wait_for(lambda x: x["tailer"]["reading"], "tailer reading")
    s = synth_client.Session(seed=31, character="Consolecheck", klass="Sorceress")
    fs.campaign_and_maps(s)
    fs.trades(s)
    fs.append(log, s)
    st.wait_for(lambda x: x["maps"]["count"] == 2, "campaign and maps")
    past = time.time() - ninja.MIN_INTERVAL_S - 100
    st.core.rates.clock = lambda: past
    assert st.req("POST", "/api/web-data", {"enabled": True})[0] == 200
    end = time.monotonic() + fs.WAIT_S
    while time.monotonic() < end and (st.core.rates._busy
                                       or not st.core.rates.doc.get("checked_at")):
        time.sleep(0.05)
    st.core.rates.clock = time.time
    assert st.req("POST", "/api/build-code",
                  {"code": codec.encode(fx.EVAL_BUILD_XML)})[0] == 200
    for item in (fx.UNIQUE_STAFF, fs.WAYSTONE, fx.RARE_GLOVES):
        assert st.req("POST", "/api/eval", {"item": item})[0] == 200
    for tick in ("tick_history", "tick_watch"):
        getattr(st.core, tick)()


def _sweep(st, tmp_path, node, browser):
    """Run the CDP sweep; fail on any issue; return its views."""
    url = f"http://127.0.0.1:{st.port}/#token={TOKEN}"
    r = subprocess.run([node, str(SCRIPT), browser, str(tmp_path / "chrome"), url],
                       capture_output=True, text=True, timeout=ci_scale(90))
    assert r.returncode == 0, (r.returncode, r.stdout[-2000:], r.stderr[-2000:])
    out = json.loads(r.stdout.strip().splitlines()[-1])
    # TEST-DASHCONSOLE-NOBUFFER-CI: views re-run once on ERR_NO_BUFFER_SPACE
    if out.get("retried"):
        print("dash_console retried on ERR_NO_BUFFER_SPACE:", out["retried"])
    assert out["issues"] == [], out["issues"]
    for tag, v in out["views"].items():
        assert v["live"], (tag, v)  # the feed came up, so the cards painted
        assert v["cards"] >= 8, (tag, v)
        assert v["sw"] <= v["cw"], (tag, v)  # no horizontal scroll, folds open
    return out["views"]


def _tools():
    browser = find_browser()
    node = shutil.which("node")
    if not browser or not node:
        pytest.skip("headless Chrome / Edge or node not found")
    return node, browser


def test_dashboard_has_no_console_error_or_csp_violation(stack, tmp_path, monkeypatch):
    node, browser = _tools()
    st, log = stack
    _busy_session(st, log, monkeypatch)
    _sweep(st, tmp_path, node, browser)


def test_no_console_error_with_checks_hint_and_ladder_all(stack, tmp_path, monkeypatch):
    """RUN-P8-6-CONSOLE (AUDIT-P8-LOW P8-6): the same sweep on a core that
    has run tick_diag (Checks rows), shows a new-character tip (a region N
    notice) and carries an all-sessions map ladder, so those painters run
    under the console / CSP watch too."""
    node, browser = _tools()
    st, log = stack
    _busy_session(st, log, monkeypatch)
    # web data off again: the "Game data: not fetched yet" note (a data
    # note, kind 5) would otherwise hold region N ahead of the tip (kind 6)
    assert st.req("POST", "/api/web-data", {"enabled": False})[0] == 200
    assert st.core.tick_diag(force=True)
    st.core.tick_ladder()
    snap = st.state()
    assert snap["diag"] and snap["diag"]["checks"], snap["diag"]
    assert snap["hint"], "no new-character tip on show"
    notices = snap["play"]["notices"]
    assert notices and notices[0]["kind"] == playview.KIND_TIP, notices
    assert snap["maps"]["ladder_all"], snap["maps"].get("ladder_all")
    title = playview.TIP_TITLES[snap["hint"]["id"]]
    views = _sweep(st, tmp_path, node, browser)
    for tag, v in views.items():
        assert v["checks"] >= len(snap["diag"]["checks"]), (tag, v)  # Checks rows
        assert v["ladder_all"] >= 1, (tag, v)  # all-sessions ladder rows
        # the tip in region N; the compact class hides tips by design
        # (web/slots.js hiddenNoticeKinds), so only a full view shows it
        if v["size"] == "full":
            assert title in v["notice"], (tag, title, v)
    assert any(v["size"] == "full" for v in views.values()), views
