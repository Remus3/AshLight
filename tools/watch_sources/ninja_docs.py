"""AUTO-10 (NINJA-WATCH, F-140 layer 2; W6 of docs/plan/06; research 0036
source ND; decisions 0013, 0026, 0069): the poe.ninja API docs page watch.

What it reads: one GET of the public API docs page DOCS_URL, purpose
'docs watch', at most once per 24 h, 3 h after a network or status error
(the frame cadence is 3 h; a good read moves data["next_at"] 24 h on).
Dev loop only (home "loop", never CI). Gates, all before any request:
- web_data on (the frame never calls a gated source otherwise; the check
  repeats it through webfetch.blocked_reason and raises WebDataOff);
- a contact set in the tree's config/local.json (webfetch.blocked_reason);
  without one the run returns nothing, makes no request and records
  data["blocked"] = "contact not set";
- no active stop: a 429 or 503 writes stopped_until (STOP_S, 7 days) to
  the cache state file and re-raises, so watch health shows the
  rate-limit cause once; every later run before stopped_until makes no
  request. A session may delete the cache state file to end the stop.

Where it keeps things (outside the tree, so only with ctx["live"] true or
an explicit ctx path; with neither the source reads nothing and makes no
request, so a scratch-root loop test stays hermetic):
- ctx["root"] (else this checkout when live): config/local.json;
- ctx["ninja_cache"] (else <sidecar>/Cache/ninja_docs when live):
  baseline.txt (the normalised text) and state.json {hash, at,
  stopped_until, stop_cause};
- ctx["ninja_logs"] (else <sidecar>/Logs/ninja_docs when live):
  diff-<YYYYMMDD>.txt, one unified diff block per change, appended.

Normalising: the HTML is reduced to text lines (script, style, svg and
template dropped; every block tag ends a line; headings carry '#' marks;
whitespace collapsed; empty lines dropped; everything from <footer> on
dropped), then cut from the 'API Reference' heading to the footer line
(the first line starting with a copyright sign, '(c)' or 'Copyright', or
holding 'all rights reserved'). The hash is SHA-256 of those lines; the
raw HTML, ETag-free headers and Last-Modified never count (research 0036).
A page with no 'API Reference' line is a shape error, baseline untouched.

Tagging each changed line (research 0036 layer 2): routes (a line starting
GET / POST ... /, or naming /poe2/api), policy (POLICY_RX: proxy, blocked,
User-Agent, contact, cache, hourly, replicate, versioning, rate limit,
backend, terms, commercial, permission), types (a line under a heading
naming 'type', or a bare CamelCase word). Order: routes, policy, types; a
line matching none counts as policy (the stricter reading: a human reads
it; ruling recorded with this package).

Findings (templates ops/loop/watch_rows/ninja.json):
- kind "ninjadocs" (NINJA-DOCS-<YYYYMMDD>, data): types or routes lines
  changed; topic = the one with more changed lines (types on a tie),
  n = types + routes lines, capped at 999;
- kind "ninjapolicy" (NINJA-POLICY-<YYYYMMDD>, review, BLOCKED: session):
  policy lines changed, n capped at 999.
Each kind gives at most one finding per 7 days (data["filed"][kind]); a
later diff inside that window only joins the Logs file. The first read
writes the baseline and finds nothing.

Python stdlib only; no subprocess.
"""

import datetime as _dt
import difflib
import hashlib
import html.parser
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import webfetch  # noqa: E402

NAME = "ninja-docs"
KIND_DOCS = "ninjadocs"
KIND_POLICY = "ninjapolicy"
DOCS_URL = "https://poe.ninja/docs/api"
PURPOSE = "docs watch"
CACHE_NAME = "ninja_docs"
BASELINE_NAME = "baseline.txt"
STATE_NAME = "state.json"

HOUR_S = 3600
DAY_S = 24 * HOUR_S
RETRY_S = 3 * HOUR_S
FILE_GAP_S = 7 * DAY_S
STOP_S = 7 * DAY_S
N_MAX = 999
RATE_STATUSES = (429, 503)

SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "head"}
BLOCK_TAGS = {"p", "div", "br", "li", "tr", "table", "thead", "tbody", "ul", "ol",
              "section", "article", "header", "nav", "pre", "dt", "dd", "dl",
              "blockquote", "hr", "aside", "main", "body", "html", "figure",
              "caption", "summary", "details", "form"}
CELL_TAGS = {"td", "th"}
HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

START_RX = re.compile(r"^(?:#{1,6}\s+)?api reference$", re.I)
FOOTER_RX = re.compile(r"^(?:\u00a9|\(c\)|copyright\b)|all rights reserved", re.I)
HEADING_RX = re.compile(r"^(#{1,6})\s+(.*)$")
ROUTE_RX = re.compile(r"^(?:GET|POST|PUT|PATCH|DELETE|HEAD)\s+/|/poe2/api\b", re.I)
POLICY_RX = re.compile(
    r"\b(?:prox(?:y|ies)|block\w*|user[- ]agent|contact\w*|cach\w*|hourly|"
    r"replicat\w*|version\w*|rate[- ]?limit\w*|throttl\w*|backend|terms|"
    r"commercial\w*|permi\w*|allowed|forbid\w*|abuse)\b", re.I)
TYPE_HEAD_RX = re.compile(r"\btypes?\b", re.I)
TYPE_WORD_RX = re.compile(r"^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)*$")


def _uw():
    import upstream_watch  # the frame; on sys.path whenever a source runs
    return upstream_watch


# ---------------------------------------------------------------- normalise

class _TextParser(html.parser.HTMLParser):
    """HTML to text lines: block tags end a line, headings get '#' marks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0
        self.done = False

    def _nl(self):
        self.out.append("\n")

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if tag == "footer":
            self.done = True
            return
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if tag in HEADING_TAGS:
            self._nl()
            self.out.append("#" * HEADING_TAGS[tag] + " ")
        elif tag in BLOCK_TAGS:
            self._nl()
        elif tag in CELL_TAGS:
            self.out.append(" | ")

    def handle_startendtag(self, tag, attrs):
        if not self.done and not self.skip and (tag in BLOCK_TAGS):
            self._nl()

    def handle_endtag(self, tag):
        if self.done:
            return
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if tag in HEADING_TAGS or tag in BLOCK_TAGS:
            self._nl()

    def handle_data(self, data):
        if not self.done and not self.skip:
            self.out.append(re.sub(r"\s+", " ", data))  # source newlines are not lines


def page_lines(text):
    """Every non-empty normalised text line of an HTML page (no cut)."""
    parser = _TextParser()
    try:
        parser.feed(text or "")
        parser.close()
    except Exception:  # noqa: BLE001 - html.parser rarely raises; treat as shape
        raise _uw().SourceError("shape", "the docs page did not parse") from None
    lines = []
    for raw in "".join(parser.out).split("\n"):
        line = " ".join(raw.replace("|", " | ").split())
        line = re.sub(r"(?:\s*\|\s*)+", " | ", line).strip(" |")
        if not line or re.fullmatch(r"#+", line):
            continue
        m = HEADING_RX.match(line)
        if m and not m.group(2).strip():
            continue
        lines.append(line)
    return lines


def normalise(text):
    """The watched lines: from the 'API Reference' line to the footer line
    (excluded). SourceError('shape') when the start line is missing."""
    lines = page_lines(text)
    # A heading line first (a nav link may carry the same words), else a plain one.
    start = next((i for i, ln in enumerate(lines)
                  if START_RX.match(ln) and HEADING_RX.match(ln)), None)
    if start is None:
        start = next((i for i, ln in enumerate(lines) if START_RX.match(ln)), None)
    if start is None:
        raise _uw().SourceError("shape", "no 'API Reference' heading on the docs page")
    out = []
    for ln in lines[start:]:
        if out and FOOTER_RX.search(ln):
            break
        out.append(ln)
    return out


def digest(lines):
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- tagging

def headings_of(lines):
    """The nearest heading text above (or at) each line, '' before any."""
    cur, out = "", []
    for ln in lines:
        m = HEADING_RX.match(ln)
        if m:
            cur = m.group(2)
        out.append(cur)
    return out


def tag_line(line, heading):
    """'routes', 'policy' or 'types' for one changed line."""
    m = HEADING_RX.match(line)
    body = m.group(2) if m else line
    if ROUTE_RX.search(body):
        return "routes"
    if POLICY_RX.search(body):
        return "policy"
    if TYPE_HEAD_RX.search(heading or "") or TYPE_HEAD_RX.search(body if m else ""):
        return "types"
    if TYPE_WORD_RX.match(body):
        return "types"
    return "policy"


def changed(old, new):
    """[(sign, line, tag)] of every removed ('-') and added ('+') line."""
    oh, nh = headings_of(old), headings_of(new)
    out = []
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("replace", "delete"):
            out += [("-", old[i], tag_line(old[i], oh[i])) for i in range(i1, i2)]
        if op in ("replace", "insert"):
            out += [("+", new[j], tag_line(new[j], nh[j])) for j in range(j1, j2)]
    return out


def counts_of(rows):
    c = {"types": 0, "routes": 0, "policy": 0}
    for _sign, _line, tag in rows:
        c[tag] += 1
    return c


# ---------------------------------------------------------------- files

def _root(ctx):
    if ctx.get("root") is not None:
        return Path(ctx["root"])
    return ROOT if ctx.get("live") else None


def _sidecar(ctx, key, name):
    if ctx.get(key) is not None:
        return Path(ctx[key])
    if not ctx.get("live"):
        return None
    from server.al import paths
    return paths.sidecar_dir(name) / CACHE_NAME


def contact_of(root):
    try:
        cfg = json.loads((Path(root) / "config" / "local.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return cfg.get(webfetch.CONTACT_KEY) if isinstance(cfg, dict) else None


def _write(path, text, append=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_cache(cache):
    try:
        doc = json.loads((cache / STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None
    return doc if isinstance(doc, dict) else {}


def save_cache(cache, doc):
    _write(cache / STATE_NAME, json.dumps(doc, indent=1, sort_keys=True) + "\n")


def load_baseline(cache):
    try:
        text = (cache / BASELINE_NAME).read_text(encoding="utf-8")
    except OSError:
        return None
    return [ln for ln in text.split("\n") if ln]


def _iso(now):
    return _dt.datetime.fromtimestamp(now).astimezone().isoformat(timespec="seconds")


def _day(now):
    return _dt.datetime.fromtimestamp(now).strftime("%Y%m%d")


def write_diff(logs, now, old, new, rows, joined):
    """Append one dated diff block to <logs>/diff-<YYYYMMDD>.txt; its path."""
    c = counts_of(rows)
    head = [f"== poe.ninja docs change {_iso(now)}: types {c['types']}, "
            f"routes {c['routes']}, policy {c['policy']} changed line(s)"]
    head += [f"   joins the {kind} row filed {at}" for kind, at in joined]
    head += [f"   [{tag}] {sign} {line}" for sign, line, tag in rows]
    body = list(difflib.unified_diff(old, new, "baseline", "now", lineterm="", n=1))
    path = logs / f"diff-{_day(now)}.txt"
    _write(path, "\n".join(head + body) + "\n\n", append=True)
    return path


# ---------------------------------------------------------------- check

def _stop(cache, now, cause):
    doc = load_cache(cache)
    doc.update(stopped_until=now + STOP_S, stop_cause=cause, stopped_at=_iso(now))
    save_cache(cache, doc)


def _filed_recently(filed, kind, now):
    at = filed.get(kind)
    return isinstance(at, (int, float)) and not isinstance(at, bool) and now - at < FILE_GAP_S


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    uw = _uw()
    root = _root(ctx)
    cache = _sidecar(ctx, "ninja_cache", "Cache")
    logs = _sidecar(ctx, "ninja_logs", "Logs")
    if root is None or cache is None or logs is None:
        return []
    data = state.setdefault("data", {})
    if not isinstance(data, dict):
        data = state["data"] = {}
    cdoc = load_cache(cache)
    until = cdoc.get("stopped_until")
    if isinstance(until, (int, float)) and not isinstance(until, bool) and now < until:
        data["blocked"] = "stopped after HTTP 429 or 503"
        return []
    nxt = data.get("next_at")
    if isinstance(nxt, (int, float)) and not isinstance(nxt, bool) and now < nxt:
        return []
    why = webfetch.blocked_reason(lambda: uw.web_data_on(root), contact_of(root))
    if why == webfetch.REASON_OFF:
        raise webfetch.WebDataOff("web data is off (opt-in setting web_data)")
    if why is not None:
        data["blocked"] = why
        return []
    data.pop("blocked", None)

    old = load_baseline(cache)
    etag = state.get("etag") if old is not None else None
    try:
        status, headers, body = fetch(DOCS_URL, etag=etag)
    except uw.SourceError as exc:
        if exc.cause == "rate-limit":
            _stop(cache, now, "rate-limit")
        raise
    if status in RATE_STATUSES:
        _stop(cache, now, "rate-limit")
        raise uw.SourceError("rate-limit", f"HTTP {status}")
    if status == 304 and old is not None:
        data["next_at"] = now + DAY_S
        return []
    if status != 200:
        raise uw.SourceError("status", f"HTTP {status}")
    new = normalise((body or b"").decode("utf-8", errors="replace"))
    new_hash = digest(new)
    tag = webfetch.header(headers or {}, "ETag")
    state["etag"] = tag if isinstance(tag, str) and tag.isascii() and len(tag) <= 200 else None
    data["next_at"] = now + DAY_S

    found = []
    if old is not None and digest(old) != new_hash:
        rows = changed(old, new)
        c = counts_of(rows)
        filed = data.get("filed") if isinstance(data.get("filed"), dict) else {}
        joined = []
        docs_n = c["types"] + c["routes"]
        if docs_n:
            if _filed_recently(filed, KIND_DOCS, now):
                joined.append((KIND_DOCS, _iso(filed[KIND_DOCS])))
            else:
                topic = "routes" if c["routes"] > c["types"] else "types"
                found.append({"kind": KIND_DOCS, "key": f"docs {_day(now)}",
                              "tokens": {"topic": topic, "n": str(min(docs_n, N_MAX))}})
                filed[KIND_DOCS] = now
        if c["policy"]:
            if _filed_recently(filed, KIND_POLICY, now):
                joined.append((KIND_POLICY, _iso(filed[KIND_POLICY])))
            else:
                found.append({"kind": KIND_POLICY, "key": f"policy {_day(now)}",
                              "tokens": {"n": str(min(c["policy"], N_MAX))}})
                filed[KIND_POLICY] = now
        data["filed"] = filed
        if rows:
            write_diff(logs, now, old, new, rows, joined)
    if old is None or digest(old) != new_hash:
        _write(cache / BASELINE_NAME, "\n".join(new) + "\n")
        cdoc = load_cache(cache)
        cdoc.update(hash=new_hash, at=_iso(now))
        cdoc.pop("stopped_until", None)
        save_cache(cache, cdoc)
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": RETRY_S,  # 3 h retry; a good read waits 24 h (data next_at)
    "window": None,
    "needs_web_data": True,
    "hosts": ["poe.ninja"],
    "urls": [DOCS_URL],
    "purpose": PURPOSE,
    "check": check,
}
