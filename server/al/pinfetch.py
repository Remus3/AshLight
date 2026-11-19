"""PINFETCH: hash-pinned download, verify and safe-extract helpers.

REL-PINFETCH (DEP-06, F-047; research 0052 cut-or-merge): one stdlib module
for pinned downloads, so the calc setup (tools/tc_pin.py), the runtime fetch
and the installer share one host allow-list check, redirect cap, size cap,
hash check, quarantine and archive path guard.

Every caller passes its own host allow-list and User-Agent purpose; nothing
here holds a default host. The running core never imports this module (a
static test in tests/test_pinfetch.py keeps every module under server/al/
outside server/al/install/ from importing it): it serves setup and install
steps only.

Floor: https only, exact host match on every redirect hop (webfetch.check_url),
a truthful AshLight User-Agent, no cookie, no stored session. Nothing from
an archive is imported or executed here.
"""

import hashlib
import os
import shutil
import stat
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from server.al import webfetch

MAX_REDIRECTS = 3
TIMEOUT_S = 60.0
CHUNK = 1024 * 1024


class HashMismatch(Exception):
    """A downloaded or cached archive does not match its pin: refused."""


class UnsafeArchive(Exception):
    """An archive member would land outside its pinned top dir: refused."""


def file_matches(path, sha256, size):
    """True when the file exists with exactly this size and SHA-256."""
    try:
        path = Path(path)
        if path.stat().st_size != size:
            return False
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(CHUNK), b""):
                h.update(block)
        return h.hexdigest() == sha256
    except OSError:
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_stream(url, max_bytes, hosts, purpose, max_redirects=MAX_REDIRECTS,
                timeout=TIMEOUT_S, opener=None):
    """Yield the body of url in chunks. Redirects are followed by hand, each
    hop checked against hosts (https, no userinfo, port 443, exact host);
    more than max_redirects hops raise webfetch.FetchError. The body is cut
    off past max_bytes (HashMismatch). The User-Agent names AshLight and
    `purpose`; no cookie is ever sent. `opener` is for tests only."""
    if not hosts:
        raise webfetch.UrlNotAllowed("no host allow-list given")
    headers = {"User-Agent": webfetch.user_agent(purpose), "Accept": "*/*"}
    opener = opener or urllib.request.build_opener(_NoRedirect())
    for _ in range(max_redirects + 1):
        webfetch.check_url(url, hosts)
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            resp = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in webfetch.REDIRECT_CODES:
                loc = e.headers.get("Location") or ""
                e.close()
                url = urllib.parse.urljoin(url, loc)
                continue
            raise
        with resp:
            got = 0
            while True:
                block = resp.read(CHUNK)
                if not block:
                    return
                got += len(block)
                if got > max_bytes:
                    raise HashMismatch(f"download larger than the pinned {max_bytes} bytes")
                yield block
    raise webfetch.FetchError("too many redirects")


def quarantine(path):
    """Move a bad archive aside as <name>.rejected (replaceable data; kept
    for inspection). Returns the new path."""
    path = Path(path)
    bad = path.with_name(path.name + ".rejected")
    try:
        os.replace(path, bad)
    except OSError:
        pass
    return bad


_quarantine = quarantine


def check_members(zf, top_dir):
    """Raise UnsafeArchive unless every member sits under top_dir/ and is a
    plain file or directory with a relative, forward-slash path."""
    prefix = top_dir + "/"
    for info in zf.infolist():
        n = info.filename
        parts = n.split("/")
        mode = (info.external_attr >> 16) & 0o170000
        if (not n.startswith(prefix) and n != prefix) or "\\" in n or ":" in n \
                or n.startswith("/") or ".." in parts or "\0" in n:
            raise UnsafeArchive(f"unsafe member path: {n!r}")
        if mode == stat.S_IFLNK:
            raise UnsafeArchive(f"symlink member refused: {n!r}")


def extract_safe(archive, top_dir, parent):
    """Extract archive into parent/<top_dir> through a temp dir, after
    check_members; a stale tree there is replaced. Returns the target path.
    Raises UnsafeArchive (nothing extracted) or zipfile.BadZipFile."""
    parent = Path(parent)
    target = parent / top_dir
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{top_dir}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)  # our own half-made extract, replaceable from the archive
    with zipfile.ZipFile(archive) as zf:
        check_members(zf, top_dir)
        zf.extractall(tmp)
    if target.exists():
        shutil.rmtree(target)  # stale tree without a matching marker, replaceable
    os.replace(tmp / top_dir, target)
    shutil.rmtree(tmp, ignore_errors=True)
    return target
