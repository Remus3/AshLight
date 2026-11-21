"""RUN-OBS-LOGS-PY (F-090, F-027; research 0051 R7): AshLight's Python logs
are bounded, share one line format and open every start with the build
banner.

Files (all in the sidecar Logs folder, AshLight's own):

- core.log (the core), keepalive.log (the supervisor) and tc-bridge.log
  (the calc child's stderr): at each start a file over START_LIMIT bytes
  (1 MB) moves to `<name>.1`, replacing an older `.1` (one old file kept).
  The core also rolls in run at BACKSTOP_BYTES (2 MB) with the same
  scheme. A rotation that fails (the file is held open elsewhere) is not
  an error: the log keeps appending to the old file.
- core-fault.log: faulthandler's own small file, opened once at start and
  kept open for the life of the core, because the fault handler holds its
  file descriptor and the core log can now roll away under it (PYFAULT).
  A native dump carries file paths; the next start rewrites the old text
  without them before it opens the file again.

Line format: `<UTC ISO stamp> <LEVEL> <name>[<pid>] <message>`, e.g.
`2026-11-20T18:41:12.345Z INFO al[4242] listening on 127.0.0.1:8960`.
The first line of every start is the banner: `AshLight <build> <component>
start (pid <n>, python <x.y.z>)`, with the build id of buildinfo (version
plus 12 hex, F-027). Every line goes through scrub(): a path inside the
checkout is written relative to it, any other absolute path as `<path>`
(a Python file keeps its base name, `<path>/socket.py`), so no log line
holds an absolute path. Nothing here reads anything but AshLight's own
log files.
"""

import faulthandler
import logging
import os
import platform
import re
import time
from pathlib import Path

from . import NAME

START_LIMIT = 1024 * 1024            # rotate at start when over 1 MB
BACKSTOP_BYTES = 2 * 1024 * 1024     # the core's in-run roll
FAULT_LIMIT = 256 * 1024             # core-fault.log stays small
FAULT_NAME = "core-fault.log"
BACKUP_SUFFIX = ".1"
SCRUB_READ_MAX = 2 * FAULT_LIMIT     # the most of an old fault file rewritten
PATH_MARK = "<path>"

_DRIVE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s\"'<>|]*")
_UNC = re.compile(r"\\\\[^\s\\\"'<>|]+\\[^\s\"'<>|]*")
# POSIX: only paths under a system top-level folder, so an API route such
# as /api/health stays as it is
_TOP = (r"/(?:home|Users|tmp|var|usr|opt|mnt|root|private|etc|srv|Volumes"
        r"|media|run|proc|lib|lib64|bin|sbin|nix|snap)")
_POSIX = re.compile(r"(?<![\w.:/])" + _TOP + r"(?:/[^\s\"'<>|]*)?")
_QUOTED = re.compile(r"(\"|')((?:[A-Za-z]:[\\/]|\\\\|" + _TOP + r"/)[^\"'\r\n]*)\1")
_TAIL = ".,;:)]}"
_ROOTS = []                          # cached [repo root] for scrub


# -- rotation ------------------------------------------------------------------

def backup_path(path):
    """`<path>.1`: the one old file kept."""
    p = Path(path)
    return p.with_name(p.name + BACKUP_SUFFIX)


def rotate_at_start(path, limit=START_LIMIT):
    """Move `path` to `<path>.1` when it is over `limit` bytes (an older
    `.1` is replaced). True when it moved; False when it was small, missing
    or could not move (then the log keeps appending). Never raises."""
    p = Path(path)
    try:
        if p.stat().st_size <= int(limit):
            return False
        os.replace(p, backup_path(p))
        return True
    except OSError:
        return False


# -- one line format -----------------------------------------------------------

def stamp(now=None):
    """UTC ISO 8601 with milliseconds and a Z."""
    t = time.time() if now is None else float(now)
    ms = int((t - int(t)) * 1000) % 1000
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % ms


def _roots():
    if not _ROOTS:
        try:
            from . import paths
            _ROOTS.append(str(paths.repo_root()))
        except Exception:  # noqa: BLE001 - no root: every path reads <path>
            _ROOTS.append("")
    return [r for r in _ROOTS if r]


def _one(text, roots):
    tail = ""
    while text and text[-1] in _TAIL:
        tail, text = text[-1] + tail, text[:-1]
    norm = text.replace("\\", "/")
    low = norm.lower()
    for root in roots:
        r = root.replace("\\", "/").rstrip("/")
        if r and low.startswith(r.lower() + "/") and len(norm) > len(r) + 1:
            return norm[len(r) + 1:] + tail
        if r and low == r.lower():
            return "." + tail
    base = norm.rstrip("/").rsplit("/", 1)[-1]
    if base.lower().endswith((".py", ".pyw")) and re.fullmatch(r"[\w.-]+", base):
        return f"{PATH_MARK}/{base}{tail}"
    return PATH_MARK + tail


def scrub(text, roots=None):
    """`text` with every absolute path made relative to the checkout or
    replaced by `<path>` (see the module text)."""
    if not text:
        return text
    roots = _roots() if roots is None else [str(r) for r in roots]
    text = _QUOTED.sub(lambda m: m.group(1) + _one(m.group(2), roots) + m.group(1), text)
    for rx in (_DRIVE, _UNC, _POSIX):
        text = rx.sub(lambda m: _one(m.group(0), roots), text)
    return text


def format_line(name, level, message, now=None, pid=None):
    """One record in the one format (no line end); paths scrubbed."""
    pid = os.getpid() if pid is None else int(pid)
    return f"{stamp(now)} {str(level).upper()} {name}[{pid}] {scrub(str(message))}"


class Formatter(logging.Formatter):
    """logging's side of format_line: the record's level word, logger name
    and pid; an exception's traceback follows on its own lines, scrubbed."""

    def format(self, record):
        msg = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            msg = msg.rstrip("\n") + "\n" + record.exc_text
        if record.stack_info:
            msg = msg.rstrip("\n") + "\n" + self.formatStack(record.stack_info)
        return format_line(record.name, record.levelname, msg, now=record.created,
                           pid=record.process)


def banner(component, pid=None, build=None):
    """The start banner: name, build id (F-027), component, pid, Python."""
    if build is None:
        try:
            from . import buildinfo
            build = buildinfo.build_id()
        except Exception:  # noqa: BLE001 - a banner never stops a start
            from . import VERSION
            build = VERSION
    pid = os.getpid() if pid is None else int(pid)
    return (f"{NAME} {build} {component} start "
            f"(pid {pid}, python {platform.python_version()})")


# -- the core's file handler ---------------------------------------------------

class BackstopHandler(logging.FileHandler):
    """core.log: a plain appending file handler that rolls to `.1` once the
    file passes `max_bytes` in run. The new file opens with the banner. A
    roll that fails keeps appending and tries again after another
    `max_bytes`."""

    def __init__(self, path, max_bytes=BACKSTOP_BYTES, component="core",
                 name="al", encoding="utf-8"):
        super().__init__(str(path), mode="a", encoding=encoding)
        self.max_bytes = int(max_bytes)
        self.component = component
        self.banner_name = name
        self.rolls = 0
        self._next = self.max_bytes

    def _size(self):
        try:
            return os.fstat(self.stream.fileno()).st_size
        except (OSError, ValueError, AttributeError):
            return 0

    def _roll(self, size):
        self.stream.close()
        self.stream = None
        try:
            os.replace(self.baseFilename, backup_path(self.baseFilename))
            moved = True
        except OSError:
            moved = False
        self.stream = self._open()
        if moved:
            self.rolls += 1
            self._next = self.max_bytes
            line = format_line(self.banner_name, "INFO",
                               banner(self.component) + ", continued after a roll")
            self.stream.write(line + self.terminator)
            self.stream.flush()
        else:
            self._next = size + self.max_bytes

    def emit(self, record):
        try:
            if self.stream is not None:
                size = self._size()
                if size >= self._next:
                    self._roll(size)
        except Exception:  # noqa: BLE001 - a roll never costs the record
            if self.stream is None:
                try:
                    self.stream = self._open()
                except OSError:
                    pass
        super().emit(record)


def start_file(path, name, component, limit=START_LIMIT, encoding="ascii"):
    """Rotate a plain appended log at start and write its banner line.
    Never raises; False when the file could not be written."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    rotate_at_start(p, limit)
    try:
        with open(p, "a", encoding=encoding, errors="replace", newline="\n") as fh:
            fh.write(format_line(name, "INFO", banner(component)) + "\n")
        return True
    except OSError:
        return False


# -- faulthandler on its own file ----------------------------------------------

_FAULT = [None]                      # the open file, kept for the process


def fault_path(core_log):
    """core-fault.log beside core.log."""
    return Path(core_log).with_name(FAULT_NAME)


def _scrub_old(path):
    """Rewrite an earlier native dump without its paths (bounded read)."""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        return False
    if size <= 0 or size > SCRUB_READ_MAX:
        return False
    try:
        raw = p.read_bytes().decode("ascii", "replace")
        clean = scrub(raw)
        if clean == raw:
            return False
        tmp = p.with_name(p.name + ".tmp")
        with open(tmp, "w", encoding="ascii", errors="replace", newline="\n") as fh:
            fh.write(clean)
        os.replace(tmp, p)
        return True
    except OSError:
        return False


def enable_faulthandler(path, limit=FAULT_LIMIT):
    """Open the fault file (append, kept open), write the banner, point
    faulthandler at it for every thread. Returns the open file. Raises
    OSError when the file cannot be opened."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _scrub_old(p)
    rotate_at_start(p, limit)
    fh = open(p, "a", encoding="ascii", errors="replace", newline="\n")
    try:
        fh.write(format_line("faulthandler", "INFO", banner("core")) + "\n")
        fh.flush()
        faulthandler.enable(file=fh, all_threads=True)
    except (OSError, ValueError, RuntimeError):
        fh.close()
        raise OSError("faulthandler could not use its file")
    old, _FAULT[0] = _FAULT[0], fh
    if old is not None and old is not fh:
        try:
            old.close()
        except OSError:
            pass
    return fh
