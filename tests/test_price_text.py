"""PRICE-1-UI: exact output of every price check template (design 0001
section 9 rule 10), the PRICE-1 result contract in the state snapshot
(decision 0016 fork 1) and the one overlay card chooser (fork 2). Fixture
values are invented."""

from server.al.state import (EVAL_CARD_S, PRICE_CARD_S, PRICE_TEXT, SAME_PRESS_S,
                             SessionState, overlay_card, price_card_text)
import srcpaths
from server.al.theorycraft import live


def price(status="done", **kw):
    doc = {"status": status, "wait_s": None, "league": "Dawn",
           "item": {"name": "Doom Grip", "base": "Example Gloves", "rarity": "Rare"},
           "count": 0, "listings": [], "error": None}
    doc.update(kw)
    return doc


FIVE = [{"amount": 10, "currency": "exalted"}, {"amount": 11, "currency": "exalted"},
        {"amount": 12, "currency": "exalted"}, {"amount": 14.5, "currency": "exalted"},
        {"amount": 1, "currency": "divine"}]


def test_done_with_listings():
    t = price_card_text(price(count=5, listings=FIVE))
    assert t["head"] == "Price: Doom Grip"
    assert t["item"] == "Doom Grip"
    assert t["line"] == "5 listed, ~12 exalted"
    assert t["detail"] == "Lowest 10 exalted"
    assert t["sentence"] == ("5 listed in Dawn. The cheapest is 10 exalted; the middle "
                             "of the 5 cheapest is 12 exalted.")
    assert t["rows"] == ["10 exalted", "11 exalted", "12 exalted", "14.5 exalted", "1 divine"]


def test_done_many_found_one_listed_and_none():
    t = price_card_text(price(count=120, listings=FIVE[:2]))
    assert t["line"] == "120 listed, ~10 exalted"
    assert t["sentence"] == ("120 listed in Dawn. The cheapest is 10 exalted; the middle "
                             "of the 2 cheapest is 10 exalted.")
    one = price_card_text(price(count=1, listings=[{"amount": 3, "currency": "chaos"}]))
    assert one["line"] == "1 listed, ~3 chaos"
    assert one["sentence"] == "1 listed in Dawn, for 3 chaos."
    none = price_card_text(price(count=0, listings=[]))
    assert (none["line"], none["detail"]) == ("No listings found", "Nobody sells this now")
    assert none["sentence"] == ("Nobody lists this item in Dawn right now, so AshLight "
                                "can't price it.")
    assert none["rows"] == []


def test_searching_and_waiting():
    t = price_card_text(price("searching"))
    assert (t["line"], t["detail"]) == ("Searching prices...", "On the official trade site")
    assert t["sentence"] == "Searching the official trade site for this item..."
    w = price_card_text(price("waiting", wait_s=7.2))
    assert (w["line"], w["detail"]) == ("Prices in about 8 s", "Waiting for the trade site")
    assert w["sentence"] == "Waiting about 8 s for the trade site, then AshLight searches by itself."
    w1 = price_card_text(price("waiting", wait_s=0.4))
    assert w1["line"] == "Prices in about 1 s"


def test_off_and_errors_say_what_to_do():
    off = price_card_text(price("off"))
    # DATA-PRICE-CARD-TEXT (F-018): names poe.ninja and the card, not a file
    assert (off["line"], off["detail"]) == ("Web data is off",
                                            "See Prices and web data")
    assert off["sentence"] == ("poe.ninja prices need web data, which is off. Turn it on "
                               "in the Prices and web data card on this page.")
    nai = price_card_text(price("error", error="not an item", item={}))
    assert nai["head"] == "Price: Unnamed item"
    assert (nai["line"], nai["detail"]) == ("Not an item", "Copy an item in game first")
    league = price_card_text(price("error", error="no league"))
    assert league["line"] == "League unknown"
    assert league["sentence"] == ("AshLight doesn't know which league to search yet. Try "
                                  "again in a minute.")
    other = price_card_text(price("error", error="trade HTTP 503"))
    # PRICE-TRADE-LINK: nothing asks the trade site, so nothing blames it
    assert (other["line"], other["detail"]) == ("Price check failed", "Press the hotkey again")
    assert other["sentence"] == ("AshLight couldn't make a trade search for this item. Press "
                                 "the hotkey again.")
    assert "503" not in str(other) and "HTTP" not in str(other)


def test_off_contact_not_set_says_what_to_do():
    # F2 (PRICE-1-COPY): off because no contact is set must not say web data is off
    t = price_card_text(price("off", error="contact not set"))
    # DATA-PRICE-CARD-TEXT (F-018): names poe.ninja and the card, not a file
    assert (t["line"], t["detail"]) == ("Contact not set", "See Prices and web data")
    assert t["sentence"] == ("poe.ninja prices need a contact, such as an email or a name. "
                             "Add it in the Prices and web data card on this page, then "
                             "press the hotkey again.")
    assert "Web data is off" not in str(t)
    assert "config/local.json" not in str(t) and "trade site" not in str(t)
    # the generic error key never borrows the contact text
    e = price_card_text(price("error", error="contact not set"))
    assert e["line"] == "Price check failed"


def test_no_base_type_says_try_another_item():
    # PRICE-1-COPY F3 + design review F1: no request was made, so it must not
    # blame the trade site or ask for a retry of the same item
    t = price_card_text(price("error", error="no base type"))
    assert (t["line"], t["detail"]) == ("Can't price this item", "Try a different item")
    assert t["sentence"] == ("AshLight can't make a trade search for this item. Try a "
                             "different one.")
    assert PRICE_TEXT["no base type"] == (t["line"], t["detail"], t["sentence"])


LINK = "https://www.pathofexile.com/trade2/search/poe2/Dawn?q=%7B%7D"


def test_link_ready():
    # PRICE-TRADE-LINK (decision 0017): the overlay says only that the link
    # is ready; the dashboard sentence names the league and the browser
    t = price_card_text(price("link", url=LINK, count=None))
    assert t["head"] == "Price: Doom Grip"
    assert (t["line"], t["detail"]) == ("Trade link ready", "")
    assert t["sentence"] == ("A trade site search for this item in Dawn is ready. Click the "
                             "link to see who sells it.")
    assert t["rows"] == []
    assert PRICE_TEXT["link"][:2] == ("Trade link ready", "")
    nolg = price_card_text(price("link", url=LINK, league=None))
    assert "in this league is ready" in nolg["sentence"]


def test_link_merges_with_the_item_check():
    ev = dict(ev_card(), at=100.0)
    pr = dict(price("link", url=LINK), at=100.0)
    card = overlay_card(ev, pr, 101.0)
    # OVL-CARD-NAME (decision 0016 amendment 2026-11-19): with no poe.ninja
    # value, line 2 stays the item name; the link is on the dashboard
    assert (card["kind"], card["head"], card["line2"], card["line3"], card["verdict"]) == (
        "merged", "Upgrade +12 vs Gloves", "Doom Grip", "+35 to maximum Life", "upgrade")
    only = overlay_card(None, pr, 101.0)
    assert (only["kind"], only["head"], only["line2"], only["line3"], only["verdict"]) == (
        "price", "Price: Doom Grip", "Doom Grip", "", "price")
    # the dashboard words are unchanged
    assert price_card_text(pr)["line"] == "Trade link ready"


NINJA = {"value": 12.5, "unit": "Divine Orb", "league": "Dawn", "listings": 342,
         "few": False, "change": None, "checked_at": 99.0, "league_changed_at": None}


def test_link_with_a_poe_ninja_value_keeps_the_price_line():
    """OVL-CARD-NAME: with a cached poe.ninja value line 2 is the price
    line, on the price card and on the merged card, as before."""
    ev = dict(ev_card(), at=100.0)
    pr = dict(price("link", url=LINK, ninja=NINJA), at=100.0)
    only = overlay_card(None, pr, 101.0)
    assert (only["kind"], only["head"], only["line2"], only["line3"]) == (
        "price", "Price: Doom Grip", "About 12.5 Divine Orb", "From poe.ninja")
    card = overlay_card(ev, pr, 101.0)
    assert (card["kind"], card["head"], card["line2"], card["line3"]) == (
        "merged", "Upgrade +12 vs Gloves", "About 12.5 Divine Orb", "+35 to maximum Life")
    # a broken value is no value: the item name again
    bad = dict(pr, ninja=dict(NINJA, value="lots"))
    assert overlay_card(None, bad, 101.0)["line2"] == "Doom Grip"
    assert overlay_card(ev, bad, 101.0)["line2"] == "Doom Grip"
    # other statuses keep their price line
    done = dict(price(count=5, listings=FIVE), at=100.0)
    assert overlay_card(None, done, 101.0)["line2"] == "5 listed, ~12 exalted"
    assert overlay_card(ev, done, 101.0)["line2"] == "5 listed, ~12 exalted"


def test_empty_clipboard_price_error_says_copy_first():
    """OVL-COPY-FIRST: PRICE_TEXT handles the eval's "empty clipboard" key."""
    t = price_card_text(price("error", error="empty clipboard", item={}))
    assert (t["line"], t["detail"]) == ("Copy the item first",
                                        "Hover it, press Ctrl+C")
    assert t["sentence"] == ("The clipboard was empty when you pressed the hotkey. Hover "
                             "an item in game, press Ctrl+C, then press the hotkey again.")


def test_missing_values_read_honestly():
    for t in (price_card_text(None), price_card_text({}),
              price_card_text({"status": "done", "listings": [{"amount": None}]})):
        assert "None" not in str(t) and "undefined" not in str(t)
        assert t["head"].startswith("Price: ")
    t = price_card_text({"status": "done", "count": 1,
                         "listings": [{"amount": 2, "currency": None}]})
    assert t["rows"] == ["2 (currency unknown)"]


def test_overlay_lines_fit_the_card():
    for c in (price(count=5, listings=FIVE), price("searching"), price("waiting", wait_s=99),
              price("off"), price("off", error="contact not set"),
              price("error", error="x"), price("error", error="no league"),
              price(count=0), price("link", url=LINK)):
        t = price_card_text(c)
        assert len(t["line"]) <= 34 and len(t["detail"]) <= 34, t


def ev_card(ok=True, error=None):
    if ok:
        return live.compact({"ok": True, "verdict": "upgrade", "slot": "Gloves",
                             "score_delta": 12, "item": {"name": "Doom Grip"},
                             "comparisons": [{"slot": "Gloves", "verdict": "upgrade",
                                              "score_delta": 12, "equipped": {"name": "Old"},
                                              "stats": [{"key": "+# to maximum Life",
                                                         "delta": 35, "score_delta": 12,
                                                         "weighted": True}]}]})
    return live.compact({"ok": False, "error": error})


def snap_parts(st):
    s = st.snapshot()
    return s, s["card"]


def test_state_price_field_contract():
    now = [1000.0]
    st = SessionState(clock=lambda: now[0])
    s = st.snapshot()
    assert s["price"] is None and s["card"] is None
    v = s["version"]
    st.set_price(price("searching"))
    s = st.snapshot()
    assert s["version"] == v + 1
    p = s["price"]
    assert p["at"] == 1000.0 and p["expires_at"] == 1000.0 + PRICE_CARD_S
    assert p["status"] == "searching" and p["id"] == 1
    assert p["text"]["line"] == "Searching prices..."
    now[0] = 1003.0
    st.set_price(price(count=5, listings=FIVE), keep_time=True)
    p = st.snapshot()["price"]
    assert p["at"] == 1000.0 and p["id"] == 2 and p["text"]["line"].endswith("~12 exalted")
    st.set_price(price("searching"), at=990.0)
    assert st.snapshot()["price"]["at"] == 990.0
    # listings are capped at 10 (contract)
    st.set_price(price(count=50, listings=[{"amount": i, "currency": "exalted"}
                                           for i in range(30)]))
    assert len(st.snapshot()["price"]["listings"]) == 10


def test_card_merged_for_the_same_press():
    now = [1000.0]
    st = SessionState(clock=lambda: now[0])
    st.set_eval(ev_card())
    now[0] = 1001.0
    st.set_price(price("searching"), at=1000.5)
    _s, card = snap_parts(st)
    assert card["kind"] == "merged"
    assert card["head"] == "Upgrade +12 vs Gloves"
    assert card["line2"] == "Searching prices..."
    assert card["line3"] == "+35 to maximum Life"
    assert card["verdict"] == "upgrade"
    assert card["expires_at"] == 1001.0 + PRICE_CARD_S  # 20 s from the last update


def test_card_price_only_when_no_build_or_no_eval():
    now = [1000.0]
    st = SessionState(clock=lambda: now[0])
    st.set_price(price(count=5, listings=FIVE))
    card = st.snapshot()["card"]
    assert (card["kind"], card["head"], card["line2"], card["line3"]) == (
        "price", "Price: Doom Grip", "5 listed, ~12 exalted", "Lowest 10 exalted")
    assert card["verdict"] == "price"
    st.set_eval(ev_card(False, "no build loaded"))
    assert st.snapshot()["card"]["kind"] == "price"


def test_card_eval_unchanged_when_price_fails_or_off():
    now = [1000.0]
    st = SessionState(clock=lambda: now[0])
    st.set_eval(ev_card())
    st.set_price(price("off"))
    card = st.snapshot()["card"]
    assert card["kind"] == "eval"
    assert (card["head"], card["line2"], card["line3"]) == (
        "Upgrade +12 vs Gloves", "Doom Grip", "+35 to maximum Life")
    assert card["expires_at"] == 1000.0 + EVAL_CARD_S
    st.set_price(price("error", error="boom"))
    assert st.snapshot()["card"]["kind"] == "eval"


def test_card_different_presses_newest_wins_and_expiry():
    ev = dict(ev_card(), at=1000.0)
    pr = dict(price(count=1, listings=FIVE[:1]), at=1000.0 + SAME_PRESS_S + 1)
    assert overlay_card(ev, pr, 1004.0)["kind"] == "price"
    assert overlay_card(dict(ev, at=1010.0), pr, 1011.0)["kind"] == "eval"
    # expired parts drop out; nothing fresh means no card
    assert overlay_card(ev, None, 1000.0 + EVAL_CARD_S) is None
    assert overlay_card(None, dict(pr, at=1000.0), 1000.0 + PRICE_CARD_S) is None
    assert overlay_card(ev, dict(pr, at=900.0), 1001.0)["kind"] == "eval"
    assert overlay_card(None, None, 0) is None


def test_dashboard_markup_opt_in_off_and_credit_visible():
    """DATA-NINJA-UI ACCEPT: the credit is in the page; the web-data box is
    never pre-ticked (the opt-in stays explicit, decision 0013)."""
    html = srcpaths.index_html()
    assert '<script src="/web/prices.js" defer></script>' in html
    assert '<input id="webdata-on" type="checkbox">' in html
    assert "checked" not in html.split('id="webdata-on"', 1)[1].split(">", 1)[0]
    assert "Prices: poe.ninja" in html
    assert 'id="price-result" role="status" aria-live="polite"' in html


def test_price_card_stays_20_s_after_a_late_result():
    """Review F1 (N5): a result that waited on the limiter still shows for
    the full card time after it arrives; the press time stays for grouping."""
    now = [1000.0]
    st = SessionState(clock=lambda: now[0])
    st.set_price(price("waiting", wait_s=15))
    now[0] = 1018.0
    st.set_price(price(count=5, listings=FIVE), keep_time=True)
    s = st.snapshot()
    assert s["price"]["at"] == 1000.0
    assert s["price"]["expires_at"] == 1018.0 + PRICE_CARD_S
    assert s["card"]["kind"] == "price" and s["card"]["expires_at"] == 1018.0 + PRICE_CARD_S
    now[0] = 1030.0
    assert st.snapshot()["card"]["kind"] == "price"
    now[0] = 1038.0
    assert st.snapshot()["card"] is None


def test_long_wait_keeps_the_card_until_the_result_can_arrive():
    """Review N4: a 45 s limiter wait does not drop the card mid-wait."""
    now = [1000.0]
    st = SessionState(clock=lambda: now[0])
    st.set_price(price("waiting", wait_s=45))
    assert st.snapshot()["price"]["expires_at"] == 1000.0 + 45 + PRICE_CARD_S
    now[0] = 1050.0
    assert st.snapshot()["card"]["kind"] == "price"


def test_card_merged_when_the_keep_part_answers_without_a_build():
    """TC-CAMPAIGN-KEEP (decision 0057): a no-build gear card that the keep
    part answers stays on the overlay merged with its price line; without
    that answer the price card alone shows (as before)."""
    now = [1000.0]
    st = SessionState(clock=lambda: now[0])
    ev = ev_card(False, "no build loaded")
    ev["parts"] = {"keep": {"status": "vendor", "level": 30, "need": 2, "of": 5,
                            "count": 1, "missed": [],
                            "met": [{"label": "life", "min": 25, "have": 30}]}}
    st.set_eval(ev)
    now[0] = 1001.0
    st.set_price(price(count=5, listings=FIVE), at=1000.5)
    _s, card = snap_parts(st)
    assert (card["kind"], card["head"], card["line2"], card["line3"], card["verdict"]) == (
        "merged", "Vendor - 1 of 5 met, Lv 30", "5 listed, ~12 exalted",
        "Paste a build first", "note")
    ev["parts"] = {"keep": {"status": "no_level"}}
    st.set_eval(ev, at=1000.0)
    assert st.snapshot()["card"]["kind"] == "price"
