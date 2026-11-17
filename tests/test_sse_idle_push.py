"""TEST-FULLSTACK-SSE-IDLE: a state change with no log line reaches SSE
clients at once (the state-version wake), never only on the heartbeat.

The heartbeat is made LONGER here (never shorter), so only the wake can
carry the change. Covered: the calc turned on / off, a price book refresh,
a trade card expiring and the idle state with the summary card (that last
one also in test_fullstack). No extra timer: the core's loop tick
(tick_summary / tick_sources) is called directly, as __main__ does.
"""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_fullstack import MockNinja, Sse, Stack, Transport  # noqa: E402

from server.al import bus as bus_mod, http as al_http, summary  # noqa: E402
from server.al.state import SessionState, TRADE_EXPIRE_S  # noqa: E402

# Design target ~1 s from the loop tick; the bound leaves room for a loaded
# box and stays far below the (lengthened) heartbeat.
PUSH_S = 3.0


@pytest.fixture
def stack(tmp_path, monkeypatch):
    monkeypatch.setattr(al_http, "SSE_HEARTBEAT_S", 600.0)
    # The stream's own bounded wait (normally 1 s) is lengthened too, so a
    # push inside PUSH_S can only come from the bus wake.
    monkeypatch.setattr(al_http, "SSE_WAIT_MAX_S", 30.0)
    rt = tmp_path / "rt"
    rt.mkdir()
    cfg = rt / "local.json"
    cfg.write_text(json.dumps({"contact": "sse-idle-test-contact"}), encoding="ascii")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    mock = MockNinja()
    st = Stack(rt, log, cfg, Transport(mock))
    sse = Sse(st.port)
    sse.wait(lambda e, d: e == "state", "the first state")
    try:
        yield st, sse, cfg
    finally:
        sse.close()
        st.close()
        mock.close()


def _pushed(sse, pred, what):
    """The first state frame sent from now on that matches pred."""
    t0 = time.monotonic()
    old = {id(f) for f in sse.frames}
    data = sse.wait(lambda e, d: e == "state" and pred(d) and not any(
        f[1] is d for f in sse.frames if id(f) in old), what, timeout=PUSH_S)
    assert time.monotonic() - t0 < PUSH_S
    return data


def test_calc_on_off_is_pushed_at_once(stack):
    st, sse, cfg = stack
    st.core.tc_provider._available = lambda: False  # never start a real calc
    cfg.write_text(json.dumps({"contact": "sse-idle-test-contact", "tc_calc": True}),
                   encoding="ascii")
    assert st.core.tick_sources() is True
    _pushed(sse, lambda d: d["sources"]["calc_on"] is True, "calc on")
    assert st.core.tick_sources() is False  # unchanged: no bump
    cfg.write_text(json.dumps({"contact": "sse-idle-test-contact"}), encoding="ascii")
    assert st.core.tick_sources() is True
    _pushed(sse, lambda d: d["sources"]["calc_on"] is False, "calc off")


def test_price_book_refresh_is_pushed_at_once(stack):
    st, sse, _cfg = stack
    book = st.core.rates.book
    book.doc.setdefault("types", {}).setdefault("Currency", {})["checked_at"] = 1234.5
    st.core.rates.doc["checked_at"] = 1200.0
    st.core.tick_sources()
    data = _pushed(sse, lambda d: d["sources"]["book_checked_at"] == 1234.5,
                   "the price book check time")
    assert data["sources"]["rates_checked_at"] == 1200.0


def test_trade_card_expiry_is_pushed_at_once(stack):
    st, sse, _cfg = stack
    state = st.core.state
    with state._lock:
        state.trade_requests.append(
            {"id": 1, "at": time.time() - TRADE_EXPIRE_S + 0.5, "from": "Buyer"})
        state.version += 1
    _pushed(sse, lambda d: len(d["trade_requests"]) == 1, "the trade card")
    time.sleep(0.6)  # the card is past TRADE_EXPIRE_S now
    st.core.tick_sources()
    _pushed(sse, lambda d: d["trade_requests"] == [], "the trade card gone")


def test_idle_and_summary_are_pushed_at_once(stack):
    st, sse, _cfg = stack
    state = st.core.state
    state.set_tailer(consented=True)
    _pushed(sse, lambda d: d["tailer"]["consented"], "consent")
    with state._lock:
        state.tailer["last_line_at"] = time.time()
        state.stretch.touch(time.time(), state._counters())
    st.core.tick_summary(now=time.time() + summary.IDLE_S + 5)
    data = _pushed(sse, lambda d: d["tailer"]["idle"], "the idle state")
    assert data["session_summary"] is not None


def test_apply_bumps_do_not_wake_but_others_do():
    calls = []
    s = SessionState()
    s.on_change = lambda: calls.append(1)
    s.apply({"type": "afk_changed", "on": True})
    assert calls == []  # pushed with its event, no extra wake
    s.set_tailer(idle=True)
    assert calls == [1]
    s.set_sources(calc_on=False)  # unchanged: no bump, no wake
    assert calls == [1]


def test_wake_is_never_lost():
    b = bus_mod.EventBus()
    sub = b.subscribe()
    b.wake_all()  # before the wait: still seen
    t0 = time.monotonic()
    assert sub.get(timeout=5) == []
    assert time.monotonic() - t0 < 1.0
    done = []
    th = threading.Thread(target=lambda: done.append(sub.get(timeout=5)))
    th.start()
    time.sleep(0.05)
    b.wake_all()
    th.join(2)
    assert done == [[]]
    sub.close()
