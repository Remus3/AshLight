"""DIAG-SELF (research 0032 section 3, ruling J): one "Checks" view that
answers "is AshLight healthy, and what do I do if not".

Every check is a passive local read the core already has (tailer state,
the local config, the cached price book, the calc component's files, the
game-data snapshot, server/al/procs.py, AshLight's own overlay log).
No network (this module never imports webfetch), no probe of the game
process, no window scan. The hotkeys read "registered" from the client's
own runtime file (ops/runtime/hotkeys.json, HOTKEYS-LIVE), else from the
overlay's own log, never "pressed".

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

from . import buildinfo, langguard, plug
from . import statuswords as words
from .num import finite

# NOTE: worth knowing, nothing to fix (a non-English game client, ruling K)
PASS, FAIL, UNKNOWN, OFF, NOTE = "pass", "fail", "unknown", "off", "note"
MARK = {PASS: "ok", FAIL: "FIX", UNKNOWN: "?", OFF: "off", NOTE: "note"}

# The overlay log tail read for the hotkey check (AshLight's own file).
OVERLAY_LOG_TAIL = 64 * 1024
LAST_LINE_QUIET_S = 1200.0  # summary.IDLE_S: the game may be closed
BOOK_STALE_S = 2 * 3600     # ninja.STALE_AFTER_S
SNAPSHOT_OLD_S = 60 * 86400  # older data may miss a new league's zones

# F-131: the reading-state wording and its next step come from the one
# status table (server/al/data/status_words.json); "fix" only for faults.
FIX_START_GAME = words.next_step("missing")
FIX_LOG_PATH = words.next_step("path_missing")
FIX_RUN = words.next_step("stalled")
FIX_CONTACT = r'Add your contact as "contact" in config\local.json.'
FIX_NET = ("Check this computer's internet connection. AshLight tries again "
           "by itself.")
# TC-CALC-OPTIN (F-132): one run of the switch installs the calc and turns
# it on (tools/tc_pin.py writes "tc_calc"); no second edit of the config.
CALC_STEP = r"scripts\setup.ps1 -TcCalc"
FIX_CALC = (f"Run {CALC_STEP}. That one step installs the calc again and "
            "turns it on.")
# DATA-SNAP-AT-START (F-072): the supervisor fetches game data by itself
# while web data is on, so no fix line names a script
FIX_SNAPSHOT = ("AshLight fetches it by itself while web data is on, at most "
                "once a day. If it stays missing or old, check this computer's "
                "internet connection.")
FIX_SNAPSHOT_OFF = ('Tick "Use web data" under Prices and web data. AshLight '
                    "then fetches it by itself.")
# HOTKEYS-LIVE (OVL-KEYS-CORE): the fix names the in-app field (Tools >
# Overlay position and size); the client re-registers with no restart.
FIX_HOTKEY = ("Another app holds the key. Pick a different item check key under "
              "Overlay position and size in AshLight's Tools. No restart needed.")
FIX_TOGGLE_KEY = ("Another app holds the key. Pick a different overlay key under "
                  "Overlay position and size in AshLight's Tools. No restart needed.")
HOTKEY_UNKNOWN = "Known once the overlay is running."


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


def _state_check(cid, label, sid, status=None, prefix=""):
    """The Checks row that names table state `sid` (F-131): its detail is
    the table's check text; only a fault state is a fix row, and its fix is
    the table's next step."""
    row = words.state(sid)
    if status is None:
        status = FAIL if row["fault"] else NOTE
    return _check(cid, label, status, prefix + row["check"], row["next"])


def check_log(f):
    if f.get("log_found"):
        return _check("log", "Client.txt", PASS, "Found.")
    if f.get("log_configured"):
        # SEC-NO-DISCOVERY: a configured path is kept, never replaced by a
        # Steam library scan; the player decides.
        return _state_check("log", "Client.txt", "path_missing")
    return _state_check("log", "Client.txt", "missing")


def check_consent(f):
    if f.get("consented"):
        return _check("consent", "Permission", PASS, "You allowed reading Client.txt.")
    # F-131 (research 0042 F23): a choice not made yet is a note, not a fault.
    return _state_check("consent", "Permission", "off")


# RUN-TAIL-HEAL-CORE (research 0050 F13): the file is there but every open
# or read fails (another program holds it locked, no rights, a broken drive).
UNREADABLE_DETAIL = "Client.txt is there but can't be read. AshLight keeps trying."
FIX_UNREADABLE = ("Close any program that has Client.txt open, "
                  "or check that you can open the file yourself.")


def check_reading(f):
    if f.get("unreadable") and f.get("consented"):
        return _check("reading", "Reading", FAIL, UNREADABLE_DETAIL, FIX_UNREADABLE)
    if f.get("reading"):
        return _state_check("reading", "Reading", "reading", status=PASS)
    if not (f.get("consented") and f.get("log_found")):
        return _check("reading", "Reading", UNKNOWN,
                      "Starts once the two checks above pass.")
    return _state_check("reading", "Reading", "stalled")


def check_last_line(f, now):
    at = finite(f.get("last_line_at"))
    if at is None:
        return _check("last_line", "Last log line", UNKNOWN, "None yet.")
    age = now - at
    if age >= LAST_LINE_QUIET_S or f.get("idle"):
        # decision 0029: a quiet log is not a fault; idle comes only from
        # Client.txt staleness
        return _state_check("last_line", "Last log line", "idle", status=UNKNOWN,
                            prefix=f"{_ago(age).capitalize()}. ")
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
                      "Off. Item checks use your stat weights. To use the calc, "
                      f"run {CALC_STEP}.")
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
                      FIX_SNAPSHOT if f.get("web_data") else FIX_SNAPSHOT_OFF)
    return _check("snapshot", "Game data", PASS, f"Present, fetched {_ago(age)}.")


def _live(f, key, cid, label, what):
    v = f.get(key)
    if v is None:
        return _check(cid, label, UNKNOWN, "Not checked yet.")
    if v:
        return _check(cid, label, PASS, f"{what} is running.")
    return _check(cid, label, FAIL, f"{what} is not running.", FIX_RUN)


# HOTKEYS-LIVE (OVL-KEYS-CORE): one row per shortcut; id, label, fix
HOTKEY_ROWS = (("eval", "hotkey", "Item check hotkey", FIX_HOTKEY),
               ("toggle", "hotkey_toggle", "Overlay hotkey", FIX_TOGGLE_KEY))


def _hotkey_row(entry, cid, label, fix):
    """One shortcut row from its hotkeys.view entry."""
    e = entry if isinstance(entry, dict) else {}
    key, want = e.get("key"), e.get("want")
    if e.get("registered") is True and key:
        if e.get("fallback") is True:
            asked = want or "Your key"
            return _check(cid, label, NOTE, f"{asked} is taken by another app, "
                                            f"so AshLight uses {key}.")
        return _check(cid, label, PASS, f"Registered: {key}.")
    if e.get("registered") is False:
        held = f" {want}" if want else " the key"
        return _check(cid, label, FAIL, f"Not registered: another app holds{held}.", fix)
    return _check(cid, label, UNKNOWN, HOTKEY_UNKNOWN)


def check_hotkey(f):
    """Two rows (item check key, overlay key) and one NOTE row while the
    player switched the overlay off. With the client's keys view
    (f["hotkeys"]) each row says what is bound, a fallback or a failure;
    without it the item check row reads the overlay log's verdict
    (f["hotkey"]) and the overlay key row is unknown. While the overlay
    process is not running the keys are unknown."""
    hk = f.get("hotkeys") if isinstance(f.get("hotkeys"), dict) else None
    legacy = f.get("hotkey")
    if f.get("overlay") is False:
        hk = legacy = None
    rows = []
    for name, cid, label, fix in HOTKEY_ROWS:
        if hk is not None:
            rows.append(_hotkey_row(hk.get(name), cid, label, fix))
        elif name == "eval" and legacy is True:
            rows.append(_check(cid, label, PASS, "Registered."))
        elif name == "eval" and legacy is False:
            rows.append(_check(cid, label, FAIL, "Not registered.", fix))
        else:
            rows.append(_check(cid, label, UNKNOWN, HOTKEY_UNKNOWN))
    if hk is not None and hk.get("overlay_on") is False:
        tog = hk.get("toggle") if isinstance(hk.get("toggle"), dict) else {}
        key = tog.get("key") if tog.get("registered") is True else None
        how = f"Press {key} to show it." if key else "Show it again from the tray icon."
        rows.append(_check("overlay_off", "Overlay switched off", NOTE,
                           f"You switched the overlay off. {how}"))
    return rows


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


# SEC-ACL-CHECK (F-011): which folder, never its path. The runtime dir and
# the sidecar are AshLight-made and setup.ps1 makes them private; the
# player's own checkout changes only on the player's command.
PRIVATE_WHAT = {"runtime": "AshLight's runtime folder", "app": "the AshLight folder",
                "sidecar": "AshLight's sidecar folder"}
FIX_PRIVATE_SETUP = r"Run scripts\setup.ps1."
FIX_PRIVATE_APP = "In the AshLight folder, run: python -m server.al.acl apply ."
FIX_PRIVATE_BOTH = (r"Run scripts\setup.ps1, then in the AshLight folder run: "
                    "python -m server.al.acl apply .")


def check_private(f):
    """SEC-ACL-CHECK: one row while someone else can write to one of
    AshLight's folders (acl_open from the core's start-up audit); None
    otherwise (no row), like check_reload. Names the folder, never a path."""
    names = [n for n in PRIVATE_WHAT if n in (f.get("acl_open") or ())]
    if not names:
        return None
    what = [PRIVATE_WHAT[n] for n in names]
    if len(what) > 1:
        what = [", ".join(what[:-1]) + " and " + what[-1]]
    fixes = []
    if "runtime" in names or "sidecar" in names:
        fixes.append(FIX_PRIVATE_SETUP)
    if "app" in names:
        fixes.append(FIX_PRIVATE_APP)
    fix = fixes[0] if len(fixes) == 1 else FIX_PRIVATE_BOTH
    return _check("private", "Private files", FAIL,
                  f"Other accounts on this computer can change files in {what[0]}.", fix)


def check_port(f):
    port = f.get("port")
    if isinstance(port, int) and not isinstance(port, bool):
        return _check("port", "Dashboard address", PASS, f"127.0.0.1:{port}")
    return _check("port", "Dashboard address", UNKNOWN, "Not known.")


def check_dev_docs(f):
    """GGG-DOCS-WATCH (decision 0044): a developer note, listed only while
    the daily docs watch's flag file says GGG's docs no longer carry the
    "unable to process new applications" sentence. Players never see it:
    the flag exists only where the dev loop runs."""
    if not f.get("ggg_reg_open"):
        return None
    return _check("dev_docs", "GGG developer API", NOTE,
                  "Developer note: GGG's API docs no longer say new app sign-ups "
                  "are closed. AshLight's own sign-in may be possible now.")


# OBS-CRASH (F-105): an exit record belongs to this start when it is newer
# than the start, or is the exit (up to this long before it) that led to it:
# a crash or a keepalive kill is followed by a restart within minutes.
EXIT_WINDOW_S = 3600.0
CORE_EXIT_WORDS = {
    "crash": "AshLight stopped {ago} after an unexpected error",
    # a worker thread's crash (exitrecord.exc_detail names the thread); the
    # core itself may still run, and a later exit overwrites the record
    "crash-thread": "Part of AshLight stopped {ago} after an unexpected error",
    "signal": "AshLight was closed from outside {ago}",
    "supervisor-kill": ("AshLight stopped responding {ago}, so the keepalive "
                        "restarted it"),
}
CLIENT_EXIT_WORDS = {
    "crash": "The desktop app stopped {ago} after an unexpected error",
    "relaunch": "The desktop app restarted itself {ago} after repeated errors",
}


def _exit_row(rec, words, started, now, cid, label):
    if not isinstance(rec, dict) or rec.get("reason") not in words:
        return None
    at = finite(rec.get("at"))
    if at is None:
        return None
    if started is not None and at < started - EXIT_WINDOW_S:
        return None  # an old exit, not why this start happened
    detail = rec.get("detail")
    key = rec["reason"]
    if (key + "-thread") in words and isinstance(detail, str) and detail.startswith("thread "):
        key += "-thread"
    text = words[key].format(ago=_ago(now - at))
    if isinstance(detail, str) and detail.strip():
        text += f" ({' '.join(detail.split())})"
    return _check(cid, label, NOTE, text + ".")


def check_last_exit(f, now):
    """OBS-CRASH: up to two notes, the core's last unclean exit
    (last-exit.json: crash, signal or a keepalive kill) and the desktop
    client's (client-exit.json: crash or relaunch), each shown only when
    it is newer than this start or led to it (EXIT_WINDOW_S). A clean stop,
    a hot reload or a quit shows nothing. Nothing to fix: both come back
    by themselves, so the rows are notes; the detail is redacted with the
    rest of the view."""
    started = finite(f.get("started_at"))
    rows = [_exit_row(f.get("last_exit"), CORE_EXIT_WORDS, started, now,
                      "last_exit", "Last stop"),
            _exit_row(f.get("client_exit"), CLIENT_EXIT_WORDS, started, now,
                      "client_exit", "Desktop app")]
    return [r for r in rows if r]


def checks(f, now):
    """Every check, in reading order, from a facts dict (see Core.diag_facts).
    RUN-SEAMS (decision 0056): plug modules' rows follow the built-in ones,
    in module ORDER; web/checks.js paints any row, so a new row needs no
    web edit."""
    rows = [check_log(f), check_consent(f), check_reading(f), check_last_line(f, now),
            check_character(f), check_language(f), check_web(f), check_prices(f, now),
            check_calc(f), check_snapshot(f, now),
            _live(f, "overlay", "overlay", "Overlay", "The overlay"),
            _live(f, "supervisor", "supervisor", "Keepalive", "The keepalive"),
            *check_hotkey(f), check_port(f)]
    rows += [r for r in (check_reload(f), check_dev_docs(f), check_private(f)) if r]
    rows += check_last_exit(f, now)
    return rows + plug.collect_rows(f, now, taken={r["id"] for r in rows})


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
    """The plain-text report the player copies (ASCII, LF). The header
    names the build (RUN-BUILD-STAMP-CORE): `version` plus buildinfo's
    commit and dev mark, the string /api/health and /api/version show."""
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now))
    lines = [f"AshLight {buildinfo.build_id(version=version)} self-check, {stamp}"]
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
