"""DATA-PRICE-CARD-TEXT (F-036, F-031): the price card says how old a cached
poe.ninja price is (over 2 h 'Price from N h ago', over 24 h the link
only) and names the league on the overlay price line for 24 h after a
league change. Exact output for every new template (design 0001 section 9
rule 10). Fake times only; fixture values are invented."""

from server.al import price
from server.al.state import (CARD_LINE, LEAGUE_NEW_S, PRICE_AGED_S, PRICE_OLD_S,
                             SessionState, ninja_text, overlay_card, price_card_text)

PRESS = 1_800_000_000.0
H = 3600.0
LINK = "https://www.pathofexile.com/trade2/search/poe2/Dawn?q=%7B%7D"
LINK_SENTENCE = ("A trade site search for this item in Dawn is ready. Click the link to "
                 "see who sells it.")


def ninja(**kw):
    doc = {"kind": "unique", "name": "Ember Veil", "value": 12.5, "unit": "Divine Orb",
           "listings": 342, "few": False, "change": 8.2, "league": "Dawn",
           "checked_at": PRESS - 60, "league_changed_at": None}
    doc.update(kw)
    return doc


def card(at=PRESS, **kw):
    return {"status": "link", "url": LINK, "league": "Dawn", "at": at,
            "item": {"name": "Ember Veil", "base": "Silk Robe", "rarity": "Unique"},
            "count": None, "listings": [], "error": None, "wait_s": None,
            "ninja": ninja(**kw)}


def test_three_hour_old_cache_exact_text():
    t = price_card_text(card(checked_at=PRESS - 3 * H - 120))
    assert t["line"] == "About 12.5 Divine Orb"
    assert t["detail"] == "Price from 3 h ago"
    assert t["sentence"] == (
        "poe.ninja puts this at about 12.5 Divine Orb in Dawn, from 342 listings; up "
        "8.2% over 7 days. This price is from 3 h ago. A trade site search in Dawn is "
        "ready too; click the link to see who sells it.")
    # the overlay card carries the same two lines
    st = SessionState(clock=lambda: PRESS)
    c = card(checked_at=PRESS - 3 * H - 120)
    st.set_price({k: v for k, v in c.items() if k != "at"}, at=PRESS)
    snap = st.snapshot()
    assert (snap["card"]["line2"], snap["card"]["line3"]) == ("About 12.5 Divine Orb",
                                                              "Price from 3 h ago")


def test_rough_old_price_keeps_the_rough_word():
    t = price_card_text(card(checked_at=PRESS - 5 * H, listings=3, few=True, change=None))
    assert t["detail"] == "Rough price, 5 h ago"
    assert t["sentence"] == (
        "poe.ninja puts this at about 12.5 Divine Orb in Dawn, but only 3 are listed. The "
        "price is rough. This price is from 5 h ago. A trade site search in Dawn is ready "
        "too; click the link to see who sells it.")


def test_age_bounds():
    # 2 h or less: no age words
    fresh = price_card_text(card(checked_at=PRESS - PRICE_AGED_S))
    assert fresh["detail"] == "Up 8.2% in 7 days"
    assert "ago" not in fresh["sentence"]
    just = price_card_text(card(checked_at=PRESS - PRICE_AGED_S - 1))
    assert just["detail"] == "Price from 2 h ago"
    # exactly 24 h still shows the price, a second more does not
    day = price_card_text(card(checked_at=PRESS - PRICE_OLD_S))
    assert (day["line"], day["detail"]) == ("About 12.5 Divine Orb", "Price from 24 h ago")
    gone = price_card_text(card(checked_at=PRESS - PRICE_OLD_S - 1))
    assert gone["line"] == "Trade link ready"
    # a cache stamped after the press (clock step) or without a stamp reads fresh
    for stamp in (PRESS + 600, None, "x", True):
        t = price_card_text(card(checked_at=stamp))
        assert t["detail"] == "Up 8.2% in 7 days", stamp
    # a card without a press time ages nothing
    t = price_card_text(dict(card(checked_at=PRESS - 30 * H), at=None))
    assert t["line"] == "About 12.5 Divine Orb" and "ago" not in t["sentence"]


def test_thirty_hour_old_cache_shows_the_link_only():
    t = price_card_text(card(checked_at=PRESS - 30 * H))
    assert (t["line"], t["detail"]) == ("Trade link ready", "")
    assert t["sentence"] == (LINK_SENTENCE + " The poe.ninja price for it is over a day "
                             "old, so AshLight does not show it.")
    assert "12.5" not in str(t)
    only = overlay_card(None, card(checked_at=PRESS - 30 * H), PRESS + 1)
    assert (only["line2"], only["line3"]) == ("Trade link ready", "")
    # no cached price at all: the plain link card, no age words
    plain = price_card_text(dict(card(), ninja=None))
    assert plain["sentence"] == LINK_SENTENCE


def test_overlay_line_names_the_league_for_24_h_after_a_change():
    t = price_card_text(card(league_changed_at=PRESS - 2 * H))
    assert t["line"] == "~12.5 Divine Orb in Dawn"
    assert t["detail"] == "Up 8.2% in 7 days"
    edge = price_card_text(card(league_changed_at=PRESS - LEAGUE_NEW_S + 1))
    assert edge["line"] == "~12.5 Divine Orb in Dawn"
    later = price_card_text(card(league_changed_at=PRESS - LEAGUE_NEW_S))
    assert later["line"] == "About 12.5 Divine Orb"
    # no change recorded, or one after the press: no league on the line
    for stamp in (None, PRESS + 60):
        assert price_card_text(card(league_changed_at=stamp))["line"] == "About 12.5 Divine Orb"
    # the overlay card shows it
    only = overlay_card(None, card(league_changed_at=PRESS - H), PRESS + 1)
    assert only["line2"] == "~12.5 Divine Orb in Dawn"
    # a name too long for the line goes to the detail line, within the cap
    long = price_card_text(card(league_changed_at=PRESS - H, league="Fate of the Vaal"))
    assert long["line"] == "About 12.5 Divine Orb"
    assert long["detail"] == "League: Fate of the Vaal"
    huge = price_card_text(card(league_changed_at=PRESS - H,
                                league="Return of the Ancients Hardcore SSF"))
    assert huge["detail"] == "League: Return of the..."
    # a non-ASCII name stays off the overlay lines (the sentence keeps it)
    accent = price_card_text(card(league_changed_at=PRESS - H, league="D" + chr(233) + "but"))
    assert accent["line"] == "About 12.5 Divine Orb"
    assert accent["detail"] == "Up 8.2% in 7 days"
    # an old price after a change says both
    both = price_card_text(card(checked_at=PRESS - 4 * H, league_changed_at=PRESS - 5 * H))
    assert (both["line"], both["detail"]) == ("~12.5 Divine Orb in Dawn",
                                              "Price from 4 h ago")


def test_new_lines_fit_the_card():
    cases = [card(checked_at=PRESS - 23 * H, few=True),
             card(checked_at=PRESS - 23 * H, league_changed_at=PRESS - H,
                  league="A" * 60),
             card(value=123456.78, unit="Exalted Orb", league_changed_at=PRESS - H),
             card(checked_at=PRESS - 30 * H)]
    for c in cases:
        t = price_card_text(c)
        assert len(t["line"]) <= CARD_LINE and len(t["detail"]) <= CARD_LINE, t
        # CARD-LINE-LIMIT-COPY: worded to fit 26 while CARD_LINE stays 34
        assert CARD_LINE == 34 and len(t["line"]) <= 26 and len(t["detail"]) <= 26, t
    for hours in range(3, 25):
        t = price_card_text(card(checked_at=PRESS - hours * H, few=True))
        assert t["detail"] == f"Rough price, {hours} h ago" and len(t["detail"]) <= 26
    # a long amount and unit: "About" turns into the "~" of the listed line
    t = price_card_text(card(value=123456.78, unit="Exalted Orb"))
    assert t["line"] == "~123456.78 Exalted Orb"
    t = price_card_text(card(value=1234.5, unit="Exalted Orb"))
    assert t["line"] == "About 1234.5 Exalted Orb"
    t = price_card_text(card(value=1234.5, unit="Exalted Orb", league_changed_at=PRESS - H))
    assert (t["line"], t["detail"]) == ("About 1234.5 Exalted Orb", "League: Dawn")
    t = price_card_text(card(league_changed_at=PRESS - H, league="A" * 60))
    assert t["detail"] == "League: " + "A" * 15 + "..."


def test_ninja_text_without_a_press_time_is_unchanged():
    # the older callers (no `at`) get exactly the PRICE-UNIQUE words
    old = ninja(checked_at=PRESS - 30 * H, league_changed_at=PRESS - H)
    assert ninja_text(old) == ninja_text(ninja())


def test_ninja_of_passes_the_new_keys():
    hit = ninja(checked_at=PRESS - 3 * H, league_changed_at=PRESS - H)
    out = price.ninja_of(dict(hit, extra="dropped"))
    assert out["checked_at"] == PRESS - 3 * H
    assert out["league_changed_at"] == PRESS - H
    assert "extra" not in out
    assert price.ninja_of({"value": 1})["checked_at"] is None


def test_press_pipeline_ages_the_cached_price():
    st = SessionState(clock=lambda: PRESS)
    looked = ninja(checked_at=PRESS - 3 * H - 1, league_changed_at=PRESS - H)
    checker = price.PriceChecker(league=lambda: "Dawn", card=st.set_price,
                                 lookup=lambda item: dict(looked), clock=lambda: PRESS)
    text = "\n".join(["Item Class: Body Armours", "Rarity: Unique", "Ember Veil",
                      "Silk Robe", "--------", "Energy Shield: 80", "--------",
                      "Item Level: 70"])
    assert checker.request(text, at=PRESS)["status"] == "link"
    snap = st.snapshot()
    assert snap["price"]["ninja"]["checked_at"] == PRESS - 3 * H - 1
    assert snap["price"]["text"]["line"] == "~12.5 Divine Orb in Dawn"
    assert snap["price"]["text"]["detail"] == "Price from 3 h ago"
    assert snap["card"]["line2"] == "~12.5 Divine Orb in Dawn"
