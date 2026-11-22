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
- TEST-SHOTS-TABS: --tab is argument-checked; a file URL other than this
  repo's app/overlay/index.html is refused without connecting and writes no
  file; the overlay file URL needs --core and is accepted only after the
  demo marker of that core is read; a real overlay and Settings tab capture.

The capture never targets the live core: every target here is a fake
listener on a leased test port or a demo process on an ephemeral port.
"""

import hashlib
import hmac
import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from browser_util import find_browser  # noqa: E402
from capture_util import HELPER, NO_WINDOW, NODE, demo_core, run_helper  # noqa: E402,F401 (fixture)
from ci_timing import ci_scale  # noqa: E402
from tc_live_util import lease_port  # noqa: E402

from server.al import hello, ports  # noqa: E402

TOKEN = "k" * 48
OFFLINE_PORT = 8977  # never dialled: refused or tripped before any socket

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


# ------------------------------------------------------------ tabs and overlay

OVERLAY_URL = (ROOT / "app" / "overlay" / "index.html").resolve().as_uri()
CORE_URL = f"http://127.0.0.1:{OFFLINE_PORT}/#token={TOKEN}"


@needs_node
@pytest.mark.parametrize("extra", [["--tab=items"], ["--tab="], ["--tab=Play"],
                                   ["--tab=play;x"], ["--tab"], ["--core="]])
def test_tab_and_core_options_are_argument_checked(extra, preloads, tmp_path):
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    r, doc = run_helper([sys.executable, str(profile), CORE_URL, str(out), *extra],
                        preloads["no_net"])
    assert_refused(r, doc, out, profile)


def _file_urls(tmp_path):
    stray = tmp_path / "index.html"
    stray.write_text("<p>x</p>\n", encoding="ascii")
    other = tmp_path / "app" / "overlay"
    other.mkdir(parents=True)
    (other / "index.html").write_text("<p>x</p>\n", encoding="ascii")
    return [
        (ROOT / "app" / "overlay" / "overlay.js").resolve().as_uri(),
        (ROOT / "web" / "index.html").resolve().as_uri(),
        (ROOT / "app" / "index.html").resolve().as_uri(),
        stray.as_uri(),
        (other / "index.html").as_uri(),
        OVERLAY_URL + "#token=" + TOKEN,
        OVERLAY_URL + "?x=1",
        OVERLAY_URL.replace("file:///", "file://host/"),
        OVERLAY_URL.replace("index.html", "sub/../../index.html"),
        "file:///demo/page.html",
    ]


@needs_node
def test_a_file_url_other_than_the_overlay_page_is_refused_with_no_network(
        preloads, tmp_path):
    for i, url in enumerate(_file_urls(tmp_path)):
        out, profile = tmp_path / f"shot{i}.png", tmp_path / f"profile{i}"
        r, doc = run_helper([sys.executable, str(profile), url, str(out),
                             f"--core={CORE_URL}"], preloads["no_net"])
        assert_refused(r, doc, out, profile)


@needs_node
@pytest.mark.parametrize("case", ["no_core", "with_tab", "core_live_port", "core_on_page",
                                  "core_file"])
def test_overlay_page_options_are_checked_with_no_network(case, preloads, tmp_path):
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    page, extra = OVERLAY_URL, [f"--core={CORE_URL}"]
    if case == "no_core":
        extra = []
    elif case == "with_tab":
        extra.append("--tab=play")
    elif case == "core_live_port":
        extra = [f"--core=http://127.0.0.1:{ports.AL_PORT}/#token={TOKEN}"]
    elif case == "core_on_page":
        page = CORE_URL
    elif case == "core_file":
        extra = [f"--core={OVERLAY_URL}"]
    r, doc = run_helper([sys.executable, str(profile), page, str(out), *extra],
                        preloads["no_net"])
    assert_refused(r, doc, out, profile)


@needs_node
def test_the_overlay_page_is_refused_when_the_core_has_no_demo_marker(preloads,
                                                                      tmp_path):
    fake = FakeCore(tmp_path, "no_marker")
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    try:
        r, doc = run_helper(["--plan", sys.executable, str(profile), OVERLAY_URL, str(out),
                             f"--core={fake.url}"], preloads["no_spawn"])
    finally:
        fake.close()
    assert_refused(r, doc, out, profile)
    assert "demo marker" in doc["refused"], doc
    assert [p for p, _ in fake.seen][0] == "/api/hello"


@needs_node
def test_the_overlay_page_passes_only_after_the_demo_marker_is_read(preloads, tmp_path):
    fake = FakeCore(tmp_path, "ok")
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    try:
        r, doc = run_helper(["--plan", sys.executable, str(profile), OVERLAY_URL, str(out),
                             f"--core={fake.url}", "--scheme=light"], preloads["no_spawn"])
    finally:
        fake.close()
    assert r.returncode == 0, (r.stdout, r.stderr)
    plan = doc["plan"]
    assert Path(plan["url"].replace("file:///", "")).resolve() == (
        ROOT / "app" / "overlay" / "index.html").resolve()
    assert plan["core"] == f"http://127.0.0.1:{fake.port}" and plan["tab"] is None
    assert plan["args"][0] == "--headless=new" and plan["args"][-1] == "about:blank"
    assert [p for p, _ in fake.seen] == ["/api/hello", "/api/health", "/api/state"]
    assert not out.exists() and not profile.exists()


@needs_node
def test_a_tab_plan_names_the_tab(preloads, tmp_path):
    fake = FakeCore(tmp_path, "ok")
    out, profile = tmp_path / "shot.png", tmp_path / "profile"
    try:
        r, doc = run_helper(["--plan", sys.executable, str(profile), fake.url, str(out),
                             "--tab=settings"], preloads["no_spawn"])
    finally:
        fake.close()
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert doc["plan"]["tab"] == "settings"
    assert doc["plan"]["url"] == f"http://127.0.0.1:{fake.port}"


def test_the_helper_source_shows_a_tab_only_from_its_frozen_list():
    text = HELPER.read_text(encoding="utf-8")
    tabs = re.search(r"export const TABS = Object\.freeze\(\[(.*?)\]\)", text, re.S)
    assert tabs and re.findall(r'"([^"]+)"', tabs.group(1)) == [
        "play", "build", "run", "settings"]
    assert "if (!TABS.includes(m[2]))" in text
    # the overlay page is the one file target, matched to this repo's app folder
    assert '"app", "overlay", "index.html"' in text
    assert text.count("Page.navigate") == 1


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


@pytest.mark.server
@needs_node
def test_writes_png_of_a_tab_and_of_the_overlay_page(demo_core, tmp_path):
    browser = find_browser()
    if not browser:
        pytest.skip("headless Chrome / Edge not found")
    port, token = demo_core
    core = f"http://127.0.0.1:{port}/#token={token}"
    runs = [("tab", [core, "--tab=settings"]),
            ("overlay", [OVERLAY_URL, f"--core={core}", "--scheme=light"])]
    for name, (page, *extra) in runs:
        out, profile = tmp_path / f"{name}.png", tmp_path / f"profile-{name}"
        r, doc = run_helper([browser, str(profile), page, str(out), "--width=640",
                             "--height=480", *extra], timeout=120)
        assert r.returncode == 0, (name, r.returncode, r.stdout[-2000:], r.stderr[-2000:])
        data = out.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) == doc["bytes"] > 1000
        assert (doc["width"], doc["height"]) == (640, 480)
