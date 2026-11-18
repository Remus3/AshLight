"""DIAG-SELF (research 0032 section 3, ruling J): one "Checks" view that
answers "is AshLight healthy, and what do I do if not".

Every check is a passive local read the core already has (tailer state,
the local config, the cached price book, the calc component's files, the
build-time data snapshot, server/al/procs.py, AshLight's own overlay log).
No network (this module never imports webfetch), no probe of the game
process, no window scan. The hotkey reads "registered" from the overlay's
own log, never "pressed".

The report is plain text the player copies on a click (the dashboard
writes the clipboard inside that click only, decision 0014). It carries
no path, user name, contact, token, character name, account id or chat:
the check details are written without them, and redact() masks any that
slipped into a free-text field (a fetch error) before the report is made.
"""

import os
import re
import time
from pathlib import Path

from . import langguard
from .num import finite

# NOTE: worth knowing, nothing to fix (a non-English game client, ruling K)
PASS, FAIL, UNKNOWN, OFF, NOTE = "pass", "fail", "unknown", "off", "note"
MARK = {PASS: "ok", FAIL: "FIX", UNKNOWN: "?", OFF: "off", NOTE: "note"}

# The overlay log tail read for the hotkey check (AshLight's own file).
OVERLAY_LOG_TAIL = 64 * 1024
LAST_LINE_QUIET_S = 1200.0  # summary.IDLE_S: the game may be closed
BOOK_STALE_S = 2 * 3600     # ninja.STALE_AFTER_S
SNAPSHOT_OLD_S = 60 * 86400  # older data may miss a new league's zones

FIX_START_GAME = ("Start Path of Exile 2 once so it writes Client.txt. AshLight "
                  "finds it by itself.")
FIX_CONSENT = 'Press "Allow reading Client.txt" at the top of this page.'
FIX_RUN = r"Run scripts\run.ps1 to start AshLight's parts again."
FIX_CONTACT = r'Add your contact as "contact" in config\local.json.'
FIX_NET = ("Check this computer's internet connection. AshLight tries again "
           "by itself.")
FIX_CALC = r"Run scripts\setup.ps1 -TcCalc to install it again."
FIX_SNAPSHOT = r"Run scripts\build.ps1 -Snapshot to fetch it."
FIX_HOTKEY = ("Another app holds the shortcut. Set a different item check key in "
              r"AshLight's settings file, then run scripts\run.ps1.")


def _ago(seconds):
    s = finite(seconds)
    if s is None:
        return None
    s = max(0.0, s)
    if s < 90:
        return "just now"
    if s < 5400:
        return f"{int(round(s / 60.0))} min ago"
    if s < 2 * 86400:
        return f"{int(round(s / 3600.0))} h ago"
    return f"{int(round(s / 86400.0))} days ago"


def _check(cid, label, status, detail, fix=None):
    return {"id": cid, "label": label, "status": status, "detail": detail,
            "fix": fix if status == FAIL else None}


def check_log(f):
    if f.get("log_found"):
        return _check("log", "Client.txt", PASS, "Found.")
    return _check("log", "Client.txt", FAIL, "Not found yet.", FIX_START_GAME)


def check_consent(f):
    if f.get("consented"):
        return _check("consent", "Permission", PASS, "You allowed reading Client.txt.")
    return _check("consent", "Permission", FAIL, "Not given yet.", FIX_CONSENT)


def check_reading(f):
    if f.get("reading"):
        return _check("reading", "Reading", PASS, "Reading Client.txt.")
    if not (f.get("consented") and f.get("log_found")):
        return _check("reading", "Reading", UNKNOWN,
                      "Starts once the two checks above pass.")
    return _check("reading", "Reading", FAIL, "Not reading Client.txt.", FIX_RUN)


def check_last_line(f, now):
    at = finite(f.get("last_line_at"))
    if at is None:
        return _check("last_line", "Last log line", UNKNOWN, "None yet.")
    age = now - at
    if age >= LAST_LINE_QUIET_S or f.get("idle"):
        return _check("last_line", "Last log line", UNKNOWN,
                      f"{_ago(age).capitalize()}. The game may be closed.")
    return _check("last_line", "Last log line", PASS, _ago(age).capitalize() + ".")


def check_character(f):
    if f.get("character_seen"):
        return _check("character", "Character", PASS, "Seen in the log.")
    return _check("character", "Character", UNKNOWN,
                  "Not seen yet. It shows after your next level-up.")


def check_language(f):
    v = f.get("lang")
    if v == langguard.ENGLISH:
        return _check("language", "Game language", PASS, "English game text seen.")
    if v == langguard.NON_ENGLISH:
        return _check("language", "Game language", NOTE,
                      "Your game seems to use a language other than English. "
                      + langguard.WORKS[0].upper() + langguard.WORKS[1:] + " still work.")
    return _check("language", "Game language", UNKNOWN, "Not enough log lines yet.")


def check_web(f):
    if not f.get("web_data"):
        return _check("web_data", "Web data", OFF,
                      "Off. Prices stay off until you turn it on.")
    if not f.get("contact_set"):
        return _check("web_data", "Web data", FAIL, "On, but no contact is set.",
                      FIX_CONTACT)
    return _check("web_data", "Web data", PASS, "On, contact set.")


def check_prices(f, now):
    if not f.get("web_data") or not f.get("contact_set"):
        return _check("prices", "Price book", OFF, "Off while web data is off or has no contact.")
    if f.get("book_error"):
        return _check("prices", "Price book", FAIL, "The last fetch failed.", FIX_NET)
    at = finite(f.get("book_checked_at"))
    if at is None:
        return _check("prices", "Price book", UNKNOWN, "No prices fetched yet.")
    age = now - at
    if age > BOOK_STALE_S:
        return _check("prices", "Price book", FAIL, f"Updated {_ago(age)}.", FIX_NET)
    return _check("prices", "Price book", PASS, f"Updated {_ago(age)}.")


def check_calc(f):
    if not f.get("calc_on"):
        return _check("calc", "Calc component", OFF,
                      "Off. Item checks use your stat weights.")
    st = f.get("calc_status")
    if not isinstance(st, dict):
        return _check("calc", "Calc component", UNKNOWN, "Not checked yet.")
    if st.get("available"):
        return _check("calc", "Calc component", PASS,
                      "Installed and matches its pinned version.")
    missing = [m for m in (st.get("missing") or []) if isinstance(m, str)]
    what = ", ".join(sorted(missing)) if missing else "a part"
    return _check("calc", "Calc component", FAIL,
                  f"Missing or changed: {what}.", FIX_CALC)


def check_snapshot(f, now):
    at = finite(f.get("snapshot_at"))
    if not f.get("snapshot"):
        if not f.get("web_data"):
            return _check("snapshot", "Game data", OFF,
                          "Not fetched (web data is off). Zone levels need it.")
        return _check("snapshot", "Game data", FAIL, "Not fetched yet.", FIX_SNAPSHOT)
    if at is None:
        return _check("snapshot", "Game data", PASS, "Present.")
    age = now - at
    if age > SNAPSHOT_OLD_S:
        return _check("snapshot", "Game data", FAIL, f"Present, fetched {_ago(age)}.",
                      FIX_SNAPSHOT)
    return _check("snapshot", "Game data", PASS, f"Present, fetched {_ago(age)}.")


def _live(f, key, cid, label, what):
    v = f.get(key)
    if v is None:
        return _check(cid, label, UNKNOWN, "Not checked yet.")
    if v:
        return _check(cid, label, PASS, f"{what} is running.")
    return _check(cid, label, FAIL, f"{what} is not running.", FIX_RUN)


def check_hotkey(f):
    v = f.get("hotkey")
    if v is True:
        return _check("hotkey", "Item check hotkey", PASS, "Registered.")
    if v is False:
        return _check("hotkey", "Item check hotkey", FAIL, "Not registered.", FIX_HOTKEY)
    return _check("hotkey", "Item check hotkey", UNKNOWN,
                  "Known once the overlay is running.")


FIX_RELOAD = ("Fix the file and save it again. AshLight keeps the last working "
              "version until then.")


def check_reload(f):
    """HOT-RELOAD (decision 0042): shown only while a data file or a code
    change did not load; None otherwise (no row)."""
    notes = [n for n in (f.get("reload_notes") or []) if isinstance(n, str) and n]
    if not notes:
        return None
    more = f" (+{len(notes) - 1} more)" if len(notes) > 1 else ""
    return _check("reload", "Live reload", FAIL, notes[0] + more, FIX_RELOAD)


def check_port(f):
    port = f.get("port")
    if isinstance(port, int) and not isinstance(port, bool):
        return _check("port", "Dashboard address", PASS, f"127.0.0.1:{port}")
    return _check("port", "Dashboard address", UNKNOWN, "Not known.")


def checks(f, now):
    """Every check, in reading order, from a facts dict (see Core.diag_facts)."""
    return [check_log(f), check_consent(f), check_reading(f), check_last_line(f, now),
            check_character(f), check_language(f), check_web(f), check_prices(f, now),
            check_calc(f), check_snapshot(f, now),
            _live(f, "overlay", "overlay", "Overlay", "The overlay"),
            _live(f, "supervisor", "supervisor", "Keepalive", "The keepalive"),
            check_hotkey(f), check_port(f)] + [r for r in (check_reload(f),) if r]


# -- redaction (ruling J)

def secrets(f=None, environ=None):
    """The strings a report must never carry: the Windows user name, the
    home, sidecar and repo paths, the contact and the character name.
    Longest first, so a path masks before its user-name part."""
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
    for key, tag in (("contact", "<contact>"), ("character", "<character>")):
        v = f.get("_" + key)
        if isinstance(v, str) and len(v.strip()) >= 2:
            out.append((v.strip(), tag))
    user = environ.get("USERNAME") or environ.get("USER")
    if user and len(user) >= 3:
        out.append((user, "<user>"))
    # forward-slash forms of each path too
    out += [(v.replace("\\", "/"), t) for v, t in out if "\\" in v]
    out.sort(key=lambda p: -len(p[0]))
    return out


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/][^\s\"']*")


def redact(text, pairs):
    """`text` with every secret masked (case-insensitive), then any e-mail
    address and any absolute drive path left over."""
    if not isinstance(text, str):
        return text
    for value, tag in pairs:
        text = re.sub(re.escape(value), tag, text, flags=re.IGNORECASE)
    text = _EMAIL.sub("<email>", text)
    return _DRIVE_PATH.sub("<path>", text)


def report(rows, version, now, pairs):
    """The plain-text report the player copies (ASCII, LF)."""
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now))
    lines = [f"AshLight {version} self-check, {stamp}"]
    for r in rows:
        line = f"[{MARK[r['status']]}] {r['label']}: {r['detail']}"
        if r.get("fix"):
            line += f" Fix: {r['fix']}"
        lines.append(line)
    text = redact("\n".join(lines) + "\n", pairs)
    return text.encode("ascii", "replace").decode("ascii")


def summary(rows):
    n = sum(1 for r in rows if r["status"] == FAIL)
    if n == 0:
        return "All checks pass."
    return "1 check needs a fix." if n == 1 else f"{n} checks need a fix."


def view(facts, version, now=None):
    """{"checks", "failed", "summary", "report"} for the snapshot."""
    now = time.time() if now is None else now
    pairs = secrets(facts)
    rows = checks(facts, now)
    for r in rows:
        r["detail"] = redact(r["detail"], pairs)
    return {"checks": rows, "failed": sum(1 for r in rows if r["status"] == FAIL),
            "summary": summary(rows), "report": report(rows, version, now, pairs)}


# -- the hotkey, from AshLight's own overlay log

def hotkey_registered(log_path, max_bytes=OVERLAY_LOG_TAIL):
    """True / False from the overlay log's newest start ("overlay started"),
    False when "item check shortcut not available" came after the start
    before it; None without a log or a start line."""
    try:
        p = Path(log_path)
        size = p.stat().st_size
        with open(p, "rb") as fh:
            fh.seek(max(0, size - max_bytes))
            text = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if "overlay started" in ln]
    if not starts:
        return None
    last = starts[-1]
    prev = starts[-2] if len(starts) > 1 else -1
    window = lines[prev + 1:last]
    return not any("item check shortcut not available" in ln for ln in window)
