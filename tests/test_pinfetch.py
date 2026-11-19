"""REL-PINFETCH: the shared hash-pinned fetch / verify / extract helpers.

Host allow-list refusal, redirect cap, size cap, hash mismatch quarantine,
unsafe archive member refusal, the User-Agent purpose passed through, and a
static check that the running core never imports the module. No network:
every opener is a fake."""

import ast
import email.message
import hashlib
import io
import stat
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import pinfetch, webfetch  # noqa: E402

HOSTS = ("github.com", "codeload.github.com")


class _Resp:
    def __init__(self, body, chunk=4):
        self._buf = io.BytesIO(body)
        self._chunk = chunk

    def read(self, n):
        return self._buf.read(min(n, self._chunk))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    """Answers each open() with the next scripted step: a bytes body, or a
    (code, location) redirect raised as HTTPError."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.requests = []

    def open(self, req, timeout=None):
        self.requests.append(req)
        step = self.steps.pop(0) if len(self.steps) > 1 else self.steps[0]
        if isinstance(step, bytes):
            return _Resp(step)
        code, loc = step
        hdrs = email.message.Message()
        hdrs["Location"] = loc
        raise urllib.error.HTTPError(req.full_url, code, "redirect", hdrs, io.BytesIO(b""))


def _stream(url, max_bytes, opener, hosts=HOSTS, purpose="test: pinned fetch", **kw):
    return b"".join(pinfetch.http_stream(url, max_bytes, hosts, purpose,
                                         opener=opener, **kw))


# --- host allow-list --------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://example.com/x.zip",
    "http://github.com/x.zip",
    "https://user" + chr(64) + "github.com/x.zip",  # userinfo
    "https://github.com:8443/x.zip",
    "https://github.com.evil.example/x.zip",
])
def test_host_off_the_allowlist_is_refused_before_any_request(url):
    op = _Opener([b"never"])
    with pytest.raises(webfetch.UrlNotAllowed):
        _stream(url, 10, op)
    assert op.requests == []


def test_no_host_list_refuses():
    with pytest.raises(webfetch.UrlNotAllowed):
        _stream("https://github.com/x.zip", 10, _Opener([b"x"]), hosts=())


def test_redirect_to_an_unlisted_host_is_refused():
    op = _Opener([(302, "https://example.com/evil.zip"), b"evil"])
    with pytest.raises(webfetch.UrlNotAllowed):
        _stream("https://github.com/x.zip", 10, op)
    assert len(op.requests) == 1


def test_redirect_within_the_list_is_followed():
    op = _Opener([(302, "https://codeload.github.com/x.zip"), b"payload"])
    assert _stream("https://github.com/x.zip", 100, op) == b"payload"
    assert op.requests[1].full_url == "https://codeload.github.com/x.zip"


# --- redirect cap -----------------------------------------------------------

@pytest.mark.parametrize("cap", [0, 1, pinfetch.MAX_REDIRECTS])
def test_redirect_cap(cap):
    op = _Opener([(301, "https://github.com/again.zip")])
    with pytest.raises(webfetch.FetchError, match="too many redirects"):
        _stream("https://github.com/x.zip", 10, op, max_redirects=cap)
    assert len(op.requests) == cap + 1


def test_default_redirect_cap_is_three():
    assert pinfetch.MAX_REDIRECTS == 3


# --- size cap ---------------------------------------------------------------

def test_body_past_max_bytes_is_cut_off():
    op = _Opener([b"0123456789ABCDEF"])
    got = []
    with pytest.raises(pinfetch.HashMismatch, match="larger than the pinned 10"):
        for block in pinfetch.http_stream("https://github.com/x.zip", 10, HOSTS, "p",
                                          opener=op):
            got.append(block)
    assert sum(len(b) for b in got) <= 10


def test_body_at_max_bytes_passes():
    assert _stream("https://github.com/x.zip", 10, _Opener([b"0123456789"])) == b"0123456789"


# --- User-Agent purpose -----------------------------------------------------

def test_user_agent_purpose_passed_through_and_no_cookie():
    op = _Opener([b"ok"])
    _stream("https://github.com/x.zip", 10, op, purpose="install: runtime download")
    req = op.requests[0]
    ua = req.get_header("User-agent")
    assert ua == webfetch.user_agent("install: runtime download")
    assert "install: runtime download" in ua and ua.startswith(webfetch.NAME + "/")
    assert req.get_header("Cookie") is None
    assert req.get_method() == "GET"


# --- hash check and quarantine ----------------------------------------------

def test_file_matches_and_mismatch_quarantine(tmp_path):
    blob = b"pinned archive bytes"
    sha = hashlib.sha256(blob).hexdigest()
    f = tmp_path / "a.zip"
    f.write_bytes(blob)
    assert pinfetch.file_matches(f, sha, len(blob))
    assert not pinfetch.file_matches(f, sha, len(blob) + 1)
    assert not pinfetch.file_matches(f, "0" * 64, len(blob))
    assert not pinfetch.file_matches(tmp_path / "missing.zip", sha, len(blob))
    bad = pinfetch.quarantine(f)
    assert bad == tmp_path / "a.zip.rejected"
    assert not f.exists() and bad.read_bytes() == blob
    assert pinfetch._quarantine is pinfetch.quarantine


def test_quarantine_of_a_missing_file_is_quiet(tmp_path):
    assert pinfetch.quarantine(tmp_path / "gone.zip").name == "gone.zip.rejected"


# --- archive path guard -----------------------------------------------------

def _zip_bytes(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for info, data in entries:
            zf.writestr(info, data)
    return buf.getvalue()


def _write_zip(tmp_path, entries):
    p = tmp_path / "in.zip"
    p.write_bytes(_zip_bytes(entries))
    return p


def test_safe_archive_extracts_under_its_top_dir(tmp_path):
    arc = _write_zip(tmp_path, [("top/", ""), ("top/a.txt", "a"), ("top/d/b.txt", "b")])
    parent = tmp_path / "out"
    (parent / "top").mkdir(parents=True)
    (parent / "top" / "stale.txt").write_text("old")
    target = pinfetch.extract_safe(arc, "top", parent)
    assert target == parent / "top"
    assert (target / "a.txt").read_text() == "a"
    assert (target / "d" / "b.txt").read_text() == "b"
    assert not (target / "stale.txt").exists()
    assert not (parent / ".top.tmp").exists()


@pytest.mark.parametrize("name", [
    "other/x.txt", "top/../x.txt", "/top/x.txt", "top/c:x.txt", "../top/x.txt",
    "top/d/../../x.txt", "topx/a.txt",
])
def test_unsafe_member_path_is_refused(tmp_path, name):
    arc = _write_zip(tmp_path, [("top/ok.txt", "ok"), (name, "evil")])
    with pytest.raises(pinfetch.UnsafeArchive):
        pinfetch.extract_safe(arc, "top", tmp_path / "out")
    assert not (tmp_path / "out" / "top").exists()


def test_symlink_member_is_refused(tmp_path):
    info = zipfile.ZipInfo("top/link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    arc = _write_zip(tmp_path, [("top/ok.txt", "ok"), (info, "/etc/passwd")])
    with pytest.raises(pinfetch.UnsafeArchive, match="symlink"):
        pinfetch.extract_safe(arc, "top", tmp_path / "out")
    assert not (tmp_path / "out" / "top").exists()


# --- tools/tc_pin.py keeps its names ----------------------------------------

def test_tc_pin_reexports_the_shared_helpers():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import tc_pin
    finally:
        sys.path.remove(str(ROOT / "tools"))
    for name in ("HashMismatch", "UnsafeArchive", "_NoRedirect", "check_members",
                 "file_matches"):
        assert getattr(tc_pin, name) is getattr(pinfetch, name), name
    assert tc_pin.MAX_REDIRECTS == pinfetch.MAX_REDIRECTS
    assert tc_pin.CHUNK == pinfetch.CHUNK


# --- the running core never imports it --------------------------------------

def _imports_pinfetch(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[-1] == "pinfetch" or a.name.endswith(".pinfetch")
                   for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".")[-1] == "pinfetch":
                return True
            if any(a.name == "pinfetch" for a in node.names):
                return True
        elif isinstance(node, ast.Call):
            f = node.func
            fname = getattr(f, "attr", None) or getattr(f, "id", None)
            if fname in ("import_module", "__import__") and any(
                    isinstance(a, ast.Constant) and isinstance(a.value, str)
                    and "pinfetch" in a.value for a in node.args):
                return True
    return False


def test_no_core_module_imports_pinfetch():
    base = ROOT / "server" / "al"
    offenders = []
    for p in sorted(base.rglob("*.py")):
        rel = p.relative_to(base).as_posix()
        if rel == "pinfetch.py" or rel.startswith("install/"):
            continue
        if _imports_pinfetch(ast.parse(p.read_text(encoding="utf-8"), str(p))):
            offenders.append(rel)
    assert offenders == [], offenders


def test_the_import_scan_sees_each_import_form():
    for src in ("import server.al.pinfetch\n", "from server.al import pinfetch\n",
                "from server.al.pinfetch import http_stream\n", "from . import pinfetch\n",
                "from .pinfetch import quarantine\n",
                "importlib.import_module('server.al.pinfetch')\n"):
        assert _imports_pinfetch(ast.parse(src)), src
    assert not _imports_pinfetch(ast.parse("from server.al import webfetch\n"))
