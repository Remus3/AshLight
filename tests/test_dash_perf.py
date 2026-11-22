"""RUN-BUDGET-TESTS-DASH (B14, research 0048): the dashboard's paint budget.

A real core and HTTP / SSE server on a leased test port (never 8960), a temp
runtime and config, a synthetic busy session from tools/synth_client.py
(campaign, maps, deaths, trades), a loaded build, three item checks, the
Checks view and the all-sessions map ladder. Web data stays off, so nothing
leaves the box. app/test/cdp/dash_perf.mjs drives headless Chrome over the
DevTools protocol at 1440 px and reads Performance.getMetrics:

- at most 1,500 elements in the document (deterministic, hard everywhere);
- at most 5 ms of main-thread task time per state push, the pushes made by
  appending log blocks to this test's own temp Client.txt;
- at most 3 ms of task time per idle second;
- a JS heap under 8 MB after a full collection.

The two task-time lines are timing budgets: under AL_CI=1 they skip with the
measured value printed (decision 0080). Skips when Chrome (or Edge) or node
is missing.
"""

import http.client
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
from ci_timing import ci_scale, skip_if_ci_timing  # noqa: E402
from fullstack_mocks import CONTACT, HIDEOUT, WAYSTONE, campaign_and_maps, trades  # noqa: E402
from tc_live_util import lease_port  # noqa: E402

from server.al.core import Core  # noqa: E402
from server.al.http import serve  # noqa: E402
from server.al.theorycraft import codec  # noqa: E402

pytestmark = pytest.mark.server
SCRIPT = ROOT / "app" / "test" / "cdp" / "dash_perf.mjs"
TOKEN = "d" * 48
WAIT_S = 8.0

# B14 (research 0048, measured value in brackets there)
MAX_ELEMENTS = 1500      # [942]
MAX_MS_PER_PUSH = 5.0    # [2.0]
MAX_IDLE_MS_PER_S = 3.0  # [1.5]
MAX_HEAP_BYTES = 8 * 1024 * 1024  # [1.3 MB]
N_PUSHES = 10


class _Stack:
    def __init__(self, core, server, port):
        self.core, self.server, self.port = core, server, port

    def req(self, method, path, body=None, timeout=10):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        h = {"Host": f"127.0.0.1:{self.port}", "X-AL-Token": TOKEN}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        return r.status, json.loads(raw) if raw else None

    def state(self):
        status, doc = self.req("GET", "/api/state")
        assert status == 200
        return doc

    def wait_for(self, pred, what, timeout=WAIT_S):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred(self.state()):
                return
            time.sleep(0.02)
        pytest.fail(f"timed out waiting for {what}")


@pytest.fixture
def stack(tmp_path):
    rt = tmp_path / "rt"
    rt.mkdir()
    cfg = rt / "local.json"
    cfg.write_text(json.dumps({"contact": CONTACT}), encoding="ascii")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=rt, log_path=str(log), poll_s=0.02, config_path=cfg)
    port, release = lease_port()
    server = serve(core, TOKEN, port=port, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        yield _Stack(core, server, port), log
    finally:
        server.stop()
        release()
        core.close()


def _push_blocks(s):
    """N_PUSHES log blocks, each a change the dashboard paints: level-ups,
    deaths, hideout trips and new maps, as a mapping player makes them."""
    out = []
    for i in range(N_PUSHES):
        kind = i % 4
        if kind == 0:
            s.level_up()
        elif kind == 1:
            s.zone_change(*HIDEOUT)
        elif kind == 2:
            s.zone_change("MapCrypt", 65, "Crypt", seed=1000 + i)
        else:
            s.death()
        out.append(s.text())
        s.lines.clear()
    return out


def test_dashboard_elements_task_time_and_heap(stack, tmp_path):
    browser = find_browser()
    node = shutil.which("node")
    if not browser or not node:
        pytest.skip("headless Chrome / Edge or node not found")
    st, log = stack
    assert st.req("POST", "/api/consent", {"consent": True})[0] == 200
    st.wait_for(lambda x: x["tailer"]["reading"], "tailer reading")
    s = synth_client.Session(seed=47, character="Perfcheck", klass="Sorceress")
    campaign_and_maps(s)
    trades(s)
    with open(log, "ab") as fh:
        fh.write(s.text().encode("utf-8"))
    s.lines.clear()
    st.wait_for(lambda x: x["maps"]["count"] == 2, "campaign and maps")
    assert st.req("POST", "/api/build-code",
                  {"code": codec.encode(fx.EVAL_BUILD_XML)})[0] == 200
    for item in (fx.UNIQUE_STAFF, WAYSTONE, fx.RARE_GLOVES):
        assert st.req("POST", "/api/eval", {"item": item})[0] == 200
    st.core.tick_history()
    st.core.tick_diag(force=True)
    st.core.tick_ladder()

    pushes = tmp_path / "pushes.json"
    pushes.write_text(json.dumps(_push_blocks(s)), encoding="ascii")
    url = f"http://127.0.0.1:{st.port}/#token={TOKEN}"
    r = subprocess.run([node, str(SCRIPT), browser, str(tmp_path / "chrome"), url,
                        str(log), str(pushes)],
                       capture_output=True, text=True, timeout=ci_scale(90))
    assert r.returncode == 0, (r.returncode, r.stdout[-2000:], r.stderr[-2000:])
    out = json.loads(r.stdout.strip().splitlines()[-1])
    print("B14", json.dumps(out))
    assert out["live"], out
    assert out["issues"] == [], out["issues"]
    # every block reached the page as its own frame (the feed may fold two
    # blocks that land inside one 250 ms window, never more)
    assert out["pushes"] >= N_PUSHES - 2, out
    assert out["elements"] <= MAX_ELEMENTS, out
    assert out["heap_bytes"] < MAX_HEAP_BYTES, out
    skip_if_ci_timing("dashboard task time",
                      f"{out['task_ms_per_push']:.2f} ms per push, "
                      f"{out['idle_ms_per_s']:.2f} ms per idle second")
    assert out["task_ms_per_push"] <= MAX_MS_PER_PUSH, out
    assert out["idle_ms_per_s"] <= MAX_IDLE_MS_PER_S, out
