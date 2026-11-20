"""GGG-DOCS-WATCH: a daily read of GGG's developer docs, above all whether
new OAuth application registration has reopened (decision 0044).

Python stdlib only. Read-only and anonymous:

- At most one run per CHECK_EVERY_S (24 h); 3 h after a network error; never
  before a 429 / 503 Retry-After has passed (the run stops at the first one).
- One sequential GET per page (PAGES), https only, host www.pathofexile.com
  only, through server/al/webfetch.py: truthful AshLight User-Agent, no
  cookie, no token, size cap, redirects re-checked against the allowlist.
- The text inside <main> is extracted (headings marked with #, list items
  with -), whitespace normalised, hashed (sha256). Baseline snapshots and the
  gate state live in the AL sidecar Cache (ggg_docs/); a changed page writes
  a unified diff to the sidecar Logs (ggg_docs/), never a tracked file.
- ops/runtime/ggg_docs/notes.log gets one dated ASCII line per change; the
  flag file ops/runtime/ggg_docs/REG_OPEN exists exactly while the index
  page is readable and no longer carries GGG's "unable to process new
  applications" sentence. The core shows it as a note in the Checks view
  (server/al/diag.py) and the next interactive session acts on ROADMAP
  TC-OAUTH-REG.

`safe_check(root, now)` (loop_check, fault-safe) is the al_loop tick hook (it runs even while the
loop is HALTed: read-only, cheap, no claude spawn; decision 0044).
CLI: `check [--force]`, `status`. Exit codes: 0 ok, 1 failure.
"""

import argparse
import difflib
import email.utils
import hashlib
import html.parser
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import paths, webfetch  # noqa: E402

HOSTS = ("www.pathofexile.com",)
BASE = "https://www.pathofexile.com/developer/docs"
PAGES = (("index", BASE), ("authorization", BASE + "/authorization"),
         ("reference", BASE + "/reference"), ("changelog", BASE + "/changelog"),
         ("data", BASE + "/data"), ("game", BASE + "/game"))
UA_PURPOSE = "dev: GGG developer docs change watch"
CHECK_EVERY_S = 24 * 3600
RETRY_S = 3 * 3600
RATE_MIN_S = 3600  # a 429 / 503 without a usable Retry-After waits this long
PAGE_GAP_S = 1.0   # pause between the sequential page reads
MAX_BYTES = 1024 * 1024
MIN_TEXT = 200     # a page shorter than this (challenge page, error) is unreadable

CLOSED_SENTENCE = "We are currently unable to process new applications."
REG_HEADING = "Registering your Application"
INDEX_MARKER = "Getting Started"

STATE_NAME = "state.json"
RUNTIME_REL = Path("ops") / "runtime" / "ggg_docs"
FLAG_NAME = "REG_OPEN"
NOTES_NAME = "notes.log"

# Changed lines are tagged with every topic whose words they carry.
TOPICS = (
    ("registration", ("application", "register", "apply", "mailto", "form",
                      "email", "e-mail")),
    ("token-lifetime", ("hour", "day", "expire", "lifetime", "last for")),
    ("scopes", ("account:", "service:", "scope")),
    ("redirect", ("redirect", "127.0.0.1", "localhost", "callback")),
    ("client-type", ("public client", "confidential client", "pkce")),
    ("poe2", ("poe2", "path of exile 2", "realm")),
    ("rate-limit", ("rate limit", "x-rate-limit", "retry-after")),
    ("policy", ("overlay", "macro", "clipboard", "screen", "terms of use")),
    ("shape", None),  # computed by shape_fields(), not a word list
)

# DOCS-SHAPE (AUTO-11, decision 0044 amendment 2026-11-20): the GGG field
# names AshLight's readers use (server/al/theorycraft/charjson.py for the
# character JSON, server/al/theorycraft/treedata.py for the tree export). A
# changed docs line naming one, as a whole case-sensitive word, tags the
# change "shape" and the note names the fields. tests/test_ggg_docs_watch.py
# checks that every name still appears in those readers.
SHAPE_FIELDS = (
    # character JSON (charjson.py)
    "equipment", "jewels", "passives", "hashes", "specialisations", "skills",
    "socketedItems", "inventoryId", "typeLine", "baseType", "frameType",
    "rarity", "ilvl", "properties", "implicitMods", "explicitMods",
    "craftedMods", "enchantMods", "fracturedMods", "runeMods",
    "desecratedMods",
    # passive tree export (treedata.py)
    "ascendancyId", "ascendancyName", "isNotable", "isKeystone",
    "isJewelSocket", "classStartIndex", "classesStart",
)
# The shape topic runs on these pages only (the API Reference and the Data
# Exports). SHAPE_ALL_PAGES stays False while operator decision A-01 is open:
# no new topic on the index, authorization, changelog or game pages.
SHAPE_PAGES = ("reference", "data")
SHAPE_ALL_PAGES = False
_SHAPE_RE = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(SHAPE_FIELDS)
                       + r")(?![A-Za-z0-9_])")

_BLOCK = {"p", "div", "li", "ul", "ol", "dl", "dt", "dd", "article", "section",
          "header", "footer", "table", "tr", "td", "th", "pre", "blockquote",
          "small", "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "nav", "form"}
_SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}
_VOID = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area",
         "base", "col", "embed", "param", "track"}


class DocsError(webfetch.FetchError):
    """A page could not be read."""


class RateLimited(DocsError):
    def __init__(self, until, status):
        super().__init__(f"HTTP {status}, rate limited until {iso(until)}")
        self.until = until


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


# --- extraction ---------------------------------------------------------

class _MainText(html.parser.HTMLParser):
    """Text of the first <main>: one line per block, headings as '#'*n,
    list items as '- '. Also counts registration channels inside it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0        # >0 while inside <main>
        self.seen_main = False
        self.skip = 0
        self.pre = 0
        self.lines = []
        self.cur = []
        self.prefix = ""
        self.mailto = []
        self.forms = 0
        self.ids = []         # article ids in order (changelog entries)

    def _flush(self):
        text = "".join(self.cur)
        self.cur = []
        if self.pre:
            for ln in text.split("\n"):
                ln = " ".join(ln.split())
                if ln:
                    self.lines.append(ln)
        else:
            text = " ".join(text.split())
            if text:
                self.lines.append(self.prefix + text)
        self.prefix = ""

    def handle_starttag(self, tag, attrs):
        if tag == "main" and not self.seen_main:
            self.seen_main = True
            self.depth = 1
            return
        if not self.depth:
            return
        if tag == "main":
            self.depth += 1
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        a = dict(attrs)
        if tag == "a":
            href = (a.get("href") or "").strip()
            if href.lower().startswith("mailto:"):
                self.mailto.append(href[7:].split("?")[0])
        if tag == "form":
            self.forms += 1
        if tag == "article" and a.get("id"):
            self.ids.append(a["id"])
        if tag in _BLOCK:
            self._flush()
            if tag == "pre":
                self.pre += 1
            if len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
                self.prefix = "#" * int(tag[1]) + " "
            elif tag == "li":
                self.prefix = "- "

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "main":
            self.depth -= 1
            if not self.depth:
                self._flush()
            return
        if tag in _BLOCK:
            self._flush()
            if tag == "pre":
                self.pre = max(0, self.pre - 1)

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.cur.append(data)


def extract(html_text):
    """{"text", "lines", "mailto", "forms", "ids"} from a docs page, or None
    when the page has no <main> (a challenge or error page)."""
    p = _MainText()
    p.feed(html_text)
    p.close()
    if not p.seen_main:
        return None
    p._flush()
    lines = [ln for ln in p.lines if ln]
    return {"text": "\n".join(lines) + ("\n" if lines else ""), "lines": lines,
            "mailto": sorted(set(p.mailto)), "forms": p.forms, "ids": p.ids}


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plain(line):
    return line.lstrip("#- ").strip()


def registration(page):
    """"closed" | "open" | "unknown" from the extracted index page."""
    if not page or len(page["text"]) < MIN_TEXT:
        return "unknown"
    plain = [_plain(ln) for ln in page["lines"]]
    if any(CLOSED_SENTENCE in ln for ln in plain):
        return "closed"
    if not any(INDEX_MARKER in ln for ln in plain):
        return "unknown"  # not the page we know: never a false alarm
    return "open"


def reg_section(page):
    """The lines from the "Registering your Application" heading to the next
    h2 / h3 heading ([] when the heading is gone)."""
    if not page:
        return []
    out, inside = [], False
    for ln in page["lines"]:
        head = re.match(r"^(#+) ", ln)
        if inside and head and len(head.group(1)) <= 3:
            break
        if _plain(ln) == REG_HEADING:
            inside = True
        if inside:
            out.append(ln)
    return out


def shape_fields(name, lines):
    """The SHAPE_FIELDS names the changed lines of page `name` carry, in
    SHAPE_FIELDS order ([] on a page outside SHAPE_PAGES while
    SHAPE_ALL_PAGES is off)."""
    if name not in SHAPE_PAGES and not SHAPE_ALL_PAGES:
        return []
    seen = set()
    for ln in lines:
        seen.update(_SHAPE_RE.findall(ln))
    return [f for f in SHAPE_FIELDS if f in seen]


def topics(lines, name=None):
    """Topic names of the changed lines; "shape" only when `name` (the page)
    is given and shape_fields() finds a field."""
    low = " ".join(lines).lower()
    out = []
    for topic, words in TOPICS:
        if words is None:
            if name is not None and shape_fields(name, lines):
                out.append(topic)
        elif any(w in low for w in words):
            out.append(topic)
    return out


def changelog_entries(page):
    """Entry headings of the changelog page, newest first ("3.30.0", ...)."""
    out = []
    for ln in (page or {}).get("lines", []):
        m = re.match(r"^#{2,3} (.+?):?$", ln)
        if m:
            out.append(m.group(1).rstrip(":").strip())
    return out


# --- fetch --------------------------------------------------------------

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


def fetch_page(url, now, fetch=None):
    """The page HTML (str); RateLimited on 429 / 503; DocsError otherwise."""
    headers = {"User-Agent": webfetch.user_agent(UA_PURPOSE),
               "Accept": "text/html", "Accept-Language": "en"}
    status, hdrs, body = webfetch.request("GET", url, headers, HOSTS, fetch=fetch,
                                          max_bytes=MAX_BYTES)
    if status in (429, 503):
        until = _retry_after(webfetch.header(hdrs, "Retry-After"), now)
        raise RateLimited(max(until or 0, now + RATE_MIN_S), status)
    if status != 200:
        raise DocsError(f"HTTP {status} from {url}")
    return (body or b"").decode("utf-8", "replace")


# --- state and files ----------------------------------------------------

def cache_dir(environ=None):
    return paths.sidecar_dir("Cache", environ) / "ggg_docs"


def logs_dir(environ=None):
    return paths.sidecar_dir("Logs", environ) / "ggg_docs"


def runtime_dir(root):
    return Path(root) / RUNTIME_REL


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, p)


def load_state(cache):
    try:
        doc = json.loads((Path(cache) / STATE_NAME).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(cache, st):
    _write(Path(cache) / STATE_NAME, json.dumps(st, indent=1, sort_keys=True) + "\n")


def _ascii(text):
    return text.encode("ascii", "replace").decode("ascii")


def note(root, now, text):
    p = runtime_dir(root) / NOTES_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="ascii", newline="\n") as fh:
        fh.write(_ascii(f"{iso(now)} | {text}") + "\n")


def set_flag(root, now, is_open, reason=""):
    p = runtime_dir(root) / FLAG_NAME
    if is_open:
        if not p.exists():
            _write(p, _ascii(f"{iso(now)} {reason}".strip()) + "\n")
    else:
        try:
            p.unlink()
        except FileNotFoundError:
            pass


# --- the run ------------------------------------------------------------

def _compare(name, old_text, new, now, logs):
    """One change record (dict) for a page whose hash moved, with the diff
    written to the sidecar Logs."""
    old_lines = old_text.splitlines()
    diff = list(difflib.unified_diff(old_lines, new["lines"], f"{name} (before)",
                                     f"{name} ({iso(now)})", lineterm=""))
    added = [ln[1:] for ln in diff if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln[1:] for ln in diff if ln.startswith("-") and not ln.startswith("---")]
    fname = time.strftime("%Y%m%d-%H%M%S", time.gmtime(now)) + f"-{name}.diff"
    _write(Path(logs) / fname, "\n".join(diff) + "\n")
    rec = {"page": name, "added": len(added), "removed": len(removed),
           "topics": topics(added + removed, name), "diff": fname}
    fields = shape_fields(name, added + removed)
    if fields:
        rec["shape_fields"] = fields
    if name == "changelog":
        before = set(changelog_entries({"lines": old_lines}))
        rec["new_entries"] = [e for e in changelog_entries(new) if e not in before]
    return rec


def run(root, now, fetch=None, sleep=time.sleep, cache=None, logs=None):
    """One full read of every page; returns and saves the state."""
    cache = Path(cache) if cache is not None else cache_dir()
    logs = Path(logs) if logs is not None else logs_dir()
    st = load_state(cache)
    pages = dict(st.get("pages") or {})
    st.update({"checked": iso(now), "next_check": now + RETRY_S})
    save_state(cache, st)  # claim the slot first: a parallel tick sees "not due"
    changes, errors, read, rate = [], [], 0, None
    index = None
    for i, (name, url) in enumerate(PAGES):
        if i:
            sleep(PAGE_GAP_S)
        try:
            raw = fetch_page(url, now, fetch=fetch)
        except RateLimited as e:
            rate = e
            errors.append(f"{name}: {e}")
            break
        except webfetch.FetchError as e:
            errors.append(f"{name}: {e}")
            continue
        page = extract(raw)
        if page is None or len(page["text"]) < MIN_TEXT:
            errors.append(f"{name}: unreadable page (no main text)")
            continue
        read += 1
        if name == "index":
            index = page
        snap = cache / "pages" / f"{name}.txt"
        digest = sha256(page["text"])
        prev = pages.get(name) or {}
        if prev.get("sha256") and prev["sha256"] != digest:
            try:
                old_text = snap.read_text(encoding="utf-8")
            except OSError:
                old_text = ""
            changes.append(_compare(name, old_text, page, now, logs))
        if prev.get("sha256") != digest or not snap.exists():
            _write(snap, page["text"])
        pages[name] = {"sha256": digest, "chars": len(page["text"]), "read": iso(now)}
        if name == "changelog":
            entries = changelog_entries(page)
            st["changelog_latest"] = entries[0] if entries else None
    st["pages"] = pages
    st["last_read"] = read
    st["errors"] = errors
    if index is not None:
        _registration_update(root, now, st, index)
    if changes:
        st["last_change"] = {"at": iso(now), "changes": changes}
        shaped = [{"page": c["page"], "fields": c["shape_fields"],
                   "count": len(c["shape_fields"])}
                  for c in changes if c.get("shape_fields")]
        if shaped:  # kept until the next shape change (LOOP-WATCH-WIRE reads it)
            st["last_shape"] = {"at": iso(now), "pages": shaped}
        for c in changes:
            extra = f" new_entries={','.join(c['new_entries'])}" if c.get("new_entries") else ""
            if c.get("shape_fields"):
                extra += f" shape_fields={','.join(c['shape_fields'])}"
            note(root, now, f"CHANGED page={c['page']} +{c['added']} -{c['removed']} "
                            f"topics={','.join(c['topics']) or 'none'}{extra} diff={c['diff']}")
    st["changes"] = changes
    if rate is not None:
        st["next_check"] = rate.until
        st["status"] = "rate-limited"
    elif errors:
        st["status"] = "partial" if read else "error"
        st["next_check"] = now + RETRY_S
    else:
        st["status"] = "ok"
        st["next_check"] = now + CHECK_EVERY_S
    save_state(cache, st)
    return st


def _registration_update(root, now, st, index):
    reg = registration(index)
    prev = st.get("reg")
    section = reg_section(index)
    channels = {"mailto": index["mailto"], "forms": index["forms"]}
    if reg != "unknown":
        if prev and prev != reg:
            note(root, now, f"REGISTRATION {prev} -> {reg}")
        if prev != reg:
            st["reg_since"] = iso(now)
        st["reg"] = reg
        set_flag(root, now, reg == "open",
                 "closed-application sentence gone from the developer docs")
    old_sec = st.get("reg_section")
    if old_sec is not None and old_sec != section:
        note(root, now, "REGISTRATION section text changed: "
                        + " / ".join(_plain(x) for x in section)[:300])
    st["reg_section"] = section
    if st.get("reg_channels") not in (None, channels):
        note(root, now, f"REGISTRATION channels changed: {json.dumps(channels)}")
    st["reg_channels"] = channels


def summary(st):
    reg = st.get("reg") or "unknown"
    head = f"ggg docs: {st.get('last_read', 0)}/{len(PAGES)} pages read"
    if reg == "open":
        head += ", REGISTRATION MAY BE OPEN (TC-OAUTH-REG)"
    else:
        head += f", registration {reg}"
    ch = st.get("changes") or []
    if ch:
        head += "; changed: " + ", ".join(
            f"{c['page']}({','.join(c['topics']) or 'text'})" for c in ch)
    if st.get("status") not in ("ok", None):
        head += f"; {st['status']}"
    return head


def loop_check(root, now, fetch=None, sleep=time.sleep, cache=None, logs=None):
    """The al_loop tick hook: None when no run is due; else one line."""
    cache = Path(cache) if cache is not None else cache_dir()
    st = load_state(cache)
    if now < float(st.get("next_check") or 0):
        return None
    st = run(root, now, fetch=fetch, sleep=sleep, cache=cache, logs=logs)
    return summary(st)


def safe_check(root, now):
    """loop_check for the al_loop tick (tools/al_loop.py Deps.docs_watch):
    a watch fault becomes one line, never a failed tick."""
    try:
        return loop_check(root, now)
    except Exception as exc:  # noqa: BLE001 - a watch fault must not stop the tick
        return f"ggg docs: {type(exc).__name__}: {exc}"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ggg_docs_watch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="read the docs now if due (or --force)")
    c.add_argument("--force", action="store_true")
    sub.add_parser("status", help="print the saved state")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(load_state(cache_dir()), indent=1, sort_keys=True))
        return 0
    now = time.time()
    if a.force:
        st = run(ROOT, now)
        print(summary(st))
    else:
        line = loop_check(ROOT, now)
        print(line or "ggg docs: not due")
        st = load_state(cache_dir())
    return 0 if st.get("status") in ("ok", None) else 1


if __name__ == "__main__":
    sys.exit(main())
