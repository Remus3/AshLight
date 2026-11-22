"""SEC-NO-PROXY / SEC-HELLO-PS: run.ps1's Test-AlHealth reaches 127.0.0.1
directly and proves the core (the hello handshake, decision 0054) before it
sends the token.

The function text is cut out of scripts/run.ps1 and run in Windows
PowerShell 5.1 against stand-in listeners on ephemeral ports: a test core
built on server.al.hello, a fake listener that answers 200 to everything,
and an in-session default proxy pointed at a listener that counts
connections. Nothing here starts the app or changes any machine proxy
setting.
"""

import http.server
import json
import re
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from server.al import hello, ports

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts" / "run.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
needs_ps51 = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")


def _function_text(name):
    text = RUN.read_text(encoding="ascii")
    m = re.search(r"^function " + re.escape(name) + r" \{\n.*?^\}\n", text,
                  re.MULTILINE | re.DOTALL)
    assert m, f"{name} not found in run.ps1"
    return m.group(0)


def _counting_proxy():
    hits = []
    sock = socket.socket()
    sock.bind((ports.LOOPBACK, 0))
    sock.listen(8)

    def accept():
        while True:
            try:
                conn, _ = sock.accept()
            except OSError:
                return
            hits.append(1)
            conn.close()
    threading.Thread(target=accept, daemon=True).start()
    return sock, hits


def _test_core(token, answer_port=None, bad_proof=False):
    """A stand-in core: /api/hello checks the client proof with
    server.al.hello and answers for its bound port (or answer_port);
    /api/health is 200 only with the right X-AL-Token. Every request's
    path and headers are recorded in srv.seen."""
    seen = []

    class Core(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path, dict(self.headers.items())))
            body = b"{}"
            if self.path == hello.PATH:
                nonce = self.headers.get(hello.NONCE_HEADER)
                ok = hello.check_client(token, nonce,
                                        self.headers.get(hello.PROOF_HEADER))
                if ok:
                    port = answer_port or self.server.server_address[1]
                    doc = hello.answer(token, nonce, port)
                    if bad_proof:
                        doc["proof"] = hello.server_proof(token, nonce, port + 1)
                    body = json.dumps(doc).encode("ascii")
                code = 200 if ok else 401
            else:
                ok = self.path == "/api/health" and self.headers.get("X-AL-Token") == token
                code = 200 if ok else 403
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    srv = http.server.HTTPServer((ports.LOOPBACK, 0), Core)
    srv.seen = seen
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _fake_listener(body=b"{}"):
    """Answers 200 with body to every request and records the headers."""
    seen = []

    class Fake(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path, dict(self.headers.items())))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    srv = http.server.HTTPServer((ports.LOOPBACK, 0), Fake)
    srv.seen = seen
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _stop(*servers):
    for srv in servers:
        srv.shutdown()
        srv.server_close()


def _run_health(port, token="tok", pre=()):
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$port = %d" % port,
        *pre,
        "function Get-AlToken { return '%s' }" % token,
        _function_text("Test-AlHealth"),
        "if (Test-AlHealth) { 'HEALTHY' } else { 'DOWN' }",
    ])
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command", "-"],
                       input=script, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip().splitlines()[-1]


def _token_paths(seen):
    return [path for path, headers in seen
            if any(k.lower() == "x-al-token" for k in headers)]


def test_health_function_sets_an_explicit_empty_proxy():
    body = _function_text("Test-AlHealth")
    assert "System.Net.WebProxy" in body
    assert "Invoke-WebRequest" not in body


@needs_ps51
def test_ps_health_check_bypasses_a_set_proxy():
    proxy, hits = _counting_proxy()
    srv = _test_core("tok")
    try:
        pre = ["[System.Net.WebRequest]::DefaultWebProxy = "
               "New-Object System.Net.WebProxy('http://%s:%d', $false)"
               % (ports.LOOPBACK, proxy.getsockname()[1])]
        assert _run_health(srv.server_address[1], pre=pre) == "HEALTHY"
        assert hits == []
    finally:
        _stop(srv)
        proxy.close()


def test_health_function_says_hello_before_the_token():
    body = _function_text("Test-AlHealth")
    assert "System.Security.Cryptography.HMACSHA256" in body
    assert "System.Security.Cryptography.RNGCryptoServiceProvider" in body
    assert hello.NONCE_HEADER in body and hello.PROOF_HEADER in body
    hello_at = body.index(hello.PATH)
    assert hello_at < body.index("X-AL-Token")
    assert hello_at < body.index("/api/health")
    assert body.count("X-AL-Token") == 1
    assert "-ne [long]$port" in body


def test_token_url_is_built_only_after_the_health_wait():
    text = RUN.read_text(encoding="ascii")
    assert text.count("#token=") == 1
    url_at = text.index('$url = "http://127.0.0.1:$port/#token="')
    assert text.index("\nif (Test-AlHealth) {") < url_at
    assert text.index("if (-not (Wait-AlCore $waitSince)) { exit 1 }") < url_at


@needs_ps51
def test_ps_hello_matches_the_python_proofs():
    srv = _test_core("tok-0123")
    try:
        assert _run_health(srv.server_address[1], token="tok-0123") == "HEALTHY"
    finally:
        _stop(srv)
    assert [p for p, _ in srv.seen] == [hello.PATH, "/api/health"]
    headers = srv.seen[0][1]
    nonce, proof = headers[hello.NONCE_HEADER], headers[hello.PROOF_HEADER]
    assert hello.valid_nonce(nonce)
    assert proof == hello.client_proof("tok-0123", nonce)
    assert "tok-0123" not in "".join(headers.values())
    assert _token_paths(srv.seen) == ["/api/health"]


@needs_ps51
@pytest.mark.parametrize("kind", ["wrong_port", "wrong_proof", "wrong_token"])
def test_ps_hello_refuses_a_bad_answer(kind):
    srv = {"wrong_port": lambda: _test_core("tok", answer_port=1),
           "wrong_proof": lambda: _test_core("tok", bad_proof=True),
           "wrong_token": lambda: _test_core("other")}[kind]()
    try:
        assert _run_health(srv.server_address[1]) == "DOWN"
    finally:
        _stop(srv)
    assert [p for p, _ in srv.seen] == [hello.PATH]
    assert _token_paths(srv.seen) == []


@needs_ps51
def test_fake_listener_gets_no_token_from_run_ps1():
    fake = _fake_listener()
    replay = _fake_listener(b'{"port": 0, "proof": "' + b"0" * 64 + b'"}')
    try:
        assert _run_health(fake.server_address[1]) == "DOWN"
        assert _run_health(replay.server_address[1]) == "DOWN"
    finally:
        _stop(fake, replay)
    for srv in (fake, replay):
        assert [p for p, _ in srv.seen] == [hello.PATH]
        assert _token_paths(srv.seen) == []
        assert all("tok" not in v for _, h in srv.seen for v in h.values())
    core = _test_core("tok")
    try:
        assert _run_health(core.server_address[1]) == "HEALTHY"
    finally:
        _stop(core)


@needs_ps51
def test_run_script_parses_in_powershell_51():
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command",
                        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
                        f"'{RUN}', [ref]$null, [ref]$e) | Out-Null; $e.Count"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", r.stdout
