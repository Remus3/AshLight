"""RUN-BUILD-STAMP-CORE (F-027): one build id for health, version and the
Checks report header, read from the .git files or an install's BUILD file.

Every git tree here is hand-made in tmp_path; no git binary runs and the
real core is never started (an ephemeral-port test server only)."""

import http.client
import json
import re
import subprocess
import threading
from pathlib import Path

import pytest

import srcpaths  # noqa: F401 - puts the repo root on sys.path
from server.al import VERSION, buildinfo, diag, webfetch
from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "b" * 48
SHA_A = "0123456789abcdef0123456789abcdef01234567"
SHA_B = "fedcba9876543210fedcba9876543210fedcba98"
BUILD_RE = re.compile(r"^%s\+[0-9a-f]{12}(\.dev)?$" % re.escape(VERSION))


@pytest.fixture(autouse=True)
def _fresh():
    buildinfo.reset()
    yield
    buildinfo.reset()


@pytest.fixture
def no_subprocess(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("buildinfo must not start a process")
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("ascii"))


def test_reads_head_ref_and_packed_refs_without_subprocess(tmp_path, no_subprocess):
    # packed-refs only
    a = tmp_path / "a"
    _write(a / ".git" / "HEAD", "ref: refs/heads/main\n")
    _write(a / ".git" / "packed-refs",
           "# pack-refs with: peeled fully-peeled sorted\n"
           f"{SHA_B} refs/heads/other\n{SHA_A} refs/heads/main\n^{SHA_B}\n")
    assert buildinfo.git_commit(a) == SHA_A[:12]
    # a loose ref wins over packed-refs
    _write(a / ".git" / "refs" / "heads" / "main", SHA_B + "\n")
    assert buildinfo.git_commit(a) == SHA_B[:12]
    # a detached HEAD
    d = tmp_path / "d"
    _write(d / ".git" / "HEAD", SHA_A + "\n")
    assert buildinfo.git_commit(d) == SHA_A[:12]
    # a linked worktree: .git file -> gitdir, commondir -> shared refs
    common = tmp_path / "main" / ".git"
    wtgit = common / "worktrees" / "w1"
    _write(wtgit / "HEAD", "ref: refs/heads/lane\n")
    _write(wtgit / "commondir", "../..\n")
    _write(common / "packed-refs", f"{SHA_B} refs/heads/lane\n")
    w = tmp_path / "w1"
    _write(w / ".git", f"gitdir: {wtgit.as_posix()}\n")
    assert buildinfo.git_commit(w) == SHA_B[:12]
    # a crafted HEAD may not leave the git dir; junk and a missing ref read None
    e = tmp_path / "e"
    _write(e / ".git" / "HEAD", "ref: ../../secret\n")
    _write(e / "secret", SHA_A + "\n")
    assert buildinfo.git_commit(e) is None
    _write(e / ".git" / "HEAD", "ref: refs/heads/none\n")
    assert buildinfo.git_commit(e) is None
    _write(e / ".git" / "HEAD", "not a ref\n")
    assert buildinfo.git_commit(e) is None
    assert buildinfo.git_commit(tmp_path / "nothing") is None
    # the composed string: version + 12 hex, .dev only while hot
    assert buildinfo.build_id(hot=False, root=a) == f"{VERSION}+{SHA_B[:12]}"
    assert buildinfo.build_id(hot=True, root=a) == f"{VERSION}+{SHA_B[:12]}.dev"
    assert buildinfo.compose("1.2.3", None, False) == "1.2.3"
    assert buildinfo.compose("1.2.3", None, True) == "1.2.3+dev"
    # cached per root: a later ref move is not re-read in this process
    _write(a / ".git" / "refs" / "heads" / "main", SHA_A + "\n")
    assert buildinfo.commit(a) == SHA_B[:12]
    # the module source starts no process
    src = (ROOT / "server" / "al" / "buildinfo.py").read_text(encoding="utf-8")
    assert "subprocess" not in src.replace("No subprocess", "")
    assert "import os" not in src


def test_build_file_wins_outside_a_checkout(tmp_path, no_subprocess):
    inst = tmp_path / "home" / "app" / VERSION
    doc = {"version": VERSION, "commit": SHA_A, "created": "2026-11-19T00:00:00Z"}
    _write(inst / "BUILD", json.dumps(doc))
    assert buildinfo.commit(inst) == SHA_A[:12]
    assert buildinfo.build_id(hot=False, root=inst) == f"{VERSION}+{SHA_A[:12]}"
    # a stale BUILD (another version) or a malformed one is ignored
    for bad in (dict(doc, version="9.9.9"), dict(doc, commit="xyz"),
                dict(doc, commit="abc"), ["not", "an", "object"]):
        buildinfo.reset()
        _write(inst / "BUILD", json.dumps(bad))
        assert buildinfo.commit(inst) is None, bad
        assert buildinfo.build_id(hot=False, root=inst) == VERSION
    buildinfo.reset()
    _write(inst / "BUILD", "{ torn")
    assert buildinfo.commit(inst) is None
    # in a checkout the .git files win over a BUILD file
    buildinfo.reset()
    _write(inst / "BUILD", json.dumps(dict(doc, commit=SHA_B)))
    _write(inst / ".git" / "HEAD", SHA_A + "\n")
    assert buildinfo.commit(inst) == SHA_A[:12]


@pytest.fixture
def srv(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def _get(server, path):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    conn.request("GET", path, headers={"Host": f"127.0.0.1:{server.port}",
                                       "X-AL-Token": TOKEN})
    r = conn.getresponse()
    body = r.read()
    conn.close()
    assert r.status == 200, path
    return json.loads(body)


def test_health_version_and_report_show_the_same_string(srv, monkeypatch):
    monkeypatch.setitem(buildinfo._COMMITS, str(buildinfo.paths.repo_root()), SHA_A[:12])
    health = _get(srv, "/api/health")
    version = _get(srv, "/api/version")
    build = health["build"]
    assert build == version["build"] == f"{VERSION}+{SHA_A[:12]}"
    assert health["version"] == version["version"] == VERSION
    srv.core.tick_diag(force=True)
    report = __import__("server.al.plug.report", fromlist=["build"]).build(srv.core)
    header = report.splitlines()[0]
    assert header.startswith(f"AshLight {build} self-check, ")
    # the same string from diag.view directly, and with no commit known
    assert diag.view({}, VERSION)["report"].startswith(f"AshLight {build} self-check")
    buildinfo.reset()
    monkeypatch.setitem(buildinfo._COMMITS, str(buildinfo.paths.repo_root()), None)
    assert _get(srv, "/api/health")["build"] == VERSION
    # the live repo reads as version + 12 hex (this is a checkout)
    buildinfo.reset()
    real = buildinfo.build_id(hot=False)
    assert BUILD_RE.match(real), real


def test_user_agent_never_carries_the_build_id(monkeypatch):
    monkeypatch.setitem(buildinfo._COMMITS, str(buildinfo.paths.repo_root()), SHA_A[:12])
    for hot in (False, True):
        bid = buildinfo.build_id(hot=hot)
        for purpose in ("price check", "rates"):
            for contact in (None, "someone"):
                ua = webfetch.user_agent(purpose, contact)
                assert ua.startswith(f"AshLight/{VERSION} ("), ua
                assert bid not in ua and SHA_A[:12] not in ua
                assert "+" not in ua.split(" ", 1)[0] and ".dev" not in ua
    src = (ROOT / "server" / "al" / "webfetch.py").read_text(encoding="utf-8")
    assert "buildinfo" not in src
