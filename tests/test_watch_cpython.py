"""DEP-19 (CPython pin watch; decisions 0063, 0069): the 'cpython' watcher
source. Every read is an injected fetch or transport over fixtures in
tmp_path: no request."""

import datetime as _dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import upstream_watch as uw  # noqa: E402
import watch_file  # noqa: E402
import watch_gate  # noqa: E402
import watch_rows  # noqa: E402
from watch_sources import cpython  # noqa: E402

DAY = 24 * 3600
NOW = _dt.datetime(2026, 11, 21, 12, 0).timestamp()
TODAY = "2026-11-21"
PIN = "3.14.10"
EMBED = "Windows embeddable package (64-bit)"


def _root(tmp_path, web_data=True, pin=PIN):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "local.json").write_text(
        json.dumps({"web_data": web_data}), encoding="ascii")
    pins = {"schema": 1, "runtimes": {"python": {
        "version": pin, "arch": "amd64", "file": f"python-{pin}-embed-amd64.zip",
        "url": f"https://www.python.org/ftp/python/{pin}/python-{pin}-embed-amd64.zip",
        "sha256": "0" * 64, "size": 1, "licence": "PSF-2.0"}}}
    (root / "config" / "runtime_pins.json").write_text(json.dumps(pins), encoding="ascii")
    return root


def _release(ver, published=True, pre=False):
    return {"name": f"Python {ver}", "slug": "python-" + ver.replace(".", ""),
            "version": 3, "is_published": published, "pre_release": pre,
            "release_date": "2026-11-20T00:00:00Z",
            "resource_uri": "https://www.python.org/api/v2/downloads/release/1/"}


def _file(ver):
    return {"name": EMBED, "os": "https://www.python.org/api/v2/downloads/os/1/",
            "url": f"https://www.python.org/ftp/python/{ver}/python-{ver}-embed-amd64.zip"}


def _releases(*vers):
    rows = [_release(v) for v in vers]
    rows += [_release("3.15.0a2", pre=True), _release("3.13.12"),
             _release("3.14.12", published=False)]
    return rows


class Fetch:
    """The frame-style fetch(url, etag=None) -> (status, headers, body)."""

    def __init__(self, releases, files, status=200):
        self.docs = {cpython.RELEASES_URL: releases, cpython.FILES_URL: files}
        self.status = status
        self.calls = []

    def __call__(self, url, etag=None):
        self.calls.append(url)
        return self.status, {}, json.dumps(self.docs[url]).encode("utf-8")


class Transport:
    """webfetch's transport fetch(method, url, headers, body) for the frame."""

    def __init__(self, releases, files):
        self.inner = Fetch(releases, files)
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        return self.inner(url)


def _sources(folder):
    folder.mkdir(parents=True)
    shutil.copyfile(ROOT / "tools" / "watch_sources" / "cpython.py", folder / "cpython.py")
    return folder


def _run(state, fetch, root, ctx=None):
    view = json.loads(json.dumps(state))
    found = cpython.check(view, NOW, fetch, dict(ctx or {}, root=root))
    state["data"] = view.get("data", {})
    return found


def test_cpython_newer_patch_files_one_row(tmp_path):
    root = _root(tmp_path)
    fetch = Fetch(_releases("3.14.9", PIN, "3.14.11"),
                  [_file("3.14.9"), _file(PIN), _file("3.14.11"), _file("3.13.12")])
    state = {}
    found = _run(state, fetch, root)
    assert [(f["kind"], f["key"]) for f in found] == [("cpythonbump", "3.14.11")]
    assert found[0]["tokens"] == {"MAJ": "3", "MIN": "14", "PAT": "11",
                                  "version": "3.14.11", "pin": PIN}
    assert fetch.calls == [cpython.RELEASES_URL, cpython.FILES_URL]
    assert state["data"] == {"pin": PIN, "newest": "3.14.11", "zip": "3.14.11"}
    table = watch_rows.load(ROOT)
    rid, text = watch_rows.render(table, "cpythonbump", found[0]["tokens"], TODAY)
    assert rid == "CPYTHON-3-14-11"
    assert text.startswith("- [ ] CPYTHON-3-14-11 (data) CPython 3.14.11 ")
    assert "BLOCKED" not in text
    assert text.endswith(f"filed {TODAY}.")
    # the frame: one row filed, User-Agent truthful, no cookie, the pin unwritten
    pins_before = (root / "config" / "runtime_pins.json").read_bytes()
    transport = Transport(fetch.docs[cpython.RELEASES_URL], fetch.docs[cpython.FILES_URL])
    d = _sources(tmp_path / "only")
    srcs = uw.discover(d)
    assert [s["name"] for s in srcs] == ["cpython"] and uw.is_network(srcs[0])
    for url in cpython.SOURCE["urls"]:
        watch_gate.check_url(srcs[0], url)
    uw.run_due(root, NOW, fetch=transport, directory=d, ctx={"root": root})
    assert [(f["source"], f["kind"], f["key"]) for f in uw.pending(root)] == [
        ("cpython", "cpythonbump", "3.14.11")]
    assert len(transport.calls) == 2
    for method, _url, headers in transport.calls:
        assert method == "GET"
        assert "AshLight" in headers["User-Agent"] and "cpython watch" in headers["User-Agent"]
        assert "Cookie" not in headers
    assert (root / "config" / "runtime_pins.json").read_bytes() == pins_before


def test_cpython_same_listing_files_nothing(tmp_path):
    root = _root(tmp_path)
    # a listing whose newest patch of the line is the pin: one request, nothing
    quiet = Fetch(_releases("3.14.9", PIN), [_file(PIN)])
    assert _run({}, quiet, root) == []
    assert quiet.calls == [cpython.RELEASES_URL]
    # the same newer listing on the next day queues nothing new
    transport = Transport(_releases(PIN, "3.14.11"), [_file(PIN), _file("3.14.11")])
    d = _sources(tmp_path / "only")
    uw.run_due(root, NOW, fetch=transport, directory=d, ctx={"root": root})
    lines = uw.run_due(root, NOW + DAY, fetch=transport, directory=d, ctx={"root": root})
    assert len(uw.pending(root)) == 1
    assert not any("new finding" in ln for ln in lines)
    # inside the 24 h cadence the source is not run at all
    calls = len(transport.calls)
    uw.run_due(root, NOW + DAY + 3600, fetch=transport, directory=d, ctx={"root": root})
    assert len(transport.calls) == calls


def test_cpython_without_embeddable_zip_logs_one_line(tmp_path):
    root = _root(tmp_path)
    fetch = Fetch(_releases(PIN, "3.14.11"), [_file(PIN)])
    found = _run({}, fetch, root)
    assert [(f["kind"], f["key"]) for f in found] == [("cpythonnozip", "nozip-3.14.11")]
    assert found[0]["tokens"] == {"version": "3.14.11", "pin": PIN}
    table = watch_rows.load(ROOT)
    assert table["cpythonnozip"]["act"] == "note"
    # the frame: exactly one tick line, once; the note is never filed as a row
    transport = Transport(_releases(PIN, "3.14.11"), [_file(PIN)])
    d = _sources(tmp_path / "only")
    lines = uw.run_due(root, NOW, fetch=transport, directory=d, ctx={"root": root})
    assert len(lines) == 1 and lines[0].startswith("watch cpython:"), lines
    again = uw.run_due(root, NOW + DAY, fetch=transport, directory=d, ctx={"root": root})
    assert again == []
    git_calls = []
    watch_file.file_pending(root, NOW + DAY, lambda *a, **k: git_calls.append(a), None)
    assert not any("commit" in call[0] for call in git_calls), git_calls
    assert not (root / "docs" / "roadmap").exists()
    # a moved endpoint fails with one line naming the URL, never guessed
    moved = Fetch(_releases(PIN), [], status=404)
    state = {"seen": [], "fails": 0}
    try:
        cpython.check(state, NOW, moved, {"root": root})
    except uw.SourceError as exc:
        assert exc.cause == "status" and cpython.RELEASES_URL in str(exc)
    else:
        raise AssertionError("a 404 must fail the run")


def test_cpython_makes_no_request_while_halted(tmp_path):
    root = _root(tmp_path)
    halt = root / "ops" / "loop" / "control" / "HALT"
    halt.parent.mkdir(parents=True)
    halt.write_text("halt\n", encoding="ascii")
    fetch = Fetch(_releases(PIN, "3.14.11"), [_file("3.14.11")])
    assert _run({}, fetch, root) == []
    assert fetch.calls == []
    transport = Transport(_releases(PIN, "3.14.11"), [_file("3.14.11")])
    d = _sources(tmp_path / "only")
    uw.run_due(root, NOW, halted=True, fetch=transport, directory=d, ctx={"root": root})
    assert transport.calls == [] and uw.pending(root) == []
    # ctx["halted"] alone also stops it; with HALT gone the next due run reads
    halt.unlink()
    assert _run({}, fetch, root, ctx={"halted": True}) == [] and fetch.calls == []
    uw.run_due(root, NOW + DAY, fetch=transport, directory=d, ctx={"root": root})
    assert len(transport.calls) == 2
    assert [f["key"] for f in uw.pending(root)] == ["3.14.11"]
    # no root and no live flag: nothing read, nothing requested
    assert cpython.check({}, NOW, fetch, {}) == [] and fetch.calls == []
