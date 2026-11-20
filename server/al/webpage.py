"""TEST-WEB-ASSEMBLE (F-194, research 0047 R8): the dashboard page with its
panel tags, made at serve time.

assemble(web_root) reads web/index.html, finds MARKER and inserts right
after it one stylesheet link per web/panels/*.css and one deferred script
tag per web/panels/*.js, each list sorted by name. The marker sits before
the app.js tag, so every panel script runs before app.js renders; a new
panel is a new file and edits no shared one. With no panel file the page
is byte-identical to index.html.

Floor (CLAUDE.md "Stack and ports", http.py CSP): every tag is a
same-origin /web/panels/ path, never an inline script or a remote origin.
A file name is taken only when it matches SAFE_NAME, so no listed name can
break out of an attribute. Links and anything that is not a regular file
are left out, the same rule as the /web/ map (static.py), so a tag never
names a file the map would not serve.

The result is cached per web root by the names, sizes and mtimes of
web/panels/ and the stat of index.html: a GET lists one small folder, and
a panel added while the core runs shows on the next GET with no restart
(ZERO-CLICK). Only the tags half of R8 is built; the page skeleton stays
in index.html.
"""

import os
import re
import threading
from pathlib import Path

PAGE = "index.html"
PANELS = "panels"
MARKER = b"<!-- al:panels -->"
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\.(?:js|css)")
MAX_ROOTS = 8  # one entry per web root; tests make many servers

_lock = threading.Lock()
_cache = {}  # resolved root -> (key, page bytes, panel names)


def _stat_key(path):
    try:
        st = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def _panel_files(root):
    """[(name, size, mtime_ns)] of the regular, safely named .js / .css
    files directly in root/panels, sorted by name."""
    folder = root / PANELS
    out = []
    try:
        with os.scandir(folder) as it:
            entries = list(it)
    except OSError:
        return out
    for e in entries:
        if not SAFE_NAME.fullmatch(e.name):
            continue
        try:
            if e.is_symlink() or not e.is_file(follow_symlinks=False):
                continue
            st = e.stat(follow_symlinks=False)
            if not Path(e.path).resolve().is_relative_to(root):
                continue  # a junction out of web/: the map skips it too
        except OSError:
            continue
        out.append((e.name, st.st_size, st.st_mtime_ns))
    out.sort()
    return out


def tags(names):
    """The inserted lines: stylesheet links first, then scripts, each
    sorted; every href / src is a same-origin /web/panels/ path."""
    css = [n for n in sorted(names) if n.endswith(".css")]
    js = [n for n in sorted(names) if n.endswith(".js")]
    lines = ['<link rel="stylesheet" href="/web/%s/%s">' % (PANELS, n) for n in css]
    lines += ['<script src="/web/%s/%s" defer></script>' % (PANELS, n) for n in js]
    return "".join("\n" + line for line in lines).encode("ascii")


def insert(page, names):
    """page bytes with the panel tags after MARKER; unchanged when there
    is no panel or no marker (a page without the seam links no panel)."""
    if not names:
        return page
    at = page.find(MARKER)
    if at < 0:
        return page
    end = at + len(MARKER)
    return page[:end] + tags(names) + page[end:]


def _build(root):
    """(key, page, names) for root, or None when index.html is missing."""
    page_key = _stat_key(root / PAGE)
    if page_key is None:
        return None
    files = _panel_files(root)
    key = (page_key, tuple(files))
    with _lock:
        hit = _cache.get(root)
    if hit is not None and hit[0] == key:
        return hit
    try:
        raw = (root / PAGE).read_bytes()
    except OSError:
        return None
    names = tuple(n for n, _, _ in files)
    entry = (key, insert(raw, names), names)
    with _lock:
        if root not in _cache and len(_cache) >= MAX_ROOTS:
            _cache.pop(next(iter(_cache)))
        _cache[root] = entry
    return entry


def page(web_root):
    """(page bytes, linked names) for web_root, or None when it has no
    index.html. The names are posix paths under web/, such as
    "panels/a.css" and "panels/x.js"; empty when there is no panel."""
    if web_root is None:
        return None
    entry = _build(Path(web_root).resolve())
    if entry is None:
        return None
    return entry[1], tuple("%s/%s" % (PANELS, n) for n in entry[2])


def assemble(web_root):
    """The served dashboard page (bytes), or None when web_root has no
    index.html."""
    out = page(web_root)
    return None if out is None else out[0]
