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
- never the official trade site or its API, whatever a caller's allowlist
  says (decision 0017, `is_trade_url`).

`http_request` is the real transport; every client takes an injectable
`fetch(method, url, headers, body)` -> (status, headers dict, body bytes) so
tests never touch the network.
"""

import ipaddress
import urllib.error
import urllib.parse
import urllib.request

from . import NAME, VERSION

TIMEOUT_S = 10.0
MAX_REDIRECTS = 3
DEFAULT_MAX_BYTES = 2 * 1024 * 1024
REDIRECT_CODES = (301, 302, 303, 307, 308)


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


def _open_once(method, url, headers, body, max_bytes, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise FetchError("response too large")
            return resp.status, dict(resp.headers.items()), data
    except urllib.error.HTTPError as e:
        try:
            data = e.read(max_bytes + 1) if e.fp is not None else b""
        except OSError:
            data = b""
        return e.code, dict((e.headers or {}).items()), data[:max_bytes]
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise FetchError(f"network: {e}") from e


def header(headers, name):
    """Case-insensitive header lookup in a plain dict (None when absent)."""
    low = name.lower()
    for k, v in (headers or {}).items():
        if k.lower() == low:
            return v
    return None


def make_transport(max_bytes=DEFAULT_MAX_BYTES, timeout=TIMEOUT_S):
    """The real one-hop transport, fetch(method, url, headers, body)."""
    def fetch(method, url, headers, body=None):
        return _open_once(method, url, headers, body, max_bytes, timeout)
    return fetch


def request(method, url, headers, allowed_hosts, body=None, fetch=None,
            max_bytes=DEFAULT_MAX_BYTES, max_redirects=MAX_REDIRECTS):
    """One logical request through `fetch` (default: the real transport),
    following at most max_redirects redirects, each checked against
    allowed_hosts. Returns (status, headers, body) of the final hop; a 3xx
    past the limit or off the allowlist raises. A User-Agent header is
    required; a Cookie header is refused."""
    if not header(headers, "User-Agent"):
        raise FetchError("a User-Agent is required")
    if header(headers, "Cookie") is not None:
        raise FetchError("cookies are never sent")
    fetch = fetch or make_transport(max_bytes)
    current = url
    for hop in range(max_redirects + 1):
        check_url(current, allowed_hosts)
        status, rh, data = fetch(method, current, dict(headers), body)
        if data is not None and len(data) > max_bytes:
            raise FetchError("response too large")
        if status not in REDIRECT_CODES:
            return status, rh, data
        location = header(rh, "Location")
        if not location:
            raise FetchError(f"HTTP {status} without Location")
        current = urllib.parse.urljoin(current, location)
        if status == 303 or (status in (301, 302) and method == "POST"):
            method, body = "GET", None
    check_url(current, allowed_hosts)  # report an off-list target first
    raise FetchError("too many redirects")
