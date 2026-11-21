"""TC-GGG-LISTENER: the one-shot loopback listener for the OAuth redirect.

Decision 0048 item 3: the browser redirect of AshLight's GGG OAuth client
lands on the loopback CALLBACK_PATH on the first port of
ports.OAUTH_REDIRECT_PORTS (the second is the fallback). A browser
redirect cannot carry the core's per-start token (research 0035 R2), so
the redirect gets its own listener instead of a core route.

The listener:
- binds ports.LOOPBACK only, on ports.OAUTH_REDIRECT_PORTS in order (the
  first free one), or on the port a caller injects (tests use a leased
  test port, never a redirect port); exclusive bind on Windows, so no other
  process can share the port;
- accepts ONE connection, then closes, whatever that request held; a
  timeout with no request also closes it and hands back nothing;
- checks the method (GET), the path (CALLBACK_PATH, exact), the Host
  header (exactly 127.0.0.1:<bound port>) and the state (constant-time
  compare against the state the caller made), and takes exactly one
  `code` value of plain URL-safe characters;
- answers every request with one fixed page that carries no token, no
  code and no state, so nothing the browser keeps (history, cache, a
  screenshot) holds a secret;
- hands back only the code (or None); it never logs the request line, the
  code or the state.

Standard library socket only: no transport, no token exchange (TC-IMPORT
wires this to the token request). Nothing in play listens until then.
"""

import hmac
import re
import socket
import time
from urllib.parse import parse_qs, urlsplit

from . import ports

CALLBACK_PATH = "/oauth/callback"
DEFAULT_TIMEOUT_S = 300.0  # the player has five minutes to approve
READ_TIMEOUT_S = 10.0  # one connection may take at most this long to send
MAX_REQUEST = 8192  # bytes of request head read; more is refused
MAX_CODE = 512  # characters of an authorization code
_CODE_RE = re.compile(r"[A-Za-z0-9._~-]+")

REPLY_PAGE = (
    b"<!doctype html>\n"
    b"<html lang=\"en\"><head><meta charset=\"utf-8\">"
    b"<title>AshLight</title></head>\n"
    b"<body><p>AshLight got the reply from the sign-in page. "
    b"You can close this tab and go back to AshLight.</p></body></html>\n"
)
_HEADERS = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/html; charset=utf-8\r\n"
    b"Cache-Control: no-store\r\n"
    b"Referrer-Policy: no-referrer\r\n"
    b"X-Content-Type-Options: nosniff\r\n"
    b"Content-Security-Policy: default-src 'none'\r\n"
    b"Connection: close\r\n"
)


class ListenerError(Exception):
    """No redirect port could be bound on the loopback address."""


def redirect_uri(port):
    """The redirect URI registered for port (a redirect port in play)."""
    return f"http://{ports.LOOPBACK}:{int(port)}{CALLBACK_PATH}"


def reply_bytes():
    """The one fixed HTTP answer (headers and page) sent to every request."""
    return (_HEADERS + b"Content-Length: " + str(len(REPLY_PAGE)).encode("ascii")
            + b"\r\n\r\n" + REPLY_PAGE)


def _bind(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((ports.LOOPBACK, int(port)))
        sock.listen(1)
    except OSError:
        sock.close()
        raise
    return sock


def check_request(head, state, port):
    """The code in one raw request head (bytes), or None when the method,
    path, Host, state or code is wrong. Pure; the listener calls it."""
    if not isinstance(head, (bytes, bytearray)) or not state:
        return None
    try:
        text = bytes(head).decode("ascii")
    except UnicodeDecodeError:
        return None
    lines = text.split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) != 3 or parts[0] != "GET" or not parts[2].startswith("HTTP/1."):
        return None
    target = urlsplit(parts[1])
    if target.scheme or target.netloc or target.path != CALLBACK_PATH:
        return None
    hosts = [ln.split(":", 1)[1].strip() for ln in lines[1:]
             if ln.lower().startswith("host:")]
    if hosts != [f"{ports.LOOPBACK}:{int(port)}"]:
        return None
    try:
        query = parse_qs(target.query, keep_blank_values=True,
                         strict_parsing=bool(target.query), max_num_fields=8)
    except ValueError:
        return None
    states = query.get("state") or []
    codes = query.get("code") or []
    if len(states) != 1 or len(codes) != 1 or "error" in query:
        return None
    if not hmac.compare_digest(states[0].encode("utf-8"),
                               str(state).encode("utf-8")):
        return None
    code = codes[0]
    if not code or len(code) > MAX_CODE or not _CODE_RE.fullmatch(code):
        return None
    return code


def _read_head(conn, deadline):
    buf = b""
    while b"\r\n\r\n" not in buf:
        left = deadline - time.monotonic()
        if left <= 0 or len(buf) > MAX_REQUEST:
            return None
        conn.settimeout(min(left, READ_TIMEOUT_S))
        try:
            chunk = conn.recv(MAX_REQUEST + 1 - len(buf))
        except OSError:
            return None
        if not chunk:
            return None
        buf += chunk
    head = buf.split(b"\r\n\r\n", 1)[0]
    return head if len(head) <= MAX_REQUEST else None


class OneShotListener:
    """One request on the loopback redirect port, then closed.

    listener = OneShotListener(state)            # first free redirect port
    url = redirect_uri(listener.port)            # goes into the auth URL
    code = listener.wait()                       # the code, or None

    port injects the port (tests); timeout_s bounds wait()."""

    def __init__(self, state, port=None, timeout_s=DEFAULT_TIMEOUT_S):
        if not state:
            raise ValueError("a non-empty state is required")
        self._state = str(state)
        self._timeout_s = float(timeout_s)
        self._sock = None
        self.port = None
        self.closed = False
        candidates = ports.OAUTH_REDIRECT_PORTS if port is None else (int(port),)
        for cand in candidates:
            try:
                self._sock = _bind(cand)
            except OSError:
                continue
            self.port = int(self._sock.getsockname()[1])
            break
        if self._sock is None:
            self.closed = True
            raise ListenerError("no OAuth redirect port could be bound on "
                                f"{ports.LOOPBACK}")

    @property
    def address(self):
        """(host, port) the socket is bound to, or None once closed."""
        return None if self._sock is None else self._sock.getsockname()[:2]

    def close(self):
        """Close the listening socket (idempotent)."""
        sock, self._sock = self._sock, None
        self.closed = True
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def wait(self):
        """Serve one request (or time out), close, and return the code or None."""
        if self._sock is None:
            return None
        deadline = time.monotonic() + max(0.0, self._timeout_s)
        try:
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            self._sock.settimeout(left)
            try:
                conn, _addr = self._sock.accept()
            except OSError:  # socket.timeout is an OSError
                return None
            self.close()  # one request only: nothing else may connect
            with conn:
                head = _read_head(conn, deadline)
                code = None if head is None else check_request(
                    head, self._state, self.port)
                try:
                    conn.settimeout(READ_TIMEOUT_S)
                    conn.sendall(reply_bytes())
                except OSError:
                    pass
                return code
        finally:
            self.close()
