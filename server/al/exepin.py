"""Executable paths that cannot be planted (AUDIT-EXE-PATH, audit finding S5).

Windows CreateProcess searches the current directory for a bare program
name, so AshLight never runs one:
- Windows tools run by their System32 absolute path (system_tool);
- a tool found on PATH is taken only from an absolute PATH entry, never the
  current directory (which_abs);
- a locally built executable with no published hash (luajit.exe) runs only
  when it matches the SHA-256 recorded right after the build (record /
  verified), checked before every exec.
Stdlib only.
"""

import hashlib
import os
from pathlib import Path

HASH_SUFFIX = ".sha256"


def system_dir():
    """The Windows System32 folder (GetSystemDirectoryW; SystemRoot as a
    fallback, then <SystemDrive>\\Windows). Off Windows the same layout is
    returned, so the path stays absolute."""
    if os.name == "nt":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            n = ctypes.windll.kernel32.GetSystemDirectoryW(buf, 260)
            if 0 < n < 260:
                return Path(buf.value)
        except (OSError, AttributeError):
            pass
    drive = os.environ.get("SystemDrive") or ""
    if not (len(drive) == 2 and drive[0].isalpha() and drive[1] == ":"):
        drive = "C" + ":"
    fallback = drive + "\\" + "Windows"
    root = os.environ.get("SystemRoot") or fallback
    if not (len(root) >= 3 and root[1] == ":" and root[2] in "\\/"):
        root = fallback
    return Path(root) / "System32"


def system_tool(*rel):
    """Absolute path of a Windows tool under System32, e.g.
    system_tool("cmd.exe") or system_tool("WindowsPowerShell", "v1.0",
    "powershell.exe")."""
    return system_dir().joinpath(*rel)


def which_abs(name, environ=None):
    """First match of name (with PATHEXT on Windows) in an ABSOLUTE PATH
    entry; the current directory and relative entries are skipped. None when
    not found."""
    env = os.environ if environ is None else environ
    exts = [""]
    if os.name == "nt" or "PATHEXT" in env:
        exts += [e for e in (env.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD").split(";") if e]
    for entry in (env.get("PATH") or "").split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry or not os.path.isabs(entry) or entry.startswith(("\\\\", "//")):
            continue
        for ext in exts:
            cand = Path(entry) / (name + ext)
            if cand.is_file():
                return cand
    return None


def _digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_file(exe):
    exe = Path(exe)
    return exe.with_name(exe.name + HASH_SUFFIX)


def record(exe):
    """Record the SHA-256 of a freshly built executable next to it."""
    hash_file(exe).write_text(_digest(exe) + "\n", encoding="ascii", newline="\n")


def verified(exe):
    """True only when exe exists and matches its recorded SHA-256."""
    try:
        want = hash_file(exe).read_text(encoding="ascii").strip()
        return len(want) == 64 and Path(exe).is_file() and _digest(exe) == want
    except (OSError, ValueError):
        return False
