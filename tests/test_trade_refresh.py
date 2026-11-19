"""PLAY-F-120-TRADE-REFRESH (folded into DATA-PRICE-CARD-TEXT): an incoming
trade whisper with the same sender and item text as an open card refreshes
that card (newest at and price fields, same id and place) instead of adding
one; the snapshot no longer carries whisper text (SEC-SSE-TAP); decision
0019 (a finished trade closes one card) is untouched. Fake clock only; names
are invented."""

from server.al.parser import parse_line
from server.al.state import TRADE_EXPIRE_S, SessionState


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _trade(sender, item="Ember Veil", amount=5, currency="exalted", **extra):
    trade = {"kind": "item", "item": item, "price_amount": amount,
             "price_currency": currency, "league": "Dawn"}
    trade.update(extra)
    return {"type": "whisper_in", "from": sender, "text": f"Hi, I would like to buy {item}",
            "trade": trade}


def _rows(st):
    return st.snapshot()["trade_requests"]


def test_three_identical_whispers_and_one_other_leave_two_cards():
    clock = Clock()
    st = SessionState(clock=clock)
    for sender in ("Buyer", "Buyer", "Other", "Buyer"):
        assert st.apply(_trade(sender)) is True
        clock.t += 10
    rows = _rows(st)
    assert [r["from"] for r in rows] == ["Buyer", "Other"]
    # the first card keeps its id and place, with the newest at
    assert rows[0]["id"] == 1 and rows[0]["at"] == 1030.0
    assert rows[1]["at"] == 1020.0
    assert "recent_whispers" not in st.snapshot()


def test_refresh_takes_the_newest_price_fields():
    clock = Clock()
    st = SessionState(clock=clock)
    st.apply(_trade("Buyer", stash_tab="Sale", left=3, top=4))
    clock.t += 5
    v = st.snapshot()["version"]
    st.apply(_trade("Buyer", amount=7, currency="divine"))
    (row,) = _rows(st)
    assert (row["price_amount"], row["price_currency"], row["at"]) == (7, "divine", 1005.0)
    # fields the newest whisper does not carry do not linger
    assert "stash_tab" not in row and "left" not in row and "top" not in row
    assert st.snapshot()["version"] > v


def test_a_different_item_or_sender_adds_a_card():
    st = SessionState(clock=Clock())
    st.apply(_trade("Buyer"))
    st.apply(_trade("Buyer", item="Doom Grip"))
    st.apply(_trade("buyer"))
    assert [(r["from"], r["item"]) for r in _rows(st)] == [
        ("Buyer", "Ember Veil"), ("Buyer", "Doom Grip"), ("buyer", "Ember Veil")]


def test_an_expired_card_is_not_refreshed():
    clock = Clock()
    st = SessionState(clock=clock)
    st.apply(_trade("Buyer"))
    clock.t += TRADE_EXPIRE_S + 1
    st.apply(_trade("Buyer"))
    (row,) = _rows(st)
    assert row["id"] == 2 and row["at"] == clock.t


def test_trade_accepted_still_closes_one_card():
    clock = Clock()
    st = SessionState(clock=clock)
    for sender in ("Buyer", "Buyer", "Other"):
        st.apply(_trade(sender))
        clock.t += 10
    st.apply(parse_line("2026/11/18 10:00:00 1 2 [INFO Client 3] : Trade accepted."))
    assert [r["from"] for r in _rows(st)] == ["Other"]


def test_parsed_whispers_refresh_one_card():
    line = ("2026/11/18 10:00:0{} 1 2 [INFO Client 3] @From Buyer: Hi, I would like to "
            "buy your Ember Veil Silk Robe listed for 5 exalted in Dawn (stash tab "
            "\"Sale\"; position: left 3, top 4)")
    st = SessionState(clock=Clock())
    applied = []
    for i in range(3):
        ev = parse_line(line.format(i))
        assert ev["type"] == "whisper_in" and ev.get("trade"), ev
        applied.append(st.apply(ev))
    assert applied == [True, True, True]
    assert len(_rows(st)) == 1
    assert "recent_whispers" not in st.snapshot()
