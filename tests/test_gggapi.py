"""TC-GGG-CLIENT-CORE: the offline GGG OAuth client core (server/al/gggapi.py).

Every request goes to an injected fake transport; no test opens a socket or
reaches a network. Decision 0048, research 0035 F3 / F4 / F8.
"""

import json
import logging
import urllib.parse

import pytest

from server.al import diag, gggapi, oauthlisten, ports, ratelimit, settingsio

CLIENT_ID = "ashlight-test"
CONTACT = "issues page placeholder"
ACCESS = "486132c90fedb152360bc0e1aa54eea155768eb9"
REFRESH = "17abaa74e599192f7650a4b89b6e9dfef2ff68cd"
REFRESH2 = "4e9dbe97e038430bd943d35f8d5f8bef99699396"
CODE = "d25cc653854f1d4db9c0797a30a374c6"

# D-AUTH's own PKCE example (also RFC 7636 appendix B)
DOC_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
DOC_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class FakeTransport:
    """Scripted one-hop transport: records every call, answers in order."""

    def __init__(self, *answers, on_call=None):
        self.answers = list(answers)
        self.calls = []
        self.on_call = on_call

    def __call__(self, method, url, headers, body=None):
        self.calls.append({"method": method, "url": url,
                           "headers": dict(headers), "body": body})
        if self.on_call:
            self.on_call()
        status, headers, doc = self.answers.pop(0)
        data = doc if isinstance(doc, bytes) else json.dumps(doc).encode("utf-8")
        return status, headers, data


class CountingStore:
    """Credential store double: counts every call of any kind."""

    def __init__(self, rec=None):
        self.rec = rec
        self.calls = []

    def load(self):
        self.calls.append("load")
        return None if self.rec is None else dict(self.rec)

    def save(self, rec):
        self.calls.append("save")
        self.rec = dict(rec)

    def clear(self):
        self.calls.append("clear")
        self.rec = None


def token_answer(access=ACCESS, refresh=REFRESH, expires=36000):
    doc = {"access_token": access, "expires_in": expires, "token_type": "bearer",
           "scope": gggapi.SCOPE, "username": "SomeAccount",
           "sub": "c5b9c286-8d05-47af-be41-67ab10a8c53e"}
    if refresh:
        doc["refresh_token"] = refresh
    return (200, {}, doc)


def make(transport, **kw):
    clock = kw.pop("clock", Clock())
    wall = kw.pop("wall", Clock(1_800_000_000.0))
    kw.setdefault("sleep", lambda s: None)
    kw.setdefault("rand", lambda n: bytes(range(n)))
    return gggapi.Client(kw.pop("client_id", CLIENT_ID), kw.pop("contact", CONTACT),
                         transport, clock=clock, wall=wall, **kw)


def connected(transport_answers=(), **kw):
    t = FakeTransport(token_answer(), *transport_answers)
    c = make(t, **kw)
    p = c.begin()
    c.finish(p, CODE)
    return c, t


# -- PKCE, state, URL, User-Agent

def test_documented_verifier_challenge_pair_round_trips():
    assert gggapi.challenge(DOC_VERIFIER) == DOC_CHALLENGE


def test_verifier_has_32_bytes_of_entropy_and_state_is_fresh():
    v = gggapi.make_verifier()
    assert len(v) == 43 and "=" not in v
    assert gggapi.make_verifier() != v
    assert len(gggapi.make_state()) == 32
    assert gggapi.make_state() != gggapi.make_state()
    with pytest.raises(gggapi.GggError):
        gggapi.make_verifier(lambda n: b"short")


def test_authorize_url_uses_registered_redirect_ports_only():
    url = gggapi.authorize_url(CLIENT_ID, 8979, "st", DOC_CHALLENGE)
    parts = urllib.parse.urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == gggapi.AUTHORIZE_URL
    q = dict(urllib.parse.parse_qsl(parts.query))
    assert q == {"client_id": CLIENT_ID, "response_type": "code",
                 "scope": "account:characters", "state": "st",
                 "redirect_uri": oauthlisten.redirect_uri(8979),
                 "code_challenge": DOC_CHALLENGE, "code_challenge_method": "S256"}
    assert q["redirect_uri"] == "http://127.0.0.1:8979/oauth/callback"
    for port in ports.OAUTH_REDIRECT_PORTS:
        assert str(port) in gggapi.authorize_url(CLIENT_ID, port, "s", "c")
    for bad in (8960, 8080, True, None, "8979"):
        with pytest.raises(gggapi.GggError):
            gggapi.authorize_url(CLIENT_ID, bad, "s", "c")


def test_user_agent_form():
    ua = gggapi.user_agent(CLIENT_ID, CONTACT, version="1.2.3")
    assert ua == (f"OAuth {CLIENT_ID}/1.2.3 (contact: {CONTACT}) AshLight/1.2.3")
    with pytest.raises(gggapi.NoContact):
        gggapi.user_agent(CLIENT_ID, "")
    with pytest.raises(gggapi.NoContact):
        gggapi.user_agent(CLIENT_ID, "bad (paren)")


def test_begin_pending_matches_its_url():
    c = make(FakeTransport())
    p = c.begin()
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(p.url).query))
    assert q["state"] == p.state
    assert q["code_challenge"] == gggapi.challenge(p._verifier.reveal())
    assert p.port == ports.OAUTH_REDIRECT_PORTS[0]
    assert c.begin(8978).port == 8978
    assert p.state not in repr(p)


# -- no request without a client id

@pytest.mark.parametrize("cid", [None, "", "   ", "bad id", "x" * 65, 42])
def test_no_request_is_possible_without_a_client_id(cid):
    t = FakeTransport(token_answer())
    c = make(t, client_id=cid)
    assert not c.has_client_id
    with pytest.raises(gggapi.NoClientId):
        c.begin()
    with pytest.raises(gggapi.NoClientId):
        c.finish(gggapi.Pending("v" * 43, "s", 8979, "u"), CODE)
    with pytest.raises(gggapi.NoClientId):
        c.characters()
    with pytest.raises(gggapi.NoClientId):
        c.character("Someone")
    with pytest.raises(gggapi.NoClientId):
        gggapi.authorize_url(cid, 8979, "s", "c")
    assert t.calls == []


def test_no_request_without_a_contact():
    t = FakeTransport(token_answer())
    c = make(t, contact=None)
    p = c.begin()
    with pytest.raises(gggapi.NoContact):
        c.finish(p, CODE)
    assert t.calls == []


def test_a_transport_is_required():
    with pytest.raises(gggapi.GggError):
        gggapi.Client(CLIENT_ID, CONTACT, None)


# -- token exchange

def test_token_exchange_request_shape():
    c, t = connected()
    assert len(t.calls) == 1
    call = t.calls[0]
    assert call["method"] == "POST" and call["url"] == gggapi.TOKEN_URL
    assert call["headers"]["User-Agent"].startswith(f"OAuth {CLIENT_ID}/")
    assert call["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    form = dict(urllib.parse.parse_qsl(call["body"].decode("ascii")))
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == CODE and form["client_id"] == CLIENT_ID
    assert form["redirect_uri"] == "http://127.0.0.1:8979/oauth/callback"
    assert form["scope"] == "account:characters"
    assert form["code_verifier"] == gggapi.b64url(bytes(range(32)))
    assert "client_secret" not in form
    assert "Authorization" not in call["headers"]
    assert c.connected and c.account == "SomeAccount"


def test_pending_is_single_use_and_code_is_checked():
    t = FakeTransport(token_answer(), token_answer())
    c = make(t)
    p = c.begin()
    with pytest.raises(gggapi.GggError):
        c.finish(p, "bad code!")
    assert t.calls == []
    c.finish(p, CODE)
    with pytest.raises(gggapi.GggError):
        c.finish(p, CODE)
    assert len(t.calls) == 1


def test_token_error_names_only_the_rfc_word():
    t = FakeTransport((400, {}, {"error": "invalid_grant",
                                 "error_description": ACCESS}))
    c = make(t)
    with pytest.raises(gggapi.HttpError) as e:
        c.finish(c.begin(), CODE)
    assert e.value.status == 400 and e.value.word == "invalid_grant"
    assert ACCESS not in str(e.value) and CODE not in str(e.value)
    assert not c.connected


def test_access_token_expires_in_memory():
    clock = Clock()
    c, t = connected(clock=clock)
    assert c.connected
    clock.t += 36000
    assert not c.connected
    with pytest.raises(gggapi.NotConnected):
        c.characters()
    assert len(t.calls) == 1


# -- refresh behind REFRESH_ALLOWED

def test_refresh_constant_is_off():
    assert gggapi.REFRESH_ALLOWED is False


def test_refresh_off_builds_no_request_and_never_calls_the_store():
    store = CountingStore({"refresh_token": REFRESH, "ceiling": 9e18})
    c, t = connected(store=store)
    assert c.connected
    with pytest.raises(gggapi.RefreshOff):
        c.refresh()
    c.disconnect()
    assert len(t.calls) == 1  # the code exchange only, no refresh request
    assert store.calls == []
    assert c.snapshot()["refresh_allowed"] is False


def test_refresh_token_in_answer_is_dropped_while_off():
    store = CountingStore()
    c, _t = connected(store=store)
    assert store.rec is None and store.calls == []
    assert REFRESH not in repr(vars(c))


def test_refresh_on_never_moves_the_stored_ceiling(monkeypatch):
    monkeypatch.setattr(gggapi, "REFRESH_ALLOWED", True)
    wall = Clock(1_800_000_000.0)
    store = CountingStore()
    t = FakeTransport(token_answer(),
                      token_answer(access="41bcefbc2f0d6ea0fa1cce10c435310d3c475e5b",
                                   refresh=REFRESH2, expires=2592000),
                      token_answer(access="aaaa", refresh="bbbb", expires=2592000))
    c = make(t, store=store, wall=wall)
    c.finish(c.begin(), CODE)
    ceiling = wall.t + gggapi.REFRESH_CEILING_S
    assert store.rec == {"refresh_token": REFRESH, "ceiling": ceiling}
    wall.t += 3 * 86400
    c.refresh()
    form = dict(urllib.parse.parse_qsl(t.calls[1]["body"].decode("ascii")))
    assert form == {"client_id": CLIENT_ID, "grant_type": "refresh_token",
                    "refresh_token": REFRESH}
    assert store.rec == {"refresh_token": REFRESH2, "ceiling": ceiling}
    wall.t += 2 * 86400
    c.refresh()
    assert store.rec["ceiling"] == ceiling
    wall.t = ceiling
    with pytest.raises(gggapi.ReconnectNeeded):
        c.refresh()
    assert len(t.calls) == 3 and store.rec is None


def test_refresh_on_without_a_stored_token_needs_a_browser(monkeypatch):
    monkeypatch.setattr(gggapi, "REFRESH_ALLOWED", True)
    t = FakeTransport()
    c = make(t, store=CountingStore())
    with pytest.raises(gggapi.ReconnectNeeded):
        c.refresh()
    assert t.calls == []


# -- redirects

@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_reply_never_resends_the_bearer(status):
    c, t = connected([(status, {"Location": "https://evil.example/x"}, b"")])
    with pytest.raises(gggapi.RedirectRefused):
        c.characters()
    assert len(t.calls) == 2  # exchange + the one refused read
    assert t.calls[1]["headers"]["Authorization"] == "Bearer " + ACCESS
    assert t.calls[1]["url"] == gggapi.API_BASE + gggapi.CHARACTERS_PATH
    assert all("evil" not in call["url"] for call in t.calls)


def test_token_endpoint_redirect_is_refused():
    t = FakeTransport((302, {"Location": "https://www.pathofexile.com/x"}, b""))
    c = make(t)
    with pytest.raises(gggapi.RedirectRefused):
        c.finish(c.begin(), CODE)
    assert len(t.calls) == 1 and not c.connected


# -- reads

def test_character_reads():
    c, t = connected([(200, {}, {"characters": []}),
                      (200, {}, {"character": {"name": "A b"}})])
    assert c.characters() == {"characters": []}
    assert c.character("A b") == {"character": {"name": "A b"}}
    assert t.calls[2]["url"] == gggapi.API_BASE + "/character/poe2/A%20b"
    assert t.calls[2]["method"] == "GET" and t.calls[2]["body"] is None


def test_401_drops_the_token():
    c, t = connected([(401, {}, b"")])
    with pytest.raises(gggapi.HttpError):
        c.characters()
    assert not c.connected
    with pytest.raises(gggapi.NotConnected):
        c.characters()
    assert len(t.calls) == 2


def test_host_allow_list():
    assert gggapi.ALLOWED_HOSTS == {"www.pathofexile.com", "api.pathofexile.com"}
    c = make(FakeTransport())
    with pytest.raises(Exception):
        c._send("GET", "https://example.com/", {}, None, "x")
    with pytest.raises(Exception):
        c._send("GET", "http://api.pathofexile.com/", {}, None, "x")


# -- the limiter

def test_limiter_wait_is_obeyed_before_each_request():
    clock = Clock()
    lim = ratelimit.RateLimiter(clock=clock, wall=lambda: 1_800_000_000.0)
    slept = []
    order = []

    def sleep(s):
        slept.append(s)
        order.append("sleep")
        clock.t += s

    limited = {"X-Rate-Limit-Rules": "Client", "X-Rate-Limit-Client": "1:10:60",
               "X-Rate-Limit-Client-State": "1:10:0"}
    t = FakeTransport((200, limited, {"characters": []}),
                      (200, limited, {"characters": []}),
                      on_call=lambda: order.append("send"))
    c, _ = connected(limiter=lim, sleep=sleep, clock=clock)
    c._fetch = t
    c.characters()
    assert slept == []
    c.characters()
    assert slept and abs(sum(slept) - 10.0) < 1e-6
    assert order == ["send", "sleep", "send"]


def test_limiter_retry_after_past_the_cap_refuses_without_sending():
    clock = Clock()
    lim = ratelimit.RateLimiter(clock=clock, wall=lambda: 1_800_000_000.0)
    t = FakeTransport(token_answer(), (429, {"Retry-After": "600"}, b""))
    c = make(t, limiter=lim, clock=clock)
    c.finish(c.begin(), CODE)
    with pytest.raises(gggapi.HttpError):
        c.characters()
    with pytest.raises(gggapi.RateLimited) as e:
        c.characters()
    assert e.value.wait_s == pytest.approx(600.0)
    assert len(t.calls) == 2


def test_token_exchange_is_paced():
    clock = Clock()
    lim = ratelimit.RateLimiter(clock=clock, wall=lambda: 1_800_000_000.0)
    lim.observe(gggapi.LIMIT_TOKEN, 429, {"Retry-After": "5"})
    slept = []

    def sleep(s):
        slept.append(s)
        clock.t += s

    c, t = connected(limiter=lim, sleep=sleep, clock=clock)
    assert slept == [pytest.approx(5.0)] and len(t.calls) == 1


# -- no token anywhere it must not be

def test_no_token_in_snapshot_log_diag_report_or_settings_export(caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    c, t = connected([(200, {}, {"characters": []}), (401, {}, b"")])
    c.characters()
    snap = c.snapshot()
    assert snap["connected"] is True and snap["scope"] == "account:characters"
    with pytest.raises(gggapi.HttpError):
        c.characters()
    secrets_ = [ACCESS, REFRESH, CODE]
    texts = [json.dumps(snap), json.dumps(c.snapshot()), repr(c), str(c),
             repr(vars(c)), caplog.text]
    texts += [r.getMessage() for r in caplog.records]
    facts = {"ggg": snap, "ggg_api": c.snapshot()}
    texts.append(json.dumps(diag.view(facts, "0.1.0", now=1_800_000_000.0)))
    cfg = {"web_data": True, "ggg": snap, "token": ACCESS,
           "ggg_access_token": ACCESS, "refresh_token": REFRESH}
    texts.append(json.dumps(settingsio.export_doc(cfg, "0.1.0")))
    for text in texts:
        for s in secrets_:
            assert s not in text
    assert "SomeAccount" not in json.dumps(snap)
