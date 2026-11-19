"""RUN-VERDICTS-CORE (F-062, OPEN-27; decision 0040 amendment 2026-11-18):
the 'Tried in game' verdict store, its token routes GET / POST
/api/verdicts (plug seam, decision 0056) and tools/live_verdicts.py, the
read-back script that drafts the ROADMAP flips.

The server binds an ephemeral port (0) so a running AshLight is never
touched; runtime state goes to tmp_path.
"""

import http.client
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from server.al import http as al_http
from server.al import plug, verdicts
from server.al.core import Core

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import live_verdicts  # noqa: E402

TOKEN = "v" * 48
PATH = "/api/verdicts"
DAY = 1795000000  # a fixed epoch second for stored rows


@pytest.fixture
def srv(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = al_http.serve(core, TOKEN, port=0, web_root=ROOT / "web",
                           tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def req(server, method, path, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    h = {"Host": f"127.0.0.1:{server.port}"}
    h.update(headers or {})
    if isinstance(body, dict):
        body = json.dumps(body)
        h.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, (json.loads(data) if data and r.getheader("Content-Type", "")
                      .startswith("application/json") else data)


def auth():
    return {"X-AL-Token": TOKEN}


def vfile(server):
    return Path(server.core.runtime) / verdicts.FILE_NAME


def test_posted_verdict_appears_in_the_readback(srv):
    status, doc = req(srv, "GET", PATH, auth())
    assert status == 200
    assert [c["id"] for c in doc["checks"]] == list(verdicts.CHECK_IDS)
    assert all(c["verdict"] is None for c in doc["checks"]) and doc["rows"] == []
    status, doc = req(srv, "POST", PATH, auth(),
                      {"check": "TC-BUILDFILE-LIVE", "result": "worked",
                       "note": "  loaded fine, tree matched  "})
    assert status == 200, doc
    assert doc["verdict"]["check"] == "TC-BUILDFILE-LIVE"
    assert doc["verdict"]["note"] == "loaded fine, tree matched"
    status, doc = req(srv, "GET", PATH, auth())
    first = next(c for c in doc["checks"] if c["id"] == "TC-BUILDFILE-LIVE")
    assert first["verdict"]["result"] == "worked"
    # the read-back script sees the same verdict in the file
    text, back = live_verdicts.report(vfile(srv))
    assert "- TC-BUILDFILE-LIVE: worked " in text
    assert "(note: loaded fine, tree matched)" in text
    assert "- LIVE-FILTER: not tried" in text
    assert back["rows"][0]["check"] == "TC-BUILDFILE-LIVE"
    # ... also as a process, by --file, in text and in JSON
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "live_verdicts.py"),
                          "--file", str(vfile(srv))],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "- TC-BUILDFILE-LIVE: worked " in out.stdout
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "live_verdicts.py"),
                          "--file", str(vfile(srv)), "--json"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["flips"][0]["row"] == "RUN-BUILDFILE-LIVE-CLOSE"
    # a new core over the same runtime dir reads the verdict back
    again = verdicts.VerdictStore(vfile(srv))
    assert again.snapshot()["rows"][0]["note"] == "loaded fine, tree matched"


def _row_known(row_id):
    """A ROADMAP row id that is open, or already closed by a done file."""
    text = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    return (f"- [ ] {row_id} (" in text
            or (ROOT / live_verdicts.DONE_DIR / f"{row_id}.md").is_file())


def test_script_drafts_the_matching_roadmap_flip(tmp_path):
    path = tmp_path / verdicts.FILE_NAME
    store = verdicts.VerdictStore(path)
    # nothing tried: no flip, every row waits, no fix row
    d = live_verdicts.drafts(store.rows)
    assert d["flips"] == [] and d["fixes"] == []
    assert {w["row"] for w in d["waiting"]} == set(live_verdicts.ROWS.values())
    # every row the script can flip is a real ROADMAP row (open or done)
    for row_id in set(live_verdicts.ROWS.values()):
        assert _row_known(row_id), row_id
    assert set(live_verdicts.ROWS) == set(verdicts.CHECK_IDS)
    store.add("TC-BUILDFILE-LIVE", "worked", now=DAY)
    store.add("LIVE-SEARCHSTR", "worked", now=DAY + 10)
    store.add("LIVE-FILTER", "worked", now=DAY + 20)
    store.add("LIVE-FILTER-MERGE", "refused", "game said bad filter", now=DAY + 30)
    text, doc = live_verdicts.report(path)
    flips = {f["row"]: f for f in doc["flips"]}
    assert set(flips) == {"RUN-BUILDFILE-LIVE-CLOSE"}
    f = flips["RUN-BUILDFILE-LIVE-CLOSE"]
    day = live_verdicts.day(DAY)
    assert f["file"] == "docs/roadmap/done/RUN-BUILDFILE-LIVE-CLOSE.md"
    assert f["line"] == f" -- done {day} (in-game verdict: TC-BUILDFILE-LIVE worked {day})"
    assert f"- RUN-BUILDFILE-LIVE-CLOSE: {f['file']}:{f['line']}" in text
    waits = {w["row"]: w["checks"] for w in doc["waiting"]}
    assert waits["RUN-VERDICTS-CLOSE"] == ["LIVE-FILTER-MERGE"]
    assert waits["OVL-FPS"] == ["OVL-FPS"]
    # the refusal drafts a fix row in the ROADMAP row format
    [fix] = doc["fixes"]
    assert fix["check"] == "LIVE-FILTER-MERGE"
    assert fix["line"].startswith("- [ ] LIVE-FILTER-MERGE-FIX (build) ")
    assert "Player note: game said bad filter." in fix["line"]
    assert " ACCEPT: " in fix["line"] and " ZERO-CLICK: " in fix["line"]
    assert fix["line"] in text
    # the newest verdict wins: a later worked try flips the shared row
    store.add("LIVE-FILTER-MERGE", "worked", now=DAY + 86400)
    _, doc = live_verdicts.report(path)
    flips = {f["row"]: f for f in doc["flips"]}
    assert set(flips) == {"RUN-BUILDFILE-LIVE-CLOSE", "RUN-VERDICTS-CLOSE"}
    assert flips["RUN-VERDICTS-CLOSE"]["line"].startswith(
        f" -- done {live_verdicts.day(DAY + 86400)} (in-game verdict: LIVE-SEARCHSTR worked")
    assert doc["fixes"] == []
    # the script writes nothing: the only files are the store's own
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        verdicts.FILE_NAME, verdicts.FILE_NAME + ".bak"]


def test_unknown_check_id_is_refused(srv, tmp_path):
    h = auth()
    bad = [
        {"check": "ZZQ-NOT-A-CHECK", "result": "worked"},
        {"check": "tc-buildfile-live", "result": "worked"},
        {"check": None, "result": "worked"},
        {"result": "worked"},
        {"check": "OVL-FPS", "result": "maybe"},
        {"check": "OVL-FPS", "result": "worked", "note": "x" * (verdicts.MAX_NOTE + 1)},
        {"check": "OVL-FPS", "result": "worked", "note": "caf" + chr(0xe9)},
        {"check": "OVL-FPS", "result": "worked", "note": "two\nlines"},
        {"check": "OVL-FPS", "result": "worked", "note": 5},
    ]
    for body in bad:
        status, doc = req(srv, "POST", PATH, h, body)
        assert status == 400, body
        assert isinstance(doc["error"], str) and doc["error"], body
    status, doc = req(srv, "POST", PATH, h, bad[0])
    assert doc == {"error": "unknown check id"}
    # nothing was recorded or written
    assert not vfile(srv).exists()
    assert req(srv, "GET", PATH, h)[1]["rows"] == []
    # a JSON body is required and capped like every small POST
    assert req(srv, "POST", PATH, {**h, "Content-Type": "text/plain"}, b"x")[0] == 415
    assert req(srv, "POST", PATH, {**h, "Content-Type": "application/json"},
               b"[" + b" " * 4096)[0] == 413
    # the store refuses the same way, and a hand-edited row is dropped on load
    store = verdicts.VerdictStore(tmp_path / verdicts.FILE_NAME)
    with pytest.raises(verdicts.VerdictError):
        store.add("ZZQ-NOT-A-CHECK", "worked")
    assert store.rows == []
    (tmp_path / "hand.json").write_text(json.dumps({"schema": 1, "rows": [
        {"check": "ZZQ", "result": "worked", "note": "", "at": DAY},
        {"check": "OVL-FPS", "result": "worked", "note": "", "at": True},
        {"check": "OVL-FPS", "result": "refused", "note": "ok", "at": DAY}]}),
        encoding="ascii")
    assert verdicts.load(tmp_path / "hand.json") == [
        {"check": "OVL-FPS", "result": "refused", "note": "ok", "at": DAY}]


def test_file_stays_bounded_and_ascii(tmp_path):
    path = tmp_path / verdicts.FILE_NAME
    store = verdicts.VerdictStore(path)
    for i in range(verdicts.MAX_ROWS * 3):
        cid = verdicts.CHECK_IDS[i % len(verdicts.CHECK_IDS)]
        store.add(cid, verdicts.RESULTS[i % 2], "n" * verdicts.MAX_NOTE, now=DAY + i)
    raw = path.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert len(raw) < verdicts.MAX_BYTES
    doc = json.loads(raw)
    assert doc["schema"] == verdicts.SCHEMA
    assert len(doc["rows"]) == verdicts.MAX_ROWS
    # the newest rows are kept, oldest first in the file
    assert [r["at"] for r in doc["rows"]] == list(
        range(DAY + verdicts.MAX_ROWS * 2, DAY + verdicts.MAX_ROWS * 3))
    assert store.snapshot()["rows"][0]["at"] == DAY + verdicts.MAX_ROWS * 3 - 1
    # one .bak of the last good copy; a broken main file falls back to it
    bak = path.with_name(path.name + ".bak")
    assert bak.read_bytes() == raw
    path.write_bytes(b"{half")
    assert len(verdicts.load(path)) == verdicts.MAX_ROWS
    # a hand-grown file is cut to the bound on load, an oversized one ignored
    path.write_text(json.dumps({"schema": 1, "rows": [
        {"check": "OVL-FPS", "result": "worked", "note": "", "at": DAY + i}
        for i in range(500)]}), encoding="ascii")
    assert len(verdicts.load(path)) == verdicts.MAX_ROWS
    path.write_bytes(b'{"rows": [' + b" " * verdicts.MAX_BYTES + b"]}")
    bak.unlink()
    assert verdicts.load(path) == []


def test_route_needs_the_token(srv):
    assert ("GET", PATH) in plug.all_routes() and ("POST", PATH) in plug.all_routes()
    body = {"check": "OVL-FPS", "result": "worked"}
    for method in ("GET", "POST"):
        for h in ({}, {"X-AL-Token": "wrong"}, {"Authorization": "Bearer wrong"}):
            status, doc = req(srv, method, PATH, h, body if method == "POST" else None)
            assert status == 401, (method, h)
            assert doc == {"error": "token required"}
        # ?token= opens only /events, never an /api route
        status, _ = req(srv, method, f"{PATH}?token={TOKEN}", {},
                        body if method == "POST" else None)
        assert status == 401, method
    # cross-site and a foreign origin are refused before the token
    assert req(srv, "POST", PATH, {**auth(), "Sec-Fetch-Site": "cross-site"}, body)[0] == 403
    assert req(srv, "POST", PATH, {**auth(), "Origin": "http://evil.example"}, body)[0] == 403
    assert not vfile(srv).exists()
    # with the token (header or bearer) it records
    assert req(srv, "POST", PATH, auth(), body)[0] == 200
    status, doc = req(srv, "GET", PATH, {"Authorization": "Bearer " + TOKEN})
    assert status == 200 and doc["rows"][0]["check"] == "OVL-FPS"
    # other verbs stay refused
    assert req(srv, "PUT", PATH, auth(), body)[0] == 405
    assert req(srv, "DELETE", PATH, auth())[0] == 405
