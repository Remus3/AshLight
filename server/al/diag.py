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
RUN-REPORT-FIELDS: the report's allow-list of fields and the hardened,
whole-word redactor live in server/al/report.py; secrets(), redact() and
report() here delegate to it.
"""

import datetime as _dt
import re
import time
from pathlib import Path

from . import diag_data, jsonfile, langguard, plug
from . import report as report_mod
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
# DATA-CONTACT-FIELD (F-018): the contact is typed in the dashboard, never
# a file path in the fix text. RUN-NO-DEAD-ENDS (research 0042 R4): the field
# moved to the Settings section Reading and web data (web/index.html h3), so
# the words name that exact place.
CONTACT_CARD = "Settings, Reading and web data"
FIX_CONTACT = f"Type your contact under {CONTACT_CARD}."
FIX_NET = ("Check this computer's internet connection. AshLight tries again "
           "by itself.")
# TC-CALC-OPTIN (F-132): one run of the switch installs the calc and turns
# it on (tools/tc_pin.py writes "tc_calc"); no second edit of the config.
# RUN-NO-DEAD-ENDS (research 0042 R4, F20 c): the words name the row's own
# button (TC-CALC-OPTIN-BUTTON, web/checks.js CALC_BUTTON), never a script,
# and never "again" for a part that was never installed.
CALC_BUTTON = "Set up the calc"
CALC_PLACE = "under Settings, Checks in the AshLight window"
CALC_STEP = f'press "{CALC_BUTTON}" {CALC_PLACE}'
FIX_CALC = (f'Press "{CALC_BUTTON}" {CALC_PLACE}. It installs the calc and '
            "turns it on.")
# DATA-SNAP-AT-START (F-072): the supervisor fetches game data by itself
# while web data is on, so no fix line names a script
FIX_SNAPSHOT = ("AshLight fetches it by itself while web data is on, at most "
                "once a day. If it stays missing or old, check this computer's "
                "internet connection.")
FIX_SNAPSHOT_OFF = (f'Tick "Use web data" under {CONTACT_CARD}. AshLight '
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


# RUN-QUIET-FEED (F-093): a row whose words carry an age keeps the age out
# of its detail: the detail holds AGO where the age goes and the row's "at"
# holds the absolute time (epoch s). The published view therefore changes
# only when a fact changes, never because a minute went by; the dashboard
# (web/checks.js) writes the age in, stepped at 5 minutes, and the report
# writes it in when it is made (render_detail).
AGO = "{ago}"


def _check(cid, label, status, detail, fix=None, at=None):
    row = {"id": cid, "label": label, "status": status, "detail": detail,
           "fix": fix if status == FAIL else None}
    if at is not None:
        row["at"] = at
    return row


def render_detail(row, now):
    """The row's detail with its age written in (AGO replaced by _ago of
    now - at; capitalised at the start of the detail). A row with no "at"
    is returned as it is."""
    detail = row.get("detail")
    at = finite(row.get("at"))
    if not isinstance(detail, str) or at is None or AGO not in detail:
        return detail
    ago = _ago(now - at)
    if detail.startswith(AGO):
        detail = ago[:1].upper() + ago[1:] + detail[len(AGO):]
    return detail.replace(AGO, ago)


def _state_check(cid, label, sid, status=None, prefix="", at=None):
    """The Checks row that names table state `sid` (F-131): its detail is
    the table's check text; only a fault state is a fix row, and its fix is
    the table's next step."""
    row = words.state(sid)
    if status is None:
        status = FAIL if row["fault"] else NOTE
    return _check(cid, label, status, prefix + row["check"], row["next"], at=at)


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
# RUN-UNREADABLE-WORD: the words are the table's unreadable state, the one
# the dashboard bar and the overlay name too.
UNREADABLE_DETAIL = words.check("unreadable")
FIX_UNREADABLE = words.next_step("unreadable")


def check_reading(f):
    if f.get("unreadable") and f.get("consented"):
        return _state_check("reading", "Reading", "unreadable")
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
        # RUN-NO-DEAD-ENDS (research 0042 F20 a): the age is known, so the
        # row is a note, never "not known yet" beside "25 min ago"
        return _state_check("last_line", "Last log line", "idle", status=NOTE,
                            prefix=AGO + ". ", at=at)
    return _check("last_line", "Last log line", PASS, AGO + ".", at=at)


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
        return _check("web_data", "Web data", FAIL,
                      f"On, but no contact is set in {CONTACT_CARD}.", FIX_CONTACT)
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
        return _check("prices", "Price book", FAIL, f"Updated {AGO}.", FIX_NET, at=at)
    return _check("prices", "Price book", PASS, f"Updated {AGO}.", at=at)


def check_calc(f):
    if not f.get("calc_on"):
        return _check("calc", "Calc component", OFF,
                      "Off. Item checks use your stat weights. To use the calc, "
                      f"{CALC_STEP}.")
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
        return _check("snapshot", "Game data", FAIL, f"Present, fetched {AGO}.",
                      FIX_SNAPSHOT if f.get("web_data") else FIX_SNAPSHOT_OFF, at=at)
    return _check("snapshot", "Game data", PASS, f"Present, fetched {AGO}.", at=at)


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
# the sidecar are AshLight-made and AshLight's setup makes them private; the
# player's own checkout changes only on the player's command.
# RUN-NO-DEAD-ENDS (research 0042 R4): the fix names the act, never a script.
PRIVATE_WHAT = {"runtime": "AshLight's runtime folder", "app": "the AshLight folder",
                "sidecar": "AshLight's sidecar folder"}
FIX_PRIVATE_SETUP = ("Run AshLight's setup again, as when you installed it. It "
                     "makes AshLight's own folders private.")
# NDE-1: the AshLight folder is the player's own, so AshLight never changes
# it (decision 0051); the fix is plain Windows steps, never a command line.
FIX_PRIVATE_APP = ("Right-click the AshLight folder, open Properties, then "
                   "Security, and take away Write from Everyone, Users and any "
                   "other person's account.")
FIX_PRIVATE_BOTH = ("Run AshLight's setup again, as when you installed it. Then "
                    "right-click the AshLight folder, open Properties, then "
                    "Security, and take away Write from Everyone, Users and any "
                    "other person's account.")


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


# LOOP-DEV-CHECKS (F-125, AUTO-08): the dev loop's own status file. It exists
# only where the dev loop runs (a HALTed tick still writes it every 15
# minutes), so players never see the note. Read from the file, never from a
# process list or the scheduled task.
LOOP_STATUS_PARTS = ("ops", "loop", "control", "progress", "loop.json")
LOOP_STATUS_MAX_BYTES = 256 * 1024
LOOP_TICK_STALE_S = 2 * 3600
# F-130: the pinned Electron line's end of life, from the tracked pin
# (decision 0068), computed offline: no version is checked online (0013).
ELECTRON_PIN_PARTS = ("config", "electron_pin.json")
ELECTRON_PIN_MAX_BYTES = 64 * 1024
ELECTRON_EOL_WARN_S = 30 * 86400
_EOL_VERSION = re.compile(r"(\d{1,4})\.\d{1,4}\.\d{1,6}\Z")
_EOL_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _stamp(value):
    """Epoch seconds of an ISO 8601 stamp (a stamp with no offset is local
    time), else None."""
    if not isinstance(value, str) or not 0 < len(value) <= 40:
        return None
    try:
        when = _dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return when.timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def loop_tick_age(root, now):
    """Seconds since the dev loop's last tick ("updated" of
    <root>/ops/loop/control/progress/loop.json), or None while the file is
    missing, unreadable or carries no stamp. Never negative."""
    doc = jsonfile.read_json(Path(root).joinpath(*LOOP_STATUS_PARTS),
                             max_bytes=LOOP_STATUS_MAX_BYTES, kind=dict)
    at = _stamp(doc.get("updated")) if isinstance(doc, dict) else None
    now = finite(now)
    if at is None or now is None:
        return None
    return max(0.0, now - at)


def electron_eol(root):
    """{"version", "eol"} of the tracked Electron pin
    (<root>/config/electron_pin.json), or None while the file is missing or
    either value is malformed (never guessed)."""
    doc = jsonfile.read_json(Path(root).joinpath(*ELECTRON_PIN_PARTS),
                             max_bytes=ELECTRON_PIN_MAX_BYTES, kind=dict)
    if not isinstance(doc, dict):
        return None
    version, eol = doc.get("version"), doc.get("eol")
    if not (isinstance(version, str) and _EOL_VERSION.match(version)
            and isinstance(eol, str) and _EOL_DATE.match(eol)):
        return None
    try:
        _dt.date.fromisoformat(eol)
    except ValueError:
        return None
    return {"version": version, "eol": eol}


def check_loop_tick(f, now):
    """LOOP-DEV-CHECKS: a developer note while the dev loop's last tick is
    older than LOOP_TICK_STALE_S; None otherwise (no row), and None where
    there is no loop status file (every player). The age is written in
    from "at" (RUN-QUIET-FEED)."""
    age = finite(f.get("loop_tick_age_s"))
    if age is None or age <= LOOP_TICK_STALE_S:
        return None
    return _check("dev_loop", "Dev loop", NOTE,
                  f"Developer note: the dev loop last ran {AGO}. Its scheduled "
                  "task may have stopped. Read it back with: python "
                  "tools/loop_task.py status", at=round(now - age))


def check_electron_eol(f, now):
    """F-130: a note for every user while the pinned Electron line is
    within ELECTRON_EOL_WARN_S of its end of life or past it; None
    otherwise (no row, also with no pin file). The date is written as a
    date, so the row changes only when it appears."""
    pin = f.get("electron_eol")
    if not isinstance(pin, dict):
        return None
    version, eol = pin.get("version"), pin.get("eol")
    m = _EOL_VERSION.match(version) if isinstance(version, str) else None
    if not m or not isinstance(eol, str) or not _EOL_DATE.match(eol):
        return None
    try:
        end = _dt.datetime.combine(_dt.date.fromisoformat(eol), _dt.time(),
                                   _dt.timezone.utc).timestamp()
    except ValueError:
        return None
    now = finite(now)
    if now is None or end - now > ELECTRON_EOL_WARN_S:
        return None
    line = f"Electron {m.group(1)}, which runs the desktop app,"
    if now >= end:
        text = f"{line} reached its end of life on {eol} and gets no more security fixes."
    else:
        text = (f"{line} reaches its end of life on {eol}. After that it gets "
                "no more security fixes.")
    ins = f.get("install")
    if isinstance(ins, dict) and ins.get("mode") == "installed":
        text += " A newer AshLight release brings a newer one by itself."
    else:
        # RUN-NO-DEAD-ENDS (tests/test_copy_dead_ends.py): the fix names the
        # act, never the script (scripts\setup.ps1 is AshLight's setup)
        text += (" Update AshLight, then run AshLight's setup again, as when you "
                 "installed it. It fetches the newer Electron.")
    return _check("electron_eol", "Desktop app runtime", NOTE, text)


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
    text = words[key].format(ago=AGO)
    if isinstance(detail, str) and detail.strip():
        # a brace in the record's own words must never read as the age mark
        text += f" ({' '.join(detail.split()).replace(AGO, '(ago)')})"
    return _check(cid, label, NOTE, text + ".", at=at)


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


# REL-UPDATE-CHECKS (F-077, DEP-11): the installed copy's rows. The facts
# are Core.diag_facts()["install"]: the marker's version and previous, the
# newest staged version (<home>/staged) and the last update result
# (<home>/logs/reports/last-update.json), read only by the core, never
# fetched or switched. Every value is a checked version, a fixed word or a
# time, never a path. A checkout has no row.
INSTALL_ID, INSTALL_LABEL = "install", "Installed copy"
UPDATE_ID, UPDATE_LABEL = "install_update", "Update"
INSTALL_ROW_IDS = (INSTALL_ID, UPDATE_ID)
# a rollback's fix row clears by itself after this long (or when the next
# update result replaces it)
ROLLBACK_SHOWN_S = 7 * 86400
FIX_ROLLBACK = ("Nothing to undo: AshLight already went back by itself. The next "
                "release installs by itself. To tell the project what went "
                "wrong, copy this report.")
_VERSION_CHARS = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-")


def _version(value):
    """A version word (digits, letters, dots and dashes, a digit first), or
    None: nothing else from the files reaches a row."""
    if (isinstance(value, str) and 0 < len(value) <= 40 and value[0].isdigit()
            and set(value) <= _VERSION_CHARS):
        return value
    return None


def _last_text(last):
    """The last update result in words, or None (an unknown word)."""
    if not isinstance(last, dict):
        return None
    action, status = last.get("action"), last.get("status")
    new, old = _version(last.get("version")), _version(last.get("from"))
    if action == "update":
        if status == "staged" and new:
            return f"{new} downloaded and checked"
        if status == "failed":
            return "a new version failed its checks, nothing changed"
        if status == "deferred":
            return "waiting until the game is idle"
        if status == "refused":
            return "refused, nothing changed"
        return None
    if action == "apply":
        if status == "switched" and new and old:
            return f"switched from {old} to {new}"
        if status == "failed":
            return "switching failed, nothing changed"
        return None
    if action == "rollback":
        if status == "rolled back" and new and old:
            return f"went back from {old} to {new}"
        if status == "failed":
            return "going back failed"
        return None
    if action == "confirm" and status == "confirmed" and new:
        return f"{new} started fine"
    return None


def _install_row(ins):
    version, previous = _version(ins.get("version")), _version(ins.get("previous"))
    if version is None:
        status, detail = UNKNOWN, "Its version file can't be read."
    else:
        status = PASS
        detail = f"Version {version}, " + (f"previous {previous} kept." if previous
                                           else "no earlier version kept.")
    last = ins.get("last")
    text, at = _last_text(last), None
    if text:
        at = finite(last.get("at"))
        detail += f" Last update: {text}" + (f", {AGO}." if at is not None else ".")
    return _check(INSTALL_ID, INSTALL_LABEL, status, detail, at=at)


def _rollback_row(last, version, now):
    """The one fix row after a rollback to the running version."""
    if not (isinstance(last, dict) and last.get("action") == "rollback"
            and last.get("status") == "rolled back"):
        return None
    bad, back = _version(last.get("from")), _version(last.get("version"))
    if not bad or not back or back != version:
        return None
    at = finite(last.get("at"))
    if at is not None and now - at > ROLLBACK_SHOWN_S:
        return None
    return _check(UPDATE_ID, UPDATE_LABEL, FAIL,
                  f"Version {bad} did not work, so AshLight went back to {back}. "
                  f"It won't offer {bad} again.", FIX_ROLLBACK)


def _staged_row(staged, version, now):
    """The one line naming a staged version."""
    new = _version(staged.get("version")) if isinstance(staged, dict) else None
    if not new or new == version:
        return None
    due = finite(staged.get("apply_after"))
    if due is not None and due > now:
        stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(due))
        when = f"the first time you open AshLight after {stamp}"
    else:
        when = "the next time you open AshLight"
    return _check(UPDATE_ID, UPDATE_LABEL, NOTE, f"Version {new} is ready. It starts {when}.")


def check_install(f, now):
    """REL-UPDATE-CHECKS: in an installed copy, the version row (mode,
    version, previous, the last update result) and at most one update row:
    the fix row after a rollback, else the note naming a staged version.
    A checkout (or no install facts) has no row."""
    ins = f.get("install")
    if not isinstance(ins, dict) or ins.get("mode") != "installed":
        return []
    rows = [_install_row(ins)]
    version = _version(ins.get("version"))
    extra = (_rollback_row(ins.get("last"), version, now)
             or _staged_row(ins.get("staged"), version, now))
    return rows + ([extra] if extra else [])


def checks(f, now):
    """Every check, in reading order, from a facts dict (see Core.diag_facts).
    RUN-SEAMS (decision 0056): plug modules' rows follow the built-in ones,
    in module ORDER; web/checks.js paints any row, so a new row needs no
    web edit. DATA-DIAG-SEAM: the data modules' diag_rows come before the
    reload and dev-docs rows (diag_data.py)."""
    rows = [check_log(f), check_consent(f), check_reading(f), check_last_line(f, now),
            check_character(f), check_language(f), check_web(f), check_prices(f, now),
            check_calc(f), check_snapshot(f, now),
            _live(f, "overlay", "overlay", "Overlay", "The overlay"),
            _live(f, "supervisor", "supervisor", "Keepalive", "The keepalive"),
            *check_hotkey(f), *check_install(f, now), check_port(f)]
    rows += diag_data.rows(f, now, taken={r["id"] for r in rows})  # DATA-DIAG-SEAM
    rows += [r for r in (check_reload(f), check_dev_docs(f), check_loop_tick(f, now),
                         check_electron_eol(f, now), check_private(f)) if r]
    rows += check_last_exit(f, now)
    return rows + plug.collect_rows(f, now, taken={r["id"] for r in rows})


# -- redaction (ruling J) and the report: server/al/report.py (RUN-REPORT-FIELDS)

def secrets(f=None, environ=None):
    """The strings a report must never carry (report.secrets): the paths,
    the Windows user, the contact and every known character name."""
    return report_mod.secrets(f, environ)


def redact(text, pairs):
    """`text` with every secret masked as a whole word, then e-mail, paths,
    URLs, addresses, host names and long hex runs (report.redact, P8-7)."""
    return report_mod.redact(text, pairs)


def report(rows, version, now, pairs, extra=None, tails=None):
    """The plain-text report the player copies (ASCII, LF), made by
    report.compose from its allow-list: the header naming the build
    (RUN-BUILD-STAMP-CORE: `version` plus buildinfo's commit and dev
    mark), the OS, Python and Electron versions, the counters, one line
    per row (ages written in at `now`), then `extra` (last restart, the
    session's not counted mod lines, ledger shapes) and, only on the
    player's second choice, `tails`. Only free text is redacted; labels
    and marks are fixed words (P8-7). REL-UPDATE-CHECKS: the installed
    copy's rows (mode, version, previous, last update result, a staged
    or rolled-back version) come first, right under the header fields."""
    rows = ([r for r in rows if r.get("id") in INSTALL_ROW_IDS]
            + [r for r in rows if r.get("id") not in INSTALL_ROW_IDS])
    return report_mod.compose(rows, version, now, pairs, render=render_detail,
                              mark=MARK, extra=extra, tails=tails)


def summary(rows):
    n = sum(1 for r in rows if r["status"] == FAIL)
    if n == 0:
        return "All checks pass."
    return "1 check needs a fix." if n == 1 else f"{n} checks need a fix."


def view(facts, version, now=None, with_report=True):
    """{"checks", "failed", "summary", "report"}. RUN-QUIET-FEED (F-093,
    F-109): the snapshot's copy is made with with_report=False and holds
    no report text (the page builds the report on the click through GET
    /api/report, server/al/plug/report.py) and no age: rows that carry one
    hold AGO in the detail and the absolute time in "at", so the view only
    changes when a fact does. With the report, the report writes the ages
    in at `now`."""
    now = time.time() if now is None else now
    pairs = secrets(facts)
    rows = checks(facts, now)
    for r in rows:
        r["detail"] = redact(r["detail"], pairs)
    out = {"checks": rows, "failed": sum(1 for r in rows if r["status"] == FAIL),
           "summary": summary(rows)}
    if with_report:
        out["report"] = report(rows, version, now, pairs)
    return out


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
