"""UTIL-SALES-TALLY (research 0064 G8, decision 0088): the session summary
card counts the trades accepted that closed an open trade card (decision
0019 pairing) and adds up their listed prices per currency, labelled an
estimate. In memory on the play stretch; the card keeps counts and sums
only, never an item, a sender or whisper text. Fixture log lines, a fake
clock, tmp runtime; no network, no game."""

import json

import srcpaths  # noqa: F401
from server.al import summary
from server.al.parser import parse_line
from server.al.state import SessionState
from server.al.text.events import sales_line


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _line(body, n):
    return "2026/11/27 10:%02d:00 1 2 [INFO Client 3] %s" % (n, body)


def _buy(sender, item, amount, cur, tab="Shop7"):
    return ('@From %s: Hi, I would like to buy your %s listed for %s %s in '
            'Standard (stash tab "%s"; position: left 1, top 2)'
            % (sender, item, amount, cur, tab))


# Three sales in two currencies, one cancelled trade, one chat line.
FIXTURE = [
    ": Generating level 65 area \"MapCrypt\" with seed 1",
    _buy("BuyerOne", "Gloom Bite, Quarterstaff", 5, "exalted"),
    _buy("BuyerTwo", "Ruby Ring", 2, "divine"),
    ": Trade accepted.",
    _buy("BuyerThree", "Sapphire Ring", 7, "exalted"),
    ": Trade accepted.",
    _buy("BuyerFour", "Topaz Ring", 9, "chaos"),
    ": Trade accepted.",
    ": Trade cancelled.",
    "@From Friend: see you later",
]


def _played(lines=FIXTURE):
    clk = Clock(1000.0)
    st = SessionState(clock=clk)
    for i, body in enumerate(lines):
        ev = parse_line(_line(body, i))
        assert ev is not None, body
        clk.t += 30
        st.apply(ev)
    return st, clk


def _close(st, clk):
    clk.t += summary.IDLE_S + 1
    return st.check_session_end()


def test_fixture_log_three_sales_two_currencies():
    st, clk = _played()
    card = _close(st, clk)
    assert card is not None
    # oldest-card pairing: Gloom Bite (5 ex), Ruby Ring (2 div), Sapphire
    # Ring (7 ex); the cancel drops the Topaz card without a sale
    assert card["sales"] == 3
    assert card["sales_sums"] == [["exalted", 12], ["divine", 2]]
    assert card["sales_unsummed"] == 0
    assert "Sales: 3, about 12 exalted and 2 divine (an estimate)." in card["lines"]


def test_card_keeps_no_item_sender_or_whisper_text(tmp_path):
    st, clk = _played()
    card = _close(st, clk)
    path = tmp_path / "session_summaries.json"
    summary.save(path, card)
    text = path.read_text(encoding="utf-8")
    for word in ("Buyer", "Gloom", "Ring", "Shop7", "Standard", "Friend", "buy"):
        assert word not in text, word
    assert json.loads(text)["summaries"][-1]["sales"] == 3


def test_cancelled_trade_is_not_a_sale():
    st, clk = _played([_buy("A", "Ring", 3, "exalted"), ": Trade cancelled."])
    card = _close(st, clk)
    assert card["sales"] == 0
    assert not any(l.startswith("Sales:") for l in card["lines"])


def test_accepted_with_no_open_card_is_not_counted():
    st, clk = _played([": Generating level 65 area \"MapCrypt\" with seed 1",
                       ": Trade accepted."])
    card = _close(st, clk)
    assert card["sales"] == 0


def test_unpriced_card_counts_but_is_not_summed():
    st = SessionState(clock=Clock())
    st.apply({"type": "whisper_in", "from": "A", "text": "Hi",
              "trade": {"kind": "item", "item": "Ring", "price_amount": None,
                        "price_currency": None}})
    st.apply({"type": "whisper_in", "from": "B", "text": "Hi",
              "trade": {"kind": "item", "item": "Ring", "price_amount": 1.5,
                        "price_currency": "divine"}})
    st.apply({"type": "trade_accepted"})
    st.apply({"type": "trade_accepted"})
    st._clock.t += summary.IDLE_S + 1
    card = st.check_session_end()
    assert card["sales"] == 2
    assert card["sales_unsummed"] == 1
    assert "Sales: 2, about 1.5 divine (an estimate; 1 not in the sum)." in card["lines"]


def test_exchange_sale_sums_the_buyers_currency():
    st, clk = _played(["@From A: Hi, I'd like to buy your 10 chaos for my 1 "
                       "exalted in Standard.", ": Trade accepted."])
    card = _close(st, clk)
    assert card["sales_sums"] == [["exalted", 1]]


def test_new_stretch_starts_a_new_tally():
    st, clk = _played()
    _close(st, clk)
    st2_lines = [_buy("A", "Ring", 4, "chaos"), ": Trade accepted."]
    for i, body in enumerate(st2_lines):
        clk.t += 30
        st.apply(parse_line(_line(body, i)))
    card = _close(st, clk)
    assert card["sales"] == 1
    assert card["sales_sums"] == [["chaos", 4]]


def test_currency_cap_and_bad_words_go_unsummed():
    t = summary.Sales()
    for cur in ("a", "b", "c", "d", "e"):
        t.add(1, cur)
    t.add(2, "a")
    t.add(1, "<script>")
    t.add(1, "x" * 40)
    t.add(float("inf"), "a")
    t.add(True, "a")
    t.add(-1, "a")
    v = t.view()
    assert v["count"] == 11
    assert v["sums"] == [["a", 3], ["b", 1], ["c", 1], ["d", 1]]
    assert v["unsummed"] == 6


def test_sales_line_words():
    assert sales_line(0) is None
    assert sales_line(1, [], 1) == "Sales: 1 (no listed price to add up)."
    assert sales_line(2, [], 2) == "Sales: 2 (no listed prices to add up)."
    assert sales_line(1, [("exalted", 3)]) == "Sales: 1, about 3 exalted (an estimate)."
    assert (sales_line(3, [("exalted", 0.1 + 0.2), ("divine", 1), ("chaos", 40)])
            == "Sales: 3, about 0.3 exalted, 1 divine and 40 chaos (an estimate).")


def test_old_saved_card_without_sales_still_builds():
    card = summary.build({"level": 5}, {"level": 6}, 60, 1.0, "idle")
    assert card["sales"] == 0
    assert not any(l.startswith("Sales:") for l in card["lines"])
