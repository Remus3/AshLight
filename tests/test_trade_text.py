"""UI-REVIEW-2 (design 0003 F4): every open trade card in the snapshot
carries its sentence ("text") and stash position ("where"), built by the
one section 9 template, so the dashboard never assembles trade wording
itself (no "undefined" from a missing field)."""

from server.al.state import SessionState


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _card(trade, sender="Quietfox"):
    st = SessionState(clock=Clock())
    ev = {"type": "whisper_in", "text": "Hi", "trade": trade}
    if sender is not None:
        ev["from"] = sender
    st.apply(ev)
    rows = st.snapshot()["trade_requests"]
    assert len(rows) == 1
    return rows[0]


def test_priced_card_text_and_where():
    row = _card({"kind": "item", "item": "Plain Belt", "price_amount": 5,
                 "price_currency": "exalted", "stash_tab": "Sale", "left": 3,
                 "top": 7})
    assert row["text"] == "Quietfox wants Plain Belt - 5 exalted"
    assert row["where"] == "tab Sale (3,7)"


def test_unpriced_card_without_position():
    row = _card({"kind": "item", "item": "Ring", "stash_tab": "Sale"})
    assert row["text"] == "Quietfox wants Ring - no price set"
    assert row["where"] == "tab Sale"


def test_exchange_card_with_missing_amounts_reads_honestly():
    row = _card({"kind": "exchange", "item": "Chaos Orb",
                 "price_currency": "divine"})
    assert row["text"] == "Quietfox wants Chaos Orb - no price set"
    assert "undefined" not in row["text"] and "None" not in row["text"]
    assert row["where"] == ""


def test_exchange_card_full():
    row = _card({"kind": "exchange", "item": "Chaos Orb", "want_amount": 10,
                 "price_amount": 1, "price_currency": "Divine Orb"})
    assert row["text"] == "Quietfox wants 10 Chaos Orb - for 1 Divine Orb"


def test_missing_sender_reads_unknown_player():
    row = _card({"kind": "item", "item": "Ring"}, sender=None)
    assert row["text"] == "Unknown player wants Ring - no price set"
