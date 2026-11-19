"""GP-09 (decision 0080): the core's listen backlog holds a connect burst.

CI saw ERR_CONNECTION_REFUSED on a dashboard load (/events,
/api/overlay-layout). Reproduced here: a server bound and listening but
not yet accepting (a stalled accept loop) gets 50 parallel connects. With
socketserver's default backlog of 5 Windows refuses most of them; with
ALServer's 128 none is refused. Ephemeral port (port=0), 127.0.0.1 only.
"""

import os
import socket
import threading

import pytest

from server.al import http as alhttp

BURST = 50


class _Core:
    """ALServer reads nothing from the core without a web root."""


def _burst(cls, n=BURST):
    srv = cls(_Core(), "a" * 48, port=0)  # bound and listening, never serving
    go = threading.Event()
    lock = threading.Lock()
    out, socks = [], []

    def one():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        go.wait()
        try:
            s.connect(("127.0.0.1", srv.port))
            r = "ok"
        except ConnectionRefusedError:
            r = "refused"
        except OSError as exc:
            r = type(exc).__name__
        with lock:
            out.append(r)
            socks.append(s)

    threads = [threading.Thread(target=one) for _ in range(n)]
    try:
        for t in threads:
            t.start()
        go.set()
        for t in threads:
            t.join(30)
    finally:
        for s in socks:
            s.close()
        srv.server_close()
    return out


def test_alserver_backlog_is_128_and_binds_loopback():
    assert alhttp.ALServer.request_queue_size == 128
    srv = alhttp.ALServer(_Core(), "a" * 48, port=0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
        assert srv.port > 0
    finally:
        srv.server_close()


def test_a_50_connect_burst_on_a_stalled_accept_loop_is_never_refused():
    out = _burst(alhttp.ALServer)
    assert len(out) == BURST
    assert out.count("ok") == BURST, sorted(set(out))


@pytest.mark.skipif(os.name != "nt", reason="Windows refuses on a full backlog")
def test_the_old_backlog_of_5_refuses_the_same_burst():
    """The control: the burst is big enough to show the defect."""
    old = type("Backlog5", (alhttp.ALServer,), {"request_queue_size": 5})
    out = _burst(old)
    assert len(out) == BURST
    assert out.count("refused") > 0, sorted(set(out))
