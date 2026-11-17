"""PRICE-1 (server part): trade2 rate-limit header parsing, the shared
limiter, the serial queue and the query builder. Mocked fetch only."""

import pytest

from server.al import NAME, VERSION, trade, webfetch
from server.al.theorycraft import item as item_mod
from tc_eval_fixtures import ADVANCED_RING, RARE_GLOVES, UNIQUE_STAFF

HDRS = {
    "X-Rate-Limit-Policy": "trade-search-request-limit",
    "X-Rate-Limit-Rules": "Ip,Account",
    "X-Rate-Limit-Ip": "5:10:60,15:60:300",
    "X-Rate-Limit-Ip-State": "1:10:0,1:60:0",
    "X-Rate-Limit-Account": "3:5:60",
    "X-Rate-Limit-Account-State": "1:5:0",
}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_parse_rate_headers():
    info = trade.parse_rate_headers({k.lower(): v for k, v in HDRS.items()})
    assert info["policy"] == "trade-search-request-limit"
    assert info["rules"]["ip"] == [
        {"max": 5, "period": 10.0, "restrict": 60.0, "hits": 1, "active": 0.0},
        {"max": 15, "period": 60.0, "restrict": 300.0, "hits": 1, "active": 0.0}]
    assert info["rules"]["account"][0]["max"] == 3
    assert info["retry_after"] is None
    junk = trade.parse_rate_headers({"X-Rate-Limit-Rules": "ip", "X-Rate-Limit-Ip": "a:b,1:2",
                                     "Retry-After": "soon"})
    assert junk["rules"] == {"ip": []} and junk["retry_after"] is None


def test_limiter_is_data_driven_with_headroom():
    clock = Clock()
    lim = trade.RateLimiter(clock=clock)
    assert lim.wait_s("search") == 0  # unknown policy: the serial queue sends one
    lim.note_sent("search")
    lim.update("search", 200, HDRS)
    # account window 3 per 5 s with one hit of headroom: 2 allowed
    assert lim.wait_s("search") == 0
    lim.note_sent("search")
    clock.t += 1
    w = lim.wait_s("search")
    assert w == pytest.approx(4.0)  # first own hit (t=1000) leaves at 1005
    clock.t += w
    assert lim.wait_s("search") == 0


def test_new_header_values_replace_old_ones():
    clock = Clock()
    lim = trade.RateLimiter(clock=clock)
    lim.update("search", 200, HDRS)
    tighter = dict(HDRS, **{"X-Rate-Limit-Account": "1:30:60",
                            "X-Rate-Limit-Account-State": "1:30:0"})
    lim.update("search", 200, tighter)
    assert lim.wait_s("search") == pytest.approx(30.0)


def test_429_retry_after_and_fallback():
    clock = Clock()
    lim = trade.RateLimiter(clock=clock)
    lim.update("search", 429, dict(HDRS, **{"Retry-After": "42"}))
    assert lim.wait_s("search") == pytest.approx(42.0)
    lim2 = trade.RateLimiter(clock=clock)
    lim2.update("fetch", 429, {})
    assert lim2.wait_s("fetch") == pytest.approx(trade.RETRY_AFTER_DEFAULT_S)


def test_active_restriction_in_state_blocks():
    clock = Clock()
    lim = trade.RateLimiter(clock=clock)
    lim.update("search", 200, dict(HDRS, **{"X-Rate-Limit-Ip-State": "6:10:55,6:60:0"}))
    assert lim.wait_s("search") == pytest.approx(55.0)


def test_kinds_sharing_a_policy_share_state():
    clock = Clock()
    lim = trade.RateLimiter(clock=clock)
    lim.update("search", 429, dict(HDRS, **{"Retry-After": "30"}))
    lim.update("exchange", 200, HDRS)  # same policy name
    assert lim.wait_s("exchange") == pytest.approx(30.0)
    other = dict(HDRS, **{"X-Rate-Limit-Policy": "trade-fetch-request-limit"})
    lim.update("fetch", 200, other)
    assert lim.wait_s("fetch") == 0


CONTACT = "test-contact"


class FakeNet:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers), body))
        return self.replies.pop(0)


def test_client_needs_opt_in_and_allowlist():
    net = FakeNet([])
    c = trade.TradeClient(enabled=lambda: False, fetch=net)
    with pytest.raises(webfetch.WebDataOff):
        c.submit("search", "POST", trade.search_url("Standard"), {"query": {}})
    on = trade.TradeClient(enabled=lambda: True, fetch=net, contact=lambda: CONTACT)
    with pytest.raises(webfetch.UrlNotAllowed):
        on.submit("search", "POST", "https://evil.example/api/trade2/search/poe2/x", {})
    assert net.calls == []


def test_client_waits_for_the_limiter_and_sends_truthful_headers():
    clock = Clock()
    slept = []

    def sleep(s):
        slept.append(s)
        clock.t += s

    net = FakeNet([(200, HDRS, b'{"id": "Q1", "result": ["a1"], "total": 1}'),
                   (200, HDRS, b'{"id": "Q2", "result": [], "total": 0}'),
                   (429, dict(HDRS, **{"Retry-After": "7"}), b"{}")])
    c = trade.TradeClient(enabled=lambda: True, fetch=net, sleep=sleep, clock=clock,
                          contact=lambda: CONTACT)
    url = trade.search_url("Example League")
    j1 = c.run_one(trade.Job("search", "POST", url, {"query": {"type": "X"}}))
    assert j1.error is None and j1.result["id"] == "Q1"
    j2 = c.run_one(trade.Job("search", "POST", url, {"query": {"type": "X"}}))
    assert j2.result["id"] == "Q2"
    j3 = c.run_one(trade.Job("search", "POST", url, {"query": {"type": "X"}}))
    assert slept and j3.error == "trade HTTP 429"
    assert c.limiter.wait_s("search") == pytest.approx(7.0)
    for method, u, h, body in net.calls:
        assert method == "POST" and u == url
        assert h["User-Agent"].startswith(f"{NAME}/{VERSION} ")
        assert h["User-Agent"].endswith(f"(contact: {CONTACT})")
        assert "Cookie" not in h and h["Content-Type"] == "application/json"


def test_client_rechecks_opt_in_before_sending():
    state = {"on": True}
    net = FakeNet([])
    c = trade.TradeClient(enabled=lambda: state["on"], fetch=net, contact=lambda: CONTACT)
    job = trade.Job("search", "POST", trade.search_url("Standard"), {})
    state["on"] = False
    c.run_one(job)
    assert job.error and net.calls == []


def test_client_needs_a_contact():
    net = FakeNet([])
    c = trade.TradeClient(enabled=lambda: True, fetch=net)
    with pytest.raises(webfetch.ContactMissing):
        c.submit("search", "POST", trade.search_url("Standard"), {"query": {}})
    job = c.run_one(trade.Job("search", "POST", trade.search_url("Standard"), {}))
    assert job.error == webfetch.REASON_CONTACT and net.calls == []


def test_queue_runs_jobs_in_order():
    net = FakeNet([(200, {}, b'{"n": 1}'), (200, {}, b'{"n": 2}')])
    c = trade.TradeClient(enabled=lambda: True, fetch=net, contact=lambda: CONTACT)
    url = trade.search_url("Standard")
    a = c.submit("search", "POST", url, {"query": {}})
    b = c.submit("search", "POST", url, {"query": {}})
    assert a.wait(5).result == {"n": 1} and b.wait(5).result == {"n": 2}


def test_urls():
    assert trade.search_url("Rise of the Abyssal") == (
        "https://www.pathofexile.com/api/trade2/search/poe2/Rise%20of%20the%20Abyssal")
    assert trade.fetch_url(["a1", "b2", "../x"], "Q1") == (
        "https://www.pathofexile.com/api/trade2/fetch/a1,b2?query=Q1")
    with pytest.raises(ValueError):
        trade.fetch_url([], "Q1")
    with pytest.raises(ValueError):
        trade.search_url(" ")


def test_build_query_rare_with_stat_ids():
    it = item_mod.parse(ADVANCED_RING)
    ids = {"+# to maximum Life": "explicit.stat_life",
           "+#% to Lightning Resistance": "explicit.stat_light"}
    q = trade.build_query(it, stat_ids=ids)
    assert q["sort"] == {"price": "asc"}
    assert q["query"]["type"] == "Example Ring" and "name" not in q["query"]
    filters = q["query"]["stats"][0]["filters"]
    assert {"id": "explicit.stat_life", "value": {"min": 49.5}} in filters
    assert any(f["id"] == "explicit.stat_light" for f in filters)


def test_build_query_without_stat_ids_and_flags():
    q = trade.build_query(item_mod.parse(RARE_GLOVES))
    assert q["query"]["type"] == "Example Gloves" and "stats" not in q["query"]
    assert q["query"]["filters"]["misc_filters"]["filters"]["corrupted"] == {"option": "true"}


def test_build_query_unique_by_name():
    q = trade.build_query(item_mod.parse(UNIQUE_STAFF))
    assert q["query"]["name"] == "Example Unique"
    assert q["query"]["type"] == "Example Quarterstaff"


def test_build_query_refuses_non_items():
    with pytest.raises(ValueError):
        trade.build_query(item_mod.parse("hello"))
    assert trade.mod_key("Adds 2 to 40 Lightning Damage") == "Adds # to # Lightning Damage"
