"""TEST-CAPTURE-HELPER (F-147, AUTO-15): app/test/cdp/capture.mjs, the one
capture path of the repo.

The helper renders AshLight's own page on a DEMO core in a headless browser
and saves it as a PNG. These tests pin that it refuses everything else:

- a target that is not http://127.0.0.1:<port>, port 8960 (the live core)
  or 8961 (the dev core), user info, an API path or a missing token is
  refused with no network at all (a preload makes any socket, fetch or
  process start end the run with exit 9, so a connect cannot hide);
- a listener that fails the hello proof, is not AshLight, names another
  port, reads a log in a game folder, a log that is not Client.txt or a log
  folder without the demo marker is refused before any browser starts
  (a preload makes a process start end the run);
- a refusal writes no file and starts no browser (no profile folder);
- the browser command is headless only, with an OS-chosen DevTools port;
- with a browser and node present it writes a PNG of a real demo core page
  (python -m server.al --demo on the tracked synthetic fixture, port 0).

The capture never targets the live core: every target here is a fake
listener on a leased test port or a demo process on an ephemeral port.
"""

import hashlib
import hmac
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from browser_util import find_browser  # noqa: E402
from ci_timing import ci_scale  # noqa: E402
from tc_live_util import lease_port  # noqa: E402

from server.al import hello, paths, ports  # noqa: E402

HELPER = ROOT / "app" / "test" / "cdp" / "capture.mjs"
FIXTURE = ROOT / "tests" / "fixtures" / "demo"
NODE = shutil.which("node")
TOKEN = "k" * 48
OFFLINE_PORT = 8977  # never dialled: refused or tripped before any socket
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
URL_RE = re.compile(r"http://127\.0\.0\.1:(\d+)/#token=([0-9A-Za-z_\-]+)")
SCRATCH_RE = re.compile(r"^demo mode: fixture .+; scratch (.+)$")

needs_node = pytest.mark.skipif(not NODE, reason="node not found")

# Preloads (node --import): a tripwire that ends the run with exit 9 and a
# {"tripped": ...} line the moment the helper would open a socket, fetch or
# start a process. NO_NET trips on all of them, NO_SPAWN on a process start.
_TRIP = """
import http from "node:http";
import net from "node:net";
import cp from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
const trip = (what) => () => {
  process.stdout.write(JSON.stringify({ tripped: what }) + "\\n");
  process.exit(9);
};
cp.spawn = trip("spawn"); cp.exec = trip("spawn"); cp.execFile = trip("spawn");
cp.fork = trip("spawn"); cp.spawnSync = trip("spawn");
"""
_NET = """
http.get = trip("http"); http.request = trip("http");
net.connect = trip("net"); net.createConnection = trip("net");
globalThis.fetch = trip("fetch");
globalThis.WebSocket = function () { trip("websocket")(); };
"""
_END = "syncBuiltinESMExports();\n"


@pytest.fixture(scope="module")
def preloads(tmp_path_factory):
    d = tmp_path_factory.mktemp("capture_preload")
    no_net = d / "no_net.mjs"
    no_spawn = d / "no_spawn.mjs"
    no_net.write_text(_TRIP + _NET + _END, encoding="ascii", newline="\n")
    no_spawn.write_text(_TRIP + _END, encoding="ascii", newline="\n")
    return {"no_net": no_net.as_uri(), "no_spawn": no_spawn.as_uri()}


def run_helper(args, preload=None, timeout=60):
    cmd = [NODE]
    if preload:
        cmd.append(f"--import={preload}")
    cmd += [str(HELPER), *args]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=ci_scale(timeout),
                       creationflags=NO_WINDOW)
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
    doc = json.loads(lines[-1]) if lines else {}
    return r, doc


def assert_refused(r, doc, out, profile):
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "refused" in doc and "tripped" not in doc, doc
    assert not out.exists(), "a refusal wrote a file"
    assert not profile.exists(), "a refusal started a browser (profile made)"


# ------------------------------------------------------------ offline refusals

OFFLINE_URLS = [
    f"http://127.0.0.1:{ports.AL_PORT}/#token={TOKEN}",
    f"http://127.0.0.1:{ports.AL_PORT}/overlay/#token={TOKEN}",
    f"http://127.0.0.1:{ports.AL_DEV_PORT}/#token={TOKEN}",
    f"http://localhost:{OFFLINE_PORT}/#token={TOKEN}",
    f"http://127.0.0.2:{OFFLINE_PORT}/#token={TOKEN}",
    f"http://[::1]:{OFFLINE_PORT}/#token={TOKEN}",
    f"http://0.0.0.0:{OFFLINE_PORT}/#token={TOKEN}",
    f"http://192.0.2.10:{OFFLINE_PORT}/#token={TOKEN}",
    f"http://example.com:{OFFLINE_PORT}/#token={TOKEN}",
    f"http://127.0.0.1.example.com:{OFFLINE_PORT}/#token={TOKEN}",
    f"http://127.0.0.1:{OFFLINE_PORT}@example.com/#token={TOKEN}",
    f"http://user:pw@127.0.0.1:{OFFLINE_PORT}/#token={TOKEN}",
    f"https://127.0.0.1:{OFFLINE_PORT}/#token={TOKEN}",
    f"file:///demo/page.html#token={TOKEN}",
    f"http://127.0.0.1/#token={TOKEN}",
    f"http://127.0.0.1:{OFFLINE_PORT}/api/state#token={TOKEN}",
    f"http://127.0.0.1:{OFFLINE_PORT}/events#token={TOKEN}",
    f"http://127.0.0.1:{OFFLINE_PORT}/",
    f"http://127.0.0.1:{OFFLINE_PORT}/#token=",
]


@needs_node
@pytest.mark.parametrize("url", OFFLINE_URLS)
def test_a_target_that_is_not_a_loopback_page_is_refused_with_no_network(
        url, preloads, tmp_path):
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    r, doc = run_helper([sys.executable, str(profile), url, str(out)], preloads["no_net"])
    assert_refused(r, doc, out, profile)


@needs_node
def test_the_live_ports_are_refused_by_name(preloads, tmp_path):
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    for port in (ports.AL_PORT, ports.AL_DEV_PORT):
        r, doc = run_helper([sys.executable, str(profile),
                             f"http://127.0.0.1:{port}/#token={TOKEN}", str(out)],
                            preloads["no_net"])
        assert_refused(r, doc, out, profile)
        assert f"port {port} is a live AshLight core" in doc["refused"], doc


@needs_node
@pytest.mark.parametrize("case", ["not_png", "no_folder", "used_profile", "no_browser",
                                  "extra_arg", "bad_option", "bad_width"])
def test_bad_arguments_are_refused_with_no_network(case, preloads, tmp_path):
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    browser = sys.executable
    url = f"http://127.0.0.1:{OFFLINE_PORT}/#token={TOKEN}"
    extra = []
    if case == "not_png":
        out = tmp_path / "shot.jpg"
    elif case == "no_folder":
        out = tmp_path / "missing" / "shot.png"
    elif case == "used_profile":
        profile = tmp_path / "used"
        profile.mkdir()
        (profile / "Local State").write_text("{}", encoding="ascii")
    elif case == "no_browser":
        browser = str(tmp_path / "no-such-browser.exe")
    elif case == "extra_arg":
        extra = ["more"]
    elif case == "bad_option":
        extra = ["--headless=false"]
    elif case == "bad_width":
        extra = ["--width=99999"]
    r, doc = run_helper([browser, str(profile), url, str(out), *extra], preloads["no_net"])
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "refused" in doc and "tripped" not in doc, doc
    assert not out.exists()
    if case != "used_profile":
        assert not profile.exists()
    else:
        assert sorted(p.name for p in profile.iterdir()) == ["Local State"]


@needs_node
def test_live_ports_come_from_ports_py(tmp_path):
    code = ("const m = await import(process.argv[1]);"
            "const out = {ports: m.readPorts()};"
            "try { m.readPorts(process.argv[2]); out.empty = 'read'; }"
            "catch (e) { out.empty = e instanceof m.Refused ? 'refused' : String(e); }"
            "console.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code, HELPER.as_uri(),
                        str(tmp_path)], capture_output=True, text=True, timeout=ci_scale(30),
                       creationflags=NO_WINDOW)
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout.strip().splitlines()[-1])
    assert doc["ports"] == {"al": ports.AL_PORT, "dev": ports.AL_DEV_PORT}
    assert doc["empty"] == "refused"  # no ports.py: fail closed


def test_the_helper_source_starts_one_headless_browser_only():
    text = HELPER.read_text(encoding="utf-8")
    assert text.isascii() and "\r" not in text
    # one process start, one browser command, headless, OS-chosen port
    assert len(re.findall(r"\bspawn\(", text)) == 1
    flags = re.search(r"BROWSER_FLAGS = Object\.freeze\(\[(.*?)\]\)", text, re.S)
    assert flags, "BROWSER_FLAGS not found"
    listed = re.findall(r'"([^"]+)"', flags.group(1))
    assert "--headless=new" in listed and "--remote-debugging-port=0" in listed
    assert "--disable-gpu" in listed
    assert not re.search(r"remote-debugging-port=[1-9]", text)
    assert "--headless=false" not in text and "--no-headless" not in text
    assert "windowsHide: true" in text and "PRIORITY_BELOW_NORMAL" in text
    # no live port literal: the ports are read from server/al/ports.py
    for port in (ports.AL_PORT, ports.AL_DEV_PORT):
        assert str(port) not in text
    # the demo check runs before the browser starts and again before the capture
    main = text[text.index("export async function main("):]
    assert main.index("await checkDemoCore(target);") < main.index("if (opts.plan)")
    assert main.index("if (opts.plan)") < main.index("await capture(opts, target)")
    cap = text.index("the one capture call of the repo")
    start = text.index("async function capture(")
    assert text.rindex("await checkDemoCore(target);", 0, cap) > start
    assert text.rindex("location.origin", 0, cap) > start


# ------------------------------------------------------------ a fake listener

class FakeCore:
    """A loopback listener on a leased test port that answers the three
    routes the helper asks, shaped by `mode`. It records every request's
    headers so a test can show the token was never sent."""

    def __init__(self, tmp, mode):
        self.mode = mode
        self.seen = []
        self.port, self._release = lease_port()
        logdir = tmp / "logs"
        self.log = logdir / "Client.txt"
        if mode == "game_folder":
            logdir = tmp / "steamapps" / "common" / "Path of Exile 2" / "logs"
            self.log = logdir / "Client.txt"
        elif mode == "not_client_txt":
            self.log = logdir / "Other.txt"
        logdir.mkdir(parents=True)
        self.log.write_text("", encoding="ascii")
        marker = {"ashlight_demo": 1, "note": "fake"}
        if mode == "marker_zero":
            marker = {"ashlight_demo": 0}
        if mode != "no_marker":
            (logdir / "ashlight-demo.json").write_text(json.dumps(marker), encoding="ascii")
        core = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                core.seen.append((self.path, dict(self.headers)))
                code, doc = core.answer(self.path, self.headers)
                body = json.dumps(doc).encode("ascii")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer((ports.LOOPBACK, self.port), H)
        threading.Thread(target=self.server.serve_forever,
                         kwargs={"poll_interval": 0.05}, daemon=True).start()

    def answer(self, path, headers):
        token_ok = headers.get("X-AL-Token") == TOKEN
        if path == "/api/hello":
            nonce = headers.get(hello.NONCE_HEADER)
            if not hello.check_client(TOKEN, nonce, headers.get(hello.PROOF_HEADER)):
                return 401, {"error": "token required"}
            doc = hello.answer(TOKEN, nonce, self.port)
            if self.mode == "bad_hello":
                doc["proof"] = hmac.new(b"x", b"y", hashlib.sha256).hexdigest()
            return 200, doc
        if not token_ok:
            return 401, {"error": "token required"}
        if path == "/api/health":
            name = "Other" if self.mode == "not_ashlight" else "AshLight"
            port = self.port + 1 if self.mode == "wrong_port" else self.port
            return 200, {"ok": True, "name": name, "port": port, "tailing": True}
        if path == "/api/state":
            tailer = {} if self.mode == "no_log" else {"path": str(self.log)}
            return 200, {"tailer": tailer}
        return 404, {"error": "not found"}

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/#token={TOKEN}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self._release()


@needs_node
@pytest.mark.parametrize("mode", ["bad_hello", "not_ashlight", "wrong_port", "no_log",
                                  "game_folder", "not_client_txt", "no_marker",
                                  "marker_zero"])
def test_a_listener_that_is_not_a_demo_core_is_refused_before_any_browser(
        mode, preloads, tmp_path):
    fake = FakeCore(tmp_path, mode)
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    try:
        r, doc = run_helper([sys.executable, str(profile), fake.url, str(out)],
                            preloads["no_spawn"])
    finally:
        fake.close()
    assert_refused(r, doc, out, profile)
    paths_seen = [p for p, _ in fake.seen]
    assert paths_seen and paths_seen[0] == "/api/hello", paths_seen
    if mode == "bad_hello":  # the token is sent only after the proof holds
        assert paths_seen == ["/api/hello"], paths_seen
        assert not any("X-AL-Token" in h for _, h in fake.seen)
    assert TOKEN not in json.dumps(fake.seen[0][1])  # the hello carries no token


@needs_node
def test_a_demo_marker_beside_the_log_passes_and_the_plan_is_headless(preloads, tmp_path):
    fake = FakeCore(tmp_path, "ok")
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    try:
        r, doc = run_helper(["--plan", sys.executable, str(profile), fake.url, str(out)],
                            preloads["no_spawn"])
    finally:
        fake.close()
    assert r.returncode == 0, (r.stdout, r.stderr)
    plan = doc["plan"]
    assert plan["browser"] == sys.executable
    assert plan["args"][0] == "--headless=new"
    assert "--remote-debugging-port=0" in plan["args"]
    assert plan["args"][-1] == "about:blank"
    assert sum(a.startswith("--headless") for a in plan["args"]) == 1
    assert plan["url"] == f"http://127.0.0.1:{fake.port}"
    assert not out.exists() and not profile.exists()  # a plan starts nothing


# ------------------------------------------------------------ a real demo core

def _child_env(sidecar):
    env = {k: v for k, v in os.environ.items()
           if k not in (paths.RUNTIME_ENV, paths.SIDECAR_ENV, ports.PORT_ENV)}
    env[paths.SIDECAR_ENV] = str(sidecar)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


@pytest.fixture
def demo_core(tmp_path):
    """A real `python -m server.al --demo <fixture> --port 0` process."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.al", "--demo", str(FIXTURE), "--port", "0"],
        cwd=str(ROOT), env=_child_env(tmp_path / "sidecar"), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", creationflags=NO_WINDOW)
    lines = queue.Queue()
    seen = []

    def read():
        for line in proc.stdout:
            seen.append(line.rstrip("\n"))
            lines.put(line)

    threading.Thread(target=read, daemon=True).start()
    port = token = scratch = None
    deadline = time.monotonic() + ci_scale(60)
    try:
        while (port is None or scratch is None) and time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            m = URL_RE.search(line)
            if m:
                port, token = int(m.group(1)), m.group(2)
            m = SCRATCH_RE.match(line.strip())
            if m:
                scratch = Path(m.group(1))
        assert port and scratch, "no URL / scratch line: " + " | ".join(seen[-20:])
        assert port not in (ports.AL_PORT, ports.AL_DEV_PORT)

        def health():
            req = urllib.request.Request(f"http://{ports.LOOPBACK}:{port}/api/health",
                                         headers={"X-AL-Token": token})
            with hello.NO_PROXY_OPENER.open(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))

        while time.monotonic() < deadline:
            try:
                if health().get("tailing"):
                    break
            except OSError:
                pass
            time.sleep(0.2)
        else:
            raise AssertionError("the demo core never tailed: " + " | ".join(seen[-20:]))
        yield port, token
    finally:
        if scratch is not None and proc.poll() is None:
            (scratch / "runtime" / "stop.request").write_text("stop\n", encoding="ascii")
            try:
                proc.wait(ci_scale(30))
            except subprocess.TimeoutExpired:
                pass
        if proc.poll() is None:
            proc.kill()
            proc.wait(30)


@pytest.mark.server
@needs_node
def test_writes_a_png_of_a_demo_core_page(demo_core, tmp_path):
    browser = find_browser()
    if not browser:
        pytest.skip("headless Chrome / Edge not found")
    port, token = demo_core
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    r, doc = run_helper([browser, str(profile), f"http://127.0.0.1:{port}/#token={token}",
                         str(out), "--width=800", "--height=600", "--scheme=light"],
                        timeout=120)
    assert r.returncode == 0, (r.returncode, r.stdout[-2000:], r.stderr[-2000:])
    assert doc["ok"] is True and Path(doc["out"]) == out.resolve()
    data = out.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) == doc["bytes"] > 1000
    assert (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")) == (800, 600)
    assert (doc["width"], doc["height"]) == (800, 600)
