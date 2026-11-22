"""SEC-LOG-PATH-FIELD (finding F-098): a typed Client.txt path on the
dashboard, sent through the existing consent API.

When no Client.txt is found (the Checks row "log" fails), Settings,
Reading and web data shows "Can't find Client.txt?" (web/logpath.js). Use
posts POST /api/consent {"consent": true, "path": ...}: the player's own
opt-in for that one file. A good path starts the tailer, a bad one gets the
existing 400 text (which the page turns into its own what-to-do line), and the request
adds no registry read, no libraryfolders.vdf read and no directory
listing: only the typed path is used.

No socket and no network: requests run through http.Handler on in-memory
streams. Every log is a file under tmp_path; the live Client.txt is never
read.
"""

import glob
import io
import json
import os
import pathlib
import threading
import time
from html.parser import HTMLParser

import pytest

import srcpaths
from server.al import http as al_http
from server.al import logfile
from server.al.core import Core

TOKEN = "t" * 48
HOST = "127.0.0.1:8961"
WAIT_S = 5.0
BAD_TEXT = "path must be a local Client.txt or the folder holding it"


class FakeServer:
    """What Handler reads of its server, with no socket bound."""

    def __init__(self, core):
        self.core = core
        self.token = TOKEN
        self.allowed_hosts = {HOST, "localhost:8961"}
        self.allowed_origins = {f"http://{h}" for h in self.allowed_hosts}
        self.events_tap = False
        self.stopping = threading.Event()
        self.sse_slots = threading.BoundedSemaphore(al_http.MAX_SSE_CLIENTS)


class FakeSocket:
    """The two calls the Handler's body drain makes of its socket."""

    def gettimeout(self):
        return None

    def settimeout(self, value):
        pass


def post(core, body):
    """POST /api/consent with the token through the real Handler; returns
    (status, doc)."""
    data = json.dumps(body).encode("ascii")
    lines = ["POST /api/consent HTTP/1.1", f"Host: {HOST}", "Connection: close",
             "Content-Type: application/json", f"Content-Length: {len(data)}",
             f"X-AL-Token: {TOKEN}"]
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + data

    class H(al_http.Handler):
        def setup(self):
            self.connection = FakeSocket()
            self.rfile = io.BytesIO(raw)
            self.wfile = io.BytesIO()

        def finish(self):
            H.out = self.wfile.getvalue()

    H(None, ("127.0.0.1", 50000), FakeServer(core))
    head, _, out = H.out.partition(b"\r\n\r\n")
    return int(head.split(b" ", 2)[1]), json.loads(out or b"{}")


def game_log(tmp_path):
    """A standalone-style game folder outside any Steam library."""
    log = tmp_path / "Games" / "PoE2" / "logs" / "Client.txt"
    log.parent.mkdir(parents=True)
    log.write_bytes(b"")
    return log


@pytest.fixture
def core(tmp_path):
    """A core with no log found: a runtime dir, no log path, no consent."""
    c = Core(runtime=tmp_path / "rt", poll_s=0.02)
    yield c
    c.close()


def wait_for(cond):
    end = time.monotonic() + WAIT_S
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_posted_path_starts_the_tailer(core, tmp_path):
    assert core.discover is False and core.log_path is None and core.tailer is None
    log = game_log(tmp_path)
    status, doc = post(core, {"consent": True, "path": str(log.parent.parent)})
    assert status == 200, doc
    assert doc["consent"]["consented"] is True
    assert doc["state"]["tailer"]["consented"] is True
    assert doc["state"]["tailer"]["path"] == str(log)
    assert core.log_path == log
    assert core.tailer is not None
    assert wait_for(lambda: core.state.snapshot()["tailer"].get("reading") is True)


def test_bad_path_shows_the_existing_error(core, tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text("x\n", encoding="ascii")
    for bad in ("logs\\Client.txt", "logs/Client.txt", str(other),
                "\\\\server\\share\\Client.txt", str(tmp_path / ".." / "Client.txt")):
        status, doc = post(core, {"consent": True, "path": bad})
        assert status == 400, bad
        assert doc == {"error": BAD_TEXT}, bad
    assert core.tailer is None and core.log_path is None
    assert not core.consented()
    # the page maps that 400 to its own sentence (design 0001 P3: what
    # happened and what to do, no HTTP code in the line)
    src = srcpaths.read("logpath.js")
    assert '"HTTP 400"' in src and "? BAD_PATH" in src
    assert "AshLight can't use that path. Type the full path to Client.txt" in src


def test_no_registry_vdf_or_directory_listing_call_is_added(core, tmp_path, monkeypatch):
    calls = []

    def spy(name, real=None):
        def wrapper(*a, **k):
            calls.append(name)
            if real is None:
                raise AssertionError(name + " called")
            return real(*a, **k)
        return wrapper

    for name in ("_steam_roots_from_registry", "_steam_roots_from_env",
                 "steam_libraries", "parse_libraryfolders"):
        monkeypatch.setattr(logfile, name, spy("logfile." + name))
    try:
        import winreg
    except ImportError:
        winreg = None
    if winreg is not None:
        for name in ("OpenKey", "OpenKeyEx", "QueryValueEx", "EnumKey", "EnumValue"):
            monkeypatch.setattr(winreg, name, spy("winreg." + name))
    for name in ("listdir", "scandir", "walk"):
        monkeypatch.setattr(os, name, spy("os." + name, getattr(os, name)))
    for name in ("iterdir", "glob", "rglob"):
        monkeypatch.setattr(pathlib.Path, name, spy("Path." + name, getattr(pathlib.Path, name)))
    for name in ("glob", "iglob"):
        monkeypatch.setattr(glob, name, spy("glob." + name, getattr(glob, name)))
    real_read_text = pathlib.Path.read_text

    def read_text(self, *a, **k):
        if self.name.lower() == "libraryfolders.vdf":
            calls.append("libraryfolders.vdf")
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_text", read_text)

    log = game_log(tmp_path)
    status, doc = post(core, {"consent": True, "path": str(log)})
    assert status == 200, doc
    assert wait_for(lambda: core.state.snapshot()["tailer"].get("reading") is True)
    core.ensure_tailing()
    assert calls == []


class _Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.found = {}
        self.labels = {}
        self.inline_scripts = 0
        self.handlers = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and not a.get("src"):
            self.inline_scripts += 1
        self.handlers += [k for k in a if k.startswith("on")]
        if a.get("id"):
            self.found[a["id"]] = (tag, a, [s for s in self.stack])
        if tag == "label" and a.get("for"):
            self.labels[a["for"]] = True
        if tag not in ("input", "img", "br", "meta", "link", "hr"):
            self.stack.append((tag, a.get("id")))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def test_field_markup_has_a_label_and_no_inline_script():
    p = _Markup()
    p.feed(srcpaths.index_html())
    assert p.inline_scripts == 0
    assert p.handlers == []
    tag, attrs, parents = p.found["logpath-form"]
    assert tag == "form" and "hidden" in attrs
    assert ("section", "set-reading") in parents
    tag, attrs, parents = p.found["logpath-in"]
    assert tag == "input" and attrs.get("type") == "text"
    assert attrs.get("maxlength") == "1024"
    assert ("form", "logpath-form") in parents
    assert p.labels.get("logpath-in") is True
    tag, attrs, parents = p.found["logpath-use"]
    assert tag == "button" and attrs.get("type") == "submit"
    assert ("form", "logpath-form") in parents
    # the answer line sits after the form (a Saved line stays when the form
    # hides); not a live region (page cap, plan 03 4.1.3), so the field and
    # Use both point at it
    tag, said, parents = p.found["logpath-said"]
    assert ("form", "logpath-form") not in parents
    assert ("section", "set-reading") in parents
    assert "aria-live" not in said and "role" not in said
    for ctl in ("logpath-in", "logpath-use"):
        assert "logpath-said" in p.found[ctl][1].get("aria-describedby", "").split(), ctl
    assert '<script src="/web/logpath.js" defer></script>' in srcpaths.index_html()
