"""TC-URL: fetch a user-pasted build share URL once per paste (decision 0013).

Supported sites (PoB's own share targets, research 0010 section 1):
- pobb.in:      https://pobb.in/<id>          -> https://pobb.in/<id>/raw
                https://pobb.in/u/<name>/<id> -> https://pobb.in/u/<name>/<id>/raw
  (a pasted .../raw link, or the PoB import route /pob/<id>, is accepted
  and rebuilt the same way);
- pastebin.com: https://pastebin.com/<id> -> https://pastebin.com/raw/<id>
  (a pasted /raw/<id> URL is taken as is).
pobb.in's /<id>/raw and /u/<name>/<id>/raw are the public third-party
routes in its README; /<id>/raw was checked live (200 text/plain, no
redirect; research 0013, 2026-11-17, TC-URL-POBBIN-RAW). The pastebin
/raw/<id> route exists; its 200 body is untested.

SSRF guard: the pasted URL is never fetched as given. Its host must be on
ALLOWED_HOSTS exactly, it must be https with no user info, no port and no
IP literal, and only the paste id (a short [A-Za-z0-9_-] token) and, for a
pobb.in user link, the user name (same charset) are taken from it; the
fetched URL is rebuilt from a fixed template. Redirects are
handled by server/al/webfetch.py and may not leave ALLOWED_HOSTS. The body
is capped at the codec's MAX_CODE_CHARS, decoded as UTF-8 and must itself be
a build (code or character JSON, paste.detect) - never another URL.
The caller loads the text through the normal paste path (store.load_code).
"""

import re
import urllib.parse

from .. import webfetch
from . import codec, paste

ALLOWED_HOSTS = ("pobb.in", "pastebin.com")
RAW_TEMPLATES = {
    "pobb.in": "https://pobb.in/{id}/raw",
    "pastebin.com": "https://pastebin.com/raw/{id}",
}
# pobb.in user links (/u/<name>/<id>), research 0013
POBB_USER_TEMPLATE = "https://pobb.in/u/{name}/{id}/raw"
USER_AGENT = webfetch.user_agent("fetching a build share link the user pasted")
MAX_BYTES = codec.MAX_CODE_CHARS
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RESERVED = ("raw", "pob", "u")


def _token(seg):
    return bool(_ID_RE.match(seg)) and seg not in _RESERVED


def raw_url(url):
    """The fixed raw-download URL for a pasted share URL, or UrlNotAllowed."""
    if not isinstance(url, str):
        raise webfetch.UrlNotAllowed("share URL must be text")
    url = url.strip()
    parts = webfetch.check_url(url, ALLOWED_HOSTS)
    host = parts.hostname.lower()
    segs = [s for s in urllib.parse.unquote(parts.path).split("/") if s]
    if host == "pastebin.com" and len(segs) == 2 and segs[0] == "raw":
        segs = segs[1:]
    if host == "pobb.in":
        if len(segs) in (2, 4) and segs[-1] == "raw":
            segs = segs[:-1]  # a pasted raw link: /<id>/raw, /u/<name>/<id>/raw
        elif len(segs) == 2 and segs[0] == "pob":
            segs = segs[1:]  # the PoB import route /pob/<id>
        if len(segs) == 3 and segs[0] == "u":
            if not (_token(segs[1]) and _token(segs[2])):
                raise webfetch.UrlNotAllowed("not a share link (bad user name or id)")
            return POBB_USER_TEMPLATE.format(name=segs[1], id=segs[2])
    if len(segs) != 1 or not _token(segs[0]):
        raise webfetch.UrlNotAllowed("not a share link (expected one paste id)")
    return RAW_TEMPLATES[host].format(id=segs[0])


def fetch_build_text(url, enabled, fetch=None):
    """Fetch the build text behind a pasted share URL, once. Raises
    webfetch.WebDataOff / UrlNotAllowed / FetchError or codec.CodeError."""
    webfetch.require_opt_in(enabled)
    target = raw_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/plain"}
    status, _rh, body = webfetch.request("GET", target, headers, ALLOWED_HOSTS,
                                         fetch=fetch, max_bytes=MAX_BYTES)
    if status != 200:
        raise webfetch.FetchError(f"share site answered HTTP {status}")
    try:
        text = body.decode("utf-8").strip()
    except UnicodeDecodeError as e:
        raise codec.CodeError("share link did not return text") from e
    if not text:
        raise codec.CodeError("share link returned nothing")
    kind = paste.detect(text)
    if kind == "url":
        raise codec.CodeError("share link returned another link; not followed")
    if kind not in ("code", "json"):
        raise codec.CodeError("share link did not return a build code")
    return text
