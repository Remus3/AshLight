"""Local HTTP server: dashboard assets, JSON API and Server-Sent Events.

Security floor (CLAUDE.md "Stack and ports", research 0008):
- binds 127.0.0.1 only (ports.LOOPBACK), on ports.AL_PORT by default;
- a per-start random token guards every /api/* and /events request
  (header X-AL-Token, or ?token= because EventSource cannot set headers);
- the Host header must be 127.0.0.1:<port> or localhost:<port> (DNS
  rebinding guard); an Origin header, when present, must match;
- strict CSP (no inline script), nosniff, no-referrer, frame-ancestors 'none'.
"""

import hmac
import json
import logging
import mimetypes
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import DISCLAIMER, NAME, VERSION, layout, ports
from .theorycraft import codec as build_codec
from .theorycraft import model as build_model

log = logging.getLogger("al.http")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; "
       "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'none'; "
       "frame-ancestors 'none'")
TOKEN_HEADER = "X-AL-Token"
SSE_MIN_INTERVAL_S = 0.25  # coalesce pushes to at most 4 Hz
SSE_HEARTBEAT_S = 15.0
SSE_WAIT_MAX_S = 1.0  # bound on one wait, so shutdown is noticed quickly
MAX_BODY = 4096
MAX_BUILD_BODY = 256 * 1024  # POST /api/build-code only (PoB codes are ~5-60 KB)
# The overlay is a local file:// page; its EventSource / fetch carry
# "Origin: null". Allowed for these read-only, token-gated GETs only.
FILE_ORIGIN_PATHS = {"/events", "/api/state", "/api/health"}
FILE_ORIGINS = {"null", "file://"}

TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json",
         ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
         ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}


def new_token():
    return os.urandom(24).hex()


class ALServer(ThreadingHTTPServer):
    daemon_threads = True
    # SO_REUSEADDR on Windows lets another process bind the same port; use
    # SO_EXCLUSIVEADDRUSE there instead.
    allow_reuse_address = os.name != "nt"

    def __init__(self, core, token, port=ports.AL_PORT, web_root=None, tokens_css=None):
        self.core = core
        self.token = token
        self.web_root = Path(web_root).resolve() if web_root else None
        self.tokens_css = Path(tokens_css) if tokens_css else None
        self.stopping = threading.Event()
        super().__init__((ports.LOOPBACK, int(port)), Handler)
        self.port = self.server_address[1]
        self.allowed_hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        self.allowed_origins = {f"http://{h}" for h in self.allowed_hosts}

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def stop(self):
        self.stopping.set()
        self.shutdown()
        self.server_close()


class Handler(BaseHTTPRequestHandler):
    server_version = f"{NAME}/{VERSION}"
    sys_version = ""

    # -- logging: never log the query string (it may carry the token)
    def log_message(self, fmt, *args):
        log.debug("%s %s", self.command, urlsplit(self.path).path)

    # -- helpers
    def _common_headers(self, ctype=None, length=None, extra=None):
        if ctype:
            self.send_header("Content-Type", ctype)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self._common_headers(ctype, len(body), extra)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code, obj, extra=None):
        self._send(code, json.dumps(obj, separators=(",", ":")),
                   "application/json; charset=utf-8", extra)

    def _url(self):
        u = urlsplit(self.path)
        return u.path, parse_qs(u.query)

    def _host_ok(self):
        return (self.headers.get("Host") or "").lower() in self.server.allowed_hosts

    def _origin_extra(self, path):
        """(ok, extra headers). No Origin = same-origin navigation or a
        non-browser client, allowed (the token still applies)."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True, {}
        if origin in self.server.allowed_origins:
            return True, {}
        if origin in FILE_ORIGINS and self.command == "GET" and path in FILE_ORIGIN_PATHS:
            return True, {"Access-Control-Allow-Origin": "null", "Vary": "Origin"}
        return False, {}

    def _token_ok(self, query):
        given = self.headers.get(TOKEN_HEADER) or (query.get("token") or [""])[0]
        return bool(given) and hmac.compare_digest(given.encode(), self.server.token.encode())

    def _guard(self, path, query, needs_token):
        """Host, Origin and token checks. Returns extra headers or None (sent)."""
        if not self._host_ok():
            self._send(400, "bad host\n")
            return None
        ok, extra = self._origin_extra(path)
        if not ok:
            self._send(403, "bad origin\n")
            return None
        if needs_token and not self._token_ok(query):
            self._json(401, {"error": "token required"}, extra)
            return None
        return extra

    @staticmethod
    def _needs_token(path):
        return path.startswith("/api/") or path == "/events"

    # -- verbs
    def do_GET(self):
        path, query = self._url()
        extra = self._guard(path, query, self._needs_token(path))
        if extra is None:
            return
        core = self.server.core
        if path == "/" or path == "/index.html":
            return self._static("index.html")
        if path.startswith("/web/"):
            return self._static(path[len("/web/"):])
        if path == "/tokens.css":
            return self._file(self.server.tokens_css)
        if path == "/favicon.ico":
            return self._send(204)
        if path == "/api/health":
            return self._json(200, {"ok": True, "name": NAME, "version": VERSION,
                                    "port": self.server.port,
                                    "tailing": bool(core.tailer and core.tailer.running)},
                              extra)
        if path == "/api/version":
            return self._json(200, {"name": NAME, "version": VERSION,
                                    "disclaimer": DISCLAIMER}, extra)
        if path == "/api/state":
            return self._json(200, core.state.snapshot(), extra)
        if path == "/api/overlay-layout":
            return self._json(200, self._layout_doc(), extra)
        if path == "/api/build":
            return self._json(200, core.builds.snapshot(), extra)
        if path == "/events":
            return self._sse(extra)
        return self._send(404, "not found\n")

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        path, query = self._url()
        extra = self._guard(path, query, self._needs_token(path))
        if extra is None:
            return
        if path == "/api/clipboard-read":
            # Decision 0003: the clipboard is read ONLY once per manual press
            # of an AshLight hotkey, never by a watcher or a timer, and
            # AshLight never sends Ctrl+C or any other input to the game.
            # Not implemented yet (ROADMAP); this stub stays a 501.
            return self._json(501, {"error": "not implemented",
                                    "policy": "docs/decisions/0003-read-policy.md"})
        if path == "/api/consent":
            return self._consent()
        if path == "/api/overlay-layout":
            return self._set_layout()
        if path == "/api/trade-dismiss":
            return self._trade_dismiss()
        if path == "/api/build-code":
            return self._build_code()
        return self._send(404, "not found\n")

    def do_PUT(self):
        self._send(405, "method not allowed\n")

    do_DELETE = do_PUT
    do_PATCH = do_PUT
    do_OPTIONS = do_PUT

    # -- endpoints
    def _read_json(self, max_body=MAX_BODY):
        """The JSON object body, or None after sending the error reply."""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(415, {"error": "application/json required"})
            return None
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > max_body:
            self._json(413, {"error": "body too large"})
            return None
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._json(400, {"error": "bad json"})
            return None
        if not isinstance(body, dict):
            self._json(400, {"error": "json object required"})
            return None
        return body

    def _layout_doc(self):
        core = self.server.core
        return {"layout": core.overlay_layout(), "displays": core.displays(),
                "corners": list(layout.CORNERS),
                "limits": {"scale": [layout.SCALE_MIN, layout.SCALE_MAX],
                           "opacity": [layout.OPACITY_MIN, layout.OPACITY_MAX],
                           "margin": [0, layout.MARGIN_MAX]}}

    def _set_layout(self):
        body = self._read_json()
        if body is None:
            return None
        try:
            self.server.core.set_overlay_layout(body)
        except layout.LayoutError as e:
            return self._json(400, {"error": str(e)})
        return self._json(200, self._layout_doc())

    def _trade_dismiss(self):
        """Dismiss a trade card on the dashboard. Display state only: it
        sends nothing to the game (CLAUDE.md ToS floor)."""
        body = self._read_json()
        if body is None:
            return None
        if body.get("all") is True:
            n = self.server.core.state.dismiss_trade(None)
        elif isinstance(body.get("id"), int) and not isinstance(body.get("id"), bool):
            n = self.server.core.state.dismiss_trade(body["id"])
        else:
            return self._json(400, {"error": "id (integer) or all: true required"})
        return self._json(200, {"dismissed": n, "state": self.server.core.state.snapshot()})

    def _build_code(self):
        """TC-CODE: load a pasted PoB2 build code (JSON {"code": text}).
        Decoded locally; a share URL is recognized but never fetched."""
        body = self._read_json(MAX_BUILD_BODY)
        if body is None:
            return None
        code = body.get("code")
        if not isinstance(code, str):
            return self._json(400, {"error": "code (string) required"})
        try:
            self.server.core.builds.load_code(code)
        except build_codec.ShareUrlError as e:
            return self._json(422, {"error": str(e), "kind": "url"})
        except (build_codec.CodeError, build_model.BuildError) as e:
            return self._json(400, {"error": str(e)})
        return self._json(200, self.server.core.builds.snapshot())

    def _consent(self):
        body = self._read_json()
        if body is None:
            return None
        if not isinstance(body.get("consent"), bool):
            return self._json(400, {"error": "consent: true|false required"})
        path = body.get("path")
        if path is not None and not isinstance(path, str):
            return self._json(400, {"error": "path must be a string"})
        rec = self.server.core.record_consent(body["consent"], path or None)
        return self._json(200, {"consent": rec, "state": self.server.core.state.snapshot()})

    def _static(self, rel):
        root = self.server.web_root
        if root is None:
            return self._send(404, "no web root\n")
        target = (root / rel).resolve()
        if not target.is_relative_to(root):
            return self._send(404, "not found\n")
        return self._file(target)

    def _file(self, target):
        if target is None or not Path(target).is_file():
            return self._send(404, "not found\n")
        target = Path(target)
        ctype = TYPES.get(target.suffix.lower()) or (
            mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        return self._send(200, target.read_bytes(), ctype)

    def _sse(self, extra):
        srv = self.server
        core = srv.core
        sub = core.bus.subscribe()
        try:
            self.send_response(200)
            self._common_headers("text/event-stream; charset=utf-8", None, extra)
            self.send_header("Connection", "close")
            self.end_headers()
            snap = core.state.snapshot()
            sent_version = snap["version"]
            self._sse_write("retry: 3000\n\n")
            self._sse_write(self._sse_msg("state", snap))
            last_push = time.monotonic()
            last_beat = last_push
            pending = []
            while not srv.stopping.is_set():
                now = time.monotonic()
                beat_in = SSE_HEARTBEAT_S - (now - last_beat)
                if pending:
                    wait = max(0.0, SSE_MIN_INTERVAL_S - (now - last_push))
                else:
                    wait = min(SSE_WAIT_MAX_S, max(0.0, beat_in))
                got = sub.get(timeout=wait)
                pending.extend(got)
                now = time.monotonic()
                if pending and now - last_push >= SSE_MIN_INTERVAL_S:
                    evs = [{k: v for k, v in ev.items() if k != "raw"} for ev in pending]
                    pending = []
                    chunk = self._sse_msg("events", evs)
                    snap = core.state.snapshot()
                    if snap["version"] != sent_version:
                        sent_version = snap["version"]
                        chunk += self._sse_msg("state", snap)
                    self._sse_write(chunk)
                    last_push = last_beat = now
                elif now - last_beat >= SSE_HEARTBEAT_S:
                    self._sse_write(": hb\n\n")
                    last_beat = now
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            sub.close()
            self.close_connection = True

    @staticmethod
    def _sse_msg(event, data):
        return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

    def _sse_write(self, text):
        self.wfile.write(text.encode("utf-8"))
        self.wfile.flush()


def serve(core, token, port=ports.AL_PORT, web_root=None, tokens_css=None):
    """Build the server (bound, not yet serving)."""
    return ALServer(core, token, port=port, web_root=web_root, tokens_css=tokens_css)
