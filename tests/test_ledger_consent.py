"""RUN-LEDGER-CONSENT (finding F-061, decision 0071): the parse ledger's own
consent line.

The "ledger" key of consent.json is the ledger's only opt-in: the
Client.txt opt-in never implies it, it can be given only while Client.txt
is read, POST /api/consent takes it as {"ledger": bool} behind the token,
and revoking it (or the Client.txt opt-in) deletes ops/runtime/
logshapes.json.

No socket, process or network: requests run through http.Handler on
in-memory streams and the core never tails (tail=False).
"""

import io
import json
import threading

import pytest

from server.al import http as al_http
from server.al import jsonfile
from server.al.core import LEDGER_FILE, Core

TOKEN = "t" * 48
HOST = "127.0.0.1:8961"


@pytest.fixture
def core(tmp_path):
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


def post(core, body, headers=None):
    """POST /api/consent through the real Handler; returns (status, doc)."""
    data = json.dumps(body).encode("ascii")
    lines = ["POST /api/consent HTTP/1.1", f"Host: {HOST}", "Connection: close",
             "Content-Type: application/json", f"Content-Length: {len(data)}"]
    lines += [f"{k}: {v}" for k, v in (headers or {}).items()]
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


def auth():
    return {"X-AL-Token": TOKEN}


def ledger_files(core):
    path = core.runtime / LEDGER_FILE
    return path, jsonfile.bak_path(path)


def write_ledger(core):
    for p in ledger_files(core):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"schema": 1}\n', encoding="ascii")


def tailer(core):
    return core.state.snapshot()["tailer"]


# -- the named tests ----------------------------------------------------------

def test_no_ledger_consent_by_default(core):
    assert not core.consent_path.exists()
    assert core.ledger_consented() is False
    assert tailer(core).get("ledger") is False
    assert tailer(core).get("consented") is False


def test_client_txt_consent_alone_does_not_grant_the_ledger(core):
    status, doc = post(core, {"consent": True}, auth())
    assert status == 200
    assert core.consented() and core.ledger_consented() is False
    assert "ledger" not in doc["consent"]
    assert doc["state"]["tailer"]["ledger"] is False
    saved = json.loads(core.consent_path.read_text(encoding="ascii"))
    assert saved["consented"] is True and "ledger" not in saved
    # a key that is not exactly {"consented": true} grants nothing
    for odd in (True, "yes", 1, {"consented": "yes"}, {"consented": 1}, {}):
        core.consent_path.write_text(json.dumps(dict(saved, ledger=odd)), encoding="ascii")
        assert core.ledger_consented() is False, odd
    # the ledger alone, before the Client.txt opt-in, is refused
    core.record_consent(False)
    status, doc = post(core, {"ledger": True}, auth())
    assert status == 400 and core.ledger_consented() is False
    # re-allowing Client.txt after a revoke does not bring the ledger back
    post(core, {"consent": True}, auth())
    post(core, {"ledger": True}, auth())
    assert core.ledger_consented() is True
    post(core, {"consent": False}, auth())
    post(core, {"consent": True}, auth())
    assert core.ledger_consented() is False


def test_revoking_ledger_consent_deletes_the_file(core):
    post(core, {"consent": True}, auth())
    status, doc = post(core, {"ledger": True}, auth())
    assert status == 200 and core.ledger_consented() is True
    assert doc["consent"]["ledger"]["consented"] is True
    assert doc["consent"]["ledger"]["file"] == LEDGER_FILE
    assert doc["state"]["tailer"]["ledger"] is True
    # granting the ledger keeps the Client.txt record as it was
    assert doc["consent"]["consented"] is True
    write_ledger(core)
    status, doc = post(core, {"ledger": False}, auth())
    assert status == 200 and core.ledger_consented() is False
    assert doc["state"]["tailer"]["ledger"] is False
    assert not any(p.exists() for p in ledger_files(core))
    assert core.consented()  # the Client.txt opt-in is untouched
    # revoking the Client.txt opt-in also turns the ledger off and deletes it
    post(core, {"ledger": True}, auth())
    write_ledger(core)
    post(core, {"consent": False}, auth())
    assert core.ledger_consented() is False
    assert not any(p.exists() for p in ledger_files(core))
    saved = json.loads(core.consent_path.read_text(encoding="ascii"))
    assert saved["ledger"]["consented"] is False
    # a revoke with no file is quiet
    post(core, {"consent": True}, auth())
    assert post(core, {"ledger": False}, auth())[0] == 200


def test_ledger_flag_needs_the_token(core):
    post(core, {"consent": True}, auth())
    for headers in ({}, {"X-AL-Token": "wrong"}):
        status, _ = post(core, {"ledger": True}, headers)
        assert status == 401
        assert core.ledger_consented() is False
    for bad in ({"ledger": "yes"}, {"ledger": 1}, {"ledger": None}, {},
                {"consent": True, "ledger": "on"}):
        status, _ = post(core, bad, auth())
        assert status == 400, bad
        assert core.ledger_consented() is False
    status, doc = post(core, {"ledger": True}, auth())
    assert status == 200 and doc["state"]["tailer"]["ledger"] is True
