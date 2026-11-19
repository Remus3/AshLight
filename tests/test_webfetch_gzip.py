"""DATA-WEBFETCH-GZIP (F-045, F-036): the one outbound path inflates a gzip
body through a size-bounded inflate, maps http.client errors to FetchError
and offers one bounded Retry-After parser. No test touches the network: the
transport is injected or its opener is replaced."""

import email.utils
import gzip
import http.client

import pytest

from server.al import webfetch

HOSTS = ("poe.ninja",)
URL = "https://poe.ninja/poe2/api/x"
UA = {"User-Agent": "AshLight/test"}


def _fetch(status, headers, body):
    def fetch(method, url, hdrs, data=None):
        return status, dict(headers), body
    return fetch


def test_gzip_body_decodes():
    raw = b'{"lines": [1, 2, 3]}' * 50
    gz = gzip.compress(raw)
    status, rh, data = webfetch.request(
        "GET", URL, UA, HOSTS,
        fetch=_fetch(200, {"Content-Encoding": "gzip", "ETag": "x"}, gz))
    assert status == 200 and data == raw
    assert webfetch.header(rh, "Content-Encoding") is None
    assert webfetch.header(rh, "ETag") == "x"
    # identity and absent encodings pass through untouched
    assert webfetch.inflate({"Content-Encoding": "identity"}, raw, 10 ** 6)[1] == raw
    assert webfetch.inflate({}, raw, 10 ** 6) == ({}, raw)
    # x-gzip and case are accepted
    assert webfetch.inflate({"content-encoding": " X-GZIP "}, gz, 10 ** 6)[1] == raw


def test_body_inflating_past_the_cap_is_refused():
    bomb = gzip.compress(b"\0" * (4 * 1024 * 1024))
    assert len(bomb) < 64 * 1024  # small on the wire
    with pytest.raises(webfetch.FetchError, match="too large"):
        webfetch.request("GET", URL, UA, HOSTS, max_bytes=1024 * 1024,
                         fetch=_fetch(200, {"Content-Encoding": "gzip"}, bomb))
    with pytest.raises(webfetch.FetchError, match="too large"):
        webfetch.inflate({"Content-Encoding": "gzip"}, gzip.compress(b"a" * 101), 100)
    # exactly at the cap is fine
    assert webfetch.inflate({"Content-Encoding": "gzip"},
                            gzip.compress(b"a" * 100), 100)[1] == b"a" * 100


@pytest.mark.parametrize("body", [
    b"not gzip at all",
    gzip.compress(b"hello world")[:-6],          # truncated
    gzip.compress(b"hello") + b"junk",           # trailing data
    b"",
])
def test_bad_gzip_stream_is_a_fetch_error(body):
    with pytest.raises(webfetch.FetchError):
        webfetch.request("GET", URL, UA, HOSTS,
                         fetch=_fetch(200, {"Content-Encoding": "gzip"}, body))


def test_unknown_encoding_is_a_fetch_error():
    with pytest.raises(webfetch.FetchError, match="Content-Encoding"):
        webfetch.inflate({"Content-Encoding": "br"}, b"\x00", 100)


@pytest.mark.parametrize("exc", [
    http.client.IncompleteRead(b"partial"),
    http.client.BadStatusLine("garbage"),
    http.client.LineTooLong("header line"),
    http.client.RemoteDisconnected("closed"),
])
def test_http_client_exception_maps_to_fetch_error(monkeypatch, exc):
    class Opener:
        def open(self, req, timeout=None):
            raise exc

    monkeypatch.setattr(webfetch.urllib.request, "build_opener", lambda *a: Opener())
    fetch = webfetch.make_transport()
    with pytest.raises(webfetch.FetchError, match="network"):
        fetch("GET", URL, dict(UA))


def test_http_client_exception_while_reading_maps_to_fetch_error(monkeypatch):
    class Resp:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            raise http.client.IncompleteRead(b"x", 10)

    class Opener:
        def open(self, req, timeout=None):
            return Resp()

    monkeypatch.setattr(webfetch.urllib.request, "build_opener", lambda *a: Opener())
    with pytest.raises(webfetch.FetchError):
        webfetch.make_transport()("GET", URL, dict(UA))


def test_retry_after_seconds_and_date_bounded_1_to_24_h():
    now = 1_800_000_000.0
    ra = webfetch.retry_after_s
    assert ra({}, now) is None
    assert ra({"Retry-After": ""}, now) is None
    assert ra({"Retry-After": "soon"}, now) is None
    assert ra({"Retry-After": "9" * 500}, now) is None  # overlong text
    assert ra({"Retry-After": "-5"}, now) is None
    # delta-seconds, clamped to [1 h, 24 h]
    assert ra({"Retry-After": "7200"}, now) == 7200.0
    assert ra({"retry-after": "30"}, now) == 3600.0
    assert ra({"Retry-After": "0"}, now) == 3600.0
    assert ra({"Retry-After": "999999999"}, now) == 86400.0
    # HTTP-date
    date = email.utils.formatdate(now + 5 * 3600, usegmt=True)
    assert ra({"Retry-After": date}, now) == pytest.approx(5 * 3600, abs=1)
    past = email.utils.formatdate(now - 100, usegmt=True)
    assert ra({"Retry-After": past}, now) == 3600.0
    far = email.utils.formatdate(now + 30 * 86400, usegmt=True)
    assert ra({"Retry-After": far}, now) == 86400.0
    # caller-chosen bounds
    assert ra({"Retry-After": "10"}, now, lo=60, hi=120) == 60.0
    assert ra({"Retry-After": "90"}, now, lo=60, hi=120) == 90.0
