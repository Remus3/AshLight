"""OVL-TRADE-CANCEL (decision 0019): "Trade accepted." and "Trade
cancelled." close one open trade card. The log lines carry no name, so the
oldest card goes; a counterparty name, if a future line carries one, picks
the matching card instead. Fake clock only."""

import srcpaths
from server.al.parser import parse_line
from server.al.state import SessionState


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _trade(sender):
    return {"type": "whisper_in", "from": sender, "text": "Hi",
            "trade": {"kind": "item", "item": "Ring", "price_amount": 1,
                      "price_currency": "exalted"}}


def _open(st):
    return [r["from"] for r in st.snapshot()["trade_requests"]]


def _state(*senders):
    clock = Clock()
    st = SessionState(clock=clock)
    for s in senders:
        st.apply(_trade(s))
        clock.t += 10
    return st


def test_accepted_drops_the_oldest_card():
    st = _state("A", "B", "C")
    v = st.snapshot()["version"]
    assert st.apply({"type": "trade_accepted"}) is True
    assert _open(st) == ["B", "C"]
    assert st.snapshot()["version"] > v


def test_cancelled_drops_the_oldest_card():
    st = _state("A", "B")
    assert st.apply({"type": "trade_cancelled"}) is True
    assert _open(st) == ["B"]


def test_parsed_log_lines_close_cards():
    st = _state("A", "B")
    st.apply(parse_line("2026/11/17 10:00:00 1 2 [INFO Client 3] : Trade accepted."))
    assert _open(st) == ["B"]
    st.apply(parse_line("2026/11/17 10:00:01 1 2 [INFO Client 3] : Trade cancelled."))
    assert _open(st) == []


def test_named_counterparty_drops_that_card():
    st = _state("A", "B", "C")
    st.apply({"type": "trade_accepted", "name": "B"})
    assert _open(st) == ["A", "C"]


def test_unknown_name_falls_back_to_the_oldest():
    st = _state("A", "B")
    st.apply({"type": "trade_cancelled", "name": "Nobody"})
    assert _open(st) == ["B"]


def test_no_open_card_changes_nothing_but_the_list():
    st = _state()
    v = st.snapshot()["version"]
    # trade_accepted is a listed event, so the snapshot still moves once.
    assert st.apply({"type": "trade_accepted"}) is True
    assert _open(st) == []
    assert st.snapshot()["version"] == v + 1
    v = st.snapshot()["version"]
    # trade_cancelled is not listed: no open card means no change at all.
    assert st.apply({"type": "trade_cancelled"}) is False
    assert st.snapshot()["version"] == v


def test_accepted_line_stays_in_recent_events():
    st = _state("A")
    st.apply({"type": "trade_accepted", "seq": 9})
    texts = [r["text"] for r in st.snapshot()["recent_events"]]
    assert texts[-1] == "Trade accepted"


def test_dashboard_loads_the_trade_helper():
    # UX-REVIEW F6, PLAY-LEGACY-OUT-1: region T (web/feed.js) carries the
    # new-trade sentence in its own polite region; web/trades.js, the old
    # #trades card and its #trade-status region are gone.
    html = srcpaths.index_html()
    assert "/web/trades.js" not in html
    for gone in ('id="trades"', 'id="trade-status"', 'id="trade-list"', 'id="trade-clear"'):
        assert gone not in html, gone
    tag = '<script src="/web/feed.js" defer></script>'
    assert tag in html
    assert html.index(tag) < html.index('<script src="/web/app.js" defer></script>')
    feed = srcpaths.read("feed.js")
    assert 'status.setAttribute("aria-live", "polite")' in feed
    assert "showStatus(ui.status, prev, m.open)" in feed
    app = srcpaths.read("app.js")
    assert "showStatus" not in app and "ALTrades" not in app
