"""SEC-CEIL-WEBFETCH: a total deadline per outbound request.

The socket timeout bounds one silent wait only; a server that trickles one
byte a second never trips it. webfetch bounds the whole read (and the whole
redirect chain) by a total deadline on an injectable clock. No socket here.
"""

import pytest

from server.al import webfetch

URL = "https://poe.ninja/api/x"
HOSTS = ("poe.ninja",)
UA = {"User-Agent": "AshLight test"}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TrickleResp:
    """Yields one byte per read call and advances the clock one second."""

    status = 200
    headers = {}

    def __init__(self, clock, total=10_000):
        self.clock = clock
        self.left = total
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read1(self, n=-1):
        self.reads += 1
        self.clock.t += 1.0
        if self.left <= 0:
            return b""
        self.left -= 1
        return b"x"

    def read(self, n=-1):  # a whole-body read would hang a real trickle
        raise AssertionError("read() must not be used when read1() exists")


def _opener(monkeypatch, resp):
    seen = {}

    class Opener:
        def open(self, req, timeout=None):
            seen["timeout"] = timeout
            return resp

    monkeypatch.setattr(webfetch.urllib.request, "build_opener", lambda *a: Opener())
    return seen


def test_trickle_raises_fetch_error_at_the_total_deadline(monkeypatch):
    clock = Clock()
    resp = TrickleResp(clock)
    _opener(monkeypatch, resp)
    fetch = webfetch.make_transport(deadline=30.0, clock=clock)
    with pytest.raises(webfetch.FetchError, match="deadline"):
        fetch("GET", URL, dict(UA))
    assert clock.t - 1000.0 == pytest.approx(30.0)
    assert resp.reads == 30


def test_default_deadline_is_bounded(monkeypatch):
    clock = Clock()
    resp = TrickleResp(clock)
    seen = _opener(monkeypatch, resp)
    with pytest.raises(webfetch.FetchError, match="deadline"):
        webfetch.make_transport(clock=clock)("GET", URL, dict(UA))
    assert clock.t - 1000.0 == pytest.approx(webfetch.DEADLINE_S)
    assert seen["timeout"] <= webfetch.TIMEOUT_S


def test_fast_body_under_the_deadline_is_returned(monkeypatch):
    clock = Clock()
    resp = TrickleResp(clock, total=5)
    _opener(monkeypatch, resp)
    status, _h, body = webfetch.make_transport(deadline=30.0, clock=clock)(
        "GET", URL, dict(UA))
    assert (status, body) == (200, b"xxxxx")


def test_size_cap_still_applies_while_reading_in_blocks(monkeypatch):
    clock = Clock()
    _opener(monkeypatch, TrickleResp(clock, total=50))
    with pytest.raises(webfetch.FetchError, match="too large"):
        webfetch.make_transport(max_bytes=10, deadline=999.0, clock=clock)(
            "GET", URL, dict(UA))


def test_read_only_response_falls_back_to_read(monkeypatch):
    class Resp:
        status = 200
        headers = {}

        def __init__(self):
            self.parts = [b"ab", b"cd", b""]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return self.parts.pop(0)

    _opener(monkeypatch, Resp())
    assert webfetch.make_transport()("GET", URL, dict(UA))[2] == b"abcd"


def test_request_deadline_spans_the_redirect_chain():
    clock = Clock()
    hops = []

    def slow_redirect(method, url, headers, body=None):
        hops.append(url)
        clock.t += 20.0
        return 302, {"Location": URL + str(len(hops))}, b""

    with pytest.raises(webfetch.FetchError, match="deadline"):
        webfetch.request("GET", URL, UA, HOSTS, fetch=slow_redirect,
                         deadline=30.0, clock=clock)
    assert len(hops) == 2  # the third hop is never started


def test_request_default_transport_shares_one_deadline(monkeypatch):
    clock = Clock()
    _opener(monkeypatch, TrickleResp(clock))
    with pytest.raises(webfetch.FetchError, match="deadline"):
        webfetch.request("GET", URL, UA, HOSTS, deadline=12.0, clock=clock)
    assert clock.t - 1000.0 == pytest.approx(12.0)
