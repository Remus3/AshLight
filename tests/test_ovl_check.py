"""OVL-CHECK (F-128, ruling Q-18, budget B19): tools/ovl_check.py against a
stub core.

The stub is a stdlib http.server on a free loopback port (never 8960) that
answers the hello proof and serves fixture /api/state documents for a
synthetic map session. AL_SIDECAR_ROOT and AL_RUNTIME_DIR point at tmp_path;
no real core, no app, no Client.txt. The tool runs on a fake clock: it waits
20 s into the open map, plays the nine 30 s blocks hidden / shown /
updating, writes the JSON report and the 15-line summary under the sidecar
Logs dir, restores the player's layout and clears its armed flag.
"""

import importlib.util
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ovl_check  # noqa: E402
from server.al import hello, layout, paths, ports  # noqa: E402
from server.al import http as al_http  # noqa: E402
from server.al import plug  # noqa: E402

TOOL = ROOT / "tools" / "ovl_check.py"
TOKEN = "t0k3n-ovl-check-test-0123456789abcdef"


class FakeClock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class Stub:
    """The fixture core: state documents, the layout, debug figures."""

    def __init__(self, clock, map_after=3, verdict=None):
        self.clock = clock
        self.calls = []
        self.state_calls = 0
        self.map_after = map_after
        self.layout = layout.normalize({"opacity": 0.9, "v": 2})
        self.layout["parts"]["hint"] = False  # the player's own choice
        self.layout_posts = []
        self.samples = 0
        self.cpu_s = 10.0
        self.verdict = verdict
        self.lock = threading.Lock()

    def state(self):
        self.state_calls += 1
        inside = self.state_calls > self.map_after
        return {"game_idle": False,
                "maps": {"current": {"inside": inside, "deaths": 0} if inside else None}}

    def debug(self):
        self.cpu_s += 0.003  # 0.3 percent of a core at one call a second
        return {"process": {"cpu_s": round(self.cpu_s, 6), "working_set_mb": 60.0}}


def _handler(stub):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, doc):
            data = json.dumps(doc).encode("ascii")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _auth(self, path):
            if path == hello.PATH:
                return hello.check_client(TOKEN, self.headers.get(hello.NONCE_HEADER),
                                          self.headers.get(hello.PROOF_HEADER))
            return self.headers.get("X-AL-Token") == TOKEN

        def do_GET(self):
            path = urlsplit(self.path).path
            with stub.lock:
                stub.calls.append(("GET", path))
                if not self._auth(path):
                    return self._send(401, {"error": "token required"})
                if path == hello.PATH:
                    return self._send(200, hello.answer(
                        TOKEN, self.headers.get(hello.NONCE_HEADER),
                        self.server.server_address[1]))
                if path == "/api/state":
                    return self._send(200, stub.state())
                if path == "/api/debug":
                    return self._send(200, stub.debug())
                if path == "/api/overlay-layout":
                    return self._send(200, {"layout": stub.layout, "limits": {
                        "opacity": [layout.OPACITY_MIN, layout.OPACITY_MAX]}})
                if path == "/api/verdicts":
                    rows = [stub.verdict] if stub.verdict else []
                    return self._send(200, {"rows": rows})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            path = urlsplit(self.path).path
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
            with stub.lock:
                stub.calls.append(("POST", path))
                if not self._auth(path):
                    return self._send(401, {"error": "token required"})
                assert self.headers.get("Content-Type") == "application/json"
                if path == "/api/overlay-layout":
                    merged = dict(stub.layout)
                    merged.update(body)
                    stub.layout = layout.normalize(merged)  # strict, as the core
                    stub.layout_posts.append(body)
                    return self._send(200, {"layout": stub.layout})
                if path == "/api/overlay-sample":
                    stub.samples += 1
                    return self._send(200, {"card": {}})
            return self._send(404, {"error": "not found"})
    return H


@pytest.fixture
def env(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "token").write_text(TOKEN, encoding="ascii")
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "sidecar"))
    monkeypatch.setenv(paths.RUNTIME_ENV, str(runtime))
    hello.forget()
    clock = FakeClock()
    stubs = []

    def start(**kw):
        stub = Stub(clock, **kw)
        srv = ThreadingHTTPServer((ports.LOOPBACK, 0), _handler(stub))
        assert srv.server_address[1] != ports.AL_PORT
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        stubs.append(srv)
        return stub, srv.server_address[1]

    def checker(port, **kw):
        return ovl_check.Checker(port, runtime=runtime, clock=clock, sleep=clock.sleep,
                                 wall=clock, system=FakeSystem(clock), **kw)

    yield {"start": start, "checker": checker, "clock": clock, "runtime": runtime,
           "logs": tmp_path / "sidecar" / "Logs"}
    for srv in stubs:
        srv.shutdown()
        srv.server_close()
    hello.forget()


class FakeSystem:
    """System-wide totals that rise 10 percent busy on a 4-CPU box."""

    def __init__(self, clock):
        self.clock = clock

    def __call__(self):
        total = self.clock() * 4
        return total * 0.9, total


def _arm(clock):
    ovl_check._write(ovl_check.ARMED_FILE,
                     {"armed_at": clock(), "expires_at": clock() + ovl_check.ARM_TTL_S})


@pytest.mark.slow  # wave 30 ruling: over the 3 s ceiling under parallel load
def test_full_check_on_a_fake_clock(env):
    stub, port = env["start"]()
    clock = env["clock"]
    _arm(clock)
    # a client figure file, fresh on the fake clock (app/metrics.js schema 1)
    import datetime
    upd = datetime.datetime.fromtimestamp(clock() + 30, datetime.timezone.utc)
    (env["runtime"] / "overlay-state.json").write_text(json.dumps({
        "schema": 1, "updated": upd.isoformat().replace("+00:00", "Z"),
        "processes": 2, "working_set_kb": 150000, "private_kb": 90000,
        "cpu_pct": 0.4, "overlay_shown": True, "companion_open": False,
        "by_type": {"tab": {"count": 1, "cpu_pct": 0.3}}}), encoding="ascii")
    out = []

    class W:
        def write(self, s):
            out.append(s)
    chk = env["checker"](port, ask=lambda: "same", out=W())
    t_start = clock()
    path = ovl_check.run(chk)
    assert path is not None and path.parent == env["logs"]

    # waited for the map (3 out-of-map polls), then 20 s inside before block 1
    assert stub.state_calls > 3
    elapsed = clock() - t_start
    assert elapsed >= ovl_check.WARMUP_S + 9 * ovl_check.BLOCK_S

    rep = json.loads(path.read_text(encoding="ascii"))
    assert [b["kind"] for b in rep["blocks"]] == ["hidden", "shown", "updating"] * 3
    for b in rep["blocks"]:
        assert b["samples"] == 30
        assert b["core_cpu_pct"] == pytest.approx(0.3, abs=0.02)
        assert b["system_cpu_pct"] == pytest.approx(10.0, abs=0.01)
    assert rep["answer"] == "same" and rep["answer_source"] == "prompt"
    assert rep["layout_restored"] is True
    assert rep["b19"]["verdict"] == "pass"
    assert rep["b19"]["system_within_noise"] is True
    assert "proxy" in rep["note"]

    summary = (env["logs"] / (rep["name"] + ".txt")).read_text(encoding="ascii")
    lines = summary.splitlines()
    assert len(lines) == ovl_check.SUMMARY_LINES == 15
    assert lines[0].startswith("ovl_check: pass")
    assert "".join(out).splitlines() == lines

    # the armed flag, the runner file and the restore copy are gone
    assert not (env["logs"] / ovl_check.ARMED_FILE).exists()
    assert not (env["logs"] / ovl_check.RUNNER_FILE).exists()
    assert not (env["logs"] / ovl_check.RESTORE_FILE).exists()

    # hidden turned every part off; the player's saved layout is back
    assert stub.layout_posts[0] == {"parts": {p: False for p in layout.PARTS}}
    assert stub.layout["parts"]["hint"] is False and stub.layout["parts"]["zone"] is True
    assert stub.layout["opacity"] == 0.9
    nudges = [p["opacity"] for p in stub.layout_posts if set(p) == {"opacity"}]
    assert 0.92 in nudges and all(layout.OPACITY_MIN <= v <= layout.OPACITY_MAX
                                  for v in nudges)
    assert stub.samples == 9  # 3 sample cards per updating block


@pytest.mark.slow  # wave 30 ruling: over the 3 s ceiling under parallel load
def test_only_existing_endpoints_are_called(env):
    stub, port = env["start"]()
    _arm(env["clock"])
    ovl_check.run(env["checker"](port, ask=lambda: "dropped"))
    used = set(stub.calls)
    assert used
    for verb, path in used:
        table = {"GET": al_http.GET_ROUTES, "POST": al_http.POST_ROUTES}[verb]
        assert al_http.route_for(table, path) is not None or \
            plug.route(verb, path) is not None, (verb, path)
    # the token never travels before the listener proved it holds it
    assert stub.calls[0] == ("GET", hello.PATH)


def test_answer_from_the_tried_in_game_card(env):
    clock = env["clock"]
    stub, port = env["start"](verdict=None)
    _arm(clock)
    chk = env["checker"](port, answer_wait_s=60)
    # the card's verdict lands while the tool waits
    orig_sleep = chk.sleep

    def sleep(s):
        orig_sleep(s)
        if stub.verdict is None and (env["logs"] / ovl_check.ARMED_FILE).exists() is False:
            stub.verdict = {"check": "OVL-FPS", "result": "refused", "note": "",
                            "at": int(clock())}
    chk.sleep = sleep
    path = ovl_check.run(chk)
    rep = json.loads(path.read_text(encoding="ascii"))
    assert rep["answer"] == "dropped" and rep["answer_source"] == "card"
    assert rep["b19"]["verdict"] == "fail"


@pytest.mark.slow  # wave 30 ruling: over the 3 s ceiling under parallel load
def test_stale_card_verdict_is_ignored_and_answer_command_records(env, capsys):
    clock = env["clock"]
    old = {"check": "OVL-FPS", "result": "worked", "note": "", "at": int(clock()) - 3600}
    stub, port = env["start"](verdict=old)
    _arm(clock)
    path = ovl_check.run(env["checker"](port, answer_wait_s=30))
    rep = json.loads(path.read_text(encoding="ascii"))
    assert rep["answer"] is None and rep["b19"]["verdict"] == "pending"
    assert ovl_check.main(["answer", "same"]) == 0
    rep = json.loads(path.read_text(encoding="ascii"))
    assert rep["answer"] == "same" and rep["answer_source"] == "command"
    assert rep["b19"]["verdict"] == "pass"
    assert ovl_check.main(["status"]) == 0
    text = capsys.readouterr().out
    assert "armed: no" in text and "answer: same" in text


def test_map_must_stay_open_20_s(env):
    stub, port = env["start"](map_after=0)
    chk = env["checker"](port)
    _arm(env["clock"])
    seq = iter([True, True, False, True, True, True, True, True, True, True, True,
                True, True, True, True])
    stub.state = lambda: {"maps": {"current": {"inside": next(seq, True)}}}
    t0 = env["clock"]()
    assert chk.wait_for_map() is True
    # the out-of-map poll at 4 s restarted the 20 s count
    assert env["clock"]() - t0 >= 6 + ovl_check.WARMUP_S


def test_disarmed_run_ends_without_touching_the_layout(env):
    stub, port = env["start"](map_after=10 ** 6)
    clock = env["clock"]
    ovl_check._write(ovl_check.ARMED_FILE, {"armed_at": clock(), "expires_at": clock() + 10})
    assert ovl_check.run(env["checker"](port)) is None
    assert stub.layout_posts == []
    assert not list(env["logs"].glob("ovl_check-*.json"))


def test_layout_restored_after_a_core_error(env):
    stub, port = env["start"]()
    _arm(env["clock"])
    chk = env["checker"](port)
    calls = {"n": 0}
    real = stub.debug

    def flaky():
        calls["n"] += 1
        if calls["n"] == 40:  # inside block 2
            raise RuntimeError("core hiccup")
        return real()
    stub.debug = flaky
    with pytest.raises(ovl_check.CoreGone):
        assert chk.wait_for_map()
        chk.run_blocks()
    assert stub.layout["parts"] == dict(layout.DEFAULT["parts"], hint=False)
    assert not (env["logs"] / ovl_check.RESTORE_FILE).exists()


def test_leftover_restore_copy_is_put_back(env):
    stub, port = env["start"]()
    saved = dict(stub.layout)
    stub.layout = layout.normalize(dict(saved, parts={p: False for p in layout.PARTS}))
    ovl_check._write(ovl_check.RESTORE_FILE, {"layout": saved})
    assert env["checker"](port).restore_leftover() is True
    assert stub.layout == saved
    assert not (env["logs"] / ovl_check.RESTORE_FILE).exists()


def test_arm_writes_the_flag_and_starts_one_runner(env):
    started = []
    args = ovl_check.build_parser().parse_args(["arm", "--port", "8961"])

    class W:
        def write(self, s):
            pass
    assert ovl_check.cmd_arm(args, W(), wall=env["clock"], spawn=started.append) == 0
    assert started == [8961]
    assert ovl_check.armed(env["clock"]())
    assert not ovl_check.armed(env["clock"]() + ovl_check.ARM_TTL_S + 1)


def test_reports_stay_in_the_sidecar(env):
    logs = ovl_check.logs_dir()
    assert logs == paths.sidecar_dir("Logs")
    assert Path(logs).resolve().is_relative_to(env["logs"].parent.resolve())


# -- static scans
def _floor_banned():
    spec = importlib.util.spec_from_file_location(
        "_floor_static_for_ovl", ROOT / "tests" / "test_floor_static.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.BANNED


def test_tool_holds_the_floor():
    text = TOOL.read_text(encoding="ascii")
    hits = [name for name, rx in _floor_banned() if rx.search(text)]
    assert hits == []
    # no counter keyed to another process, no process or window look-up,
    # no screen capture, no input
    other = re.compile(
        r"OpenProcess|CreateToolhelp32Snapshot|EnumProcesses|Process32|psutil"
        r"|GetProcessTimes|list_processes|overlay_pids|is_ours|tasklist|wmic"
        r"|FindWindow|EnumWindows|GetForegroundWindow|typeperf|Get-Counter"
        r"|Get-Process|nvidia-smi|screenshot|PostMessage|SendMessage", re.I)
    assert other.findall(text) == []
    assert "Client.txt" not in text.replace("no Client.txt", "")


def test_no_measurement_only_code_under_app_or_server():
    words = re.compile(r"ovl_check|ovl-check|GetSystemTimes|/proc/stat")
    hits = []
    for top in ("app", "server", "web"):
        for p in (ROOT / top).rglob("*"):
            if not p.is_file() or "node_modules" in p.parts or "__pycache__" in p.parts:
                continue
            if p.suffix not in {".py", ".js", ".mjs", ".cjs", ".html", ".json", ".css"}:
                continue
            if words.search(p.read_text(encoding="utf-8", errors="replace")):
                hits.append(str(p.relative_to(ROOT)))
    assert hits == []
