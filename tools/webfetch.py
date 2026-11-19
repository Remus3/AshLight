"""DIVE-FLOOR (decision 0050, ruling Q-07): the one web path of a research
dive. A dive lane is spawned without WebFetch or WebSearch; every page it
reads goes through this CLI, which sends nothing unless `allowed(url)` passes.

Python stdlib only; the transport, URL checks and User-Agent are
server/al/webfetch.py (request rules, check_url, is_trade_url, user_agent).

The allow-list (one function, `allowed`):
- GGG (any pathofexile.com, pathofexile2.com, grindinggear.com or
  poecdn.com host): ONLY https://www.pathofexile.com/developer/docs/reference
  and /developer/docs/data, no query. GGG's forum, the trade site and every
  other GGG path are refused. GGG's other developer-docs pages (index,
  authorization, changelog, game) stay refused while the constant
  A01_OTHER_DOCS_PAGES is False (operator decision A-01, default no).
- Public non-GGG repositories through the documented GitHub API:
  https://api.github.com/repos/<owner>/<repo>... only.
- Nothing else: poe2db and every wiki host are refused by name, every other
  host by the list.

Every request also obeys the web-data opt-in (config/local.json
"web_data" strictly true, read at call time, as webfetch.require_opt_in),
carries the truthful AshLight User-Agent (plus the configured contact),
never a cookie; each redirect hop is re-checked against `allowed`, and a
429 / 503 Retry-After is kept per host and obeyed. Every hop, fetched or
refused, appends one ASCII line to the host log in the AL sidecar Logs
(dive_fetch/hosts.log).

CLI:
  python tools/webfetch.py check <url>   allow-list verdict, sends nothing
  python tools/webfetch.py get <url> [--raw]
  python tools/webfetch.py hosts         the allow-list in words
Exit codes: 0 ok, 1 fetch / HTTP error, 2 refused by the allow-list,
3 web data off, 4 rate limited (Retry-After not yet passed).
"""

import argparse
import email.utils
import html.parser
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import paths, webfetch  # noqa: E402

UA_PURPOSE = "dev: research dive read"
GGG_HOST = "www.pathofexile.com"
GGG_DOMAINS = ("pathofexile.com", "pathofexile2.com", "grindinggear.com", "poecdn.com")
GGG_PAGES = ("/developer/docs/reference", "/developer/docs/data")
# Operator decision A-01 (docs/plan/09): whether GGG's developer-docs pages
# outside the API Reference and Data Exports may be read. Default no.
A01_OTHER_DOCS_PAGES = False
GGG_OTHER_DOCS = ("/developer/docs", "/developer/docs/authorization",
                  "/developer/docs/changelog", "/developer/docs/game")
GITHUB_API = "api.github.com"
GGG_GITHUB_OWNERS = ("grindinggear", "grindinggeargames", "ggg", "pathofexile")
REFUSED_WORDS = ("poe2db", "wiki", "fandom")
HOSTS = (GGG_HOST, GITHUB_API)  # the transport's host list; allowed() narrows it
MAX_BYTES = 2 * 1024 * 1024
RATE_MIN_S = 3600  # a 429 / 503 without a usable Retry-After waits this long
LOG_DIR = "dive_fetch"
LOG_NAME = "hosts.log"
RATE_NAME = "ratelimit.json"

EXIT_OK, EXIT_FETCH, EXIT_REFUSED, EXIT_OFF, EXIT_RATE = 0, 1, 2, 3, 4


class RateLimited(webfetch.FetchError):
    """The host asked us to wait (Retry-After) and the time has not passed."""


def _is_ggg(host):
    return any(host == d or host.endswith("." + d) for d in GGG_DOMAINS)


def allowed(url):
    """(True, "ok") when a dive may fetch url, else (False, reason). Sends
    nothing. The one allow-list of decision 0050."""
    try:
        parts = urllib.parse.urlsplit(url) if isinstance(url, str) else None
        host = (parts.hostname or "").lower().rstrip(".") if parts else ""
    except ValueError:
        host = ""
    if any(w in host for w in REFUSED_WORDS):
        return False, f"{host}: poe2db and wiki hosts are never read by a dive (decision 0050)"
    try:
        parts = webfetch.check_url(url, HOSTS)
    except webfetch.UrlNotAllowed as e:
        if host and _is_ggg(host):
            return False, _ggg_reason(urllib.parse.urlsplit(url), host, str(e))
        return False, str(e)
    host = (parts.hostname or "").lower()
    path = parts.path or "/"
    if path != urllib.parse.unquote(path) or "//" in path or "/." in path:
        return False, "encoded or dot path segments are not fetched"
    if host == GGG_HOST:
        trimmed = path.rstrip("/") or "/"
        if trimmed.lower().startswith("/forum"):
            return False, "GGG's forum is never read by an agent or tool (decision 0050, Q-07)"
        if trimmed in GGG_PAGES or (A01_OTHER_DOCS_PAGES and trimmed in GGG_OTHER_DOCS):
            if parts.query:
                return False, "a query on a GGG docs page is not fetched"
            return True, "ok"
        return False, _ggg_reason(parts, host, "")
    if host == GITHUB_API:
        seg = [s for s in path.split("/") if s]
        if len(seg) < 3 or seg[0] != "repos":
            return False, "only /repos/<owner>/<repo> paths of the GitHub API are read"
        if seg[1].lower() in GGG_GITHUB_OWNERS:
            return False, "GGG's own repositories are not a dive source (decision 0050)"
        return True, "ok"
    return False, f"host not allowed: {host}"


def _ggg_reason(parts, host, base):
    path = urllib.parse.unquote(parts.path or "").lower()
    if path.startswith("/forum") or host.startswith("forum."):
        return "GGG's forum is never read by an agent or tool (decision 0050, Q-07)"
    if webfetch.is_trade_url(parts):
        return "the trade site is never called (decision 0017)"
    if path.rstrip("/") in GGG_OTHER_DOCS:
        return ("GGG's docs pages outside the API Reference and Data Exports are "
                "not read (operator decision A-01, off)")
    return base or ("on GGG's hosts only the API Reference and Data Exports pages "
                    "are read (decision 0050)")


# --- files ----------------------------------------------------------------

def log_dir(environ=None):
    return paths.sidecar_dir("Logs", environ) / LOG_DIR


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _ascii(text):
    return str(text).encode("ascii", "replace").decode("ascii").replace("\n", " ")


def log_hop(logs, now, url, ua, status=None, refused=None):
    """One ASCII line per hop: time, host, path, outcome and the User-Agent
    sent (for a refusal: nothing was sent)."""
    try:
        parts = urllib.parse.urlsplit(url)
        host, path = (parts.hostname or "-"), (parts.path or "/")
    except ValueError:
        host, path = "-", "-"
    what = f"refused={_ascii(refused)} sent=no" if refused else f"status={status}"
    line = f"{_iso(now)} host={_ascii(host)} path={_ascii(path)} {what} ua={_ascii(ua)}\n"
    Path(logs).mkdir(parents=True, exist_ok=True)
    with open(Path(logs) / LOG_NAME, "a", encoding="ascii", newline="\n") as fh:
        fh.write(line)


def _load_rate(logs):
    try:
        doc = json.loads((Path(logs) / RATE_NAME).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_rate(logs, doc):
    Path(logs).mkdir(parents=True, exist_ok=True)
    p = Path(logs) / RATE_NAME
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="ascii")
    os.replace(tmp, p)


def _retry_after(value, now):
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return now + int(value)
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return dt.timestamp() if dt else None


# --- fetch ----------------------------------------------------------------

def get(url, enabled, contact=None, fetch=None, logs=None, now=time.time):
    """(status, headers, body) of one GET, every hop through allowed().
    Raises webfetch.WebDataOff, webfetch.UrlNotAllowed, RateLimited or
    webfetch.FetchError; never sends a request that allowed() refuses."""
    webfetch.require_opt_in(enabled)
    logs = Path(logs) if logs is not None else log_dir()
    ua = webfetch.user_agent(UA_PURPOSE, webfetch.contact_value(contact))
    headers = {"User-Agent": ua, "Accept": "text/html, application/json;q=0.9",
               "Accept-Language": "en"}
    current = url
    for _hop in range(webfetch.MAX_REDIRECTS + 1):
        ok, reason = allowed(current)
        if not ok:
            log_hop(logs, now(), current, ua, refused=reason)
            raise webfetch.UrlNotAllowed(reason)
        host = urllib.parse.urlsplit(current).hostname.lower()
        until = _load_rate(logs).get(host)
        if isinstance(until, (int, float)) and until > now():
            log_hop(logs, now(), current, ua, refused=f"rate limited until {_iso(until)}")
            raise RateLimited(f"{host} rate limited until {_iso(until)}")
        status, rh, data = _one_hop(current, headers, fetch)
        log_hop(logs, now(), current, ua, status=status)
        if status in (429, 503):
            t = now()
            wait = max(_retry_after(webfetch.header(rh, "Retry-After"), t) or 0,
                       t + RATE_MIN_S)
            doc = _load_rate(logs)
            doc[host] = wait
            _save_rate(logs, doc)
            raise RateLimited(f"HTTP {status} from {host}, waiting until {_iso(wait)}")
        if status not in webfetch.REDIRECT_CODES:
            return status, rh, data
        location = webfetch.header(rh, "Location")
        if not location:
            raise webfetch.FetchError(f"HTTP {status} without Location")
        current = urllib.parse.urljoin(current, location)
    raise webfetch.FetchError("too many redirects")


def _one_hop(url, headers, fetch):
    """One request, no redirect following (get() re-checks every hop
    against allowed(), which is narrower than a host list)."""
    if not webfetch.header(headers, "User-Agent"):
        raise webfetch.FetchError("a User-Agent is required")
    if webfetch.header(headers, "Cookie") is not None:
        raise webfetch.FetchError("cookies are never sent")
    webfetch.check_url(url, HOSTS)
    fetch = fetch or webfetch.make_transport(MAX_BYTES)
    status, rh, data = fetch("GET", url, dict(headers), None)
    if data is not None and len(data) > MAX_BYTES:
        raise webfetch.FetchError("response too large")
    return status, rh, data


class _Text(html.parser.HTMLParser):
    """Readable text of an HTML page: one line per block, scripts dropped."""

    BLOCK = {"p", "div", "li", "tr", "br", "pre", "section", "article", "table",
             "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "header", "footer"}
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.cur, self.skip = [], [], 0

    def _flush(self):
        text = " ".join("".join(self.cur).split())
        if text:
            self.out.append(text)
        self.cur = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(self.skip - 1, 0)
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self.skip:
            self.cur.append(data)


def page_text(body, content_type):
    text = (body or b"").decode("utf-8", "replace")
    if "html" in (content_type or "").lower():
        p = _Text()
        p.feed(text)
        p.close()
        p._flush()
        return "\n".join(p.out) + "\n"
    return text


# --- CLI ------------------------------------------------------------------

def _config():
    cfg = paths.load_local_config()
    return cfg if isinstance(cfg, dict) else {}


def describe():
    pages = ", ".join("https://" + GGG_HOST + p for p in GGG_PAGES)
    return ("allowed: " + pages + "; https://" + GITHUB_API + "/repos/<owner>/<repo>... "
            "(public non-GGG repositories)\nrefused: GGG's forum, the trade site, every "
            "other GGG path (A-01 off), poe2db, wiki hosts, every other host\n")


def main(argv=None, fetch=None, logs=None, config=None, out=None):
    ap = argparse.ArgumentParser(prog="webfetch", description="AshLight research-dive fetch "
                                 "(decision 0050)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="allow-list verdict for a URL; sends nothing")
    c.add_argument("url")
    g = sub.add_parser("get", help="fetch one allowed URL and print its text")
    g.add_argument("url")
    g.add_argument("--raw", action="store_true", help="print the body as sent, no HTML strip")
    sub.add_parser("hosts", help="print the allow-list")
    args = ap.parse_args(argv)
    out = out or sys.stdout
    if args.cmd == "hosts":
        out.write(describe())
        return EXIT_OK
    if args.cmd == "check":
        ok, reason = allowed(args.url)
        out.write(("allowed: " if ok else "refused: ") + _ascii(reason) + "\n")
        return EXIT_OK if ok else EXIT_REFUSED
    cfg = _config() if config is None else config
    try:
        status, rh, data = get(args.url, enabled=lambda: cfg.get("web_data") is True,
                               contact=cfg.get(webfetch.CONTACT_KEY), fetch=fetch, logs=logs)
    except webfetch.WebDataOff as e:
        out.write(f"webfetch: {e}\n")
        return EXIT_OFF
    except webfetch.UrlNotAllowed as e:
        out.write(f"webfetch: refused: {_ascii(e)}\n")
        return EXIT_REFUSED
    except RateLimited as e:
        out.write(f"webfetch: {e}\n")
        return EXIT_RATE
    except webfetch.FetchError as e:
        out.write(f"webfetch: {_ascii(e)}\n")
        return EXIT_FETCH
    if status != 200:
        out.write(f"webfetch: HTTP {status} from {args.url}\n")
        return EXIT_FETCH
    ctype = webfetch.header(rh, "Content-Type")
    text = (data or b"").decode("utf-8", "replace") if args.raw else page_text(data, ctype)
    out.write(f"# {args.url} (HTTP {status}, accessed {time.strftime('%Y-%m-%d')})\n")
    out.write(text.encode("ascii", "replace").decode("ascii"))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
