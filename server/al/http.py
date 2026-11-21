"""Local HTTP server: dashboard assets, JSON API and Server-Sent Events.

Security floor (CLAUDE.md "Stack and ports", research 0008):
- binds 127.0.0.1 only (ports.LOOPBACK), on ports.AL_PORT by default;
- a per-start random token guards every /api/* and /events request
  (header X-AL-Token or Authorization: Bearer, or ?token= because
  EventSource cannot set headers; decision 0002 "API token");
- the Host header must be 127.0.0.1:<port> or localhost:<port> (DNS
  rebinding guard); an Origin header, when present, must match;
- SEC-CROSS-SITE: a request whose Sec-Fetch-Site is present and neither
  same-origin nor none gets 403 on every route, before the token check
  (one exception: GET /events from the file:// overlay, Origin null);
  every reply carries Cross-Origin-Resource-Policy: same-origin and
  Vary: Sec-Fetch-Site; the Server header names no version;
- SEC-STATIC-MAP: /web/ answers by exact lookup in a map of AshLight's own
  listing of web/ (static.py), so no file system call sees request text;
- TEST-WEB-ASSEMBLE (F-194): / and /index.html serve index.html with one
  same-origin tag per web/panels/*.js and *.css inserted at its marker
  (webpage.py); no inline script, no remote origin, the same CSP;
- strict CSP (no inline script), nosniff, no-referrer, frame-ancestors 'none';
- SEC-HELLO-CORE (decision 0054): GET /api/hello takes a proof of the token
  (hello.py), never the token value, as its token gate, so a client can
  prove the core before it sends the token;
- TEST-HTTP-ROUTES (F-193): do_GET / do_POST / do_PUT split the path,
  run _guard (PUT: after its 405 test) and then look the path up in one
  table per verb (GET_ROUTES, POST_ROUTES, PUT_ROUTES); a new endpoint is
  a table entry, never a new dispatch arm;
- RUN-SEAMS (decision 0056): a GET or POST path no built-in route takes
  falls through to plug.route (server/al/plug/), after _guard, and only
  for an exact path under /api/, so a plug route always needs the token;
- SEC-SSE-TAP (F-106): /events sends state frames only; a bus event just
  wakes the state push. The per-event "events" frame is a dev tap,
  /events?tap=1, served only in a source checkout (a .git entry at the
  repo root), and each tapped event keeps its type plus its numeric,
  boolean and null fields: no chat text, name or other string leaves.
- RUN-METRICS-CORE (decision 0067): _send counts each reply by route key
  and status class plus the 401s, _sse_write counts SSE frames and bytes
  (server/al/metrics.py); read only through the token-gated GET /api/debug
  (server/al/plug/debug.py). A route is a table key or "other", never
  request text.
"""

import contextlib
import hmac
import json
import logging
import mimetypes
import os
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import (DISCLAIMER, NAME, VERSION, buildinfo, gfx, hello, layout, metrics, paths, plug,
               ports, settingsio, static, webfetch, webpage)
from .theorycraft import codec as build_codec
from .theorycraft import datacredit
from .theorycraft import lootfilter
from .theorycraft import model as build_model
from .theorycraft import paste as build_paste
from .theorycraft import shareurl
from .theorycraft import weights as tc_weights

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
# AREA-AUDIT P5-1: a config write refused (config/local.json unreadable or
# not writable); nothing was changed
SAVE_FAILED = "AshLight couldn't save the settings."
# TC-WORN-WIRE: the worn-gear file could not be written
WEAR_SAVE_FAILED = "AshLight couldn't save the worn item."
MAX_BUILD_BODY = 256 * 1024  # POST /api/build-code only (PoB codes are ~5-60 KB)
# POST /api/eval: the item key's one clipboard text, an item or a copied
# build (TC-PRESS-BUILD: the build size, app/eval_hotkey.js caps 256 KB)
MAX_EVAL_BODY = MAX_BUILD_BODY
MAX_WEIGHTS_BODY = 64 * 1024  # PUT /api/weights
DRAIN_MAX = 1024 * 1024  # a rejected body up to this is read and dropped (413 / 415)
DRAIN_TIMEOUT_S = 2.0  # ... within this time, else the connection just closes
# TEST-HTTP: socket timeout per connection. A client that connects and sends
# nothing, sends a body shorter than its Content-Length, or (SSE) stops
# reading is dropped after this, so it cannot pin a thread forever.
REQUEST_TIMEOUT_S = 10.0
# TEST-HTTP: at most this many live SSE streams (dashboard tabs + overlay);
# one more gets 503 with Retry-After, so a runaway client cannot spawn
# unbounded threads and bus subscriptions.
MAX_SSE_CLIENTS = 16
# SEC-CEIL-HTTP (F-173): at most this many handler threads at once, SSE
# streams included. One more connection is closed at once, before a thread
# starts; slots free as idle connections hit REQUEST_TIMEOUT_S.
MAX_HANDLER_THREADS = 64
SSE_BUSY_RETRY_MS = 30000  # a stream refused for the cap reconnects after this
# The overlay is a local file:// page; its EventSource carries
# "Origin: null". Allowed for this read-only, token-gated GET only
# (SEC-CROSS-SITE: /api/state and /api/health no longer; the overlay never
# fetched them).
FILE_ORIGIN_PATHS = {"/events"}
FILE_ORIGINS = {"null", "file://"}
# SEC-CROSS-SITE: Sec-Fetch-Site values let through. same-site is refused
# on purpose: a page on another loopback port is same-site.
FETCH_SITE_OK = {"same-origin", "none"}
# SEC-CROSS-SITE: fixed reply texts; the OS error detail goes to the log only
LAYOUT_READ_FAILED = ("AshLight couldn't read its settings file, so the overlay "
                      "layout wasn't saved.")
SHARE_FETCH_FAILED = ("AshLight couldn't fetch that share link. Check the link, "
                      "or paste the build code itself.")

TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json",
         ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
         ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}


def new_token():
    return os.urandom(24).hex()


def tap_event(ev):
    """SEC-SSE-TAP: one bus event as the dev tap sends it: its type plus
    the numeric, boolean and null fields; every other string (chat text,
    names, raw lines), list and object is left out."""
    out = {"type": ev.get("type")}
    for k, v in ev.items():
        if k != "type" and (v is None or isinstance(v, (bool, int, float))):
            out[k] = v
    return out


class ALServer(ThreadingHTTPServer):
    daemon_threads = True
    # SO_REUSEADDR on Windows lets another process bind the same port; use
    # SO_EXCLUSIVEADDRUSE there instead.
    allow_reuse_address = os.name != "nt"
    # GP-09 (decision 0080): the listen backlog. socketserver's default of 5
    # lets a page load's parallel connects (Chrome opens up to six at once,
    # plus the SSE stream) overflow while the accept loop is stalled, and
    # Windows answers an overflow with a reset (ERR_CONNECTION_REFUSED).
    request_queue_size = 128

    def __init__(self, core, token, port=ports.AL_PORT, web_root=None, tokens_css=None):
        self.core = core
        self.token = token
        self.web_root = Path(web_root).resolve() if web_root else None
        # SEC-STATIC-MAP: the served names, listed once; rebuilt when the
        # hot-reload scan bumps core.reload_web (decision 0042)
        self.static = (static.StaticMap(self.web_root, getattr(core, "reload_web", 0))
                       if self.web_root else None)
        self.panels_synced = ()  # TEST-WEB-ASSEMBLE: panel set last listed
        self.tokens_css = Path(tokens_css) if tokens_css else None
        self.stopping = threading.Event()
        self.sse_slots = threading.BoundedSemaphore(MAX_SSE_CLIENTS)
        self.handler_slots = threading.BoundedSemaphore(MAX_HANDLER_THREADS)
        # GFX-ADVISOR: hardware read once, on the first GET /api/gfx.
        self.gfx = gfx.Advisor()
        # SEC-SSE-TAP: the /events?tap=1 dev tap exists only in a source
        # checkout; not tied to the hot-reload switch (the suite turns it off)
        self.events_tap = (paths.repo_root() / ".git").exists()
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

    def process_request(self, request, client_address):
        """SEC-CEIL-HTTP: take a handler slot before the thread starts; with
        none free the connection is closed at once (no reply, no thread)."""
        if not self.handler_slots.acquire(blocking=False):
            log.debug("handler thread ceiling reached; connection closed")
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            # the thread never started, so it will not release the slot
            self.handler_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.handler_slots.release()

    def handle_error(self, request, client_address):
        """TEST-HTTP: a dropped or timed-out client is routine (debug); any
        other handler error goes to the core log, not to a stderr that
        pythonw does not have."""
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, OSError):
            log.debug("client connection error: %s", type(exc).__name__)
        else:
            log.exception("request handler error")


class Handler(BaseHTTPRequestHandler):
    server_version = NAME  # SEC-CROSS-SITE: no version in the Server header
    sys_version = ""
    # AUDIT-HTTP-HARDEN S2: a socket timeout, so an idle or stalled local
    # connection frees its thread.
    timeout = REQUEST_TIMEOUT_S  # TEST-HTTP (StreamRequestHandler applies it)

    # -- logging: never log the query string (it may carry the token).
    # TEST-HTTP: a malformed request line (garbage, a 64 KB+ URI) is logged
    # before command / path exist; reading them unguarded raised and the
    # client got no 400 / 414 at all.
    def version_string(self):
        """SEC-CROSS-SITE: the Server header is the name only."""
        return NAME

    def log_message(self, fmt, *args):
        log.debug("%s %s", getattr(self, "command", None) or "-",
                  urlsplit(getattr(self, "path", "") or "").path)

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
        # SEC-CROSS-SITE: no other site may embed a reply; caches key on the
        # fetch site (the Origin too where the reply depends on it)
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        extra = dict(extra or {})
        vary = [v for v in (extra.pop("Vary", ""), "Sec-Fetch-Site") if v]
        self.send_header("Vary", ", ".join(vary))
        for k, v in extra.items():
            self.send_header(k, v)

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._count_reply(code)
        self._discard_unread()
        self.send_response(code)
        self._common_headers(ctype, len(body), extra)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _count_reply(self, code):
        """RUN-METRICS-CORE: one reply by route key and status class, and
        the 401s (decision 0067). Never raises into a reply."""
        try:
            path = urlsplit(getattr(self, "path", "") or "").path
            metrics.inc(f"http|{route_label(path)}|{int(code) // 100}xx")
            if code == 401:
                metrics.inc("http.401")
        except Exception:  # noqa: BLE001 - a counter never breaks a reply
            log.debug("reply counter failed", exc_info=True)

    def _json(self, code, obj, extra=None):
        self._send(code, json.dumps(obj, separators=(",", ":")),
                   "application/json; charset=utf-8", extra)

    def _url(self):
        u = urlsplit(self.path)
        return u.path, parse_qs(u.query)

    def _host_ok(self):
        return (self.headers.get("Host") or "").lower() in self.server.allowed_hosts

    def _cross_site(self, path=None):
        """SEC-CROSS-SITE: True when the browser says the request comes from
        another site (Sec-Fetch-Site present and neither same-origin nor
        none). The one exception is GET /events from the file:// overlay
        (Origin null). No header = a non-browser client or an older
        browser, judged by the other checks as before."""
        site = self.headers.get("Sec-Fetch-Site")
        if site is None or site.strip().lower() in FETCH_SITE_OK:
            return False
        return not (self.command == "GET" and path in FILE_ORIGIN_PATHS
                    and self.headers.get("Origin") in FILE_ORIGINS)

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

    def _bearer(self):
        """The token from "Authorization: Bearer <token>" ('' otherwise)."""
        value = (self.headers.get("Authorization") or "").strip()
        scheme, _, rest = value.partition(" ")
        return rest.strip() if scheme.lower() == "bearer" else ""

    def _token_ok(self, query, path=None):
        # header first (X-AL-Token, then Authorization: Bearer), then ?token=
        # ONLY on /events, for EventSource, which cannot set headers
        # (API-TOKEN-HDR, decision 0002 "API token"; AUDIT-HTTP-HARDEN S3: a
        # token in an /api URL would reach history and logs). All compare in
        # constant time.
        given = self.headers.get(TOKEN_HEADER) or self._bearer()
        if not given and path == "/events":
            given = (query.get("token") or [""])[0]
        return bool(given) and hmac.compare_digest(given.encode(), self.server.token.encode())

    def _guard(self, path, query, needs_token):
        """Host, Origin and token checks. Returns extra headers or None (sent)."""
        if not self._host_ok():
            self._send(400, "bad host\n")
            return None
        if self._cross_site(path):
            self._send(403, "cross-site request refused\n")
            return None
        ok, extra = self._origin_extra(path)
        if not ok:
            self._send(403, "bad origin\n")
            return None
        if needs_token and not self._credential_ok(query, path):
            self._json(401, {"error": "token required"}, extra)
            return None
        return extra

    def _credential_ok(self, query, path):
        """The token gate. SEC-HELLO-CORE (decision 0054): /api/hello takes
        only the client proof (nonce + HMAC of the token, two headers),
        never the token value; every other token route takes the token."""
        if path == hello.PATH:
            return hello.check_client(self.server.token,
                                      self.headers.get(hello.NONCE_HEADER),
                                      self.headers.get(hello.PROOF_HEADER))
        return self._token_ok(query, path)

    @staticmethod
    def _needs_token(path):
        return path.startswith("/api/") or path == "/events"

    # -- verbs (TEST-HTTP-ROUTES, F-193): the path split and _guard first,
    # then one lookup in the verb's route table (GET_ROUTES / POST_ROUTES /
    # PUT_ROUTES, below the class). A new endpoint is a table entry and a
    # route method; no dispatch function changes.
    def do_GET(self):
        path, query = self._url()
        extra = self._guard(path, query, self._needs_token(path))
        if extra is None:
            return
        fn = route_for(GET_ROUTES, path)
        if fn is not None:
            return fn(self, path, query, extra)
        return self._plug("GET", path, query, extra)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        path, query = self._url()
        extra = self._guard(path, query, self._needs_token(path))
        if extra is None:
            return
        fn = route_for(POST_ROUTES, path)
        if fn is not None:
            return fn(self, path, query, extra)
        return self._plug("POST", path, query, extra)

    # -- GET routes: fn(handler, path, query, extra), after _guard
    def _get_index(self, path, query, extra):
        """TEST-WEB-ASSEMBLE (F-194): index.html with one tag per
        web/panels/ file inserted at its marker (webpage.py); the request
        text never reaches a file system call."""
        srv = self.server
        smap = srv.static
        if smap is None:
            return self._send(404, "no web root\n")
        seq = getattr(srv.core, "reload_web", 0)
        if smap.lookup("index.html", seq) is None:
            return self._send(404, "not found\n")
        built = webpage.page(srv.web_root)
        if built is None:
            return self._send(404, "not found\n")
        body, names = built
        if names != srv.panels_synced and any(smap.lookup(n, seq) is None for n in names):
            # a panel added since the last /web/ listing: list again once
            # for this set, so its tag and its file arrive together
            srv.static = static.StaticMap(srv.web_root, seq)
        srv.panels_synced = names
        return self._send(200, body, TYPES[".html"])

    def _get_web(self, path, query, extra):
        return self._static(path[len("/web/"):])

    def _get_tokens_css(self, path, query, extra):
        return self._file(self.server.tokens_css)

    def _get_favicon(self, path, query, extra):
        # BRAND-ICON: the local icon file (web/favicon.ico), no network.
        return self._static("favicon.ico")

    def _get_hello(self, path, query, extra):
        # SEC-HELLO-CORE: the proof was checked by _guard; the answer
        # binds the nonce and the port this server bound
        return self._json(200, hello.answer(self.server.token,
                                            self.headers.get(hello.NONCE_HEADER),
                                            self.server.port), extra)

    def _get_health(self, path, query, extra):
        # DEP-05 (decision 0059): mode (checkout / installed) and the
        # marker's previous version (null in a checkout).
        # RUN-BUILD-STAMP-CORE (F-027): "build" is buildinfo's one string
        # RUN-SUPERVISOR-CLOCK (F-136): loop_age_s, seconds since the core
        # loop's last pass (core.loop_at, monotonic; null before the first);
        # the supervisor counts a check with a loop over 60 s old as failed
        core = self.server.core
        loop_at = getattr(core, "loop_at", None)
        loop_age = None if loop_at is None else round(max(time.monotonic() - loop_at, 0.0), 2)
        return self._json(200, {"ok": True, "name": NAME, "version": VERSION,
                                "build": buildinfo.build_id(getattr(core, "hot", None)),
                                "port": self.server.port,
                                "tailing": bool(core.tailer and core.tailer.running),
                                "loop_age_s": loop_age,
                                **paths.install_info()},
                          extra)

    def _get_version(self, path, query, extra):
        # TC-SNAP-UI: the snapshot attribution, only while snapshot data
        # exists in the sidecar cache (decision 0009); else null.
        # RUN-BUILD-STAMP-CORE: the same build string as /api/health
        return self._json(200, {"name": NAME, "version": VERSION,
                                "build": buildinfo.build_id(
                                    getattr(self.server.core, "hot", None)),
                                "disclaimer": DISCLAIMER,
                                "data_credit": datacredit.credit_doc(),
                                **paths.install_info()}, extra)

    def _get_state(self, path, query, extra):
        return self._json(200, self.server.core.state.snapshot(), extra)

    def _get_layout(self, path, query, extra):
        return self._json(200, self._layout_doc(), extra)

    def _get_build(self, path, query, extra):
        return self._json(200, self.server.core.builds.snapshot(), extra)

    def _get_filter(self, path, query, extra):
        # UTIL-FILTER (decision 0031): a download the player saves; the
        # core writes no file anywhere
        core = self.server.core
        hdr = dict(extra, **{"Content-Disposition":
                             f'attachment; filename="{lootfilter.FILE_NAME}"'})
        names = getattr(core, "base_names", None)
        names = names.get() if names is not None else None
        # UTIL-FILTER-2 (decision 0032): value tiers from the cached
        # poe.ninja prices; None while web data is off; never a request
        rates = getattr(core, "rates", None)
        prices = rates.filter_prices() if rates is not None else None
        return self._send(200, lootfilter.generate(core.builds.build, names, prices),
                          "text/plain; charset=utf-8", hdr)

    def _get_buildfile(self, path, query, extra):
        # TC-BUILDFILE (decision 0034): the game's .build JSON as a
        # download the player saves; the core writes no file anywhere.
        # The name comes from buildfile.filename (letters, digits, -).
        out = self.server.core.builds.file_export()
        if out is None:
            return self._json(404, {"error": "no build loaded"}, extra)
        hdr = dict(extra, **{"Content-Disposition":
                             f'attachment; filename="{out["filename"]}"'})
        return self._send(200, out["text"], "application/json; charset=utf-8", hdr)

    def _get_settings_export(self, path, query, extra):
        # UX-SETTINGS-IO (ruling E): AshLight's own settings as a
        # download the player saves; allow-list only (no contact,
        # token, cookie or path); the core writes no file anywhere.
        hdr = dict(extra, **{"Content-Disposition":
                             f'attachment; filename="{settingsio.FILE_NAME}"'})
        text = json.dumps(self.server.core.export_settings(), indent=2,
                          ensure_ascii=True) + "\n"
        return self._send(200, text, "application/json; charset=utf-8", hdr)

    def _get_weights(self, path, query, extra):
        return self._json(200, self.server.core.weights.snapshot(), extra)

    def _get_gfx(self, path, query, extra):
        # GFX-ADVISOR: recommend only; never touches the game's files.
        return self._json(200, self.server.gfx.get(), extra)

    def _get_rates(self, path, query, extra):
        # DATA-NINJA: cached rates with their age, never a blocking fetch;
        # a due refresh (opt-in on, at most hourly) runs in the background.
        rates = self.server.core.rates
        self.server.core.note_rates_read()  # DATA-PRICE-REFRESH-CORE: keeps the loop refreshing
        started = rates.refresh_async()
        doc = rates.snapshot()
        doc["refreshing"] = bool(doc["refreshing"] or started)
        return self._json(200, doc, extra)

    def _get_web_data(self, path, query, extra):
        return self._json(200, self._web_data_doc(), extra)

    def _get_events(self, path, query, extra):
        if self.command == "HEAD":
            # AUDIT-HTTP-HARDEN S1: HEAD never opens the endless stream.
            return self._send(405, "use GET\n", extra={**extra, "Allow": "GET"})
        return self._sse(extra, query)

    # -- POST routes
    def _post_clipboard_read(self, path, query, extra):
        # Decision 0003: the clipboard is read ONLY once per manual press
        # of an AshLight hotkey, never by a watcher or a timer, and
        # AshLight never sends Ctrl+C or any other input to the game.
        # Not implemented yet (ROADMAP); this stub stays a 501.
        return self._json(501, {"error": "not implemented",
                                "policy": "docs/decisions/0003-read-policy.md"})

    def _plug(self, verb, path, query, extra):
        """RUN-SEAMS (decision 0056): the fall-through after the built-in
        routes. _guard already ran (Host, Origin, Sec-Fetch-Site, token);
        plug.route answers only an exact /api/ path, so nothing outside
        /api/ (and nothing token-free) is ever a plug route."""
        fn = plug.route(verb, path) if self._needs_token(path) else None
        if fn is None:
            return self._send(404, "not found\n")
        return fn(self, query, extra)

    def _hints(self, path, query, extra):
        """NEWBIE-HINTS: {"reset": true} shows the new-character tips
        again."""
        body = self._read_json()
        if body is None:
            return None
        if body.get("reset") is not True:
            return self._json(400, {"error": "reset: true required"})
        return self._json(200, {"text": self.server.core.reset_hints()})

    def _overlay_sample(self, path, query, extra):
        """OVL-CARD-SLOT: the Settings button's sample card. A JSON object
        body (empty is fine); the card shows on the overlay for 10 s and
        leaves by itself. Display state only: nothing is recorded and
        nothing is sent to the game."""
        body = self._read_json()
        if body is None:
            return None
        card = self.server.core.show_overlay_sample()
        return self._json(200, {"card": card})

    def _settings_import(self, path, query, extra):
        """UX-SETTINGS-IO: the settings file the player picked in the
        browser, as its JSON. Size-capped; allow-list keys only; nothing
        applied on a bad file; web data never switched on here."""
        body = self._read_json(max_body=settingsio.MAX_BYTES)
        if body is None:
            return None
        try:
            report = self.server.core.import_settings(body)
        except settingsio.SettingsError as e:
            return self._json(400, {"error": str(e)})
        except OSError:
            return self._json(500, {"error": SAVE_FAILED})
        return self._json(200, report)

    def _run_history(self, path, query, extra):
        """UTIL-RUN-HISTORY: {"enabled": bool} turns it on or off,
        {"clear": true} deletes every saved run."""
        body = self._read_json()
        if body is None:
            return None
        enabled = body.get("enabled")
        clear = body.get("clear") is True
        if not (isinstance(enabled, bool) or clear):
            return self._json(400, {"error": "enabled: true|false or clear: true required"})
        try:
            view = self.server.core.set_history(enabled if isinstance(enabled, bool) else None,
                                                clear=clear)
        except OSError:  # AREA-AUDIT P5-1: a broken config is never overwritten
            return self._json(500, {"error": SAVE_FAILED})
        return self._json(200, {"run_history": view})

    def _price_watch(self, path, query, extra):
        """UTIL-PRICE-WATCH: {"clear": true} empties the watched list."""
        body = self._read_json()
        if body is None:
            return None
        if body.get("clear") is not True:
            return self._json(400, {"error": "clear: true required"})
        try:
            view = self.server.core.clear_watch()
        except OSError:  # AREA-AUDIT P5-1: the runtime file could not be written
            return self._json(500, {"error": SAVE_FAILED})
        return self._json(200, {"price_watch": view})

    def do_PUT(self):
        path, query = self._url()
        # an unknown PUT path is 405 before the token check, as it always
        # was; a known one runs only after _guard
        fn = route_for(PUT_ROUTES, path)
        if fn is None:
            return self._not_allowed()
        extra = self._guard(path, query, self._needs_token(path))
        if extra is None:
            return None
        return fn(self, path, query, extra)

    def _not_allowed(self):
        if self._cross_site():  # SEC-CROSS-SITE: every route, 405 ones too
            return self._send(403, "cross-site request refused\n")
        return self._send(405, "method not allowed\n")

    do_DELETE = _not_allowed
    do_PATCH = _not_allowed
    do_OPTIONS = _not_allowed

    def parse_request(self):
        self._body_done = False  # per request: the body is not read yet
        return super().parse_request()

    def _discard_unread(self):
        """FLAKY-EVAL-API: every reply sent before the body was read (the
        400 / 403 / 401 guard, 404, 405, 501) drains it first. Replying and
        closing with request bytes still unread makes Windows reset the
        connection, and the client loses the reply (WinError 10053 / 10054).
        Once per request; a request without a body costs nothing."""
        if getattr(self, "_body_done", True):
            return
        self._body_done = True
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length:
            self._discard_body(length)

    def _discard_body(self, length):
        """TEST-413-FLAKE: before an early error reply, read and drop a
        rejected body of at most DRAIN_MAX bytes within DRAIN_TIMEOUT_S, so
        the client finishes sending and the close is not a reset (WinError
        10053 / 10054 on the client). Bounded both ways, never an unbounded
        read; past the cap, a bad length or a timeout the connection just
        closes after the reply."""
        self.close_connection = True
        if length <= 0 or length > DRAIN_MAX:
            return
        sock = self.connection
        old = sock.gettimeout()
        end = time.monotonic() + DRAIN_TIMEOUT_S
        left = length
        try:
            while left > 0:
                rem = end - time.monotonic()
                if rem <= 0:
                    return
                sock.settimeout(rem)
                chunk = self.rfile.read1(min(left, 65536))
                if not chunk:
                    return
                left -= len(chunk)
        except (OSError, ValueError):
            return
        finally:
            with contextlib.suppress(OSError):
                sock.settimeout(old)

    # -- endpoints
    def _read_json(self, max_body=MAX_BODY):
        """The JSON object body, or None after sending the error reply."""
        self._body_done = True  # read or discarded below, never twice
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if ctype != "application/json":
            self._discard_body(length)
            self._json(415, {"error": "application/json required"})
            return None
        if length < 0 or length > max_body:
            self._discard_body(length)
            self._json(413, {"error": "body too large"})
            return None
        try:
            raw = self.rfile.read(length)
        except OSError:  # TEST-HTTP: body shorter than its length (timeout) or reset
            self.close_connection = True
            return None
        if len(raw) < length:  # the client closed mid-body: nobody to answer
            self.close_connection = True
            return None
        try:
            body = json.loads(raw or b"{}")
        except (ValueError, RecursionError):  # TEST-HTTP: deep nesting too
            self._json(400, {"error": "bad json"})
            return None
        if not isinstance(body, dict):
            self._json(400, {"error": "json object required"})
            return None
        return body

    def _filter_merge(self, path, query, extra):
        """UTIL-FILTER-MERGE (decision 0033): the filter the player picked in
        the browser, as raw bytes, comes back with AshLight's Show blocks
        prepended, as a download. Body in memory only; the name, path and
        content are never logged or stored; the core writes no file."""
        self._body_done = True  # read or discarded below, never twice
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if ctype != "application/octet-stream":
            self._discard_body(length)
            return self._json(415, {"error": "application/octet-stream required"})
        if length < 0 or length > lootfilter.MAX_MERGE_BYTES:
            self._discard_body(length)
            return self._json(413, {"error": lootfilter.REFUSED_TEXT["too_big"]})
        try:
            raw = self.rfile.read(length)
        except OSError:
            self.close_connection = True
            return None
        if len(raw) < length:
            self.close_connection = True
            return None
        core = self.server.core
        names = getattr(core, "base_names", None)
        names = names.get() if names is not None else None
        rates = getattr(core, "rates", None)
        prices = rates.filter_prices() if rates is not None else None
        try:
            out = lootfilter.merge(raw, core.builds.build, names, prices)
        except lootfilter.MergeRefused as exc:
            return self._json(400, {"error": str(exc), "reason": exc.reason})
        name = lootfilter.out_name((query.get("name") or [""])[0])
        hdr = {"Content-Disposition": f'attachment; filename="{name}"'}
        return self._send(200, out, "application/octet-stream", hdr)

    def _layout_doc(self):
        core = self.server.core
        return {"layout": core.overlay_layout(), "displays": core.displays(),
                "corners": list(layout.CORNERS),
                "limits": {"scale": [layout.SCALE_MIN, layout.SCALE_MAX],
                           "opacity": [layout.OPACITY_MIN, layout.OPACITY_MAX],
                           "margin": [0, layout.MARGIN_MAX]}}

    def _set_layout(self, path, query, extra):
        body = self._read_json()
        if body is None:
            return None
        try:
            self.server.core.set_overlay_layout(body)
        except layout.LayoutError as e:
            if e.__cause__ is not None:
                # SEC-CROSS-SITE: config/local.json unreadable; the OS text
                # (it names a path) goes to the log as its type only
                log.warning("overlay layout not saved: config unreadable (%s)",
                            type(e.__cause__).__name__)
                return self._json(500, {"error": LAYOUT_READ_FAILED})
            return self._json(400, {"error": str(e)})
        except OSError as e:
            log.warning("overlay layout not saved (%s)", type(e).__name__)
            return self._json(500, {"error": SAVE_FAILED})
        return self._json(200, self._layout_doc())

    def _trade_dismiss(self, path, query, extra):
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

    def _web_data_doc(self):
        core = self.server.core
        return {"web_data": core.web_data_enabled(),
                # decision 0017: the trade link is built offline, so it is
                # no web-data use; the app calls no trade-site endpoint
                "uses": ["poe.ninja currency rates", "poe.ninja unique and stackable item values",
                         "build share links you paste"],
                # UA-CONTACT: rates also need the contact (config/local.json
                # "contact", typed in the dashboard: DATA-CONTACT-FIELD);
                # write-only, the value is never echoed, only contact_set.
                "contact_set": core.contact() is not None,
                "needs_contact": ["poe.ninja currency rates", "poe.ninja unique and stackable item values"],
                "blocked": core.web_blocked_reason(),
                # DATA-LEAGUE-PICKER-API (F-141): the league picker reads the
                # setting, the auto league, the league prices come from (a
                # solo league maps to its trade league) and the cached names
                "league": core.league_setting(),
                "league_auto": core.league_auto(),
                "prices_from": core.trade_league(),
                "leagues": core.league_names(),
                "policy": "docs/decisions/0013-web-data.md"}

    def _set_web_data(self, path, query, extra):
        """The one web-data opt-in (decision 0013), default off.
        DATA-CONTACT-FIELD (F-018): the body holds "enabled" (bool) and / or
        "contact" (text; '' removes it). Both are checked before anything is
        written; the contact is stored only in config/local.json and the
        answer says only contact_set, never the value.
        DATA-LEAGUE-PICKER-API (F-141): an optional "league" (text) sets
        the "league" key to a league of the cached list ('' clears it, so
        the auto league is followed again); checked first like the rest."""
        refused = ("AshLight can't use that contact. Use up to 120 plain "
                   "characters, without brackets or a backslash.")
        league_refused = ("AshLight can't price that league. Pick one from the "
                          "list, or the automatic league.")
        body = self._read_json()
        if body is None:
            return None
        has_on, has_contact = "enabled" in body, "contact" in body
        has_league = "league" in body
        if not (has_on or has_contact or has_league) or (
                has_on and not isinstance(body["enabled"], bool)):
            return self._json(400, {"error": "enabled: true|false required"})
        contact = body.get("contact")
        if has_contact and not (isinstance(contact, str) and (
                not contact.strip() or webfetch.clean_contact(contact) is not None)):
            return self._json(400, {"error": refused})
        core = self.server.core
        if has_league:
            try:
                core.league_choice(body["league"])
            except ValueError:
                return self._json(400, {"error": league_refused})
        try:
            if has_league:
                core.set_league(body["league"])
            if has_contact:
                core.set_contact(contact)
            if has_on:
                core.set_web_data(body["enabled"])
        except ValueError:
            return self._json(400, {"error": refused})
        except OSError:  # AREA-AUDIT P5-1: a broken config is never overwritten
            return self._json(500, {"error": SAVE_FAILED})
        return self._json(200, self._web_data_doc())

    def _set_hotkey(self, path, query, extra):
        """HOTKEYS-LIVE (decision 0058, OVL-KEYS-CORE): {"name": "eval" |
        "toggle", "key": str} stores one shortcut in config/local.json; the
        desktop client re-registers it by itself. A game key or the other
        shortcut's key is refused (400, settingsio's sentence). The core
        registers nothing and sends nothing to the game."""
        body = self._read_json()
        if body is None:
            return None
        name, key = body.get("name"), body.get("key")
        if not isinstance(name, str) or not isinstance(key, str):
            return self._json(400, {"error": 'name: "eval"|"toggle" and key: text required'})
        try:
            view = self.server.core.set_hotkey(name, key)
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except OSError:  # AREA-AUDIT P5-1: a broken config is never overwritten
            return self._json(500, {"error": SAVE_FAILED})
        return self._json(200, {"hotkeys": view})

    def _build_code(self, path, query, extra):
        """TC-CODE / TC-JSON / TC-URL: load a pasted build (JSON {"code":
        text}, or a character object {"character": {...}}). The format (PoB
        code, share URL, character JSON) is auto-detected; codes decode
        locally; a share URL is fetched once per paste through
        theorycraft/shareurl.py, only with the web-data opt-in on."""
        body = self._read_json(MAX_BUILD_BODY)
        if body is None:
            return None
        code = body.get("code")
        if code is None and isinstance(body.get("character"), dict):
            code = json.dumps({"character": body["character"]})
        if not isinstance(code, str):
            return self._json(400, {"error": "code (string) required"})
        core = self.server.core
        try:
            if build_paste.detect(code) == "url":
                core.load_share_url(code)
            else:
                core.builds.load_code(code)
        except webfetch.WebDataOff:
            return self._json(422, {"error": "web data is off: turn it on to load "
                                    "share links, or paste the build code itself",
                                    "kind": "url", "web_data": False})
        except webfetch.UrlNotAllowed as e:
            return self._json(422, {"error": f"share link not supported: {e}",
                                    "kind": "url", "hosts": list(shareurl.ALLOWED_HOSTS)})
        except webfetch.FetchError as e:
            # SEC-CROSS-SITE: a fixed sentence; the detail (it can hold OS
            # text, a host or the query) goes to the log as types only
            log.warning("share link fetch failed (%s%s)", type(e).__name__,
                        f" from {type(e.__cause__).__name__}" if e.__cause__ else "")
            return self._json(502, {"error": SHARE_FETCH_FAILED, "kind": "url"})
        except build_codec.ShareUrlError as e:
            return self._json(422, {"error": str(e), "kind": "url"})
        except (build_codec.CodeError, build_model.BuildError) as e:
            return self._json(400, {"error": str(e)})
        return self._json(200, core.builds.snapshot())

    def _eval(self, path, query, extra):
        """TC-EVAL: score item text ({"item": text, "slot": optional}) against
        the loaded build with the stored weights. The text comes from the
        caller (the one per-press clipboard read, decision 0003); this
        endpoint never reads the clipboard and sends nothing to the game.
        TC-PRESS-BUILD (ruling Q-02): a PoB code, character JSON or share
        link in that text loads the build instead (core.eval_press, the
        paste box's rules: a share link only with web data on) and the
        answer is the press doc (status "loaded" or "refused").
        TC-PRESS-STAGED-LIVE (decision 0024 amendment 2026-11-19): the reply
        is the first stage's result (the stat-weight card); with the calc on,
        Path of Building's numbers reach the state card later as updates of
        the same press, so the reply never waits on the calc."""
        body = self._read_json(MAX_EVAL_BODY)
        if body is None:
            return None
        text = body.get("item")
        # TC-EVAL-UI: a blank string (an empty clipboard at the hotkey press)
        # is checked too, so the overlay can say "Not an item".
        if not isinstance(text, str):
            return self._json(400, {"error": "item (string) required"})
        slot = body.get("slot")
        if slot is not None and (not isinstance(slot, str) or len(slot) > 40):
            return self._json(400, {"error": "slot must be a short string"})
        # TC-EVAL-UI: the result is also published in the state (dashboard
        # and overlay card) and re-scored when the weights or build change.
        # PRICE-TRADE-LINK (decision 0017): the same press builds one
        # offline trade-search link (no second clipboard read, no request to
        # the trade site; the core never opens it). It arrives in the state
        # (`price`, the decision 0016 card, status "link" with `url`) with
        # the same press time as the eval.
        result = self.server.core.eval_press(text, slot or None)
        return self._json(200, result)

    def _wear(self, path, query, extra):
        """TC-WORN-WIRE (decision 0052): file the last checked item as the
        worn item of its slot ({} or {"slot": optional}), or the item text
        the optional wear key's own press sends ({"item": text}). The text
        comes from the caller (the one per-press clipboard read of decision
        0003); this endpoint never reads the clipboard. The reply is
        {"worn": {"ok", "slot", "error"}}; nothing is stored while the
        worn_gear switch is off."""
        body = self._read_json(MAX_EVAL_BODY)
        if body is None:
            return None
        text = body.get("item")
        if text is not None and not isinstance(text, str):
            return self._json(400, {"error": "item must be a string"})
        slot = body.get("slot")
        if slot is not None and (not isinstance(slot, str) or len(slot) > 40):
            return self._json(400, {"error": "slot must be a short string"})
        try:
            doc = self.server.core.wear(slot=slot or None, text=text)
        except OSError:  # the worn file could not be written
            return self._json(500, {"error": WEAR_SAVE_FAILED})
        return self._json(200, {"worn": doc})

    def _put_weights(self, path, query, extra):
        body = self._read_json(MAX_WEIGHTS_BODY)
        if body is None:
            return None
        try:
            self.server.core.weights.put(body)
        except tc_weights.WeightsError as e:
            return self._json(400, {"error": str(e)})
        self.server.core.last_eval.rerun()  # TC-EVAL-UI: re-score at once
        return self._json(200, self.server.core.weights.snapshot())

    def _consent(self, path, query, extra):
        """POST /api/consent: {"consent": bool, "path"?} records the
        Client.txt opt-in; {"ledger": bool} (decision 0071) records the
        parse ledger's own opt-in, alone or after "consent" in one body.
        At least one of the two is required and each must be a bool."""
        body = self._read_json()
        if body is None:
            return None
        has_consent = "consent" in body
        has_ledger = "ledger" in body
        if not (has_consent or has_ledger) or (
                has_consent and not isinstance(body.get("consent"), bool)):
            return self._json(400, {"error": "consent: true|false required"})
        if has_ledger and not isinstance(body.get("ledger"), bool):
            return self._json(400, {"error": "ledger: true|false required"})
        path = body.get("path")
        if path is not None and not isinstance(path, str):
            return self._json(400, {"error": "path must be a string"})
        core = self.server.core
        try:
            if has_consent:
                rec = core.record_consent(body["consent"], path or None)
            if has_ledger:
                rec = core.record_ledger_consent(body["ledger"])
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        return self._json(200, {"consent": rec, "state": core.state.snapshot()})

    def _static(self, rel):
        """SEC-STATIC-MAP: an exact name lookup in the listing of web/; the
        request text never reaches a file system call."""
        smap = self.server.static
        if smap is None:
            return self._send(404, "no web root\n")
        target = smap.lookup(rel, getattr(self.server.core, "reload_web", 0))
        if target is None:
            return self._send(404, "not found\n")
        return self._file(target)

    def _file(self, target):
        if target is None or not Path(target).is_file():
            return self._send(404, "not found\n")
        target = Path(target)
        ctype = TYPES.get(target.suffix.lower()) or (
            mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        return self._send(200, target.read_bytes(), ctype)

    def _sse(self, extra, query=None):
        srv = self.server
        if not srv.sse_slots.acquire(blocking=False):
            # A non-200 reply makes an EventSource give up for good (the
            # overlay would stay offline); a 200 stream that only sets a long
            # retry and closes makes it come back on its own (ZERO-CLICK).
            self.close_connection = True
            return self._send(200, "retry: %d\nevent: busy\ndata: {}\n\n"
                              % SSE_BUSY_RETRY_MS, "text/event-stream; charset=utf-8",
                              dict(extra, **{"Retry-After": str(SSE_BUSY_RETRY_MS // 1000)}))
        try:
            tap = bool(srv.events_tap) and (query or {}).get("tap") == ["1"]
            return self._sse_stream(extra, tap)
        finally:
            srv.sse_slots.release()

    def _sse_stream(self, extra, tap=False):
        """State frames, a reload notice and heartbeats. With tap (a dev
        tap, source checkout only) each push also carries an "events" frame
        of tap_event() rows."""
        srv = self.server
        core = srv.core
        sub = core.bus.subscribe()
        try:
            self.send_response(200)
            self._count_reply(200)
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
            # HOT-RELOAD (decision 0042): a web/ change bumps
            # core.reload_web; each stream says "reload" once per bump
            sent_reload = getattr(core, "reload_web", 0)
            while not srv.stopping.is_set():
                now = time.monotonic()
                beat_in = SSE_HEARTBEAT_S - (now - last_beat)
                # TEST-FULLSTACK-SSE-IDLE: a version bump with no event (the
                # core loop tick: idle, the summary card, calc / price book
                # status) wakes this wait (bus.wake_all) and is pushed now.
                dirty = core.state.version != sent_version
                if pending or dirty:
                    wait = max(0.0, SSE_MIN_INTERVAL_S - (now - last_push))
                else:
                    wait = min(SSE_WAIT_MAX_S, max(0.0, beat_in))
                got = sub.get(timeout=wait)
                if self._client_gone():
                    break
                reload_web = getattr(core, "reload_web", 0)
                if reload_web != sent_reload:
                    sent_reload = reload_web
                    self._sse_write(self._sse_msg("reload", {"target": "web",
                                                             "seq": reload_web}))
                pending.extend(got)
                now = time.monotonic()
                if pending and now - last_push >= SSE_MIN_INTERVAL_S:
                    # SEC-SSE-TAP: by default a bus event only triggers the
                    # state push; the events frame goes to the tap only
                    chunk = (self._sse_msg("events", [tap_event(ev) for ev in pending])
                             if tap else "")
                    pending = []
                    snap = core.state.snapshot()
                    if snap["version"] != sent_version:
                        sent_version = snap["version"]
                        chunk += self._sse_msg("state", snap)
                    if chunk:
                        self._sse_write(chunk)
                        last_push = last_beat = now
                elif (not pending and core.state.version != sent_version
                      and now - last_push >= SSE_MIN_INTERVAL_S):
                    snap = core.state.snapshot()
                    sent_version = snap["version"]
                    self._sse_write(self._sse_msg("state", snap))
                    last_push = last_beat = now
                elif now - last_beat >= SSE_HEARTBEAT_S:
                    # A state can change with no log event (a trade card
                    # expiring, DS-TRADE-EXPIRE): the heartbeat sends it.
                    snap = core.state.snapshot()
                    if snap["version"] != sent_version:
                        sent_version = snap["version"]
                        self._sse_write(self._sse_msg("state", snap))
                        last_push = now
                    else:
                        self._sse_write(": hb\n\n")
                    last_beat = now
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            sub.close()
            self.close_connection = True

    def _client_gone(self):
        """SOAK-1: True once the SSE client closed its end. The loop wakes
        at least every SSE_WAIT_MAX_S, so a dropped tab frees its slot,
        subscription and thread within about a second instead of after two
        failed writes (up to two heartbeats)."""
        try:
            readable, _, _ = select.select([self.connection], [], [], 0)
            if not readable:
                return False
            return self.connection.recv(1, socket.MSG_PEEK) == b""
        except (OSError, ValueError):
            return True

    @staticmethod
    def _sse_msg(event, data):
        return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

    def _sse_write(self, text):
        data = text.encode("utf-8")
        self.wfile.write(data)
        self.wfile.flush()
        metrics.inc("sse.frames")  # RUN-METRICS-CORE (decision 0067)
        metrics.inc("sse.bytes", len(data))


def route_label(path):
    """RUN-METRICS-CORE: the counter key of a request path: a built-in
    route key, a plug route path, or "other". Never request text."""
    if not isinstance(path, str):
        return "other"
    for table in (GET_ROUTES, POST_ROUTES, PUT_ROUTES):
        if path in table and not path.endswith("*"):
            return path
        for key in table:
            if key.endswith("*") and path.startswith(key[:-1]):
                return key
    if plug.route("GET", path) is not None or plug.route("POST", path) is not None:
        return path
    return "other"


def route_for(table, path):
    """The route function for path in one verb table, or None. A key that
    ends in "*" is a prefix route; an exact key wins over a prefix."""
    fn = None if path.endswith("*") else table.get(path)
    if fn is not None:
        return fn
    for key, prefix_fn in table.items():
        if key.endswith("*") and path.startswith(key[:-1]):
            return prefix_fn
    return None


# TEST-HTTP-ROUTES (F-193): the built-in routes, one table per verb. Each
# function is called as fn(handler, path, query, extra) after _guard; HEAD
# runs the GET table. A path no table holds falls through to plug.route
# (GET / POST, decision 0056) or is 405 (PUT). tests/test_security_surface.py
# reads these keys and pins them.
GET_ROUTES = {
    "/": Handler._get_index,
    "/index.html": Handler._get_index,
    "/web/*": Handler._get_web,
    "/tokens.css": Handler._get_tokens_css,
    "/favicon.ico": Handler._get_favicon,
    "/api/hello": Handler._get_hello,
    "/api/health": Handler._get_health,
    "/api/version": Handler._get_version,
    "/api/state": Handler._get_state,
    "/api/overlay-layout": Handler._get_layout,
    "/api/build": Handler._get_build,
    "/api/filter": Handler._get_filter,
    "/api/buildfile": Handler._get_buildfile,
    "/api/settings-export": Handler._get_settings_export,
    "/api/weights": Handler._get_weights,
    "/api/gfx": Handler._get_gfx,
    "/api/rates": Handler._get_rates,
    "/api/web-data": Handler._get_web_data,
    "/events": Handler._get_events,
}

POST_ROUTES = {
    "/api/clipboard-read": Handler._post_clipboard_read,
    "/api/consent": Handler._consent,
    "/api/overlay-layout": Handler._set_layout,
    "/api/trade-dismiss": Handler._trade_dismiss,
    "/api/build-code": Handler._build_code,
    "/api/eval": Handler._eval,
    "/api/web-data": Handler._set_web_data,
    "/api/filter-merge": Handler._filter_merge,
    "/api/settings-import": Handler._settings_import,
    "/api/run-history": Handler._run_history,
    "/api/price-watch": Handler._price_watch,
    "/api/hints": Handler._hints,
    "/api/wear": Handler._wear,  # TC-WORN-WIRE
    "/api/hotkeys": Handler._set_hotkey,  # HOTKEYS-LIVE (OVL-KEYS-CORE)
    "/api/overlay-sample": Handler._overlay_sample,  # OVL-CARD-SLOT
}

PUT_ROUTES = {
    "/api/weights": Handler._put_weights,
}


def serve(core, token, port=ports.AL_PORT, web_root=None, tokens_css=None):
    """Build the server (bound, not yet serving)."""
    return ALServer(core, token, port=port, web_root=web_root, tokens_css=tokens_css)
