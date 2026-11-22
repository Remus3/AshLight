"""RUN-REPORT-FIELDS (finding F-109, research 0051 R6 and F7, audit P8-7;
folded F-185): the Checks report, made from an allow-list of structured
fields, and the redactor every free-text part of it goes through.

The report is plain ASCII text with LF line ends that the player copies on
a click (decision 0014; nothing is uploaded, ever, ruling J). Its lines
come only from this list (FIELD_LABELS and the Checks rows):

- the header: "AshLight <build> self-check, <UTC minute>" (the build
  string /api/health shows, RUN-BUILD-STAMP-CORE);
- "OS build", "Python" and "Electron": the Windows build number, the
  running Python version and the pinned Electron version
  (config/electron_pin.json), each a short version token or "unknown";
- "Counters": AshLight's own line and request counters (server/al/
  metrics.py names, RUN-METRICS-CORE): numbers only;
- one line per Checks row, "[mark] Label: detail Fix: fix";
- "Last restart": the keepalive's last restart (time and reason code),
  while one is recorded;
- "Not counted mod lines": the session's unweighted mod lines (F-185,
  server/al/plug/unknownitems.py), in memory only (decision 0045);
- "Log shapes": the parse ledger's confirmed masked shapes, only while
  the ledger consent is on (decision 0071);
- "Log tails": the last lines of AshLight's own core.log and overlay.log,
  only on the player's explicit second choice (the preview's checkbox,
  GET /api/report?tails=1). Never Client.txt (decision 0067).

The redactor (P8-7, F7) masks whole words only, so a character named like
a label word never blanks that label; labels, marks and the header are
fixed text and never go through it. It masks every value of secrets()
(paths, the Windows user, the contact, every known character name),
then e-mail, quoted, UNC, drive and POSIX home paths, URLs, IP addresses
(loopback kept: the dashboard address row), host names under a common
top-level domain and hex runs of 32 or more.

Standard library only; no request, no write. The only reads are the small
tracked Electron pin (once per process) and, on the second choice, the
tails of AshLight's own two logs.
"""

import json
import os
import platform
import re
import sys
import time
from pathlib import Path

from . import buildinfo, metrics

# The allow-list: the only line labels a report holds besides the header
# and the Checks rows (tests/test_report.py pins it).
FIELD_OS = "OS build"
FIELD_PYTHON = "Python"
FIELD_ELECTRON = "Electron"
FIELD_COUNTERS = "Counters"
FIELD_RESTART = "Last restart"
FIELD_UNKNOWN = "Not counted mod lines"
FIELD_SHAPES = "Log shapes"
FIELD_TAILS = "Log tails"
FIELD_LABELS = (FIELD_OS, FIELD_PYTHON, FIELD_ELECTRON, FIELD_COUNTERS,
                FIELD_RESTART, FIELD_UNKNOWN, FIELD_SHAPES, FIELD_TAILS)
ITEM_INDENT = "  "  # a list section's item lines

# (report word, metrics counter name): the counters the report names.
# Only ones that do not move while the player reads the preview.
COUNTERS = (("lines read", "lines.fed"), ("lines ignored", "lines.ignored"),
            ("lines failed", "lines.failed"), ("log events", "events.log"),
            ("refused requests", "http.401"))

MAX_UNKNOWN = 200     # the session list's cap (plug/unknownitems.py)
MAX_SHAPES = 20       # confirmed ledger shapes listed
TAIL_FILES = ("core.log", "overlay.log")
TAIL_LINES = 20       # lines per log
TAIL_BYTES = 16 * 1024
LINE_MAX = 240        # a free-text line is cut to this many characters

_VERSION_TOKEN = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,39}\Z")
_PIN_FILE = Path(__file__).resolve().parents[2] / "config" / "electron_pin.json"
_CACHE = {}


def _token(value):
    """A short version token, else "unknown" (nothing free-form passes)."""
    v = str(value).strip() if value is not None else ""
    return v if _VERSION_TOKEN.match(v) else "unknown"


def os_build():
    """The Windows build number (e.g. 19045); elsewhere the OS release."""
    if "os" not in _CACHE:
        try:
            gw = getattr(sys, "getwindowsversion", None)
            _CACHE["os"] = _token(gw().build if gw else platform.release())
        except Exception:  # noqa: BLE001 - unknown, never a fault
            _CACHE["os"] = "unknown"
    return _CACHE["os"]


def python_version():
    return _token(platform.python_version())


def electron_version(pin_file=None):
    """The pinned Electron version (decision 0068: the pin equals the
    electron entry of app/package.json), read once per process."""
    if pin_file is None and "electron" in _CACHE:
        return _CACHE["electron"]
    try:
        with open(pin_file or _PIN_FILE, encoding="utf-8") as f:
            doc = json.load(f)
        v = _token(doc.get("version") if isinstance(doc, dict) else None)
    except (OSError, ValueError):
        v = "unknown"
    if pin_file is None:
        _CACHE["electron"] = v
    return v


def counters_text(counts=None):
    counts = metrics.counters() if counts is None else counts
    parts = []
    for word, name in COUNTERS:
        n = counts.get(name, 0)
        n = n if isinstance(n, int) and not isinstance(n, bool) else 0
        parts.append(f"{word} {n}")
    return ", ".join(parts)


# -- secrets and the redactor ---------------------------------------------------

def secrets(f=None, environ=None):
    """[(value, tag)]: the strings a report must never carry: the repo,
    sidecar, home and Client.txt paths, the Windows user name and home,
    the contact, the current character and every other known character
    name ("_characters", plug/report.py facts). Longest first, so a path
    masks before its user-name part."""
    environ = os.environ if environ is None else environ
    f = f or {}
    out = []
    for key, tag in (("repo", "<repo>"), ("sidecar", "<sidecar>"), ("home", "<home>"),
                     ("log_path", "<Client.txt>")):
        v = f.get("_" + key)
        if isinstance(v, str) and len(v) >= 3:
            out.append((v, tag))
    home = environ.get("USERPROFILE") or environ.get("HOME")
    if home and len(home) >= 3:
        out.append((home, "<home>"))
    names = [f.get("_contact"), f.get("_character")]
    tags = ["<contact>", "<character>"]
    chars = f.get("_characters")
    if isinstance(chars, (list, tuple, set, frozenset)):
        for c in chars:
            names.append(c)
            tags.append("<character>")
    for v, tag in zip(names, tags):
        if isinstance(v, str) and len(v.strip()) >= 2:
            out.append((v.strip(), tag))
    user = environ.get("USERNAME") or environ.get("USER")
    if user and len(user) >= 3:
        out.append((user, "<user>"))
    # forward-slash forms of each path too
    out += [(v.replace("\\", "/"), t) for v, t in out if "\\" in v]
    seen = set()
    uniq = []
    for v, t in out:
        if v.lower() not in seen:
            seen.add(v.lower())
            uniq.append((v, t))
    uniq.sort(key=lambda p: -len(p[0]))
    return uniq


def _word(value):
    """The whole-word pattern of a secret: a word-character edge must not
    touch another word character, so "Price" never masks "Pricey" and a
    path still masks before its next separator."""
    left = r"(?<!\w)" if re.match(r"\w", value[0]) else ""
    right = r"(?!\w)" if re.match(r"\w", value[-1]) else ""
    return re.compile(left + re.escape(value) + right, re.IGNORECASE)


_PCHAR = r"[^\s\"'<>|]"
_TOP = (r"/(?i:home|Users|tmp|var|usr|opt|mnt|root|private|etc|srv|Volumes"
        r"|media|run|proc|lib|lib64|bin|sbin|nix|snap)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_QUOTED = re.compile(r"(\"|')(?:[A-Za-z]:[\\/]|\\\\|" + _TOP + r"/|~/)[^\"'\r\n]*\1")
_UNC = re.compile(r"\\\\[^\s\\\"'<>|]+(?:\\" + _PCHAR + r"*)?")
# a drive path; an unquoted space continues it while the next piece still
# holds a separator (a drive path through "Program Files" masks whole)
_DRIVE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]" + _PCHAR + r"*"
                    r"(?: " + _PCHAR + r"*[\\/]" + _PCHAR + r"*)*")
_POSIX = re.compile(r"(?<![\w.:/])(?:" + _TOP + r"|~)(?:/" + _PCHAR + r"*)?(?=[\s\"'<>|]|$)")
_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]{1,15}://" + _PCHAR + r"+")
_IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?!\w|\.\d)")
_IPV6 = re.compile(r"(?<![\w:])\[?(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}\]?"
                   r"(?::\d{1,5})?(?![\w:])")
_TLDS = ("com|net|org|io|gg|dev|app|co|uk|de|fr|nl|se|no|fi|pl|ru|cn|jp|kr|br"
         "|au|ca|us|eu|info|biz|me|tv|cc|xyz|local|lan|home|internal|arpa")
_HOST = re.compile(r"(?<![\w.@-])(?:[A-Za-z0-9-]{1,63}\.)+(?:" + _TLDS + r")(?![\w-]|\.\w)",
                   re.IGNORECASE)
_HEX = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32,}(?![0-9A-Fa-f])")
_TAIL_PUNCT = ".,;:)]}"


def _path_sub(m):
    """<path>, keeping trailing sentence punctuation outside the mask."""
    s = m.group(0)
    tail = ""
    while s and s[-1] in _TAIL_PUNCT:
        tail, s = s[-1] + tail, s[:-1]
    return "<path>" + tail


def _ipv4_sub(m):
    s = m.group(0)
    octets = s.split(":")[0].split(".")
    if any(int(o) > 255 for o in octets):
        return s  # not an address (a version or a count)
    return s if octets[0] == "127" else "<address>"


def _ipv6_sub(m):
    s = m.group(0).strip("[]")
    core = s.split("]")[0]
    if "::" not in core and core.count(":") < 7:
        return m.group(0)  # a clock time or a ratio, not an address
    if core in ("::1", "::"):
        return m.group(0)
    return "<address>"


def redact(text, pairs=()):
    """`text` with every secret of `pairs` masked as a whole word (case
    insensitive), then e-mail, paths, URLs, addresses, host names and long
    hex runs. A non-string is returned as it is."""
    if not isinstance(text, str) or not text:
        return text
    for value, tag in pairs:
        if isinstance(value, str) and value:
            text = _word(value).sub(tag, text)
    text = _EMAIL.sub("<email>", text)
    text = _QUOTED.sub(lambda m: m.group(1) + "<path>" + m.group(1), text)
    text = _URL.sub("<url>", text)
    text = _UNC.sub(_path_sub, text)
    text = _DRIVE.sub(_path_sub, text)
    text = _POSIX.sub(_path_sub, text)
    text = _IPV4.sub(_ipv4_sub, text)
    text = _IPV6.sub(_ipv6_sub, text)
    text = _HOST.sub("<host>", text)
    return _HEX.sub("<hex>", text)


def _free(text, pairs):
    """One free-text value: one line, redacted, then cut to LINE_MAX (in
    that order: a cut never splits a secret out of its mask's reach)."""
    s = redact(" ".join(str(text).split()), pairs)
    if len(s) > LINE_MAX:
        s = s[:LINE_MAX - 3] + "..."
    return s


# -- the report -------------------------------------------------------------------

def _stamp(at):
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(at))


def restart_text(rec):
    """The "Last restart" value of a keepalive record {"at", "reason"}, or
    None for no usable record (the reason is a code word, never text)."""
    if not isinstance(rec, dict):
        return None
    at = rec.get("at")
    reason = rec.get("reason")
    if isinstance(at, bool) or not isinstance(at, (int, float)) or at != at:
        return None
    if not (isinstance(reason, str) and re.fullmatch(r"[a-z][a-z-]{0,23}", reason)):
        return None
    return f"{_stamp(at)} ({reason})"


def compose(rows, version, now, pairs, render=None, mark=None, extra=None, tails=None):
    """The report text. `rows` are the Checks rows (render(row, now) gives
    a row's detail with its age written in; mark maps a status to its
    word); `extra` is {"restart": record, "unknown": [lines], "shapes":
    [shape lines]} (plug/report.py, any part may be missing); `tails` is
    [(log name, [lines])] or None (the second choice is off)."""
    pairs = list(pairs or ())
    render = render or (lambda r, n: r.get("detail"))
    mark = mark or {}
    extra = extra or {}
    lines = [f"AshLight {buildinfo.build_id(version=version)} self-check, {_stamp(now)}",
             f"{FIELD_OS}: {os_build()}",
             f"{FIELD_PYTHON}: {python_version()}",
             f"{FIELD_ELECTRON}: {electron_version()}",
             f"{FIELD_COUNTERS}: {counters_text()}"]
    for r in rows:
        detail = render(r, now)
        line = f"[{mark.get(r.get('status'), '?')}] {r.get('label', '')}: "
        line += _free(detail if detail is not None else "", pairs)
        if r.get("fix"):
            line += " Fix: " + _free(r["fix"], pairs)
        lines.append(line)
    restart = restart_text(extra.get("restart"))
    if restart:
        lines.append(f"{FIELD_RESTART}: {restart}")
    unknown = [u for u in (extra.get("unknown") or ()) if isinstance(u, str) and u.strip()]
    if unknown:
        unknown = unknown[-MAX_UNKNOWN:]
        lines.append(f"{FIELD_UNKNOWN}: {len(unknown)} this session")
        lines += [ITEM_INDENT + _free(u, pairs) for u in unknown]
    shapes = [s for s in (extra.get("shapes") or ()) if isinstance(s, str) and s.strip()]
    if shapes:
        shapes = shapes[:MAX_SHAPES]
        lines.append(f"{FIELD_SHAPES}: {len(shapes)}")
        lines += [ITEM_INDENT + _free(s, pairs) for s in shapes]
    if tails is not None:
        lines.append(f"{FIELD_TAILS}: added on your choice, redacted")
        for name, got in tails:
            lines.append(f"{ITEM_INDENT}{name}: {len(got)} line(s)")
            lines += [ITEM_INDENT * 2 + _free(t, pairs) for t in got]
    text = "\n".join(lines) + "\n"
    return text.encode("ascii", "replace").decode("ascii")


def read_tail(path, max_lines=TAIL_LINES, max_bytes=TAIL_BYTES):
    """The last `max_lines` lines of AshLight's own log `path` ([] when
    missing or unreadable). Nothing is kept."""
    try:
        p = Path(path)
        size = p.stat().st_size
        with open(p, "rb") as fh:
            fh.seek(max(0, size - max_bytes))
            raw = fh.read(max_bytes)
    except OSError:
        return []
    lines = raw.decode("utf-8", "replace").splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]  # the first line was cut by the seek
    return [ln for ln in lines if ln.strip()][-max_lines:]


def log_tails(log_dir):
    """[(name, [lines])] for TAIL_FILES in AshLight's own log folder."""
    return [(name, read_tail(Path(log_dir) / name)) for name in TAIL_FILES]
