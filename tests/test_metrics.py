"""RUN-METRICS-CORE (finding F-032, decision 0067): server/al/metrics.py
and the token-gated GET /api/debug (server/al/plug/debug.py).

No socket, process, registry or network call: requests run through
http.Handler on in-memory streams, the tailer is polled by hand on a tmp
file, and the own-process read is faked.
"""

import io
import json
import re
import threading
import time

import pytest

from ci_timing import skip_if_ci_timing
from server.al import http as al_http
from server.al import logfile, metrics, parser, plug
from server.al.core import Core
from server.al.plug import debug
from srcpaths import ROOT

TOKEN = "t" * 48
HOST = "127.0.0.1:8961"
FIXTURE = ROOT / "tests" / "fixtures" / "client_sample.txt"
# a Windows-style path, built from parts (the leak sweep refuses literals)
DRIVE = "Q" + ":"
WIN_PATH = DRIVE + "\\" + "zzqhome" + "\\" + "zzq"
FAKE_PROC = {"working_set_mb": 42.0, "cpu_s": 1.5, "threads": 7}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    metrics.reset()
    monkeypatch.setattr(metrics, "own_process", lambda: dict(FAKE_PROC))
    yield
    metrics.reset()


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    yield c
    c.close()


class FakeServer:
    """What Handler reads of its server, with no socket bound."""

    def __init__(self, core):
        self.core = core
        self.token = TOKEN
        self.allowed_hosts = {HOST, "localhost:8961"}
        self.allowed_origins = {f"http://{h}" for h in self.allowed_hosts}
        self.events_tap = False
        self.stopping = threading.Event()
        self.sse_slots = threading.BoundedSemaphore(al_http.MAX_SSE_CLIENTS)


def call(core, method, path, headers=None, handler=al_http.Handler):
    """One request through the real Handler on in-memory streams; returns
    (status, body bytes)."""
    lines = [f"{method} {path} HTTP/1.1", f"Host: {HOST}", "Connection: close"]
    lines += [f"{k}: {v}" for k, v in (headers or {}).items()]
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")

    class H(handler):
        def setup(self):
            self.connection = None
            self.rfile = io.BytesIO(raw)
            self.wfile = io.BytesIO()

        def finish(self):
            H.out = self.wfile.getvalue()

    H(None, ("127.0.0.1", 50000), FakeServer(core))
    head, _, body = H.out.partition(b"\r\n\r\n")
    return int(head.split(b" ", 2)[1]), body


def auth():
    return {"X-AL-Token": TOKEN}


def get_debug(core):
    status, body = call(core, "GET", debug.PATH, auth())
    assert status == 200
    return json.loads(body), body


# -- the named tests ----------------------------------------------------------

def test_lines_read_equals_events_plus_ignored_after_replay(core, tmp_path):
    sample = FIXTURE.read_text(encoding="ascii").splitlines()
    junk = ["not a log line", "2026/11/19 10:00:00 12345 abc [INFO Client 1] zzq nothing",
            "\x00\x01 binary-ish", ""]
    lines = sample + junk + sample[:5]
    log = tmp_path / "replay.txt"
    log.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    tailer = logfile.Tailer(log, core.feed_line, core._on_status, start_at_end=False)
    core.tailer = tailer
    while tailer.poll_once():
        pass
    doc, _ = get_debug(core)
    nonempty = [ln for ln in lines if ln]
    expected_events = len(parser.parse_lines(nonempty))
    assert doc["tailer"]["lines"] == len(nonempty) == doc["lines"]["fed"]
    assert doc["tailer"]["running"] is False and doc["tailer"]["bytes"] > 0
    assert doc["events"]["log"] == expected_events
    assert doc["lines"]["ignored"] >= 3 and doc["lines"]["failed"] == 0
    assert doc["tailer"]["lines"] == (doc["events"]["log"] + doc["lines"]["ignored"]
                                      + doc["lines"]["failed"])
    # every Client.txt event is counted by its type too (tailer status
    # events come on top)
    by_type = sum(v for k, v in doc["events"].items() if k not in ("log", "other"))
    assert by_type >= expected_events
    core.tailer = None


def test_sse_gauge_goes_0_1_0(core, monkeypatch):
    monkeypatch.setattr(al_http, "SSE_WAIT_MAX_S", 0.01)
    assert get_debug(core)[0]["sse"]["subscribers"] == 0
    seen = []

    class Stream(al_http.Handler):
        def _sse_write(self, text):
            seen.append(debug.body(self.server.core)["sse"]["subscribers"])
            super()._sse_write(text)

        def _client_gone(self):
            return True  # the client leaves after the first frames

    status, body = call(core, "GET", "/events", auth(), handler=Stream)
    assert status == 200 and b"event: state" in body
    assert seen and set(seen) == {1}
    doc = get_debug(core)[0]
    assert doc["sse"]["subscribers"] == 0
    assert doc["sse"]["frames"] == len(seen)
    assert doc["sse"]["bytes"] > 0
    assert doc["http"]["replies"]["/events"] == {"2xx": 1}


def test_debug_needs_token_and_is_not_in_snapshot(core):
    assert ("GET", debug.PATH) in plug.all_routes()
    for headers in ({}, {"X-AL-Token": "wrong"}, {"Authorization": "Bearer wrong"}):
        status, body = call(core, "GET", debug.PATH, headers)
        assert status == 401 and json.loads(body) == {"error": "token required"}
    # ?token= opens /events only, never an /api route
    assert call(core, "GET", f"{debug.PATH}?token={TOKEN}")[0] == 401
    assert call(core, "POST", debug.PATH, auth())[0] == 404  # GET only
    doc, _ = get_debug(core)
    assert doc["http"]["unauthorized"] == 4
    # the reply being built is counted once it is sent
    assert doc["http"]["replies"][debug.PATH] == {"4xx": 5}
    assert get_debug(core)[0]["http"]["replies"][debug.PATH] == {"4xx": 5, "2xx": 1}
    # pull only: not in the snapshot (and so not in any SSE state frame)
    snap = json.dumps(core.state.snapshot())
    for word in ("working_set", "unauthorized", "sse.frames", "lines.fed", "uptime_s",
                 "/api/debug", "tick_ms"):
        assert word not in snap, word
    status, body = call(core, "GET", "/api/state", auth())
    assert status == 200 and b"working_set" not in body


def test_debug_body_is_under_4_kb_and_holds_no_path_name_or_pid(core, tmp_path):
    # a log naming a character, a path and a whisper with chat text
    secret = ["2026/11/19 10:00:01 1 abc [INFO Client 98765] : Zzqchar (Warrior) is now level 12",
              "2026/11/19 10:00:02 2 abc [INFO Client 98765] @From Zzqfriend: buy " + WIN_PATH,
              "2026/11/19 10:00:03 3 abc [INFO Client 98765] : Zzqchar has been slain."]
    log = tmp_path / "zzqdir" / "Client.txt"
    log.parent.mkdir()
    log.write_bytes(("\n".join(secret * 40) + "\n").encode("ascii"))
    core.tailer = logfile.Tailer(log, core.feed_line, core._on_status, start_at_end=False)
    while core.tailer.poll_once():
        pass
    # flood every family past its listed size
    for i in range(300):
        metrics.inc(f"event|zzq_type_{i}", i)
        metrics.inc(f"http|/api/zzq-{i}|2xx", i)
        metrics.inc(f"zzq.counter.{i}")
        metrics.timing(f"zzq.ring.{i}", i)
    for i in range(40):
        core.tick_ms[f"tick_zzq_{i}"] = 1.0
    core.tick_all()
    _, raw = get_debug(core)
    assert len(raw) < debug.MAX_BODY
    doc = json.loads(raw)
    assert doc["trimmed"]
    # the named, whispering and dying lines were all read and parsed
    assert doc["lines"]["fed"] == 120 and doc["lines"]["ignored"] == 0
    assert doc["tailer"]["lines"] == 120
    text = raw.decode("ascii")
    for bad in ("Zzqchar", "Zzqfriend", "zzqdir", "zzqhome", "Client.txt", TOKEN,
                str(tmp_path.name), "\\\\", ":\\", '"pid"'):
        assert bad not in text, bad

    def leaves(node):
        if isinstance(node, dict):
            for k, v in node.items():
                assert isinstance(k, str) and re.match(r"[a-z0-9_.:/*|-]+\Z", k), k
                yield from leaves(v)
        elif isinstance(node, list):
            for v in node:
                yield from leaves(v)
        else:
            yield node
    for leaf in leaves({k: v for k, v in doc.items() if k != "trimmed"}):
        assert leaf is None or isinstance(leaf, (bool, int, float)), leaf
        assert leaf != 98765  # the game pid of every line
    core.tailer = None


@pytest.mark.timing
def test_100000_updates_under_50_ms():
    reg = metrics.Registry()
    names = [f"c{i}" for i in range(10)]
    for n in names:  # first use validates the name; time the steady state
        reg.inc(n)
        reg.set_gauge(n, 0)
        reg.timing(n, 0)
    best = None
    for _ in range(3):
        t0 = time.perf_counter()
        for i in range(25_000):
            n = names[i % 10]
            reg.inc(n)
            reg.inc(n, 3)
            reg.set_gauge(n, i)
            reg.timing(n, 0.5)
        elapsed = time.perf_counter() - t0
        best = elapsed if best is None else min(best, elapsed)
    assert reg.counter("c0") == 1 + 3 * 2_500 * 4
    assert len(reg.ring("c0")) == metrics.RING_SIZE
    skip_if_ci_timing("100000 metric updates", f"{best * 1000:.1f} ms")
    assert best < 0.050, f"{best * 1000:.1f} ms"


# -- the rest of the contract -----------------------------------------------

def test_names_are_bounded_and_checked():
    reg = metrics.Registry(max_names=3)
    for bad in ("", "Upper", "a b", "x" * 200, WIN_PATH, None):
        with pytest.raises(ValueError):
            reg.inc(bad)
    for i in range(5):
        reg.inc(f"n{i}")
    assert len([k for k in reg.counters() if k.startswith("n")]) == 3
    assert reg.counter(metrics.DROPPED) == 2
    assert reg.add_gauge("g", 1) == 1 and reg.add_gauge("g", -1) == 0


def test_emit_is_typed_and_reaches_subscribers():
    reg = metrics.Registry()
    got = []
    stop = reg.subscribe(got.append)
    reg.subscribe(lambda rec: 1 / 0)  # a failing subscriber is skipped
    rec = reg.emit("fetch", host="poe.ninja", status="2xx", ms=41.5, ok=True, n=None)
    assert got == [rec] and rec["kind"] == "fetch" and rec["host"] == "poe.ninja"
    assert reg.counter("emit|fetch") == 1 and reg.subscriber_errors == 1
    for bad in ({"text": "free text here"}, {"path": WIN_PATH}, {"who": "Name"},
                {"items": [1]}, {"t": 1}, {"Bad": 1}, {"w": "a/b"}):
        with pytest.raises(ValueError):
            reg.emit("fetch", **bad)
    with pytest.raises(ValueError):
        reg.emit("Bad kind")
    stop()
    reg.emit("fetch", ok=False)
    assert len(got) == 1 and reg.counter("emit|fetch") == 2


def test_ring_stats_and_loop_ring(core):
    core.tick_all()
    core.tick_all()
    ring = metrics.timings().get(debug.LOOP_RING)
    assert ring and ring["n"] == 2
    assert metrics.ring_stats([3.0, 1.0, 2.0]) == {"n": 3, "last": 2.0, "p50": 2.0,
                                                   "max": 3.0}
    doc, _ = get_debug(core)
    assert doc["loop"]["age_s"] is not None and "tick_metrics" in doc["loop"]["tick_ms"]
    assert doc["process"] == FAKE_PROC and doc["tailer"] is None
    assert "trimmed" not in doc  # an ordinary body fits whole


def test_route_label_never_echoes_request_text():
    assert al_http.route_label("/api/state") == "/api/state"
    assert al_http.route_label("/web/app.js") == "/web/*"
    assert al_http.route_label(debug.PATH) == debug.PATH
    for odd in ("/api/zzq-Name", "/" + DRIVE + "/zzqhome/x", "/zzq", "", None):
        assert al_http.route_label(odd) == "other"


# -- RUN-METRICS-SITES: the fetch, calc bridge and press call sites ----------

NINJA_URL = "https://poe.ninja/api/data/zzq?league=Zzq+Name"


class FakeOpener:
    """What webfetch._open_once asks of urllib's opener: open() raises the
    next prepared error (no socket)."""

    def __init__(self, errors):
        self.errors = list(errors)

    def open(self, req, timeout=None):
        raise self.errors.pop(0)


def test_304_and_network_error_land_in_the_right_counters(core, monkeypatch):
    import urllib.error

    from server.al import webfetch
    got = []
    metrics.subscribe(got.append)
    not_modified = urllib.error.HTTPError(NINJA_URL, 304, "Not Modified",
                                          {"ETag": "x"}, io.BytesIO(b""))
    opener = FakeOpener([not_modified, urllib.error.URLError("zzq refused")])
    monkeypatch.setattr(webfetch.urllib.request, "build_opener", lambda *a: opener)
    fetch = webfetch.make_transport()
    status, _, body = fetch("GET", NINJA_URL, {"User-Agent": "AshLight test"})
    assert (status, body) == (304, b"")
    with pytest.raises(webfetch.FetchError):
        fetch("GET", NINJA_URL, {"User-Agent": "AshLight test"})
    assert metrics.counter("fetch|poe.ninja|3xx") == 1
    assert metrics.counter("fetch|poe.ninja|error") == 1
    assert metrics.counters("fetch|") == {"fetch|poe.ninja|3xx": 1,
                                          "fetch|poe.ninja|error": 1}
    assert len(metrics.REGISTRY.ring("fetch_ms")) == 2 and metrics.counter("emit|fetch") == 2
    assert [(r["host"], r["cls"]) for r in got] == [("poe.ninja", "3xx"),
                                                   ("poe.ninja", "error")]
    for rec in got:  # typed values only: never the path, query or error text
        assert set(rec) == {"kind", "t", "host", "cls", "ms"}
        assert "zzq" not in json.dumps(rec)
    # an odd host is never a counter name of its own
    assert webfetch.host_word("https://" + "x" * 70 + ".com/") == "other"
    assert webfetch.status_class(503) == "5xx" and webfetch.status_class(None) == "error"
    doc, raw = get_debug(core)
    assert doc["counters"]["fetch|poe.ninja|3xx"] == 1
    assert doc["timings"]["fetch_ms"]["n"] == 2 and b"zzq" not in raw


def _quiet_bridge(monkeypatch, send):
    """A Bridge whose process parts are stubs: nothing is spawned."""
    from server.al.theorycraft import bridge
    b = bridge.Bridge(["zzq-not-run"], timeout=0.1)
    monkeypatch.setattr(b, "running", lambda: False)
    monkeypatch.setattr(b, "_start", lambda: None)
    monkeypatch.setattr(b, "_replay", lambda timeout: None)
    monkeypatch.setattr(b, "_send", send)
    return bridge, b


def test_calc_timeout_is_counted(core, monkeypatch):
    got = []
    metrics.subscribe(got.append)

    def timed_out(cmd, args, timeout):
        raise bridge.BridgeTimeout("bridge call timed out after 0.1 s")

    bridge, b = _quiet_bridge(monkeypatch, timed_out)
    with pytest.raises(bridge.BridgeTimeout):
        b.request("outputs")
    assert metrics.counter("calc.start") == 1
    assert metrics.counter("calc.timeout") == 1
    assert metrics.counter("calc|timeout") == 1
    assert len(metrics.REGISTRY.ring("calc_ms")) == 1
    assert got[-1]["cmd"] == "outputs" and got[-1]["outcome"] == "timeout"

    def crashed(cmd, args, timeout):
        raise bridge._Crashed("bridge exited (code 1)")

    monkeypatch.setattr(b, "_send", crashed)
    with pytest.raises(bridge.BridgeError):
        b.request("set_item", text="Zzq Name's Item")
    # a crash restarts once, then gives up
    assert metrics.counter("calc.start") == 2 and metrics.counter("calc.restart") == 1
    assert metrics.counter("calc|crash") == 1

    monkeypatch.setattr(b, "_send", lambda cmd, args, timeout: {"pong": True})
    assert b.request("ping") == {"pong": True}
    assert metrics.counter("calc|ok") == 1 and len(metrics.REGISTRY.ring("calc_ms")) == 3
    for rec in got:  # the command only, never the item or build text
        assert set(rec) == {"kind", "t", "cmd", "outcome", "ms"}
        assert "zzq" not in json.dumps(rec).lower()
    doc, _ = get_debug(core)
    assert doc["counters"]["calc.timeout"] == 1 and doc["timings"]["calc_ms"]["n"] == 3


def test_press_outcome_and_ms_are_counted(core, monkeypatch):
    got = []
    metrics.subscribe(got.append)
    core.eval_press("  ")
    core.eval_press("Item Class: Gloves\nRarity: Rare\nZzq Grip\nSuede Bracers\n")
    real = core.last_eval.run

    def broken(*a, **kw):
        raise RuntimeError("zzq")

    monkeypatch.setattr(core.last_eval, "run", broken)
    with pytest.raises(RuntimeError):
        core.eval_press("Item Class: Gloves\nRarity: Rare\nZzq Grip\nSuede Bracers\n")
    monkeypatch.setattr(core.last_eval, "run",
                        lambda text, slot=None, at=None: dict(real(text, slot, at=at),
                                                              ok=True))
    core.eval_press("Item Class: Gloves\nRarity: Rare\nZzq Grip\nSuede Bracers\n")
    assert metrics.counter("press|empty") == 1
    assert metrics.counter("press|unscored") == 1
    assert metrics.counter("press|error") == 1
    assert metrics.counter("press|item") == 1
    ring = metrics.REGISTRY.ring("press_ms")
    assert len(ring) == 4 and all(ms >= 0 for ms in ring)
    assert [r["outcome"] for r in got] == ["empty", "unscored", "error", "item"]
    for rec in got:  # outcome and ms only: never the item text
        assert set(rec) == {"kind", "t", "outcome", "ms"}
        assert "zzq" not in json.dumps(rec).lower()
    doc, raw = get_debug(core)
    assert doc["counters"]["press|empty"] == 1 and doc["timings"]["press_ms"]["n"] == 4
    assert b"zzq" not in raw.lower()
