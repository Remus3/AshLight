"""DS-TRADE-EXPIRE: a trade request card clears by itself 10 minutes after
it arrived (design 0001 N5); Dismiss still works. Fake clock only."""

import socket
import threading
import time
from pathlib import Path

import srcpaths
from server.al import http as http_mod
from server.al.core import Core
from server.al.state import TRADE_EXPIRE_S, SessionState

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "e" * 48


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _trade(sender):
    return {"type": "whisper_in", "from": sender, "text": "Hi",
            "trade": {"kind": "item", "item": "Ring", "price_amount": 1,
                      "price_currency": "exalted"}}


def test_rule_is_ten_minutes():
    assert TRADE_EXPIRE_S == 600


def test_card_expires_after_ten_minutes():
    clock = Clock()
    st = SessionState(clock=clock)
    st.apply(_trade("A"))
    clock.t += 300
    st.apply(_trade("B"))
    assert [r["from"] for r in st.snapshot()["trade_requests"]] == ["A", "B"]
    clock.t = 1000 + TRADE_EXPIRE_S - 0.5
    assert [r["from"] for r in st.snapshot()["trade_requests"]] == ["A", "B"]
    v = st.snapshot()["version"]
    clock.t = 1000 + TRADE_EXPIRE_S
    snap = st.snapshot()
    assert [r["from"] for r in snap["trade_requests"]] == ["B"]
    assert snap["version"] > v  # the change is pushed like any other
    # A second read with nothing new expiring does not bump the version.
    assert st.snapshot()["version"] == snap["version"]
    clock.t = 1300 + TRADE_EXPIRE_S
    assert st.snapshot()["trade_requests"] == []


def test_expiry_also_runs_on_apply():
    clock = Clock()
    st = SessionState(clock=clock)
    st.apply(_trade("A"))
    clock.t += TRADE_EXPIRE_S + 1
    st.apply(_trade("B"))
    assert [r["from"] for r in st.snapshot()["trade_requests"]] == ["B"]


def test_dismiss_still_works_before_expiry():
    clock = Clock()
    st = SessionState(clock=clock)
    st.apply(_trade("A"))
    rid = st.snapshot()["trade_requests"][0]["id"]
    assert st.dismiss_trade(rid) == 1
    assert st.snapshot()["trade_requests"] == []


def test_dashboard_states_the_rule():
    html = srcpaths.index_html()
    assert "Requests clear after 10 minutes." in html
    assert 'id="trade-clear"' in html  # Dismiss all stays


def test_sse_heartbeat_pushes_a_changed_state(tmp_path, monkeypatch):
    # Expiry happens without a log event, so the heartbeat path must send
    # the new state when the version moved.
    monkeypatch.setattr(http_mod, "SSE_HEARTBEAT_S", 0.2)
    core = Core(runtime=tmp_path / "rt", tail=False)
    server = http_mod.serve(core, TOKEN, port=0, web_root=ROOT / "web",
                            tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever,
                         kwargs={"poll_interval": 0.05}, daemon=True)
    t.start()
    s = None
    try:
        s = socket.create_connection(("127.0.0.1", server.port), timeout=5)
        crlf = "\r\n"
        s.sendall((f"GET /events?token={TOKEN} HTTP/1.1{crlf}"
                   f"Host: 127.0.0.1:{server.port}{crlf}"
                   f"Accept: text/event-stream{crlf}{crlf}").encode())
        buf = b""
        while buf.count(b"event: state") < 1:
            buf += s.recv(65536)
        # A state change with no bus event (what expiry does).
        core.state.set_overlay_layout({"corner": "top-left"})
        deadline = time.monotonic() + 5
        while buf.count(b"event: state") < 2 and time.monotonic() < deadline:
            buf += s.recv(65536)
        assert buf.count(b"event: state") >= 2
        assert b"event: events" not in buf
    finally:
        if s:
            s.close()
        server.stop()
        core.close()
