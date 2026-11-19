"""SEC-HELLO-CORE: clients prove the core before they send the token.

GET /api/hello (decision 0054). The client makes a fresh 128-bit nonce and
sends it with HMAC-SHA256(token, "client" + nonce) in two request headers,
never the token itself. The core checks that proof in constant time (the
proof is this route's token gate: no valid proof, 401) and answers
HMAC-SHA256(token, "server" + nonce + the port it bound). The client checks
the answer and that the port is the one it dialled, and only then sends the
token. A foreign listener learns one MAC over a nonce it cannot choose; the
role tags stop a client proof being reflected as a server answer; the bound
port in the answer stops a listener on a wrong port relaying the challenge
to the real core.

The key is the token's ASCII text; every message is ASCII: the role tag,
the nonce as 32 lowercase hex digits, and (server only) the port in
decimal. The nonce has a fixed length, so the concatenation is unambiguous.

verify() is the Python client (the supervisor): no proxy, a per-token cache
so the handshake runs once per token value, cleared by forget() after any
request error. Nothing here looks at a process (clear of decision 0029).
"""

import hashlib
import hmac
import json
import os
import re
import threading
import urllib.request

from . import ports

PATH = "/api/hello"
NONCE_HEADER = "X-AL-Hello-Nonce"
PROOF_HEADER = "X-AL-Hello-Proof"
NONCE_BYTES = 16  # 128 bits
MAX_ANSWER = 4096  # bytes of an answer read by verify()
_NONCE_RE = re.compile(r"[0-9a-f]{32}")
_PROOF_RE = re.compile(r"[0-9a-f]{64}")

# Loopback only: an empty ProxyHandler ignores http_proxy and the system
# proxy (SEC-NO-PROXY), so neither the proof nor the token reaches a proxy.
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_lock = threading.Lock()
_verified = set()  # (port, sha256 of the token); never the token itself


def new_nonce():
    """A fresh 128-bit nonce as 32 lowercase hex digits."""
    return os.urandom(NONCE_BYTES).hex()


def _mac(token, text):
    return hmac.new(str(token).encode("ascii"), text.encode("ascii"),
                    hashlib.sha256).hexdigest()


def client_proof(token, nonce):
    """HMAC-SHA256(token, "client" + nonce), hex."""
    return _mac(token, "client" + str(nonce))


def server_proof(token, nonce, port):
    """HMAC-SHA256(token, "server" + nonce + port), hex."""
    return _mac(token, "server" + str(nonce) + str(int(port)))


def valid_nonce(nonce):
    return isinstance(nonce, str) and _NONCE_RE.fullmatch(nonce) is not None


def check_client(token, nonce, proof):
    """True when proof is the client proof of nonce under token. The nonce
    and proof shapes are checked first; the MAC compares in constant time."""
    if not token or not valid_nonce(nonce):
        return False
    if not isinstance(proof, str) or _PROOF_RE.fullmatch(proof) is None:
        return False
    try:
        want = client_proof(token, nonce)
    except UnicodeEncodeError:
        return False
    return hmac.compare_digest(want, proof)


def answer(token, nonce, port):
    """The core's reply body for a checked request."""
    return {"port": int(port), "proof": server_proof(token, nonce, port)}


def _key(port, token):
    return int(port), hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def is_verified(port, token):
    with _lock:
        return _key(port, token) in _verified


def forget(port=None):
    """Drop the cached verification (of one port, or all). Called after any
    request error, so the next call proves the listener again."""
    with _lock:
        if port is None:
            _verified.clear()
        else:
            for k in [k for k in _verified if k[0] == int(port)]:
                _verified.discard(k)


def verify(port, token, opener=None, timeout=3.0):
    """True when the listener on 127.0.0.1:port proves it holds token and
    bound that port. Cached per (port, token value); a failure of any kind
    clears the port's cache entry. The token itself is never sent."""
    port = int(port)
    if not token:
        return False
    if is_verified(port, token):
        return True
    nonce = new_nonce()
    try:
        proof = client_proof(token, nonce)
    except UnicodeEncodeError:
        return False
    req = urllib.request.Request(f"http://{ports.LOOPBACK}:{port}{PATH}",
                                 headers={NONCE_HEADER: nonce, PROOF_HEADER: proof})
    ok = False
    try:
        with (opener or NO_PROXY_OPENER).open(req, timeout=timeout) as r:
            data = r.read(MAX_ANSWER + 1)
            if r.status == 200 and len(data) <= MAX_ANSWER:
                ok = _answer_ok(json.loads(data or b"null"), token, nonce, port)
    except (OSError, ValueError):
        ok = False
    if ok:
        with _lock:
            _verified.add(_key(port, token))
    else:
        forget(port)
    return ok


def _answer_ok(doc, token, nonce, port):
    if not isinstance(doc, dict):
        return False
    got_port, got = doc.get("port"), doc.get("proof")
    if type(got_port) is not int or got_port != port:
        return False
    if not isinstance(got, str) or _PROOF_RE.fullmatch(got) is None:
        return False
    return hmac.compare_digest(server_proof(token, nonce, port), got)
