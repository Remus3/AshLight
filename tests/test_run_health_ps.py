"""SEC-NO-PROXY: run.ps1's Test-AlHealth reaches 127.0.0.1 directly.

The function text is cut out of scripts/run.ps1 and run in Windows
PowerShell 5.1 against a stand-in core on an ephemeral port, with an
in-session default proxy pointed at a listener that counts connections.
Nothing here starts the app or changes any machine proxy setting.
"""

import http.server
import re
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from server.al import ports

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


def _test_core(token):
    class Health(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            ok = self.path == "/api/health" and self.headers.get("X-AL-Token") == token
            self.send_response(200 if ok else 403)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass
    srv = http.server.HTTPServer((ports.LOOPBACK, 0), Health)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_health_function_sets_an_explicit_empty_proxy():
    body = _function_text("Test-AlHealth")
    assert "System.Net.WebProxy" in body
    assert "Invoke-WebRequest" not in body


@needs_ps51
def test_ps_health_check_bypasses_a_set_proxy():
    proxy, hits = _counting_proxy()
    srv = _test_core("tok")
    try:
        script = "\n".join([
            "$ErrorActionPreference = 'Stop'",
            "$port = %d" % srv.server_address[1],
            "[System.Net.WebRequest]::DefaultWebProxy = "
            "New-Object System.Net.WebProxy('http://%s:%d', $false)"
            % (ports.LOOPBACK, proxy.getsockname()[1]),
            "function Get-AlToken { return 'tok' }",
            _function_text("Test-AlHealth"),
            "if (Test-AlHealth) { 'HEALTHY' } else { 'DOWN' }",
        ])
        r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command", "-"],
                           input=script, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().splitlines()[-1] == "HEALTHY", (r.stdout, r.stderr)
        assert hits == []
    finally:
        srv.shutdown()
        srv.server_close()
        proxy.close()


@needs_ps51
def test_run_script_parses_in_powershell_51():
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command",
                        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
                        f"'{RUN}', [ref]$null, [ref]$e) | Out-Null; $e.Count"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", r.stdout
