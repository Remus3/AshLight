"""TC-GGG-LISTENER: the one-shot loopback listener for the OAuth redirect
(decision 0048 item 3). Every real bind is on a leased test port
(tests/tc_live_util.lease_port), never on 8978 or 8979."""

import socket
import threading
import time

import pytest

from server.al import oauthlisten as ol
from server.al import ports
from tc_live_util import leased_port  # noqa: F401  (pytest fixture)

STATE = "s7Qe-2xY_kP9.mN~aB"
CODE = "AbC123-_.~xyz"


def _head(path=None, host=None, method="GET", extra=""):
    return (f"{method} {path} HTTP/1.1\r\nHost: {host}\r\n{extra}"
            "User-Agent: test\r\n\r\n").encode("ascii")


def _good(port, state=STATE, code=CODE):
    return _head(f"{ol.CALLBACK_PATH}?code={code}&state={state}",
                 f"127.0.0.1:{port}")


def _serve(listener):
    out = {}
    th = threading.Thread(target=lambda: out.setdefault("code", listener.wait()),
                          daemon=True)
    th.start()
    return th, out


def _send(port, data, wait_s=5.0):
    with socket.create_connection((ports.LOOPBACK, port), timeout=wait_s) as c:
        c.sendall(data)
        buf = b""
        while True:
            chunk = c.recv(65536)
            if not chunk:
                return buf
            buf += chunk


def _refused(port):
    try:
        with socket.create_connection((ports.LOOPBACK, port), timeout=1.0):
            return False
    except OSError:
        return True


# -- pure request checks -----------------------------------------------------

def test_good_request_yields_only_the_code():
    assert ol.check_request(_good(8964), STATE, 8964) == CODE


@pytest.mark.parametrize("head", [
    _good(8964, state="wrong"),
    _good(8964, state=STATE + "x"),
    _head(f"{ol.CALLBACK_PATH}?code={CODE}", "127.0.0.1:8964"),
    _head(f"{ol.CALLBACK_PATH}?code={CODE}&state={STATE}&state={STATE}",
          "127.0.0.1:8964"),
])
def test_wrong_state_is_refused(head):
    assert ol.check_request(head, STATE, 8964) is None


@pytest.mark.parametrize("path", [
    f"/?code={CODE}&state={STATE}",
    f"/oauth/callback/?code={CODE}&state={STATE}",
    f"/oauth/Callback?code={CODE}&state={STATE}",
    f"/api/state?code={CODE}&state={STATE}",
    f"http://127.0.0.1:8964/oauth/callback?code={CODE}&state={STATE}",
])
def test_wrong_path_is_refused(path):
    assert ol.check_request(_head(path, "127.0.0.1:8964"), STATE, 8964) is None


@pytest.mark.parametrize("host", [
    "localhost:8964", "127.0.0.1:8965", "127.0.0.1", "evil.example:8964",
    "127.0.0.1:8964.evil.example",
])
def test_wrong_host_is_refused(host):
    head = _head(f"{ol.CALLBACK_PATH}?code={CODE}&state={STATE}", host)
    assert ol.check_request(head, STATE, 8964) is None


def test_missing_or_doubled_host_is_refused():
    path = f"{ol.CALLBACK_PATH}?code={CODE}&state={STATE}"
    no_host = f"GET {path} HTTP/1.1\r\nUser-Agent: t\r\n\r\n".encode("ascii")
    assert ol.check_request(no_host, STATE, 8964) is None
    two = _head(path, "127.0.0.1:8964", extra="Host: 127.0.0.1:8964\r\n")
    assert ol.check_request(two, STATE, 8964) is None


@pytest.mark.parametrize("head", [
    _head(f"{ol.CALLBACK_PATH}?code={CODE}&state={STATE}", "127.0.0.1:8964",
          method="POST"),
    _head(f"{ol.CALLBACK_PATH}?state={STATE}", "127.0.0.1:8964"),
    _head(f"{ol.CALLBACK_PATH}?code=&state={STATE}", "127.0.0.1:8964"),
    _head(f"{ol.CALLBACK_PATH}?code=a%20b&state={STATE}", "127.0.0.1:8964"),
    _head(f"{ol.CALLBACK_PATH}?code={'a' * (ol.MAX_CODE + 1)}&state={STATE}",
          "127.0.0.1:8964"),
    _head(f"{ol.CALLBACK_PATH}?code={CODE}&code=x&state={STATE}", "127.0.0.1:8964"),
    _head(f"{ol.CALLBACK_PATH}?error=access_denied&code={CODE}&state={STATE}",
          "127.0.0.1:8964"),
    b"garbage\r\n\r\n",
    "GET /oauth/callback?code=\u00e9 HTTP/1.1\r\n\r\n".encode("utf-8"),
])
def test_bad_method_code_or_shape_is_refused(head):
    assert ol.check_request(head, STATE, 8964) is None


def test_empty_state_never_matches():
    head = _head(f"{ol.CALLBACK_PATH}?code={CODE}&state=", "127.0.0.1:8964")
    assert ol.check_request(head, "", 8964) is None
    with pytest.raises(ValueError):
        ol.OneShotListener("")


# -- the fixed reply page ----------------------------------------------------

def test_reply_page_is_fixed_and_carries_no_secret():
    raw = ol.reply_bytes()
    assert raw == ol.reply_bytes()
    text = raw.decode("ascii").lower()
    for word in ("token", "code", "state", "secret"):
        assert word not in text
    assert "cache-control: no-store" in text
    assert "content-security-policy: default-src 'none'" in text
    assert "connection: close" in text


def test_redirect_uri_names_the_loopback_callback():
    assert ol.redirect_uri(8979) == "http://127.0.0.1:8979/oauth/callback"


# -- port choice (no real bind on the redirect ports) -------------------------

class _FakeSock:
    def __init__(self, port):
        self.port = port

    def getsockname(self):
        return (ports.LOOPBACK, self.port)

    def close(self):
        pass


def test_default_ports_are_the_redirect_constants_in_order(monkeypatch):
    tried = []

    def fake_bind(port):
        tried.append(port)
        if port == ports.OAUTH_REDIRECT_PORTS[0]:
            raise OSError("in use")
        return _FakeSock(port)

    monkeypatch.setattr(ol, "_bind", fake_bind)
    lis = ol.OneShotListener(STATE)
    assert tried == list(ports.OAUTH_REDIRECT_PORTS) == [8979, 8978]
    assert lis.port == 8978
    lis.close()


def test_no_free_redirect_port_raises(monkeypatch):
    def fake_bind(port):
        raise OSError("in use")

    monkeypatch.setattr(ol, "_bind", fake_bind)
    with pytest.raises(ol.ListenerError):
        ol.OneShotListener(STATE)


def test_injected_port_is_the_only_port_tried(monkeypatch):
    tried = []
    monkeypatch.setattr(ol, "_bind", lambda p: tried.append(p) or _FakeSock(p))
    ol.OneShotListener(STATE, port=8966).close()
    assert tried == [8966]


def test_the_module_binds_loopback_from_ports_only():
    from pathlib import Path
    text = Path(ol.__file__).read_text(encoding="ascii")
    assert "sock.bind((ports.LOOPBACK, int(port)))" in text
    for literal in ("8978", "8979", "0.0.0.0", "\"localhost\""):
        assert literal not in text


# -- live: a leased test port -------------------------------------------------

def test_binds_127_0_0_1_only(leased_port):
    assert leased_port not in ports.OAUTH_REDIRECT_PORTS
    with ol.OneShotListener(STATE, port=leased_port, timeout_s=5) as lis:
        assert lis.address == (ports.LOOPBACK, leased_port)
        assert lis.port == leased_port


def test_one_good_request_returns_the_code_then_closes(leased_port):
    lis = ol.OneShotListener(STATE, port=leased_port, timeout_s=10)
    th, out = _serve(lis)
    reply = _send(leased_port, _good(leased_port))
    th.join(10)
    assert not th.is_alive()
    assert out["code"] == CODE
    assert reply == ol.reply_bytes()
    assert CODE.encode() not in reply and STATE.encode() not in reply
    assert lis.closed and _refused(leased_port)


@pytest.mark.parametrize("make", [
    lambda p: _good(p, state="nope"),
    lambda p: _head(f"/elsewhere?code={CODE}&state={STATE}", f"127.0.0.1:{p}"),
    lambda p: _head(f"{ol.CALLBACK_PATH}?code={CODE}&state={STATE}",
                    f"localhost:{p}"),
])
def test_a_wrong_request_gets_the_page_and_closes_with_no_code(leased_port, make):
    lis = ol.OneShotListener(STATE, port=leased_port, timeout_s=10)
    th, out = _serve(lis)
    reply = _send(leased_port, make(leased_port))
    th.join(10)
    assert out["code"] is None
    assert reply == ol.reply_bytes()
    assert lis.closed and _refused(leased_port)


def test_closes_after_the_timeout_with_no_request(leased_port):
    lis = ol.OneShotListener(STATE, port=leased_port, timeout_s=0.3)
    t0 = time.monotonic()
    assert lis.wait() is None
    assert time.monotonic() - t0 < 5
    assert lis.closed and _refused(leased_port)
    assert lis.wait() is None


def test_a_silent_client_times_out(leased_port, monkeypatch):
    monkeypatch.setattr(ol, "READ_TIMEOUT_S", 0.3)
    lis = ol.OneShotListener(STATE, port=leased_port, timeout_s=1.0)
    th, out = _serve(lis)
    with socket.create_connection((ports.LOOPBACK, leased_port), timeout=5):
        th.join(5)
    assert not th.is_alive()
    assert out["code"] is None and lis.closed


def test_an_oversized_request_is_refused(leased_port):
    lis = ol.OneShotListener(STATE, port=leased_port, timeout_s=10)
    th, out = _serve(lis)
    big = _good(leased_port)[:-2] + b"X-Pad: " + b"a" * ol.MAX_REQUEST + b"\r\n\r\n"
    try:
        _send(leased_port, big)
    except OSError:
        pass  # the listener may reset a connection it stopped reading
    th.join(10)
    assert out["code"] is None and lis.closed
