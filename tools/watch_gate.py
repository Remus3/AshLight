"""LOOP-WATCH-GATE (F-030, AUTO-05): the one gate in front of every watcher
request. A watcher (a loop-tick source that checks an upstream for news)
asks this module three things:

- web_data_on(root): is the web-data opt-in on? It reads the 'web_data' key
  of <root>/config/local.json exactly as Core.web_data_enabled does (strictly
  True; a missing, unreadable or non-dict file is off), at call time.
- check_url(source, url): may this source read this URL? Only
  api.github.com repository METADATA paths (repository, commits, tags,
  branches, refs, releases by id / tag / latest; for the CI issue protocol
  the issue list /issues and the watch workflow /actions/workflows/watch.yml
  and its /runs, decision 0069 amendment 2026-11-21; the open pull request
  list /pulls and the alert list /dependabot/alerts for the Dependabot
  watch, and the community profile /community/profile for the GitHub page
  watch, amendments 2026-11-27) and the exact https URLs
  the source lists in SOURCE['urls'] pass. Every GGG host (the settled docs
  watch and release check keep their own reads, decisions 0044 and 0025),
  the trade site (webfetch.is_trade_url, decision 0017), raw / codeload /
  objects hosts and GitHub contents, archive, blob, raw and release-asset
  paths are refused, a listed URL included. Never a game data file
  (decisions 0009, 0013; floor audit L3).
- fetch(root, source, url, transport): one GET through
  server/al/webfetch.request with webfetch.check_url(url, hosts). It raises
  webfetch.WebDataOff before any request while web data is off, sends
  webfetch.user_agent(<purpose>) and never a cookie; every redirect hop is
  re-checked by check_url here, not only by the host list.

Python stdlib only. A source is a mapping (or a module with a SOURCE
mapping): {"name": str, "purpose": str (optional), "urls": [exact https
URLs] (optional)}.
"""

import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import webfetch  # noqa: E402

WebDataOff = webfetch.WebDataOff
UrlNotAllowed = webfetch.UrlNotAllowed

GITHUB_API = "api.github.com"
# GGG hosts: these domains and every subdomain of them.
GGG_DOMAINS = ("pathofexile.com", "pathofexile2.com", "grindinggear.com",
               "grindinggeargames.com", "poecdn.com")
# File-serving hosts: these hosts and every subdomain of them.
FILE_DOMAINS = ("githubusercontent.com", "codeload.github.com",
                "objects.githubusercontent.com", "githubassets.com")
# api.github.com/repos/<owner>/<repo><tail>: the metadata tails that pass.
_SEG = r"[A-Za-z0-9._-]+"
_REF = r"[A-Za-z0-9._/-]+"
METADATA_TAILS = tuple(re.compile(p) for p in (
    r"",
    r"/commits",
    r"/commits/" + _REF,
    r"/tags",
    r"/branches",
    r"/branches/" + _REF,
    r"/git/refs",
    r"/git/refs/" + _REF,
    r"/git/ref/" + _REF,
    r"/releases",
    r"/releases/latest",
    r"/releases/tags/" + _REF,
    r"/releases/[0-9]+",
    # CI issue protocol (decision 0076 item 6; 0069 amendment 2026-11-21):
    # the open issue list and the watch workflow's own state and runs. Every
    # other /issues/ and /actions/ sub-path stays refused.
    r"/issues",
    r"/actions/workflows/watch\.yml",
    r"/actions/workflows/watch\.yml/runs",
    # Dependabot watch (AUTO-20; 0069 amendment 2026-11-27): the open pull
    # request list and the alert list only; every sub-path stays refused.
    r"/pulls",
    r"/dependabot/alerts",
    # GitHub page watch (REVIEW-GH, decision 0088; 0069 amendment
    # 2026-11-27): the community profile (which community files exist and
    # the health percentage); every sub-path stays refused.
    r"/community/profile",
))
_REPO_PATH = re.compile(r"^/repos/(" + _SEG + r")/(" + _SEG + r")(/.*)?$")
# Path words that mean file content, never metadata (any GitHub host).
FILE_PATH_WORDS = ("contents", "archive", "tarball", "zipball", "assets",
                   "download", "raw", "blob", "blobs", "readme", "trees")


def web_data_on(root):
    """True only when <root>/config/local.json holds "web_data": true
    (read now, never cached; the same test as Core.web_data_enabled)."""
    try:
        cfg = json.loads((Path(root) / "config" / "local.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(cfg, dict) and cfg.get("web_data") is True


def _source(source):
    """The source mapping (a module's SOURCE, or the mapping itself)."""
    src = getattr(source, "SOURCE", source)
    if not isinstance(src, dict):
        raise UrlNotAllowed("a watcher source must be a mapping")
    return src


def listed_urls(source):
    """The exact URLs the source lists, as a tuple of strings."""
    urls = _source(source).get("urls") or ()
    if isinstance(urls, str) or not all(isinstance(u, str) for u in urls):
        raise UrlNotAllowed("SOURCE['urls'] must be a list of URL strings")
    return tuple(urls)


def _in_domains(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)


def _refuse_hosts(parts):
    """Raise UrlNotAllowed for a GGG, trade, file-serving or GitHub file URL."""
    host = (parts.hostname or "").lower().rstrip(".")
    if webfetch.is_trade_url(parts):
        raise UrlNotAllowed("the trade site is never called by the app (decision 0017)")
    if _in_domains(host, GGG_DOMAINS):
        raise UrlNotAllowed(f"GGG host not read by a watcher: {host}")
    if _in_domains(host, FILE_DOMAINS):
        raise UrlNotAllowed(f"file-serving host not read by a watcher: {host}")
    if host == "github.com" or host.endswith(".github.com"):
        words = {w.lower() for w in urllib.parse.unquote(parts.path or "").split("/")}
        hit = words.intersection(FILE_PATH_WORDS)
        if hit:
            raise UrlNotAllowed(f"GitHub file path not read by a watcher: {sorted(hit)[0]}")


def _github_metadata(parts):
    """True when the parsed URL is an api.github.com repository metadata path."""
    path = urllib.parse.unquote(parts.path or "")
    m = _REPO_PATH.match(path.rstrip("/") if path != "/" else path)
    if not m:
        return False
    tail = m.group(3) or ""
    return any(rx.fullmatch(tail) for rx in METADATA_TAILS)


def check_url(source, url):
    """The parsed URL when `source` may read `url`, else UrlNotAllowed.
    Base rules (https, no userinfo, port 443, no IP literal, ASCII, never the
    trade site) are webfetch.check_url's; then the host refusals; then the
    URL must be an api.github.com metadata path or an exact listed URL."""
    try:
        parts = urllib.parse.urlsplit(url) if isinstance(url, str) else None
        host = (parts.hostname or "").lower() if parts else ""
    except ValueError:
        parts, host = None, ""
    webfetch.check_url(url, [host] if host else [])
    _refuse_hosts(parts)
    if host == GITHUB_API:
        if _github_metadata(parts):
            return parts
        raise UrlNotAllowed("only GitHub repository metadata is read by a watcher")
    if url in listed_urls(source):
        return parts
    raise UrlNotAllowed(f"URL not listed by the source: {host or '(none)'}")


def purpose(source):
    """The User-Agent purpose text for this source."""
    src = _source(source)
    text = src.get("purpose") or f"dev: watcher {src.get('name') or 'read'}"
    return str(text)


def fetch(root, source, url, transport=None, max_bytes=webfetch.DEFAULT_MAX_BYTES):
    """One GET of `url` for `source`: (status, headers, body). Raises
    WebDataOff before any request while web data is off, UrlNotAllowed for
    a refused URL or redirect hop. `transport` is webfetch's
    fetch(method, url, headers, body) (default: the real one)."""
    if not web_data_on(root):
        raise WebDataOff("web data is off (opt-in setting web_data)")
    parts = check_url(source, url)
    hosts = [(parts.hostname or "").lower()]
    inner = transport or webfetch.make_transport(max_bytes)

    def guarded(method, hop_url, headers, body=None):
        check_url(source, hop_url)  # every hop meets the watcher rules too
        return inner(method, hop_url, headers, body)

    headers = {"User-Agent": webfetch.user_agent(purpose(source))}
    if parts.hostname and parts.hostname.lower() == GITHUB_API:
        headers["Accept"] = "application/vnd.github+json"
    return webfetch.request("GET", url, headers, hosts, fetch=guarded,
                            max_bytes=max_bytes)
