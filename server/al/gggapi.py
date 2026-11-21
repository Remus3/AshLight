"""TC-GGG-CLIENT-CORE: the offline core of AshLight's GGG OAuth client.

Decision 0048 (AshLight's own public client, realm poe2, authorization
code with PKCE S256, scope account:characters only, loopback redirects on
ports.OAUTH_REDIRECT_PORTS) and research 0035 (F3, F4, F8; GGG's
authorization docs, D-AUTH, and developer index, D-IDX). This module holds:

- PKCE: a verifier from 32 random bytes (base64url, 43 characters) and its
  S256 challenge; the state, 16 random bytes as hex.
- The authorize URL on GGG's documented /oauth/authorize, with the redirect
  URI built by oauthlisten.redirect_uri() on one of the two registered
  redirect ports (never any other port).
- The token exchange on /oauth/token (no client secret: a public client
  has none), paced by ratelimit.RateLimiter before every request.
- The User-Agent in GGG's required form,
  `OAuth <clientId>/<version> (contact: <contact>)`, followed by AshLight's
  own name and version, so the header names AshLight truthfully.
- The two character reads of decision 0048 (GET /character/poe2 and
  /character/poe2/<name>) with the bearer token.

Rules the code keeps:

- No request is possible without a client id: every request path checks it
  before the transport is touched. A granted id lives only in gitignored
  config/local.json (decision 0048 item 7); this module never reads it.
- The access token lives in this object's memory only. It is never in the
  snapshot, a log record, an exception message or a repr.
- REFRESH_ALLOWED is False. While it is False no refresh request is built,
  a refresh token in a token answer is dropped, and the injected credential
  store is never called, not even read. It is turned on only by a decision
  citing GGG's written answer to question 1 of
  docs/ops/ggg-oauth-application.md (F-083). When on (tests patch it), a
  refresh token is kept in the store with its 7-day ceiling set once at the
  code exchange; a refresh never moves that ceiling (D-AUTH: the new token
  inherits the old expiry), and past it a browser approval is needed.
- The bearer token never follows a redirect: the transport is one hop (the
  webfetch.make_transport shape, fetch(method, url, headers, body) ->
  (status, headers, body)), and any 3xx answer is refused, nothing re-sent.
- Every URL is checked against ALLOWED_HOSTS (webfetch.check_url: https,
  exact host, no IP literal, no trade path) before it is sent.

The transport is injected and required: this module opens no connection of
its own. Nothing in play builds a Client until TC-IMPORT wires it to the
player's Connect click (decision 0048 item 4).
"""

import base64
import hashlib
import json
import logging
import re
import secrets
import time
import urllib.parse

from . import NAME, VERSION, oauthlisten, ports, ratelimit, webfetch

AUTH_HOST = "www.pathofexile.com"
API_HOST = "api.pathofexile.com"
ALLOWED_HOSTS = frozenset({AUTH_HOST, API_HOST})
AUTHORIZE_URL = f"https://{AUTH_HOST}/oauth/authorize"
TOKEN_URL = f"https://{AUTH_HOST}/oauth/token"
API_BASE = f"https://{API_HOST}"
CHARACTERS_PATH = "/character/poe2"
SCOPE = "account:characters"  # decision 0048 item 2: the whole list

# Off until a decision cites GGG's written answer to question 1 (F-083).
REFRESH_ALLOWED = False
REFRESH_CEILING_S = 7 * 86400  # public client refresh lifetime (D-AUTH)

VERIFIER_BYTES = 32  # D-AUTH: at least 32 bytes of entropy
STATE_BYTES = 16
MAX_BODY = 2 * 1024 * 1024
MAX_TOKEN_CHARS = 512
MAX_EXPIRES_S = 90 * 86400
MAX_SLEEP_S = 60.0  # a longer limiter wait refuses the call instead of sleeping

LIMIT_TOKEN = "oauth-token"
LIMIT_LIST = "character-list"
LIMIT_CHAR = "character"

_CLIENT_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9._~+/=-]+")
_CODE_RE = re.compile(r"[A-Za-z0-9._~-]{1,%d}" % oauthlisten.MAX_CODE)
_WORD_RE = re.compile(r"[a-z_]{1,40}")
_REDIRECTS = (301, 302, 303, 307, 308)

log = logging.getLogger(__name__)


class GggError(Exception):
    """A GGG client call was refused or failed. Messages carry no token,
    code, verifier, state or response text."""


class NoClientId(GggError):
    """No usable client id: nothing is sent."""


class NoContact(GggError):
    """No usable contact for GGG's User-Agent form: nothing is sent."""


class RateLimited(GggError):
    """The limiter's wait is longer than this client will sleep."""

    def __init__(self, wait_s):
        super().__init__(f"rate limited for {wait_s:.0f} s")
        self.wait_s = wait_s


class RedirectRefused(GggError):
    """A 3xx answer: the request is not followed and nothing is re-sent."""


class NotConnected(GggError):
    """No live access token in memory."""


class RefreshOff(GggError):
    """REFRESH_ALLOWED is False: no refresh request is built."""


class ReconnectNeeded(GggError):
    """No usable refresh token (none kept, or past its ceiling)."""


class HttpError(GggError):
    """A non-2xx answer (status and, for OAuth errors, the RFC code word)."""

    def __init__(self, status, word=None):
        text = f"HTTP {status}" + (f" ({word})" if word else "")
        super().__init__(text)
        self.status = status
        self.word = word


# -- PKCE and state

def b64url(data):
    """base64url without padding (RFC 7636 appendix A)."""
    return base64.urlsafe_b64encode(bytes(data)).rstrip(b"=").decode("ascii")


def make_verifier(rand=secrets.token_bytes):
    """A code verifier from VERIFIER_BYTES random bytes (43 characters)."""
    raw = rand(VERIFIER_BYTES)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < VERIFIER_BYTES:
        raise GggError("not enough random bytes for a verifier")
    return b64url(raw)


def challenge(verifier):
    """The S256 code challenge of a verifier."""
    return b64url(hashlib.sha256(str(verifier).encode("ascii")).digest())


def make_state(rand=secrets.token_bytes):
    """A fresh state value (STATE_BYTES random bytes as hex)."""
    raw = rand(STATE_BYTES)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < STATE_BYTES:
        raise GggError("not enough random bytes for a state")
    return bytes(raw).hex()


# -- identity

def clean_client_id(value):
    """The client id as safe text, or None when unset or unusable."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _CLIENT_ID_RE.fullmatch(value) else None


def user_agent(client_id, contact, version=VERSION):
    """GGG's User-Agent form (D-IDX) plus AshLight's name and version.
    Raises NoClientId / NoContact when either part is unusable."""
    cid = clean_client_id(client_id)
    if cid is None:
        raise NoClientId("no GGG client id")
    who = webfetch.clean_contact(contact)
    if who is None:
        raise NoContact("no contact for the GGG User-Agent")
    return f"OAuth {cid}/{version} (contact: {who}) {NAME}/{version}"


def redirect_uri(port):
    """The registered redirect URI for one of ports.OAUTH_REDIRECT_PORTS."""
    if isinstance(port, bool) or port not in ports.OAUTH_REDIRECT_PORTS:
        raise GggError("the redirect port is not a registered one")
    return oauthlisten.redirect_uri(port)


def authorize_url(client_id, port, state, code_challenge, scope=SCOPE):
    """The consent page URL the player opens in the system browser."""
    cid = clean_client_id(client_id)
    if cid is None:
        raise NoClientId("no GGG client id")
    if not state or not code_challenge:
        raise GggError("state and challenge are required")
    query = urllib.parse.urlencode([
        ("client_id", cid),
        ("response_type", "code"),
        ("scope", scope),
        ("state", state),
        ("redirect_uri", redirect_uri(port)),
        ("code_challenge", code_challenge),
        ("code_challenge_method", "S256"),
    ], quote_via=urllib.parse.quote)
    return f"{AUTHORIZE_URL}?{query}"


# -- tokens in memory

class _Secret:
    """A string that never shows itself in a repr or str."""

    __slots__ = ("_value",)

    def __init__(self, value):
        self._value = value

    def reveal(self):
        return self._value

    def __repr__(self):
        return "<hidden>"

    __str__ = __repr__


class Pending:
    """One sign-in in flight: the verifier, state and redirect port. It is
    used once; finish() spends it."""

    __slots__ = ("_verifier", "_state", "port", "url", "spent")

    def __init__(self, verifier, state, port, url):
        self._verifier = _Secret(verifier)
        self._state = _Secret(state)
        self.port = port
        self.url = url
        self.spent = False

    @property
    def state(self):
        """The state to hand the one-shot listener (oauthlisten)."""
        return self._state.reveal()

    def __repr__(self):
        return f"<Pending port={self.port} spent={self.spent}>"


def _word(value):
    """An RFC OAuth error code as a safe word, or None."""
    if isinstance(value, str) and _WORD_RE.fullmatch(value):
        return value
    return None


def _json(data):
    if data is None or len(data) > MAX_BODY:
        raise GggError("answer missing or too large")
    try:
        doc = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise GggError("answer is not JSON") from e
    if not isinstance(doc, dict):
        raise GggError("answer is not a JSON object")
    return doc


def _token_text(value):
    if (isinstance(value, str) and 0 < len(value) <= MAX_TOKEN_CHARS
            and _TOKEN_RE.fullmatch(value)):
        return value
    return None


class Client:
    """AshLight's GGG OAuth public client (memory only).

    client = Client(client_id, contact, transport)
    pending = client.begin()        # pending.url -> system browser
    ... oauthlisten.OneShotListener(pending.state, ...) hands back the code
    client.finish(pending, code)    # token exchange; token kept in memory
    client.characters()             # GET /character/poe2

    transport: fetch(method, url, headers, body) -> (status, headers, body),
    one hop, injected (webfetch.make_transport in play). limiter: a
    ratelimit.RateLimiter (a new one by default). sleep / clock / wall /
    rand: injected for tests. store: the OS credential store adapter
    (load() -> dict or None, save(dict), clear()), used ONLY while
    REFRESH_ALLOWED is True.
    """

    def __init__(self, client_id, contact, transport, limiter=None,
                 store=None, sleep=time.sleep, clock=time.monotonic,
                 wall=time.time, rand=secrets.token_bytes,
                 max_sleep_s=MAX_SLEEP_S):
        if not callable(transport):
            raise GggError("a transport is required")
        self._client_id = clean_client_id(client_id)
        self._contact = contact
        self._fetch = transport
        self._clock = clock
        self._wall = wall
        self.limiter = limiter if limiter is not None else ratelimit.RateLimiter(clock, wall)
        self._store = store
        self._sleep = sleep
        self._rand = rand
        self._max_sleep_s = float(max_sleep_s)
        self._access = None
        self._expires_at = None
        self.scope = None
        self.account = None

    def __repr__(self):
        return f"<gggapi.Client connected={self.connected}>"

    # -- state

    @property
    def has_client_id(self):
        return self._client_id is not None

    @property
    def connected(self):
        return (self._access is not None and self._expires_at is not None
                and self._clock() < self._expires_at)

    def snapshot(self):
        """What a view may show: never a token, a code or the account."""
        left = None
        if self.connected:
            left = max(0, int(self._expires_at - self._clock()))
        return {"client_id_set": self.has_client_id, "connected": self.connected,
                "expires_in_s": left, "scope": self.scope if self.connected else None,
                "refresh_allowed": bool(REFRESH_ALLOWED)}

    def disconnect(self):
        """Forget the access token (and, when refresh is on, the stored one)."""
        self._access = None
        self._expires_at = None
        self.scope = None
        if REFRESH_ALLOWED and self._store is not None:
            self._store.clear()

    # -- sign-in

    def begin(self, port=None):
        """A Pending sign-in: fresh verifier and state, the authorize URL."""
        if self._client_id is None:
            raise NoClientId("no GGG client id")
        port = ports.OAUTH_REDIRECT_PORTS[0] if port is None else port
        verifier = make_verifier(self._rand)
        state = make_state(self._rand)
        url = authorize_url(self._client_id, port, state, challenge(verifier))
        return Pending(verifier, state, port, url)

    def finish(self, pending, code):
        """Exchange the code for an access token (kept in memory only)."""
        if self._client_id is None:
            raise NoClientId("no GGG client id")
        if not isinstance(pending, Pending) or pending.spent:
            raise GggError("no sign-in in flight")
        if not isinstance(code, str) or not _CODE_RE.fullmatch(code):
            raise GggError("the authorization code is unusable")
        pending.spent = True
        form = [("client_id", self._client_id),
                ("grant_type", "authorization_code"),
                ("code", code),
                ("redirect_uri", redirect_uri(pending.port)),
                ("scope", SCOPE),
                ("code_verifier", pending._verifier.reveal())]
        doc = self._token_request(form)
        self._take_tokens(doc, new_grant=True)
        log.info("ggg sign-in: token exchange ok")
        return self.snapshot()

    def refresh(self):
        """A new access token from the stored refresh token. While
        REFRESH_ALLOWED is False this raises RefreshOff and builds nothing."""
        if not REFRESH_ALLOWED:
            raise RefreshOff("refresh tokens are off (decision 0048 item 4)")
        if self._client_id is None:
            raise NoClientId("no GGG client id")
        if self._store is None:
            raise ReconnectNeeded("no credential store")
        rec = self._store.load()
        token = _token_text((rec or {}).get("refresh_token")) if isinstance(rec, dict) else None
        ceiling = rec.get("ceiling") if isinstance(rec, dict) else None
        if (token is None or isinstance(ceiling, bool)
                or not isinstance(ceiling, (int, float))
                or self._wall() >= ceiling):
            self._store.clear()
            raise ReconnectNeeded("a browser approval is needed")
        form = [("client_id", self._client_id),
                ("grant_type", "refresh_token"),
                ("refresh_token", token)]
        try:
            doc = self._token_request(form)
        except HttpError as e:
            if e.status in (400, 401):
                self._store.clear()
            raise
        self._take_tokens(doc, new_grant=False, ceiling=ceiling)
        log.info("ggg refresh ok")
        return self.snapshot()

    # -- reads

    def characters(self):
        """GET /character/poe2: the account's own characters (JSON object)."""
        return self._api_get(CHARACTERS_PATH, LIMIT_LIST)

    def character(self, name):
        """GET /character/poe2/<name> (JSON object)."""
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            raise GggError("a character name is required")
        path = CHARACTERS_PATH + "/" + urllib.parse.quote(name.strip(), safe="")
        return self._api_get(path, LIMIT_CHAR)

    # -- internals

    def _headers(self):
        return {"User-Agent": user_agent(self._client_id, self._contact),
                "Accept": "application/json"}

    def _pace(self, key):
        """Obey the limiter before a request: sleep its wait, or refuse a
        wait longer than max_sleep_s."""
        for _ in range(4):
            wait = self.limiter.wait_s(key)
            if wait <= 0:
                return
            if wait > self._max_sleep_s:
                raise RateLimited(wait)
            self._sleep(wait)
        wait = self.limiter.wait_s(key)
        if wait > 0:
            raise RateLimited(wait)

    def _send(self, method, url, headers, body, key):
        """One hop: host check, limiter, send, observe. No redirect followed."""
        if self._client_id is None:
            raise NoClientId("no GGG client id")
        webfetch.check_url(url, ALLOWED_HOSTS)
        self._pace(key)
        self.limiter.note_request(key)
        try:
            status, rh, data = self._fetch(method, url, dict(headers), body)
        except (webfetch.FetchError, OSError):
            raise GggError("network error") from None
        self.limiter.observe(key, status, rh)
        if status in _REDIRECTS:
            log.warning("ggg %s answer refused: redirect", key)
            raise RedirectRefused(f"HTTP {status} redirect refused")
        return status, rh, data

    def _token_request(self, form):
        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urllib.parse.urlencode(form).encode("ascii")
        status, _rh, data = self._send("POST", TOKEN_URL, headers, body, LIMIT_TOKEN)
        if not 200 <= status < 300:
            word = None
            try:
                err = _json(data).get("error")
                word = _word(err)
            except GggError:
                pass
            log.warning("ggg token request failed: HTTP %s", status)
            raise HttpError(status, word)
        return _json(data)

    def _take_tokens(self, doc, new_grant, ceiling=None):
        access = _token_text(doc.get("access_token"))
        if access is None or str(doc.get("token_type", "")).lower() != "bearer":
            raise GggError("the token answer has no bearer token")
        expires = doc.get("expires_in")
        if isinstance(expires, bool) or not isinstance(expires, (int, float)) or expires <= 0:
            raise GggError("the token answer has no lifetime")
        self._access = _Secret(access)
        self._expires_at = self._clock() + min(float(expires), MAX_EXPIRES_S)
        scope = doc.get("scope")
        self.scope = scope if isinstance(scope, str) and len(scope) <= 200 else None
        user = doc.get("username")
        self.account = user if isinstance(user, str) and len(user) <= 64 else None
        if not REFRESH_ALLOWED or self._store is None:
            return  # a refresh token in the answer is dropped, never kept
        refresh = _token_text(doc.get("refresh_token"))
        if refresh is None:
            return
        if new_grant:
            ceiling = self._wall() + REFRESH_CEILING_S
        # D-AUTH: a refreshed token inherits the old expiry; never moved
        self._store.save({"refresh_token": refresh, "ceiling": ceiling})

    def _api_get(self, path, key):
        if self._client_id is None:
            raise NoClientId("no GGG client id")
        if not self.connected:
            raise NotConnected("not connected to GGG")
        headers = self._headers()
        headers["Authorization"] = "Bearer " + self._access.reveal()
        status, _rh, data = self._send("GET", API_BASE + path, headers, None, key)
        if status == 401:
            self._access = None
            self._expires_at = None
            log.warning("ggg %s: token expired or revoked", key)
            raise HttpError(401)
        if not 200 <= status < 300:
            log.warning("ggg %s failed: HTTP %s", key, status)
            raise HttpError(status)
        return _json(data)
