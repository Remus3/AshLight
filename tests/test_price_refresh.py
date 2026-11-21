"""DATA-PRICE-REFRESH-CORE (F-036, decision 0026 amendment 2026-11-20): the
core loop starts a due price refresh once a minute while web data is on and
either the log is active or /api/rates was read in the last 10 minutes; the
hourly gates still decide. Idle is Client.txt staleness (decision 0029).

Mocked fetch and clocks only; no request reaches the network.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import ninja, pricerefresh
from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "r" * 48
CONTACT = "test-contact"
LEAGUES = json.dumps([{"id": "Standard", "name": "Standard"}]).encode()
OVERVIEW = json.dumps({
    "core": {"items": [{"id": "divine", "name": "Divine Orb"}],
             "rates": {"exalted": 500.0}, "primary": "divine"},
    "lines": [{"id": "exalted", "primaryValue": 0.002}],
    "items": [{"id": "exalted", "name": "Exalted Orb"}]}).encode()
WALL = 1_800_000_000.0
T0 = 10_000.0  # the loop's monotonic seconds


class FakeNet:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append(url)
        if url.endswith(ninja.LEAGUES_PATH):
            return 200, {}, LEAGUES
        return 200, {}, OVERVIEW


class Clock:
    def __init__(self, t=WALL):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def made(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "local.json").write_text(json.dumps({"web_data": True, "contact": CONTACT,
                                               "league": "Standard"}), encoding="ascii")
    net = FakeNet()
    core = Core(runtime=rt, log_path=str(log), tail=False, web_fetch=net)
    clock = Clock()
    core.rates.clock = clock
    yield core, net, clock
    core.close()


def _active(core, idle=False):
    with core.state._lock:
        core.state.tailer.update(consented=True, idle=idle, last_line_at=WALL)


def _settle():
    for t in threading.enumerate():
        if t.name == "al-ninja":
            t.join(5)


def _tick(core, now):
    started = core.tick_prices(now=now)
    _settle()
    return started


def test_active_log_and_no_http_client_gives_one_round_an_hour(made):
    core, net, clock = made
    _active(core)
    assert _tick(core, T0) is True
    n = len(net.calls)
    assert n > 0 and core.rates.path.is_file()
    assert _tick(core, T0 + 30) is False  # at most one check a minute
    for k in range(1, 60):  # an hour of checks, one a minute
        clock.t = WALL + 60 * k
        assert _tick(core, T0 + 60 * k) is False
    assert len(net.calls) == n  # the hourly gates still decide
    clock.t = WALL + 3601
    assert _tick(core, T0 + 3660) is True
    assert len(net.calls) > n
    assert core.rates_read_at is None  # no page read anything


def test_log_idle_20_minutes_gives_no_request(made):
    core, net, clock = made
    with core.state._lock:
        core.state.tailer.update(consented=True, last_line_at=WALL)
    # decision 0029: 20 quiet minutes turn the log idle (staleness only)
    assert core.state.check_log_idle(now=WALL + 1201) is True
    clock.t = WALL + 1201
    for k in range(0, 30):
        assert _tick(core, T0 + 60 * k) is False
    assert net.calls == []
    # a log never consented to counts as not active too
    with core.state._lock:
        core.state.tailer.update(consented=False, idle=False)
    assert _tick(core, T0 + 3600) is False and net.calls == []


@pytest.mark.server
def test_rates_read_in_the_last_10_minutes_keeps_refreshing(made):
    core, net, clock = made
    _active(core, idle=True)
    # the GET /api/rates arm records the read (and asks for its own refresh)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        conn.request("GET", "/api/rates", headers={"Host": f"127.0.0.1:{server.port}",
                                                   "X-AL-Token": TOKEN})
        assert conn.getresponse().status == 200
        conn.close()
    finally:
        server.stop()
    _settle()
    assert isinstance(core.rates_read_at, float)
    n = len(net.calls)
    assert n > 0  # the page's own read started the first round
    core.note_rates_read(now=T0)
    clock.t = WALL + 3601
    assert _tick(core, T0 + 60) is True  # idle log, read a minute ago
    m = len(net.calls)
    assert m > n
    clock.t = WALL + 2 * 3601
    assert _tick(core, T0 + 540) is True  # still inside the 10 minutes
    assert len(net.calls) > m
    clock.t = WALL + 3 * 3601
    assert _tick(core, T0 + 661) is False  # 11 minutes since the read
    assert _tick(core, T0 + 1300) is False
    # the rule itself
    gate = pricerefresh.Gate()
    assert gate.due(0.0, True, True, -599.0) is True
    assert gate.due(30.0, True, False, None) is False  # inside the minute
    assert gate.due(60.0, True, True, -541.0) is False  # 601 s since the read
    assert gate.due(120.0, True, True, None) is False
    assert gate.due(180.0, True, False, None) is True
    assert gate.due(100.0, True, False, None) is True  # a clock moved back


def test_web_data_off_or_no_contact_never_asks(made):
    core, net, clock = made
    _active(core)
    core.set_web_data(False)
    assert _tick(core, T0) is False
    core.note_rates_read(now=T0 + 60)
    assert _tick(core, T0 + 61) is False
    core.set_contact("")
    core.set_web_data(True)
    assert _tick(core, T0 + 130) is False  # on, but no contact
    assert net.calls == []
    assert core.web_blocked_reason() == "contact not set"
    core.set_web_data(False)
    core.set_contact(CONTACT)  # a contact with web data off asks nothing
    assert _tick(core, T0 + 200) is False
    assert net.calls == []
