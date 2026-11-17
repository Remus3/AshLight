"""Client.txt discovery and a read-only, low-CPU tailer.

Read policy (decision 0003): the tailer runs only after the user's opt-in,
opens the file read-only with full sharing, never writes to it and never
touches the game process. It starts at the END of the file by default, so an
old session is never replayed; state is recovered from the skipped bytes by
the on_resume hook (server/al/resume.py, LIVE-RESUME).

Discovery reads Steam's libraryfolders.vdf (read only) and looks for
steamapps/common/Path of Exile 2/logs/Client.txt in every library.
"""

import os
import re
import threading
from pathlib import Path

GAME_DIR = "Path of Exile 2"
LOG_REL = Path("steamapps") / "common" / GAME_DIR / "logs" / "Client.txt"
DEFAULT_POLL_S = 0.25
MAX_READ = 4 * 1024 * 1024  # bytes per poll; a large backlog drains over polls
_BOM = b"\xef\xbb\xbf"
# TEST-E2E: the longest unterminated line held back. Real Client.txt lines are
# well under 2 KB; a longer run with no newline (NUL padding after a crash,
# garbage) is dropped up to its next newline instead of growing without bound.
MAX_PARTIAL = 64 * 1024


# ---------------------------------------------------------------- discovery

def _steam_roots_from_registry():
    """Steam install dirs from the registry (read only). Windows only."""
    roots = []
    if os.name != "nt":
        return roots
    try:
        import winreg
    except ImportError:
        return roots
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]
    for hive, sub, name in keys:
        try:
            with winreg.OpenKey(hive, sub) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value:
                    roots.append(Path(value))
        except OSError:
            continue
    return roots


def _steam_roots_from_env(environ=None):
    env = os.environ if environ is None else environ
    roots = []
    for var in ("ProgramFiles(x86)", "ProgramFiles"):
        base = env.get(var)
        if base:
            roots.append(Path(base) / "Steam")
    return roots


_VDF_PATH = re.compile(r'^\s*"path"\s*"((?:[^"\\]|\\.)*)"', re.M)
_VDF_OLD = re.compile(r'^\s*"\d+"\s*"((?:[^"\\]|\\.)*)"', re.M)


def _vdf_unescape(value):
    return value.replace("\\\\", "\\")


def parse_libraryfolders(text):
    """Library paths from a libraryfolders.vdf text (new and old layout)."""
    out = [Path(_vdf_unescape(m.group(1))) for m in _VDF_PATH.finditer(text)]
    if not out:  # old layout: "1"  "<path>"
        out = [Path(_vdf_unescape(m.group(1))) for m in _VDF_OLD.finditer(text)]
    return out


def steam_libraries(steam_roots=None):
    """Every Steam library dir: the Steam roots plus libraryfolders.vdf entries."""
    if steam_roots is None:
        steam_roots = _steam_roots_from_registry() + _steam_roots_from_env()
    libs = []
    for root in steam_roots:
        root = Path(root)
        if root not in libs:
            libs.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lib in parse_libraryfolders(text):
            if lib not in libs:
                libs.append(lib)
    return libs


def discover_client_log(configured=None, steam_roots=None):
    """The Client.txt path: the configured value when it exists, else the first
    Steam library holding the PoE2 log. None when nothing is found."""
    if configured:
        p = Path(configured)
        if p.is_dir():
            p = p / "logs" / "Client.txt" if (p / "logs").is_dir() else p / "Client.txt"
        if p.is_file():
            return p
    for lib in steam_libraries(steam_roots):
        cand = lib / LOG_REL
        if cand.is_file():
            return cand
    return None


# ---------------------------------------------------------------- open

def _open_shared(path):
    """Open read-only with FILE_SHARE_READ | WRITE | DELETE on Windows, so the
    game can keep writing, rotating or deleting the file. Plain open elsewhere."""
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.HANDLE]
        generic_read = 0x80000000
        share_all = 0x1 | 0x2 | 0x4
        open_existing = 3
        normal = 0x80
        invalid = wintypes.HANDLE(-1).value
        h = k32.CreateFileW(str(path), generic_read, share_all, None,
                            open_existing, normal, None)
        if not h or h == invalid:
            err = ctypes.get_last_error()
            if err in (2, 3):
                raise FileNotFoundError(err, "Client.txt not found", str(path))
            raise OSError(err, "CreateFileW failed", str(path))
        fd = msvcrt.open_osfhandle(h, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        return os.fdopen(fd, "rb", buffering=0)
    return open(path, "rb", buffering=0)


def _identity(st):
    if st.st_ino:
        return (st.st_dev, st.st_ino)
    return (st.st_dev, int(getattr(st, "st_birthtime", st.st_ctime) * 1e6))


# ---------------------------------------------------------------- tailer

class Tailer:
    """Polls the file size every poll_s seconds and emits complete lines.

    on_line(str) gets each complete line (no terminator); on_status(dict) gets
    tailer_started / tailer_reset events. No busy loop: the thread sleeps on an
    Event between polls. poll_once() is the synchronous step (tests use it).
    """

    def __init__(self, path, on_line, on_status=None, poll_s=DEFAULT_POLL_S,
                 start_at_end=True, on_resume=None):
        self.path = Path(path)
        self.on_line = on_line
        self.on_status = on_status or (lambda ev: None)
        self.poll_s = float(poll_s)
        self.start_at_end = start_at_end
        # LIVE-RESUME: on_resume(path, end_offset) runs once, before the
        # first start at the end, so state can be recovered from the bytes
        # the tailer skips (server/al/resume.py). Its errors never stop
        # the tailer.
        self.on_resume = on_resume
        self._fh = None
        self._ident = None
        self._offset = 0
        self._partial = b""
        self._skipping = False  # inside an oversized line, until its newline
        self.dropped_lines = 0
        self._opened_once = False
        self._missing = False
        self._stop = threading.Event()
        self._thread = None
        self.lines = 0

    # -- lifecycle
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="al-tailer", daemon=True)
        self._thread.start()

    def stop(self, timeout=2.0):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
        self._close()

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def _run(self):
        while not self._stop.is_set():
            try:
                self.poll_once()
            except OSError:
                self._close()
            self._stop.wait(self.poll_s)

    # -- internals
    def _close(self):
        """Kept for API symmetry: no handle is held between polls."""
        self._fh = None

    def _started(self, st, at_end):
        if at_end and not self._opened_once and self.on_resume is not None:
            try:
                self.on_resume(self.path, st.st_size)
            except Exception:  # noqa: BLE001 - recovery is best effort
                pass
        self._ident = _identity(st)
        self._offset = st.st_size if at_end else 0
        self._partial = b""
        self._skipping = False
        resumed = self._opened_once
        self._opened_once = True
        self.on_status({"type": "tailer_started", "path": str(self.path),
                        "offset": self._offset, "file_size": st.st_size,
                        "resumed": resumed})

    def _reset(self, reason):
        self.on_status({"type": "tailer_reset", "reason": reason})

    def poll_once(self):
        """One poll step: one stat, and an open/read/close only when the file
        grew. No handle is held while idle, so the game can rotate, replace or
        delete the file at any time. Returns the number of lines emitted."""
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            if not self._missing:
                self._missing = True
                self._reset("missing")
            return 0
        if self._ident is None:
            # The first sighting honours start_at_end, unless the file was
            # missing first: then it is new and is read from its start.
            self._started(st, at_end=self.start_at_end and not self._missing)
        elif self._missing or _identity(st) != self._ident:
            if not self._missing:
                self._reset("replaced")
            self._started(st, at_end=False)
        elif st.st_size < self._offset:
            self._reset("truncated")
            self._offset = 0
            self._partial = b""
            self._skipping = False
        self._missing = False
        if st.st_size <= self._offset:
            return 0
        fh = _open_shared(self.path)
        try:
            fh.seek(self._offset)
            data = fh.read(min(st.st_size - self._offset, MAX_READ))
        finally:
            fh.close()
        if not data:
            return 0
        if self._offset == 0 and data.startswith(_BOM):
            data = data[len(_BOM):]
            self._offset += len(_BOM)
        self._offset += len(data)
        return self._emit(data)

    def _emit(self, data):
        buf = self._partial + data
        parts = buf.split(b"\n")
        self._partial = parts.pop()  # the unterminated tail waits for its "\n"
        if self._skipping:
            if parts:
                parts.pop(0)  # the rest of the oversized line
                self._skipping = False
            else:
                self._partial = b""
        if len(self._partial) > MAX_PARTIAL:
            self._partial = b""
            self._skipping = True
            self.dropped_lines += 1
        n = 0
        for raw in parts:
            if raw.endswith(b"\r"):
                raw = raw[:-1]
            if not raw:
                continue
            self.on_line(raw.decode("utf-8", errors="replace"))
            n += 1
        self.lines += n
        return n
