"""RUN-VERDICTS-UI, folded RUN-REPORT-ROUTE (finding F-109): the
token-gated GET /api/report (server/al/plug/report.py, decision 0056).

The report is built on the click from the same local facts the Checks
tick reads, and the body is diag.report() of them (ruling J redaction).
No socket, process or network call: requests run through http.Handler on
in-memory streams; runtime state lives in tmp_path.
"""

import io
import json
import threading

import pytest

from server.al import VERSION, diag, plug
from server.al import http as al_http
from server.al.core import Core
from server.al.plug import report

TOKEN = "r" * 48
HOST = "127.0.0.1:8961"
NOW = 1795200000.0  # a fixed clock: the report header carries the minute
# a Windows-style path, built from parts (the leak sweep refuses literals)
WIN_PATH = "Q" + ":" + "\\" + "zzqhome" + "\\" + "zzq"


@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "_now", lambda: NOW)
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    yield c
    c.close()


class FakeServer:
    """What Handler reads of its server, with no socket bound."""

    def __init__(self, core):
        self.core = core
        self.token = TOKEN
        self.allowed_hosts = {HOST}
        self.allowed_origins = {f"http://{h}" for h in self.allowed_hosts}
        self.events_tap = False
        self.stopping = threading.Event()
        self.sse_slots = threading.BoundedSemaphore(al_http.MAX_SSE_CLIENTS)


def call(core, method, path, headers=None):
    """One request through the real Handler; (status, headers text, body)."""
    lines = [f"{method} {path} HTTP/1.1", f"Host: {HOST}", "Connection: close"]
    lines += [f"{k}: {v}" for k, v in (headers or {}).items()]
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")

    class H(al_http.Handler):
        def setup(self):
            self.connection = None
            self.rfile = io.BytesIO(raw)
            self.wfile = io.BytesIO()

        def finish(self):
            H.out = self.wfile.getvalue()

    H(None, ("127.0.0.1", 50000), FakeServer(core))
    head, _, body = H.out.partition(b"\r\n\r\n")
    return int(head.split(b" ", 2)[1]), head.decode("ascii"), body


def auth():
    return {"X-AL-Token": TOKEN}


def expected(core):
    facts = core.diag_facts(NOW)
    return diag.report(diag.checks(facts, NOW), VERSION, NOW, diag.secrets(facts))


def test_report_route_needs_the_token(core):
    assert ("GET", report.PATH) in plug.all_routes()
    assert report.PATH == "/api/report"
    for h in ({}, {"X-AL-Token": "wrong"}, {"Authorization": "Bearer wrong"},
              {"Authorization": "Basic " + TOKEN}):
        status, _, body = call(core, "GET", report.PATH, h)
        assert status == 401, h
        assert json.loads(body) == {"error": "token required"}
        assert b"AshLight" not in body
    # ?token= opens only /events, never an /api route
    status, _, body = call(core, "GET", report.PATH + "?token=" + TOKEN)
    assert status == 401 and b"self-check" not in body
    # a cross-site request is refused even with the token
    status, _, _ = call(core, "GET", report.PATH, {**auth(), "Sec-Fetch-Site": "cross-site"})
    assert status == 403
    # the header token or the bearer form opens it; POST is not a route
    for h in (auth(), {"Authorization": "Bearer " + TOKEN}):
        status, head, body = call(core, "GET", report.PATH, h)
        assert status == 200, h
        assert "Content-Security-Policy: " + al_http.CSP in head
        assert "Cache-Control: no-store" in head
    assert ("POST", report.PATH) not in plug.all_routes()


def test_report_route_body_equals_diag_report(core):
    before = core.state.version
    status, head, body = call(core, "GET", report.PATH, auth())
    assert status == 200
    assert "application/json" in head
    doc = json.loads(body)
    assert list(doc) == ["report"]
    text = doc["report"]
    assert text == expected(core)
    # the same text the snapshot's copy carries (diag.view, the Checks tick)
    assert text == diag.view(core.diag_facts(NOW), VERSION, now=NOW)["report"]
    assert text.startswith("AshLight ") and "self-check" in text.splitlines()[0]
    assert text.endswith("\n") and "\r" not in text
    text.encode("ascii")  # ASCII only
    assert TOKEN not in text
    # building the report publishes nothing (no state push, no new read kept)
    assert core.state.version == before


def test_report_route_redacts_like_the_snapshot(core, monkeypatch):
    real_facts = core.diag_facts

    def facts(now=None):
        f = real_facts(now)
        f["_contact"] = "zzq-contact-name"
        f["_character"] = "Zzqcharname"
        return f

    def rows(f, now):
        return [{"id": "zzq", "label": "Probe", "status": diag.FAIL,
                 "detail": "Zzqcharname at " + WIN_PATH + " wrote zzq@example.org",
                 "fix": "Ask zzq-contact-name."}]

    monkeypatch.setattr(core, "diag_facts", facts)
    monkeypatch.setattr(diag, "checks", rows)
    status, _, body = call(core, "GET", report.PATH, auth())
    assert status == 200
    text = json.loads(body)["report"]
    for secret in ("Zzqcharname", "zzqhome", "zzq@example.org", "zzq-contact-name"):
        assert secret.lower() not in text.lower(), secret
    assert "<character>" in text and "<contact>" in text
    assert "<path>" in text and "<email>" in text
    assert "[FIX] Probe:" in text
