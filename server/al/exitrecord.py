"""OBS-CRASH (finding F-105): why the core (and the desktop client) last
exited.

The core writes <runtime>/last-exit.json on every exit path: a stop
request, a hot reload restart, a signal, an unhandled exception in the
main or a worker thread, and a normal return of main(). The keepalive
supervisor writes it when it kills a hung core. The desktop client writes
<runtime>/client-exit.json the same way (OVL-CLIENT-GUARD, reasons quit,
relaunch, crash). Checks (diag.check_last_exit) reads both with no click.

    {"at": <epoch seconds>, "pid": <int>, "reason": <one of REASONS>,
     "detail": <one ASCII line, no path, at most DETAIL_MAX chars, or null>}

Writes are atomic (jsonfile: unique temp file, replace), ASCII and LF; the
file is one small object, rewritten on every exit, never appended to. A
write never raises: an exit path must not fail on its record. Nothing here
reads the game or the network.
"""

import os
import re
import time
from pathlib import Path

from . import jsonfile

FILE = "last-exit.json"
CLIENT_FILE = "client-exit.json"

STOP, RELOAD, SIGNAL, CRASH, SUPERVISOR_KILL = (
    "stop", "reload", "signal", "crash", "supervisor-kill")
REASONS = (STOP, RELOAD, SIGNAL, CRASH, SUPERVISOR_KILL)
# the desktop client's record (OVL-CLIENT-GUARD)
CLIENT_REASONS = ("quit", "relaunch", "crash")

# the reasons Checks shows: an exit nobody asked for
UNCLEAN = frozenset((SIGNAL, CRASH, SUPERVISOR_KILL))
CLIENT_UNCLEAN = frozenset(("relaunch", "crash"))

DETAIL_MAX = 160
MAX_BYTES = 4096  # a bigger file is not ours; it reads as no record

_DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/][^\s\"']*")
_UNC_PATH = re.compile(r"\\\\[^\s\"']+")
_POSIX_PATH = re.compile(r"(?<![\w.])/(?:[^\s/\"']+/)+[^\s\"']*")


def clean_detail(text):
    """`text` as one short ASCII line with no path, or None when empty."""
    if text is None:
        return None
    text = str(text)
    text = _DRIVE_PATH.sub("<path>", text)
    text = _UNC_PATH.sub("<path>", text)
    text = _POSIX_PATH.sub("<path>", text)
    text = " ".join(text.split())
    text = text.encode("ascii", "replace").decode("ascii")
    if len(text) > DETAIL_MAX:
        text = text[:DETAIL_MAX - 3].rstrip() + "..."
    return text or None


def exc_detail(exc_type, exc, thread=None):
    """The detail line of an unhandled exception: its type and message,
    plus the thread name for a worker thread."""
    name = getattr(exc_type, "__name__", None) or "Exception"
    msg = " ".join(str(exc).split()) if exc is not None else ""
    text = f"{name}: {msg}" if msg else name
    if thread:
        text = f"thread {thread}: {text}"
    return clean_detail(text)


def record(reason, detail=None, now=None, pid=None):
    """The record dict for `reason` (one of REASONS)."""
    if reason not in REASONS:
        raise ValueError(f"unknown exit reason {reason!r}")
    return {"at": float(time.time() if now is None else now),
            "pid": int(os.getpid() if pid is None else pid),
            "reason": reason, "detail": clean_detail(detail)}


def write(runtime_dir, reason, detail=None, now=None, pid=None):
    """Write <runtime_dir>/last-exit.json atomically; True when written.
    Never raises (an unknown reason is a programming error and does)."""
    doc = record(reason, detail, now=now, pid=pid)
    try:
        jsonfile.write_json(Path(runtime_dir) / FILE, doc, indent=None)
    except (OSError, ValueError):
        return False
    return True


def _valid(doc, reasons):
    if not isinstance(doc, dict) or doc.get("reason") not in reasons:
        return None
    at = doc.get("at")
    if isinstance(at, bool) or not isinstance(at, (int, float)) or at != at:
        return None
    pid = doc.get("pid")
    pid = pid if isinstance(pid, int) and not isinstance(pid, bool) else None
    detail = doc.get("detail")
    detail = clean_detail(detail) if isinstance(detail, str) else None
    return {"at": float(at), "pid": pid, "reason": doc["reason"], "detail": detail}


def read(runtime_dir):
    """The core's last exit record, or None (missing, unreadable, malformed)."""
    doc = jsonfile.read_json(Path(runtime_dir) / FILE, max_bytes=MAX_BYTES, kind=dict)
    return _valid(doc, REASONS)


def read_client(runtime_dir):
    """The desktop client's last exit record (client-exit.json), or None."""
    doc = jsonfile.read_json(Path(runtime_dir) / CLIENT_FILE, max_bytes=MAX_BYTES,
                             kind=dict)
    return _valid(doc, CLIENT_REASONS)
