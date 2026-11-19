"""TEST-FULLSTACK: one synthetic session through every feature at once.

A real core and its HTTP / SSE server on a free port in 8961-8979, a temp
runtime and a temp config (never the operator's), Client.txt lines from
tools/synth_client.py, and a LOCAL mock poe.ninja (stdlib HTTP server on
127.0.0.1) behind the core's injectable web transport: the core still
builds the real https://poe.ninja URLs and runs them through webfetch's
allowlist; the transport only re-points each checked URL at the mock, so the
mock sees the real request headers (User-Agent, If-None-Match, no Cookie).

Stages: web data OFF (zero outbound requests) -> consent -> log opened ->
campaign acts 1-4 with level-ups, deaths and act splits -> maps with a
portal re-entry (same seed) -> whispers and trades accepted / cancelled ->
item checks (gear, waystone, unique) -> web data ON: price book from the
mock (ETag, conditional requests, hourly cap, truthful User-Agent) -> build
code (calc OFF path) -> 20 minutes of quiet (time-injected) -> idle and the
session summary saved under the temp runtime -> core restart -> resume
rebuilds acts, maps and deaths. The /api/state snapshot and the SSE frames
are checked at each stage. The calc ON leg runs only where the optional calc
component exists (setup.ps1 -TcCalc), else it skips.
"""

import http.client
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import synth_client  # noqa: E402
import tc_eval_fixtures as fx  # noqa: E402
from tc_live_util import BUDGET, free_test_port  # noqa: E402

from server.al import VERSION, http as al_http, ninja, pricebook, summary, webfetch  # noqa: E402
from server.al.core import Core  # noqa: E402
from server.al.http import serve  # noqa: E402
from server.al.theorycraft import codec  # noqa: E402

from fullstack_mocks import (CAMPAIGN, CONTACT, HIDEOUT, LEAGUE, WAYSTONE,  # noqa: E402,F401
                             MockNinja, Transport, campaign_and_maps, trades)

pytestmark = pytest.mark.server
TOKEN = "f" * 48
WAIT_S = 8.0
# TEST-FULLSTACK-SSE-IDLE: the idle state reaches SSE within ~1 s of the
# loop tick (design); the bound leaves room for a loaded box and is still
# far below any heartbeat.
IDLE_PUSH_S = 3.0
EXPECTED_UA = (f"AshLight/{VERSION} (local Path of Exile 2 companion; "
               f"{ninja.UA_PURPOSE}) (contact: {CONTACT})")
N_BOOK = len(pricebook.UNIQUE_TYPES) + len(pricebook.EXCHANGE_TYPES)

# -- core + HTTP / SSE helpers ----------------------------------------------

class Stack:
    def __init__(self, rt, log, cfg, fetch):
        self.core = Core(runtime=rt, log_path=str(log), poll_s=0.02, config_path=cfg,
                         web_fetch=fetch)
        assert self.core.config_path == cfg  # never the operator's config
        self.port = free_test_port()
        self.server = serve(self.core, TOKEN, port=self.port)
        threading.Thread(target=self.server.serve_forever,
                         kwargs={"poll_interval": 0.05}, daemon=True).start()

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
        snap = None
        while time.monotonic() < end:
            snap = self.state()
            if pred(snap):
                return snap
            time.sleep(0.02)
        pytest.fail(f"timed out waiting for {what}; last: "
                    f"{ {k: snap.get(k) for k in ('zone', 'level', 'deaths', 'tailer')} }")

    def close(self):
        self.server.stop()
        self.core.close()


class Sse:
    """A raw SSE client that keeps every frame as (event, data)."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.sock.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{port}"
                           "\r\nAccept: text/event-stream\r\n\r\n").encode())
        self.buf = b""
        self.frames = []

    def _pump(self, deadline):
        self.sock.settimeout(max(0.05, deadline - time.monotonic()))
        try:
            chunk = self.sock.recv(65536)
        except socket.timeout:
            return
        if not chunk:
            raise AssertionError("SSE stream closed")
        self.buf += chunk
        while b"\n\n" in self.buf:
            block, self.buf = self.buf.split(b"\n\n", 1)
            ev, data = None, None
            for line in block.split(b"\n"):
                if line.startswith(b"event: "):
                    ev = line[7:].decode()
                elif line.startswith(b"data: "):
                    data = json.loads(line[6:])
            if ev:
                self.frames.append((ev, data))

    def wait(self, pred, what, timeout=WAIT_S):
        """The first frame (from the start) for which pred(event, data)."""
        end = time.monotonic() + timeout
        seen = 0
        while True:
            for ev, data in self.frames[seen:]:
                if pred(ev, data):
                    return data
            seen = len(self.frames)
            if time.monotonic() > end:
                raise AssertionError(f"SSE never sent {what}")
            self._pump(end)

    def event_types(self):
        return {e["type"] for ev, data in self.frames if ev == "events" for e in data}

    def last_state(self):
        return next((d for ev, d in reversed(self.frames) if ev == "state"), None)

    def close(self):
        self.sock.close()


def append(path, s):
    with open(path, "ab") as fh:
        fh.write(s.text().encode("utf-8"))
    s.lines.clear()


@pytest.fixture
def env(tmp_path):
    rt = tmp_path / "rt"
    rt.mkdir()
    cfg = rt / "local.json"
    cfg.write_text(json.dumps({"contact": CONTACT}), encoding="ascii")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    mock = MockNinja()
    made = []
    out = {"rt": rt, "cfg": cfg, "log": log, "mock": mock,
           "fetch": Transport(mock), "made": made}
    yield out
    for st in made:
        st.close()
    mock.close()


def test_fullstack_session_through_http_and_sse(env, monkeypatch):
    # TEST-FULLSTACK-SSE-IDLE: a state change with no log event (idle, the
    # summary card) is pushed at once by the state-version wake, not by the
    # heartbeat: a LONGER heartbeat proves no beat can carry it.
    monkeypatch.setattr(al_http, "SSE_HEARTBEAT_S", 600.0)
    t_start = time.monotonic()
    rt, log, mock, fetch = env["rt"], env["log"], env["mock"], env["fetch"]
    st = Stack(rt, log, env["cfg"], fetch)
    env["made"].append(st)
    sse = Sse(st.port)
    try:
        # -- stage 0: no consent, web data off
        first = sse.wait(lambda e, d: e == "state", "the first state")
        assert first["tailer"]["consented"] is False and not first["tailer"]["reading"]
        assert st.req("GET", "/api/web-data")[1]["web_data"] is False
        rates = st.req("GET", "/api/rates")[1]
        assert rates["blocked"] == webfetch.REASON_OFF and rates["refreshing"] is False
        status, doc = st.req("POST", "/api/build-code",
                             {"code": "https://pobb.in/AbCdEf123"})
        assert status == 422 and doc["web_data"] is False
        status, doc = st.req("POST", "/api/eval", {"item": fx.UNIQUE_STAFF})
        assert status == 200
        snap = st.state()
        assert snap["price"]["status"] == "link" and snap["price"].get("ninja") is None

        # -- stage 1: consent, then the game writes its log
        status, doc = st.req("POST", "/api/consent", {"consent": True})
        assert status == 200 and doc["consent"]["consented"] is True
        st.wait_for(lambda x: x["tailer"]["reading"], "tailer reading")
        s = synth_client.Session(seed=21, character="Fullstack", klass="Sorceress")
        campaign_and_maps(s)
        trades(s)
        append(log, s)
        snap = st.wait_for(lambda x: x["maps"]["count"] == 2 and len(x["trade_requests"]) == 2,
                           "campaign, maps and two trade cards")
        assert snap["character"] == "Fullstack" and snap["class"] == "Sorceress"
        assert snap["level"] == s.level == 10 and snap["level_ups"] == 9
        assert snap["deaths"] == s.deaths == 3
        assert snap["zone"] == "Sun Temple" and snap["area_id"] == "MapSunTemple"
        assert [r["key"] for r in snap["acts"]["splits"]] == ["G1", "G2", "G3", "G4"]
        assert snap["acts"]["finished"] is True
        assert all(r["ended_at"] is not None for r in snap["acts"]["splits"])
        assert snap["acts"]["splits"][0]["partial"] is False
        maps = snap["maps"]
        # the portal re-entry (same seed) merged into the Crypt run
        assert maps["count"] == 2 and maps["done"] == 1
        assert maps["current"]["name"] == "Sun Temple" and maps["current"]["inside"]
        assert maps["recent"][0]["name"] == "Crypt" and maps["recent"][0]["deaths"] == 1
        assert maps["deaths_text"] == "1 death in maps."
        recap = snap["death_recap"]["recent"]
        assert len(recap) == 3 and recap[0]["zone"] == "Crypt"
        assert [t["from"] for t in snap["trade_requests"]] == ["Firstbuyer", "Secondbuyer"]

        # -- stage 2: trades finish (cancelled closes the oldest, decision 0019)
        s.trade_cancelled()
        append(log, s)
        snap = st.wait_for(lambda x: len(x["trade_requests"]) == 1, "the cancel")
        assert snap["trade_requests"][0]["from"] == "Secondbuyer"
        s.whisper_out("Secondbuyer", "invite sent")
        s.trade_accepted()
        append(log, s)
        snap = st.wait_for(lambda x: not x["trade_requests"], "the accept")
        assert len(snap["recent_whispers"]) == 3
        sse.wait(lambda e, d: e == "events" and any(x["type"] == "trade_accepted" for x in d),
                 "trade_accepted")
        types = sse.event_types()
        for t in ("log_opened", "scene_changed", "area_generated", "level_up", "death",
                  "whisper_in", "whisper_out", "trade_cancelled", "trade_accepted"):
            assert t in types, (t, sorted(types))
        pushed = sse.wait(lambda e, d: e == "state" and d["maps"]["count"] == 2
                          and not d["trade_requests"], "the state after the trades")
        assert pushed["acts"]["finished"] is True

        # -- stage 3: item checks (gear, waystone, unique) with web data off
        status, doc = st.req("POST", "/api/eval", {"item": fx.RARE_GLOVES})
        assert status == 200
        gear = st.state()
        assert gear["eval"]["text"]["head"] and gear["price"]["status"] == "link"
        assert gear["eval"]["at"] == gear["price"]["at"]  # one press, one time
        status, doc = st.req("POST", "/api/eval", {"item": WAYSTONE})
        assert status == 200
        ws = st.state()["eval"]
        assert ws.get("waystone"), ws
        assert ws["text"]["head"] and ws["text"]["sentence"]
        assert fetch.calls == [] and mock.requests == []  # web data off: nothing sent

        # -- stage 4: web data on; the price book comes from the mock
        past = time.time() - ninja.MIN_INTERVAL_S - 100
        st.core.rates.clock = lambda: past  # the first fetch "an hour ago"
        status, doc = st.req("POST", "/api/web-data", {"enabled": True})
        assert status == 200 and doc["web_data"] is True and doc["blocked"] is None
        end = time.monotonic() + WAIT_S
        while time.monotonic() < end and (len(mock.requests) < 2 + N_BOOK
                                          or st.core.rates._busy):
            time.sleep(0.02)
        first_round = list(mock.requests)
        paths = [(r["path"], r["query"].get("type")) for r in first_round]
        assert paths[0] == (ninja.LEAGUES_PATH, None)
        assert paths[1] == (ninja.OVERVIEW_PATH, "Currency")
        assert len(first_round) == 2 + N_BOOK and len(set(paths)) == len(paths)
        for r in first_round:
            assert r["headers"]["user-agent"] == EXPECTED_UA
            assert "cookie" not in r["headers"]
            assert "if-none-match" not in r["headers"]  # nothing cached yet
            if r["path"] != ninja.LEAGUES_PATH:
                assert r["query"]["league"] == LEAGUE
        rates = st.req("GET", "/api/rates")[1]
        assert rates["league"] == LEAGUE and rates["rates"]["divine"]["value"] == 180
        assert rates["last_error"] is None and rates["blocked"] is None
        assert rates["movers"]["up"][0]["name"] == "Example Unique"
        # hourly cap: asking again within the hour sends nothing
        for _ in range(3):
            st.req("GET", "/api/rates")
        time.sleep(0.1)
        assert len(mock.requests) == len(first_round)
        status, doc = st.req("POST", "/api/eval", {"item": fx.UNIQUE_STAFF})
        assert status == 200
        price = st.state()["price"]
        assert price["ninja"]["value"] == 42 and price["ninja"]["league"] == LEAGUE
        assert price["league"] == LEAGUE  # the trade link follows the ninja league
        # an hour later: conditional requests, the mock answers 304
        st.core.rates.clock = time.time
        st.req("GET", "/api/rates")
        end = time.monotonic() + WAIT_S
        while time.monotonic() < end and (len(mock.requests) < len(first_round) + 1 + N_BOOK
                                          or st.core.rates._busy):
            time.sleep(0.02)
        second = mock.requests[len(first_round):]
        assert len(second) == 1 + N_BOOK  # no leagues re-read inside 6 h
        assert all(r["path"] != ninja.LEAGUES_PATH for r in second)
        for r in second:
            assert r["headers"].get("if-none-match", "").startswith('"v1-'), r
            assert r["headers"]["user-agent"] == EXPECTED_UA
        rates = st.req("GET", "/api/rates")[1]
        assert rates["rates"]["divine"]["value"] == 180 and rates["last_error"] is None
        assert rates["age_s"] is not None and rates["age_s"] < 60
        time.sleep(0.1)
        n_after = len(mock.requests)
        st.req("GET", "/api/rates")
        time.sleep(0.1)
        assert len(mock.requests) == n_after  # capped again

        # -- stage 5: build code, calc OFF path (no "tc_calc" in the config)
        status, doc = st.req("POST", "/api/build-code",
                             {"code": codec.encode(fx.EVAL_BUILD_XML)})
        assert status == 200, doc
        snap = st.wait_for(lambda x: x["build"] is not None, "the build summary")
        status, doc = st.req("POST", "/api/eval", {"item": fx.RARE_GLOVES})
        assert status == 200
        card = st.state()["eval"]
        assert card["calc"]["source"] == "weights"  # the calc is off: weights, said so
        assert card["calc"]["notice"]
        sse.wait(lambda e, d: e == "state" and d.get("build") is not None, "the build state")

        # -- stage 6: 20 minutes of quiet (time-injected), then idle
        quiet = time.time() + summary.IDLE_S + 5
        t_idle = time.monotonic()
        saved = st.core.tick_summary(now=quiet)
        assert saved is not None and saved["reason"] == "idle"
        snap = st.state()
        assert snap["tailer"]["idle"] is True
        card = snap["session_summary"]
        assert card["id"] == saved["id"] and card["deaths"] == 3 and card["maps"] == 2
        assert card["level_to"] == 10
        assert any("Example Unique up 61%" in line for line in card["lines"]), card["lines"]
        pushed = sse.wait(lambda e, d: e == "state" and d["tailer"].get("idle"),
                          "the idle state", timeout=IDLE_PUSH_S)
        assert time.monotonic() - t_idle < IDLE_PUSH_S  # pushed now, no heartbeat
        assert pushed["session_summary"]["id"] == saved["id"]
        disk = json.loads((rt / summary.summary_file().name).read_text(encoding="utf-8"))
        assert disk["summaries"][-1]["id"] == saved["id"]
        assert st.core.tick_summary(now=quiet + 60) is None  # saved once
        before = {k: snap[k] for k in ("character", "level", "deaths")}
        acts_before = [r["key"] for r in snap["acts"]["splits"]]
    finally:
        sse.close()

    # -- stage 7: core restart; resume rebuilds acts, maps and deaths
    n_requests = len(mock.requests)
    st.close()
    env["made"].remove(st)
    st2 = Stack(rt, log, env["cfg"], fetch)
    env["made"].append(st2)
    assert st2.core.ensure_tailing(now=time.monotonic()) is True  # the main loop's path
    snap = st2.wait_for(lambda x: x["tailer"].get("resume"), "resume")
    rec = snap["tailer"]["resume"]
    assert rec["hit_marker"] is True
    for k in ("acts", "maps", "deaths", "character", "level"):
        assert k in rec["recovered"], rec
    assert {k: snap[k] for k in before} == before
    assert [r["key"] for r in snap["acts"]["splits"]] == acts_before
    assert snap["acts"]["finished"] is True
    assert snap["maps"]["count"] == 2 and snap["maps"]["done"] == 1
    assert snap["maps"]["recent"][0]["name"] == "Crypt"
    assert snap["maps"]["recent"][0]["deaths"] == 1
    assert len(snap["death_recap"]["recent"]) == 3
    assert snap["death_recap"]["earlier_text"] == ""
    assert snap["session_summary"]["id"] == saved["id"]  # the saved card shows
    assert snap["zone"] == "Sun Temple"
    assert not snap["recent_whispers"] and not snap["trade_requests"]  # never replayed
    # a restart never refetches early (attempt times persisted)
    st2.req("GET", "/api/rates")
    time.sleep(0.1)
    assert len(mock.requests) == n_requests
    assert all(u.startswith(ninja.BASE + "/") for u in fetch.calls)
    # the resumed log is 20+ minutes old: the restarted core turns idle by
    # itself, and no second card is made for the stretch already saved
    later = time.time() + summary.IDLE_S + 5
    assert st2.core.tick_summary(now=later) is None
    snap = st2.state()
    assert snap["tailer"]["idle"] is True
    assert snap["session_summary"]["id"] == saved["id"]
    disk = json.loads((rt / summary.summary_file().name).read_text(encoding="utf-8"))
    assert len(disk["summaries"]) == 1
    # web data turned off again: hours later still nothing is sent, and the
    # cached prices are no longer shown
    assert st2.req("POST", "/api/web-data", {"enabled": False})[1]["web_data"] is False
    st2.core.rates.clock = lambda: time.time() + 3 * ninja.MIN_INTERVAL_S
    rates = st2.req("GET", "/api/rates")[1]
    assert rates["blocked"] == webfetch.REASON_OFF and rates["movers"] == {"up": [], "down": []}
    assert st2.req("POST", "/api/eval", {"item": fx.UNIQUE_STAFF})[0] == 200
    assert st2.state()["price"].get("ninja") is None
    time.sleep(0.1)
    assert len(mock.requests) == n_requests
    import fleet_test_guard  # load-scaled bound (TEST-FLAKE-SSE)
    assert time.monotonic() - t_start < fleet_test_guard.budget(20.0)


def _guard_sockets(monkeypatch):
    """AREA-AUDIT P4-3: record every connect to a non-loopback address and
    every name lookup other than the loopback, below any transport seam, so
    a code path that bypassed the injected fetch would still be seen."""
    seen = []
    real_connect, real_gai = socket.socket.connect, socket.getaddrinfo

    def connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            seen.append(("connect", host))
        return real_connect(self, address)

    def getaddrinfo(host, *a, **k):
        if host not in ("127.0.0.1", "::1", "localhost", None):
            seen.append(("lookup", host))
        return real_gai(host, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return seen


def test_fullstack_web_data_off_sends_nothing(env, monkeypatch):
    """Web data OFF across every feature that could reach the network:
    the mock and the transport see nothing, and no socket leaves the
    loopback (P4-3)."""
    seen = _guard_sockets(monkeypatch)
    st = Stack(env["rt"], env["log"], env["cfg"], env["fetch"])
    env["made"].append(st)
    st.req("POST", "/api/consent", {"consent": True})
    s = synth_client.Session(seed=22, character="Offline", klass="Monk")
    campaign_and_maps(s)
    append(env["log"], s)
    st.wait_for(lambda x: x["maps"]["count"] == 2, "the session")
    for item in (fx.RARE_GLOVES, WAYSTONE, fx.UNIQUE_STAFF, fx.CURRENCY):
        assert st.req("POST", "/api/eval", {"item": item})[0] == 200
    for _ in range(3):
        assert st.req("GET", "/api/rates")[1]["blocked"] == webfetch.REASON_OFF
    assert st.req("POST", "/api/build-code", {"code": "https://pobb.in/AbCdEf123"})[0] == 422
    assert st.req("POST", "/api/build-code",
                  {"code": codec.encode(fx.EVAL_BUILD_XML)})[0] == 200
    st.core.tick_summary(now=time.time() + summary.IDLE_S + 5)
    st.core.tick_sources()
    st.core.tick_calc()
    conn = http.client.HTTPConnection("127.0.0.1", st.port, timeout=10)
    conn.request("GET", "/api/filter", headers={"Host": f"127.0.0.1:{st.port}",
                                                "X-AL-Token": TOKEN})
    r = conn.getresponse()
    body = r.read().decode("ascii")
    conn.close()
    assert r.status == 200 and "Value tiers" not in body  # no prices while off
    assert st.req("GET", "/api/web-data")[1]["web_data"] is False
    time.sleep(0.1)
    assert env["fetch"].calls == [] and env["mock"].requests == []
    assert seen == []


def test_synth_marker_has_the_live_shape():
    """Regression (TEST-FULLSTACK): synth_client wrote the LOG FILE OPENING
    marker with a millisecond counter, a shape the live log never has
    (tests/fixtures/client_live_restart.txt), so the parser saw no
    log_opened and resume found no run start time."""
    from server.al import parser, resume
    s = synth_client.Session(seed=1)
    line = s.marker()
    live = next(ln for ln in (ROOT / "tests" / "fixtures" / "client_live_restart.txt")
                .read_text(encoding="utf-8").splitlines() if "LOG FILE OPENING" in ln)
    assert len(line.split()) == len(live.split())
    ev = parser.parse_line(line)
    assert ev is not None and ev["type"] == "log_opened"
    assert resume._marker_ts(line.encode()) == "2026-11-16T21:00:01"


@pytest.mark.slow
def test_fullstack_calc_on_leg(env, warm_bridge):
    """The calc ON path: "tc_calc" on in the temp config, the PoB reference
    build loaded as a code, one item check scored by PoB. Runs only where
    the optional calc component and the PoB GUI reference exist."""
    from tc_live_util import keep_warm, reference
    from server.al.theorycraft import bridge
    import math_live_items as items
    if not bridge.available() or reference() is None:
        pytest.skip("optional calc component or PoB reference absent (setup.ps1 -TcCalc)")
    _ref, xml = reference()
    env["cfg"].write_text(json.dumps({"contact": CONTACT, "tc_calc": True}), encoding="ascii")
    st = Stack(env["rt"], env["log"], env["cfg"], env["fetch"])
    keep_warm(st.core)  # TEST-FULLSTACK-CALC-WARM: the session's warm bridge
    env["made"].append(st)
    status, doc = st.req("POST", "/api/build-code", {"code": codec.encode(xml)}, timeout=60)
    assert status == 200, doc
    # the first press starts the calc process (decision 0028 budget)
    status, result = st.req("POST", "/api/eval", {"item": items.RING_UPGRADE},
                            timeout=BUDGET["first_press_s"])
    assert status == 200 and result["calc"]["source"] == "pob", result["calc"]
    assert st.state()["eval"]["calc"]["source"] == "pob"
    assert env["fetch"].calls == [] and env["mock"].requests == []
