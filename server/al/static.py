"""SEC-STATIC-MAP: the token-free /web/ route answers from a fixed name map.

The map is AshLight's own listing of web/ (recursive, posix relative names
-> absolute paths), made without any request text. A request is answered by
an exact dict lookup, so no file system call ever sees what the client sent
(no resolve of a UNC tail, a drive name, a stream suffix, a trailing dot or
a device name; research 0045 F1, go-public blocker B7 (a)).

The listing is rebuilt only when the caller's sequence number changes: the
server passes core.reload_web, which the hot-reload scan bumps when a file
under web/ changes (decision 0042), so a new file is served after the next
scan with no click (ZERO-CLICK).
"""

import os
import threading
from pathlib import Path


def scan(root):
    """{posix relative name: absolute Path} for every regular file under
    root. Links are left out, and so is anything that resolves outside
    root (a junction), so the map never names a file outside web/."""
    out = {}
    if root is None or not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if not (base / d).is_symlink())
        for name in sorted(filenames):
            p = base / name
            if p.is_symlink() or not p.is_file():
                continue
            real = p.resolve()
            if not real.is_relative_to(root):
                continue
            out[p.relative_to(root).as_posix()] = real
    return out


class StaticMap:
    """The served files of one web root. lookup() is a dict get; it lists
    the folder again only when seq differs from the one of the last scan."""

    def __init__(self, web_root, seq=0):
        self.root = Path(web_root).resolve() if web_root else None
        self._lock = threading.Lock()
        self._seq = seq
        self._map = scan(self.root)

    def names(self):
        return sorted(self._map)

    def lookup(self, name, seq=0):
        """The absolute path served for the exact name, or None. name is
        request text and only ever used as a dict key."""
        if seq != self._seq:
            with self._lock:
                if seq != self._seq:
                    self._map = scan(self.root)
                    self._seq = seq
        if not isinstance(name, str):
            return None
        return self._map.get(name)
