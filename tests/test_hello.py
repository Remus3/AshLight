"""SEC-HELLO-CORE: clients prove the core before they send the token.

GET /api/hello (decision 0054): the client sends a fresh 128-bit nonce and
HMAC-SHA256(token, "client" + nonce), never the token; the core answers
HMAC-SHA256(token, "server" + nonce + bound port). The supervisor
(keepalive.health_check) checks that answer before it sends the token.

Every server binds an ephemeral port (0), so a running AshLight is never
touched; runtime state goes to tmp_path. No process is looked at.
"""

import hashlib
import hmac
import http.client
import http.server
import io
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from server.al import hello, ports
from server.al import http as al_http
from server.al import keepalive as ka
from server.al.core import Core

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "h" * 48


@pytest.fixture(autouse=True)
def _fresh_cache():
    hello.forget()
    yield
    hello.forget()


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


def get(port, path, headers=None, host=None):
    conn = http.client.HTTPConnection(ports.LOOPBACK, port, timeout=10)
    h = {"Host": host or f"{ports.LOOPBACK}:{port}"}
    h.update(headers or {})
    conn.request("GET", path, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r, data


def proof_headers(nonce, token=TOKEN):
    return {hello.NONCE_HEADER: nonce, hello.PROOF_HEADER: hello.client_proof(token, nonce)}


class Recorder(http.server.ThreadingHTTPServer):
    """A loopback listener that records every request head; `reply(handler)`
    returns (status, body bytes)."""

    daemon_threads = True

    def __init__(self, reply):
        self.reply = reply
        self.seen = []
        super().__init__((ports.LOOPBACK, 0), _RecorderHandler)
        threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()

    @property
    def port(self):
        return self.server_address[1]

    def close(self):
        self.shutdown()
        self.server_close()


class _RecorderHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.seen.append((self.path, dict(self.headers.items())))
        status, body = self.server.reply(self)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_POST = do_GET

    def log_message(self, *args):
        pass


def test_proofs_are_hmac_sha256_over_role_nonce_and_port():
    nonce = "0123456789abcdef" * 2
    key = TOKEN.encode("ascii")
    assert hello.client_proof(TOKEN, nonce) == hmac.new(
        key, ("client" + nonce).encode("ascii"), hashlib.sha256).hexdigest()
    assert hello.server_proof(TOKEN, nonce, 8960) == hmac.new(
        key, ("server" + nonce + "8960").encode("ascii"), hashlib.sha256).hexdigest()
    # the role tags keep a client proof from passing as a server answer
    assert hello.client_proof(TOKEN, nonce) != hello.server_proof(TOKEN, nonce, 8960)
    # the port is bound in; another port or token is another answer
    assert hello.server_proof(TOKEN, nonce, 8960) != hello.server_proof(TOKEN, nonce, 8961)
    assert hello.server_proof(TOKEN, nonce, 8960) != hello.server_proof("x" * 48, nonce, 8960)
    # a fresh 128-bit nonce each time: 32 lowercase hex digits
    seen = {hello.new_nonce() for _ in range(64)}
    assert len(seen) == 64 and all(hello.valid_nonce(n) for n in seen)
    # check_client: the right proof only, nonce and proof shapes enforced
    good = hello.client_proof(TOKEN, nonce)
    assert hello.check_client(TOKEN, nonce, good)
    for n, p in ((nonce, good.upper()), (nonce.upper(), good), (nonce[:-1], good),
                 (nonce + "0", good), (nonce, good[:-1]), (None, good), (nonce, None),
                 (nonce, TOKEN), ("z" * 32, good),
                 (nonce, hello.client_proof("x" * 48, nonce)),
                 (nonce, hello.server_proof(TOKEN, nonce, 8960))):
        assert not hello.check_client(TOKEN, n, p), (n, p)
    assert not hello.check_client("", nonce, good)
    assert hello.answer(TOKEN, nonce, 8960) == {
        "port": 8960, "proof": hello.server_proof(TOKEN, nonce, 8960)}


def test_route_refuses_a_bad_or_missing_proof_with_401(srv):
    port = srv.port
    nonce = hello.new_nonce()
    other = hello.new_nonce()
    bad = [
        {},
        {hello.NONCE_HEADER: nonce},
        {hello.PROOF_HEADER: hello.client_proof(TOKEN, nonce)},
        {hello.NONCE_HEADER: nonce, hello.PROOF_HEADER: hello.client_proof(TOKEN, other)},
        {hello.NONCE_HEADER: nonce, hello.PROOF_HEADER: hello.client_proof("w" * 48, nonce)},
        {hello.NONCE_HEADER: nonce, hello.PROOF_HEADER: hello.server_proof(TOKEN, nonce, port)},
        {hello.NONCE_HEADER: nonce, hello.PROOF_HEADER: TOKEN},
        {hello.NONCE_HEADER: "short", hello.PROOF_HEADER: hello.client_proof(TOKEN, "short")},
        # the token value is not this route's credential
        {"X-AL-Token": TOKEN},
        {"Authorization": "Bearer " + TOKEN},
    ]
    for h in bad:
        r, data = get(port, hello.PATH, h)
        assert r.status == 401, h
        assert json.loads(data) == {"error": "token required"}
    r, _ = get(port, f"{hello.PATH}?token={TOKEN}")
    assert r.status == 401
    # the Host / Origin / cross-site checks still run first
    good = proof_headers(nonce)
    assert get(port, hello.PATH, good, host="evil.example")[0].status == 400
    assert get(port, hello.PATH, {**good, "Origin": "http://evil.example"})[0].status == 403
    assert get(port, hello.PATH, {**good, "Sec-Fetch-Site": "cross-site"})[0].status == 403
    # a valid proof opens no other route
    assert get(port, "/api/state", good)[0].status == 401
    # and a valid proof gets the answer, with the security headers intact
    r, data = get(port, hello.PATH, good)
    assert r.status == 200
    assert r.getheader("Content-Security-Policy") == al_http.CSP
    assert r.getheader("X-Content-Type-Options") == "nosniff"
    assert "port" in json.loads(data)


def test_answer_binds_the_bound_port(srv):
    port = srv.port
    nonce = hello.new_nonce()
    r, data = get(port, hello.PATH, proof_headers(nonce))
    assert r.status == 200
    doc = json.loads(data)
    assert doc == {"port": port, "proof": hello.server_proof(TOKEN, nonce, port)}
    assert doc["proof"] != hello.server_proof(TOKEN, nonce, port + 1)
    # the Python client accepts the real core on its own port
    assert hello.verify(port, TOKEN, timeout=5)

    # a listener on another port relays the challenge to the real core and
    # passes the real answer back: the bound port gives it away
    def relay(handler):
        n = handler.headers.get(hello.NONCE_HEADER) or ""
        p = handler.headers.get(hello.PROOF_HEADER) or ""
        rr, body = get(port, hello.PATH, {hello.NONCE_HEADER: n, hello.PROOF_HEADER: p})
        return rr.status, body
    fake = Recorder(relay)
    try:
        assert not hello.verify(fake.port, TOKEN, timeout=5)
        assert len(fake.seen) == 1
        # the same relay that also rewrites the port field: the proof fails
        fake.reply = lambda h: (200, json.dumps(
            {**json.loads(relay(h)[1]), "port": fake.port}).encode("ascii"))
        assert not hello.verify(fake.port, TOKEN, timeout=5)
        assert not hello.is_verified(fake.port, TOKEN)
    finally:
        fake.close()


def test_fake_server_answering_200_gets_no_token_from_the_supervisor(tmp_path):
    (tmp_path / "token").write_text(TOKEN + "\n", encoding="ascii")
    for body in (b"{}", b'{"ok": true}', b"null", b"x",
                 json.dumps({"port": 0, "proof": "0" * 64}).encode("ascii")):
        fake = Recorder(lambda h, body=body: (200, body))
        try:
            fake.reply = (lambda h, body=body, fp=fake: (200, body.replace(
                b'"port": 0', f'"port": {fp.port}'.encode("ascii"))))
            assert ka.health_check(tmp_path, fake.port, timeout=5) is False
            # the supervisor's own poll, default health check, no core alive
            sup = ka.Keepalive(runtime=tmp_path, port=fake.port, launch=lambda: 1,
                               pid_alive=lambda p: False, now=lambda: 1000.0)
            assert sup._health() is False
            assert fake.seen, "the listener was never asked"
            for path, headers in fake.seen:
                assert path == hello.PATH
                assert "x-al-token" not in {k.lower() for k in headers}
                assert "authorization" not in {k.lower() for k in headers}
                assert TOKEN not in path and all(TOKEN not in v for v in headers.values())
            assert not hello.is_verified(fake.port, TOKEN)
        finally:
            fake.close()


class FakeOpener:
    """An opener that plays the core: hello answers with the right proof;
    /api/health answers 200 unless `fail_health` is set."""

    def __init__(self, port, token):
        self.port = port
        self.token = token
        self.calls = []
        self.fail_health = False

    def open(self, req, timeout=None):
        path = urllib.parse.urlsplit(req.full_url).path
        self.calls.append(path)
        if path == hello.PATH:
            nonce = req.get_header(hello.NONCE_HEADER.capitalize())
            assert nonce and req.get_header("X-al-token") is None
            body = json.dumps(hello.answer(self.token, nonce, self.port)).encode("ascii")
        else:
            if self.fail_health:
                raise urllib.error.URLError("connection reset")
            body = b"{}"
        return _Resp(body)


class _Resp(io.BytesIO):
    status = 200


def test_verified_once_per_token_and_again_after_an_error(tmp_path):
    port = ports.PORT_BLOCK[1]
    opener = FakeOpener(port, TOKEN)
    assert hello.verify(port, TOKEN, opener=opener)
    assert hello.verify(port, TOKEN, opener=opener)
    assert opener.calls == [hello.PATH]  # once per token value
    # a new token value is proven again
    opener.token = "n" * 48
    assert hello.verify(port, "n" * 48, opener=opener)
    assert opener.calls == [hello.PATH] * 2
    # a wrong answer for a token is never cached
    assert not hello.verify(port, "q" * 48, opener=opener)
    assert not hello.is_verified(port, "q" * 48)

    # the supervisor: hello once, then the token goes to /api/health
    hello.forget()
    (tmp_path / "token").write_text(TOKEN + "\n", encoding="ascii")
    core = FakeOpener(port, TOKEN)
    orig = ka._NO_PROXY_OPENER
    ka._NO_PROXY_OPENER = core
    try:
        assert ka.health_check(tmp_path, port)
        assert ka.health_check(tmp_path, port)
        assert core.calls == [hello.PATH, "/api/health", "/api/health"]
        # a request error clears the proof; the next check proves again
        core.fail_health = True
        assert not ka.health_check(tmp_path, port)
        assert not hello.is_verified(port, TOKEN)
        core.fail_health = False
        core.calls.clear()
        assert ka.health_check(tmp_path, port)
        assert core.calls == [hello.PATH, "/api/health"]
        # a dead core: the supervisor's poll drops the proof for its port
        sup = ka.Keepalive(runtime=tmp_path, port=port, launch=lambda: 1,
                           pid_alive=lambda p: False, health=lambda: False,
                           now=lambda: 1000.0)
        assert hello.is_verified(port, TOKEN)
        sup.step()
        assert not hello.is_verified(port, TOKEN)
    finally:
        ka._NO_PROXY_OPENER = orig
