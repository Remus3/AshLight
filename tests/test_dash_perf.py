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


@pytest.mark.parametrize("which", ["driver", "hidden"])
def test_the_driver_owns_its_browser(which):
    """TEST-CDP-OS-PORT: dash_perf.mjs (and the hidden-page script below)
    drew the same random DevTools port range as dash_console.mjs, so two
    parallel drivers could attach to one browser; the OS picks the port,
    read from the driver's own profile."""
    text = SCRIPT.read_text(encoding="utf-8") if which == "driver" else HIDDEN_SCRIPT
    assert "--remote-debugging-port=0" in text
    assert "DevToolsActivePort" in text
    assert "Math.random" not in text
    assert "startsWith(`ws://127.0.0.1:${port}/`)" in text


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


# RUN-PERF-DASH-IDLE (F-178, B14 idle line): a hidden dashboard paints
# nothing on a state push and paints once when it shows again. The page's
# visibility is set from the DevTools side (document.hidden and
# visibilityState read a flag, then a visibilitychange fires), so the test
# needs no window manager. Written next to the test's temp files; the same
# protocol client as app/test/cdp/dash_perf.mjs.
HIDDEN_SCRIPT = r"""
import { spawn } from "node:child_process";
import { appendFileSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
const [chromePath, profile, url, logPath, pushesPath] = process.argv.slice(2);
const blocks = JSON.parse(readFileSync(pushesPath, "utf8"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CI = process.env.AL_CI === "1";
// TEST-CDP-OS-PORT: the OS picks the DevTools port, read back from this
// profile's DevToolsActivePort (as app/test/cdp/dash_perf.mjs does).
const portFile = path.join(profile, "DevToolsActivePort");
try { rmSync(portFile, { force: true }); } catch { /* none yet */ }
const chrome = spawn(chromePath, ["--headless=new", "--disable-gpu", "--in-process-gpu",
  "--no-first-run", "--no-default-browser-check", "--disable-extensions",
  "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"],
  { stdio: "ignore" });
const killer = setTimeout(() => { chrome.kill(); process.exit(3); }, CI ? 180000 : 60000);
let chromeExit = null;
// a clean 0 exit may be a hand-off to a running browser: keep polling then
chrome.on("exit", (code, signal) => { if (signal || code) { chromeExit = signal || code; } });
// TEST-CDP-ENDPOINT-CI-WAIT (decision 0080): the same DevTools endpoint
// wait as app/test/cdp/dash_perf.mjs, 100 x 100 ms locally, 3x under AL_CI.
const ENDPOINT_POLLS = CI ? 300 : 100;
let port = 0;
let targets = null;
for (let i = 0; i < ENDPOINT_POLLS && !targets && chromeExit === null; i++) {
  if (!port) {
    try {
      const first = readFileSync(portFile, "utf8").split(/\r?\n/)[0].trim();
      if (/^\d{1,5}$/.test(first) && Number(first) > 0) { port = Number(first); }
    } catch { /* not written yet */ }
  }
  if (port) {
    try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); }
    catch { targets = null; }
  }
  if (!targets) { await sleep(100); }
}
if (!targets) {
  chrome.kill();
  console.log(JSON.stringify({ error: "no DevTools endpoint" + (chromeExit === null
    ? ` after ${ENDPOINT_POLLS} polls` : ` (browser exited: ${chromeExit})`) }));
  process.exit(2);
}
const page = targets.find((t) => t.type === "page" &&
  String(t.webSocketDebuggerUrl).startsWith(`ws://127.0.0.1:${port}/`));
if (!page) { chrome.kill(); console.log(JSON.stringify({ error: "no page target" })); process.exit(2); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
const pending = new Map();
const issues = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  const p = m.params || {};
  if (m.method === "Runtime.consoleAPICalled" && (p.type === "error" || p.type === "assert")) {
    issues.push(["console." + p.type, p.args.map((a) => a.value ?? a.description).join(" ")]);
  } else if (m.method === "Runtime.exceptionThrown") {
    const d = p.exceptionDetails || {};
    issues.push(["exception", (d.exception && d.exception.description) || d.text || ""]);
  }
});
const send = (method, params = {}) => new Promise((r) => {
  const i = ++seq; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params }));
});
const value = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true });
  return r.result && r.result.result ? r.result.result.value : undefined;
};
const metrics = async () => {
  const r = await send("Performance.getMetrics");
  const out = {};
  for (const m of (r.result && r.result.metrics) || []) { out[m.name] = m.value; }
  return out;
};
await send("Page.enable");
await send("Runtime.enable");
await send("Performance.enable", { timeDomain: "timeTicks" });
await send("Page.addScriptToEvaluateOnNewDocument", { source:
  "(function () { window.__alHidden = false;" +
  " Object.defineProperty(Document.prototype, 'hidden', { configurable: true," +
  "  get: function () { return window.__alHidden; } });" +
  " Object.defineProperty(Document.prototype, 'visibilityState', { configurable: true," +
  "  get: function () { return window.__alHidden ? 'hidden' : 'visible'; } });" +
  " var O = window.EventSource; window.__alPushes = 0;" +
  " function W(u, o) { var e = new O(u, o);" +
  "  e.addEventListener('state', function () { window.__alPushes++; }); return e; }" +
  " W.prototype = O.prototype; W.CONNECTING = 0; W.OPEN = 1; W.CLOSED = 2;" +
  " window.EventSource = W; })();" });
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url });
let live = false;
for (let i = 0; i < (CI ? 240 : 80) && !live; i++) {
  await sleep(100);
  live = !!(await value(
    "!!document.getElementById('build-title') && /^(running|done|idle|blocked)$/.test((document.getElementById('reading') || {getAttribute(){return ''}}).getAttribute('data-state') || '')"));
}
if (!live) {
  console.log(JSON.stringify({ live, issues }));
  clearTimeout(killer); ws.close(); chrome.kill(); process.exit(0);
}
await sleep(1500);
const vis = (hidden) => value("window.__alHidden = " + hidden +
  "; document.dispatchEvent(new Event('visibilitychange')); true");
await vis(true);
await sleep(500);
const p0 = await value("window.__alPushes");
const m0 = await metrics();
for (const b of blocks) { appendFileSync(logPath, b); await sleep(600); }
await sleep(600);
const m1 = await metrics();
const p1 = await value("window.__alPushes");
await vis(false);
await sleep(600);
const m2 = await metrics();
console.log(JSON.stringify({
  live, issues, hidden_pushes: p1 - p0,
  hidden_layouts: m1.LayoutCount - m0.LayoutCount,
  hidden_styles: m1.RecalcStyleCount - m0.RecalcStyleCount,
  shown_layouts: m2.LayoutCount - m1.LayoutCount,
}));
clearTimeout(killer);
ws.close();
chrome.kill();
"""


@pytest.mark.slow  # drives a real browser page through four pushes and a return
def test_hidden_page_shows_0_layouts(stack, tmp_path):
    """B14 idle line (RUN-PERF-DASH-IDLE): state pushes to a hidden page
    run no painter, so the page lays out nothing; showing it again paints
    the newest snapshot once."""
    browser = find_browser()
    node = shutil.which("node")
    if not browser or not node:
        pytest.skip("headless Chrome / Edge or node not found")
    st, log = stack
    assert st.req("POST", "/api/consent", {"consent": True})[0] == 200
    st.wait_for(lambda x: x["tailer"]["reading"], "tailer reading")
    s = synth_client.Session(seed=48, character="Hiddencheck", klass="Sorceress")
    campaign_and_maps(s)
    with open(log, "ab") as fh:
        fh.write(s.text().encode("utf-8"))
    s.lines.clear()
    st.wait_for(lambda x: x["maps"]["count"] == 2, "campaign and maps")
    pushes = tmp_path / "pushes.json"
    pushes.write_text(json.dumps(_push_blocks(s)[:4]), encoding="ascii")
    script = tmp_path / "dash_hidden.mjs"
    script.write_text(HIDDEN_SCRIPT, encoding="ascii")
    url = f"http://127.0.0.1:{st.port}/#token={TOKEN}"
    r = subprocess.run([node, str(script), browser, str(tmp_path / "chrome"), url,
                        str(log), str(pushes)],
                       capture_output=True, text=True, timeout=ci_scale(90))
    assert r.returncode == 0, (r.returncode, r.stdout[-2000:], r.stderr[-2000:])
    out = json.loads(r.stdout.strip().splitlines()[-1])
    print("B14 hidden", json.dumps(out))
    assert out["live"], out
    assert out["issues"] == [], out["issues"]
    assert out["hidden_pushes"] >= 2, out       # the frames did reach the page
    assert out["hidden_layouts"] == 0, out      # and no painter ran
    assert out["shown_layouts"] >= 1, out       # one paint on return


def _sse_read(port, view, want, timeout):
    """The raw SSE stream until want(text) or the timeout; the text read."""
    import socket
    q = f"/events?token={TOKEN}" + (f"&view={view}" if view else "")
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    try:
        sock.sendall((f"GET {q} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                      "Accept: text/event-stream\r\n\r\n").encode())
        buf = b""
        end = time.monotonic() + timeout
        while time.monotonic() < end and not want(buf.decode("utf-8", "replace")):
            sock.settimeout(max(0.05, end - time.monotonic()))
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
        return buf.decode("utf-8", "replace")
    finally:
        sock.close()


@pytest.mark.parametrize("view", [None, "overlay"])
def test_keep_alive_is_a_named_event(stack, monkeypatch, view):
    """RUN-FEED-TRUTH (F-175): the idle stream's keep-alive is the named
    "alive" event with a data line (an SSE comment never reaches page
    code), on the dashboard feed and the overlay view alike."""
    from server.al import http as al_http
    monkeypatch.setattr(al_http, "SSE_HEARTBEAT_S", 0.3)
    st, _log = stack
    text = _sse_read(st.port, view, lambda t: t.count("event: alive\n") >= 2, ci_scale(8))
    assert "event: alive\ndata: {}\n\n" in text, text[-500:]
    assert text.count("event: alive\n") >= 2, text[-500:]
    assert ": hb" not in text
    assert al_http.SSE_ALIVE_EVENT == "alive"
