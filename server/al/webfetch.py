"""The one outbound web path of the AshLight core (DATA-NINJA, TC-URL).

Rules (CLAUDE.md "Game ToS floor", decision 0013):
- nothing is requested unless the user's web-data opt-in is on (the caller
  checks it through `require_opt_in`; every client in the core takes an
  `enabled` callable);
- https only, an explicit host allowlist per caller, no userinfo, no port
  other than 443, no IP literal, ASCII-only URL text;
- urllib never follows a redirect by itself: a 3xx is returned to this module,
  the Location is checked against the SAME allowlist and followed at most
  MAX_REDIRECTS times, so no redirect can leave the allowlist (SSRF guard);
- a truthful User-Agent naming AshLight and its version on every request;
  never a cookie (no POESESSID, no cookie jar);
- a response size cap and a short timeout on every request;
- SEC-CEIL-WEBFETCH: a TOTAL deadline (DEADLINE_S) per request on an
  injectable clock. The socket timeout bounds one silent wait only, so a
  server trickling one byte a second would never trip it; the body is read
  in blocks through read1 (one socket read each) and the deadline is
  checked between blocks and between redirect hops. A read overshoots it by
  at most one socket timeout;
- never the official trade site or its API, whatever a caller's allowlist
  says (decision 0017, `is_trade_url`);
- a gzip body is inflated through `inflate` with the same size cap applied
  AFTER inflation (a small compressed body cannot blow up in memory);
- `retry_after_s` is the one Retry-After parser, bounded to [lo, hi];
- RUN-METRICS-SITES (decision 0067): every real hop (`_open_once`) is
  counted in AshLight's own metrics as `fetch|<host>|<class>` (the host
  from the caller's allow-list, the class `2xx` .. `5xx` or `error`), its
  milliseconds in the `fetch_ms` ring and one typed `fetch` emit; no URL
  path, query or body is ever recorded.

`http_request` is the real transport; every client takes an injectable
`fetch(method, url, headers, body)` -> (status, headers dict, body bytes) so
tests never touch the network.
"""

import datetime
import email.utils
import http.client
import ipaddress
import math
import time
import zlib
import urllib.error
import urllib.parse
import urllib.request

from . import NAME, VERSION, metrics

TIMEOUT_S = 10.0
DEADLINE_S = 30.0
READ_BLOCK = 64 * 1024
MAX_REDIRECTS = 3
DEFAULT_MAX_BYTES = 2 * 1024 * 1024
REDIRECT_CODES = (301, 302, 303, 307, 308)
GZIP_ENCODINGS = ("gzip", "x-gzip")
RETRY_AFTER_LO_S = 3600
RETRY_AFTER_HI_S = 86400
RETRY_AFTER_MAX_CHARS = 64


class FetchError(Exception):
    """A request failed or was refused (network, HTTP status, policy)."""


class UrlNotAllowed(FetchError):
    """The URL breaks the https / allowlist / SSRF rules; nothing was sent."""


class WebDataOff(FetchError):
    """The web-data opt-in is off; nothing was sent."""


CONTACT_KEY = "contact"  # the key in gitignored config/local.json, never a tracked file
CONTACT_MAX = 120
REASON_OFF = "web data off"
REASON_CONTACT = "contact not set"


def clean_contact(value):
    """The configured contact as safe header text, or None when it is unset
    or unusable (non-string, blank, too long, non-printable-ASCII, or a
    parenthesis / backslash that would break the User-Agent comment)."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > CONTACT_MAX:
        return None
    if any(not 32 <= ord(c) < 127 or c in "()\\" for c in value):
        return None
    return value


def contact_value(contact):
    """clean_contact of contact() (a callable, read at call time) or of a value."""
    return clean_contact(contact() if callable(contact) else contact)


def user_agent(purpose, contact=None):
    """AshLight's truthful User-Agent: name, version and what the call is
    for, plus "(contact: <value>)" when a contact is configured (UA-CONTACT;
    GGG's developer docs and poe.ninja's API docs ask for one, research 0011)."""
    ua = f"{NAME}/{VERSION} (local Path of Exile 2 companion; {purpose})"
    value = clean_contact(contact)
    return f"{ua} (contact: {value})" if value else ua


def blocked_reason(enabled, contact):
    """Why a contact-requiring fetch (poe.ninja, GGG) may not run now:
    REASON_OFF, REASON_CONTACT, or None when it may."""
    if not (enabled() if callable(enabled) else enabled):
        return REASON_OFF
    if contact_value(contact) is None:
        return REASON_CONTACT
    return None


def require_opt_in(enabled):
    """Raise WebDataOff unless enabled() is true. `enabled` is a callable so
    the setting is read at call time, never cached."""
    if not (enabled() if callable(enabled) else enabled):
        raise WebDataOff("web data is off (opt-in setting web_data)")


def check_url(url, allowed_hosts):
    """The parsed URL when it is allowed, else UrlNotAllowed. Exact host
    match only (no subdomain, no trailing dot), lower-case compared."""
    if not isinstance(url, str) or not url or len(url) > 2048:
        raise UrlNotAllowed("URL missing or too long")
    if not url.isascii() or any(c.isspace() or c == "\\" or ord(c) < 32 for c in url):
        raise UrlNotAllowed("URL has non-ASCII, space or backslash characters")
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError as e:
        raise UrlNotAllowed(f"URL does not parse: {e}") from e
    if parts.scheme.lower() != "https":
        raise UrlNotAllowed("only https URLs are fetched")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise UrlNotAllowed("URL with user info is not fetched")
    if port not in (None, 443):
        raise UrlNotAllowed("URL with a non-default port is not fetched")
    host = (parts.hostname or "").lower()
    try:
        ipaddress.ip_address(host.strip("[]"))
        raise UrlNotAllowed("IP-literal hosts are not fetched")
    except ValueError:
        pass
    if is_trade_url(parts):
        raise UrlNotAllowed("the trade site is never called by the app (decision 0017)")
    if host not in {h.lower() for h in allowed_hosts}:
        raise UrlNotAllowed(f"host not allowed: {host or '(none)'}")
    return parts


def is_trade_url(parts):
    """True for any path of the official trade site or its API (decision
    0017: the app calls no trade endpoint; a link the user opens in their
    own browser is built by server/al/trade.py, never requested here)."""
    host = (parts.hostname or "").lower().rstrip(".")
    if host != "pathofexile.com" and not host.endswith(".pathofexile.com"):
        return False
    path = urllib.parse.unquote(parts.path or "").lower()
    return path.startswith(("/trade", "/api/trade"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand every 3xx back as an HTTPError; this module decides."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def host_word(url):
    """RUN-METRICS-SITES: the URL's host as a metrics WORD (lower-case, the
    host of the caller's allow-list), else "other"; never a path or query."""
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
    except (ValueError, AttributeError, TypeError):
        host = ""
    return host if host and metrics.WORD_RE.match(host) else "other"


def status_class(status):
    """"2xx" .. "5xx" for an HTTP status, else "error" (no reply)."""
    if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
        return f"{status // 100}xx"
    return "error"


def _count_fetch(url, status, t0):
    """One fetch in AshLight's own counters (decision 0067): typed values only."""
    host = host_word(url)
    cls = status_class(status)
    ms = round((time.monotonic() - t0) * 1000.0, 1)
    metrics.inc(f"fetch|{host}|{cls}")
    metrics.timing("fetch_ms", ms)
    metrics.emit("fetch", host=host, cls=cls, ms=ms)


def _past(deadline_at, clock):
    if clock() >= deadline_at:
        raise FetchError("request passed its total deadline")


def read_body(resp, max_bytes, deadline_at, clock=time.monotonic, cut=False):
    """The body of `resp`, at most max_bytes (more raises FetchError, or
    with cut=True is cut to max_bytes), read in blocks of at most READ_BLOCK
    through read1 when the response has it (one socket read per call, so a
    trickle returns between bytes), else read; FetchError once clock()
    reaches deadline_at (SEC-CEIL-WEBFETCH)."""
    reader = getattr(resp, "read1", None) or resp.read
    parts, size = [], 0
    while True:
        _past(deadline_at, clock)
        block = reader(min(READ_BLOCK, max_bytes + 1 - size))
        if not block:
            break
        parts.append(block)
        size += len(block)
        if size > max_bytes:
            if cut:
                return b"".join(parts)[:max_bytes]
            raise FetchError("response too large")
    return b"".join(parts)


def _open_once(method, url, headers, body, max_bytes, timeout,
               deadline_at=None, clock=time.monotonic):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect())
    t0 = time.monotonic()
    if deadline_at is None:
        deadline_at = clock() + DEADLINE_S
    status = None  # stays None (class "error") unless a reply is returned
    try:
        _past(deadline_at, clock)
        timeout = max(0.001, min(timeout, deadline_at - clock()))
        with opener.open(req, timeout=timeout) as resp:
            data = read_body(resp, max_bytes, deadline_at, clock)
            status = resp.status
            return status, dict(resp.headers.items()), data
    except urllib.error.HTTPError as e:
        try:
            data = (read_body(e, max_bytes, deadline_at, clock, cut=True)
                    if e.fp is not None else b"")
        except (OSError, http.client.HTTPException, FetchError):
            data = b""
        status = e.code
        return e.code, dict((e.headers or {}).items()), data[:max_bytes]
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
        # F-036: IncompleteRead, BadStatusLine, LineTooLong and the rest of
        # http.client's family are network failures too, never a crash
        raise FetchError(f"network: {type(e).__name__}: {e}") from e
    finally:
        _count_fetch(url, status, t0)


def header(headers, name):
    """Case-insensitive header lookup in a plain dict (None when absent)."""
    low = name.lower()
    for k, v in (headers or {}).items():
        if k.lower() == low:
            return v
    return None


def inflate(headers, data, max_bytes=DEFAULT_MAX_BYTES):
    """(headers, body) with a gzip body inflated (F-045). No
    Content-Encoding or "identity": returned as is. gzip / x-gzip: inflated
    through one zlib.decompressobj bounded at max_bytes + 1 output bytes, so
    a decompression bomb costs at most max_bytes of memory; the returned
    headers drop Content-Encoding. Any other encoding, a body that inflates
    past max_bytes, a broken, truncated or trailing-data gzip stream raises
    FetchError."""
    headers = dict(headers or {})
    enc = header(headers, "Content-Encoding")
    if enc is None or data is None:
        return headers, data
    enc = str(enc).strip().lower()
    if enc in ("", "identity"):
        return headers, data
    if enc not in GZIP_ENCODINGS:
        raise FetchError(f"unsupported Content-Encoding: {enc[:40]}")
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = d.decompress(bytes(data), max_bytes + 1)
    except (zlib.error, TypeError, ValueError) as e:
        raise FetchError(f"bad gzip body: {e}") from e
    if len(out) > max_bytes or d.unconsumed_tail:
        raise FetchError("response too large")
    if not d.eof:
        raise FetchError("bad gzip body: truncated")
    if d.unused_data:
        raise FetchError("bad gzip body: trailing data")
    return {k: v for k, v in headers.items()
            if k.lower() != "content-encoding"}, out


def retry_after_s(headers, now, lo=RETRY_AFTER_LO_S, hi=RETRY_AFTER_HI_S):
    """Seconds to wait from a Retry-After header (delta-seconds or an
    HTTP-date, RFC 9110 10.2.3), clamped to [lo, hi] (default 1 h to 24 h);
    `now` is epoch seconds. None when the header is absent or unreadable,
    so the caller keeps its own back-off."""
    raw = header(headers, "Retry-After")
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or len(text) > RETRY_AFTER_MAX_CHARS:
        return None
    if text.isdigit() and text.isascii():
        wait = float(int(text))
    else:
        try:
            when = email.utils.parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
        if when is None:
            return None
        if when.tzinfo is None:  # "-0000" / no zone: HTTP-dates are GMT
            when = when.replace(tzinfo=datetime.timezone.utc)
        try:
            wait = when.timestamp() - float(now)
        except (OverflowError, OSError, ValueError, TypeError):
            return None
    if not math.isfinite(wait):
        return None
    return min(max(wait, float(lo)), float(hi))


def make_transport(max_bytes=DEFAULT_MAX_BYTES, timeout=TIMEOUT_S,
                   deadline=DEADLINE_S, clock=time.monotonic):
    """The real one-hop transport, fetch(method, url, headers, body); each
    call gets its own total deadline of `deadline` seconds on `clock`."""
    def fetch(method, url, headers, body=None):
        return _open_once(method, url, headers, body, max_bytes, timeout,
                          clock() + deadline, clock)
    return fetch


def request(method, url, headers, allowed_hosts, body=None, fetch=None,
            max_bytes=DEFAULT_MAX_BYTES, max_redirects=MAX_REDIRECTS,
            deadline=DEADLINE_S, clock=time.monotonic):
    """One logical request through `fetch` (default: the real transport),
    following at most max_redirects redirects, each checked against
    allowed_hosts. Returns (status, headers, body) of the final hop; a 3xx
    past the limit or off the allowlist raises. A User-Agent header is
    required; a Cookie header is refused. The whole chain has one total
    deadline (SEC-CEIL-WEBFETCH): no hop starts after it, and the default
    transport's body reads stop at it."""
    if not header(headers, "User-Agent"):
        raise FetchError("a User-Agent is required")
    if header(headers, "Cookie") is not None:
        raise FetchError("cookies are never sent")
    deadline_at = clock() + deadline
    if fetch is None:
        def fetch(m, u, h, b=None):
            return _open_once(m, u, h, b, max_bytes, TIMEOUT_S, deadline_at, clock)
    current = url
    for hop in range(max_redirects + 1):
        check_url(current, allowed_hosts)
        _past(deadline_at, clock)
        status, rh, data = fetch(method, current, dict(headers), body)
        if data is not None and len(data) > max_bytes:
            raise FetchError("response too large")
        if status not in REDIRECT_CODES:
            rh, data = inflate(rh, data, max_bytes)  # cap applies after inflation
            return status, rh, data
        location = header(rh, "Location")
        if not location:
            raise FetchError(f"HTTP {status} without Location")
        current = urllib.parse.urljoin(current, location)
        if status == 303 or (status in (301, 302) and method == "POST"):
            method, body = "GET", None
    check_url(current, allowed_hosts)  # report an off-list target first
    raise FetchError("too many redirects")
