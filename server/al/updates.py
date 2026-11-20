"""DEP-16: the release check client of the in-app update notice (decision 0065).

One read of the project's GitHub `releases/latest` per 24 h, and only while
all three hold:

- the web-data opt-in is on (`enabled`, a callable read at call time;
  decision 0013: nothing hits the network while it is off);
- the player has acknowledged the opt-in wording that names the update
  check and the automatic apply (`acked` returns the acknowledged wording
  version; an opt-in given before WORDING_VERSION makes 0 requests until
  the player has seen the new sentence once, ruling Q-21);
- the repository constant is set: `<owner>/<name>` from the tracked
  config/public_repo.json the go-public address package writes; missing,
  empty or malformed = off, so nothing is requested before the address
  exists.

The request goes through server/al/webfetch only: host allow-list
api.github.com, the truthful AshLight User-Agent (no contact value is sent
to GitHub), never a cookie. A 304 against the cached ETag keeps the cached
answer and parses nothing; a 403 / 429 rate-limit reset time and a
Retry-After are honoured (the next read waits for the later of them and
the daily slot). Every attempt, failed or not, uses the day's one read.

The trimmed answer (tag, flags, dates and the asset names, sizes, digests
and download URLs) is cached under `cache_dir` for the installer process
(DEP-17), which verifies and stages; this module never downloads an asset
and never applies anything. A pre-release never counts as newer than a
release. view() is the one snapshot shape; the core wiring, the
acknowledgement click and the Settings text are REL-UPDATE-WIRE.
"""

import json
import re
import threading
import time
from pathlib import Path

from . import VERSION, jsonfile, paths, webfetch

WORDING_VERSION = 1          # the opt-in sentence that names the update check
DAY_S = 24 * 3600
WAIT_MAX_S = 7 * DAY_S       # a reset or Retry-After further out is not believed
API_HOST = "api.github.com"
ALLOWED_HOSTS = (API_HOST,)
MAX_BYTES = 1024 * 1024
STATE_NAME = "update_check.json"
STATE_MAX_BYTES = 256 * 1024
REPO_FILE = "public_repo.json"
REPO_MAX_BYTES = 4096
MAX_ASSETS = 32
TEXT_MAX = 200
URL_MAX = 512
NOTES_VERSIONS = 3
NOTES_TEXT_MAX = 600
CHANGELOG_MAX_BYTES = 2 * 1024 * 1024
UA_PURPOSE = "update check"

_REPO = re.compile(r"^(?!-)[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")
_SEMVER = re.compile(
    r"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$")
_HEAD = re.compile(r"^## \[([^\]]{1,40})\](?: - (\d{4}-\d{2}-\d{2}))?\s*$")
_ETAG = re.compile(r'^(W/)?"[\x21\x23-\x7e]{0,200}"$')


# ---------------------------------------------------------------- inputs

def clean_repo(value):
    """`<owner>/<name>` in GitHub's character set, else '' (off)."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not _REPO.match(value) or value.split("/")[1] in (".", ".."):
        return ""
    return value


def load_repo(path=None):
    """The repository constant from config/public_repo.json ('repo'), or ''
    when the file is missing, not JSON, or the value is malformed."""
    p = Path(path) if path is not None else paths.repo_root() / "config" / REPO_FILE
    doc = jsonfile.read_json(p, max_bytes=REPO_MAX_BYTES, kind=dict, default=None)
    return clean_repo((doc or {}).get("repo"))


def ack_ok(value):
    """True when the acknowledged wording version covers WORDING_VERSION.
    A bool, a string or a missing value is no acknowledgement."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= WORDING_VERSION


def _call(value):
    return value() if callable(value) else value


# --------------------------------------------------------------- versions

def parse_version(text):
    """(major, minor, patch, prerelease ids tuple) of a SemVer text with an
    optional leading 'v', or None. Build metadata is dropped."""
    if not isinstance(text, str) or len(text) > 64:
        return None
    m = _SEMVER.match(text.strip())
    if not m:
        return None
    pre = tuple(m.group(4).split(".")) if m.group(4) else ()
    if any(p.isdigit() and len(p) > 1 and p[0] == "0" for p in pre):
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), pre


def _pre_key(pre):
    # SemVer 11: no pre-release sorts above any pre-release; numeric ids
    # below alphanumeric; numeric compared as numbers; shorter list first.
    if not pre:
        return (1,)
    return (0,) + tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre) + ((-1, 0, ""),)


def version_key(parsed):
    return parsed[:3] + (_pre_key(parsed[3]),)


def is_newer(latest, installed, latest_prerelease=False):
    """True when `latest` is a release (never a pre-release, by its SemVer
    text or the API flag) that sorts above `installed`."""
    a, b = parse_version(latest), parse_version(installed)
    if a is None or b is None or a[3] or latest_prerelease:
        return False
    return version_key(a) > version_key(b)


# -------------------------------------------------------------- changelog

def changelog_notes(path=None, limit=NOTES_VERSIONS):
    """The newest `limit` version sections of the shipped CHANGELOG.md, each
    {"version", "date", "text"}: the hand-written lead when there is one,
    else the first bullet lines, cut at NOTES_TEXT_MAX characters. A
    missing or unreadable file gives []."""
    p = Path(path) if path is not None else paths.repo_root() / "CHANGELOG.md"
    try:
        if not p.is_file() or p.stat().st_size > CHANGELOG_MAX_BYTES:
            return []
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out, cur = [], None
    for line in lines:
        m = _HEAD.match(line)
        if m:
            if len(out) >= limit:
                break
            cur = {"version": m.group(1), "date": m.group(2), "lead": [], "items": [], "in_lead": False}
            out.append(cur)
            continue
        if cur is None:
            continue
        s = line.strip()
        if s.startswith("<!-- lead"):
            cur["in_lead"] = True
        elif s.startswith("<!-- /lead"):
            cur["in_lead"] = False
        elif cur["in_lead"] and s:
            cur["lead"].append(s)
        elif s.startswith("- "):
            cur["items"].append(s[2:].strip())
    notes = []
    for c in out:
        text = " ".join(c["lead"]) if c["lead"] else "; ".join(c["items"])
        if len(text) > NOTES_TEXT_MAX:
            text = text[:NOTES_TEXT_MAX - 3].rstrip() + "..."
        notes.append({"version": c["version"], "date": c["date"], "text": text})
    return notes


# ----------------------------------------------------------------- answer

def _text(value, cap=TEXT_MAX):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > cap or not value.isascii():
        return None
    return value


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _parse_release(body):
    """The trimmed releases/latest answer, or None when it is not a usable
    release object (not JSON, no tag, a draft)."""
    try:
        doc = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(doc, dict) or doc.get("draft") is True:
        return None
    tag = _text(doc.get("tag_name"), 64)
    if tag is None:
        return None
    assets = []
    for a in doc.get("assets") or []:
        if len(assets) >= MAX_ASSETS:
            break
        if not isinstance(a, dict):
            continue
        name = _text(a.get("name"))
        if name is None:
            continue
        assets.append({"name": name, "size": _int(a.get("size")),
                       "digest": _text(a.get("digest"), 100),
                       "url": _text(a.get("browser_download_url"), URL_MAX)})
    return {"tag": tag, "prerelease": doc.get("prerelease") is True,
            "published_at": _text(doc.get("published_at"), 40),
            "html_url": _text(doc.get("html_url"), URL_MAX), "assets": assets}


def _wait_s(headers, now):
    """Seconds the server asked us to wait (Retry-After, or a rate-limit
    reset with no requests left), at most WAIT_MAX_S; 0 when none."""
    waits = [webfetch.retry_after_s(headers, now, lo=0, hi=WAIT_MAX_S) or 0.0]
    remaining = webfetch.header(headers, "X-RateLimit-Remaining")
    reset = webfetch.header(headers, "X-RateLimit-Reset")
    if str(remaining).strip() == "0" and reset is not None and str(reset).strip().isdigit():
        waits.append(min(max(float(int(str(reset).strip())) - now, 0.0), float(WAIT_MAX_S)))
    return max(waits)


def _num(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


# ----------------------------------------------------------------- client

class UpdateClient:
    """The daily releases/latest read and its snapshot view.

    enabled: callable -> the web-data opt-in (read at call time).
    acked: callable -> the acknowledged opt-in wording version.
    repo: '<owner>/<name>', or None to read config/public_repo.json.
    fetch: webfetch transport fetch(method, url, headers, body); tests inject.
    clock: callable -> epoch seconds (used when tick() gets no `now`).
    cache_dir: folder for update_check.json (None: memory only).
    """

    def __init__(self, enabled, acked, repo=None, fetch=None, clock=time.time,
                 cache_dir=None, changelog=None, installed=VERSION):
        self.enabled = enabled
        self.acked = acked
        self.repo = load_repo() if repo is None else clean_repo(repo)
        self.fetch = fetch
        self.clock = clock
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.changelog = changelog
        self.installed = installed
        self._lock = threading.Lock()
        self.state = self._load()

    # state file ---------------------------------------------------------

    def state_file(self):
        return self.cache_dir / STATE_NAME if self.cache_dir is not None else None

    def _load(self):
        st = {"checked_at": None, "next_at": None, "etag": None, "latest": None,
              "error": None, "repo": self.repo}
        f = self.state_file()
        if f is None:
            return st
        doc = jsonfile.read_json(f, max_bytes=STATE_MAX_BYTES, kind=dict, default={})
        if doc.get("repo") != self.repo:
            return st  # another repository's answer is never reused
        st["checked_at"] = _num(doc.get("checked_at"))
        st["next_at"] = _num(doc.get("next_at"))
        latest = doc.get("latest")
        if isinstance(latest, dict) and _text(latest.get("tag"), 64):
            st["latest"] = latest
            etag = doc.get("etag")
            st["etag"] = etag if isinstance(etag, str) and _ETAG.match(etag) else None
        st["error"] = _text(doc.get("error"))
        return st

    def _save(self):
        f = self.state_file()
        if f is None:
            return
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            jsonfile.write_json(f, self.state)
        except OSError:
            pass  # next_at stays in memory: still one read per 24 h this run

    # gate ---------------------------------------------------------------

    def allowed(self):
        """True when a read may be made at all (enabled, acked, repo set)."""
        return bool(self.repo) and bool(_call(self.enabled)) and ack_ok(_call(self.acked))

    def due(self, now):
        nxt = self.state["next_at"]
        if nxt is None and self.state["checked_at"] is not None:
            nxt = self.state["checked_at"] + DAY_S
        return nxt is None or now >= nxt

    # the read -----------------------------------------------------------

    def url(self):
        return f"https://{API_HOST}/repos/{self.repo}/releases/latest"

    def tick(self, now=None):
        """Make the day's one read when allowed and due. True when a request
        was sent. Never raises on network or answer trouble."""
        with self._lock:
            if not self.allowed():
                return False
            now = float(self.clock() if now is None else now)
            if not self.due(now):
                return False
            headers = {"User-Agent": webfetch.user_agent(UA_PURPOSE),
                       "Accept": "application/vnd.github+json",
                       "X-GitHub-Api-Version": "2022-11-28"}
            if self.state["etag"] and self.state["latest"]:
                headers["If-None-Match"] = self.state["etag"]
            st = self.state
            st["checked_at"] = now
            st["next_at"] = now + DAY_S
            try:
                fetch = self.fetch or webfetch.make_transport(MAX_BYTES)
                status, rh, body = webfetch.request("GET", self.url(), headers, ALLOWED_HOSTS,
                                                    fetch=fetch, max_bytes=MAX_BYTES)
            except webfetch.FetchError as e:
                st["error"] = _text(f"request failed: {type(e).__name__}") or "request failed"
                self._save()
                return True
            st["next_at"] = now + max(float(DAY_S), _wait_s(rh, now))
            if status == 304:
                st["error"] = None
            elif status == 200:
                rel = _parse_release(body or b"")
                if rel is None:
                    st["error"] = "unreadable release answer"
                else:
                    st["latest"] = rel
                    etag = webfetch.header(rh, "ETag")
                    st["etag"] = etag if isinstance(etag, str) and _ETAG.match(etag) else None
                    st["error"] = None
            elif status == 404:
                st["latest"], st["etag"], st["error"] = None, None, None  # no release yet
            elif status in (403, 429):
                st["error"] = "refused or rate limited by GitHub"
            else:
                st["error"] = f"HTTP {int(status)}"
            self._save()
            return True

    # the snapshot view --------------------------------------------------

    def view(self):
        """The one snapshot shape: installed, latest, newer, prerelease,
        notes (newest 3 versions of the shipped CHANGELOG.md), releases_url
        (None while the repository constant is empty), checked_at,
        next_at, error and ack_needed."""
        with self._lock:
            latest = self.state["latest"] if self.repo else None
            tag = latest.get("tag") if latest else None
            pre = bool(latest.get("prerelease")) if latest else False
            parsed = parse_version(tag) if tag else None
            enabled = bool(_call(self.enabled))
            return {
                "installed": self.installed,
                "latest": tag[1:] if parsed and tag.startswith("v") else tag,
                "newer": bool(tag) and is_newer(tag, self.installed, pre),
                "prerelease": pre or bool(parsed and parsed[3]),
                "notes": changelog_notes(self.changelog),
                "releases_url": f"https://github.com/{self.repo}/releases" if self.repo else None,
                "checked_at": self.state["checked_at"] if self.repo else None,
                "next_at": self.state["next_at"] if self.repo else None,
                "error": self.state["error"] if self.repo else None,
                "ack_needed": bool(self.repo) and enabled and not ack_ok(_call(self.acked)),
            }
