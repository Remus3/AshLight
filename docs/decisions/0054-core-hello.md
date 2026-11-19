# 0054 - Core hello handshake: clients prove the core before they send the token

Date: 2026-11-18. Source: package SEC-HELLO-CORE (wave 4); finding F-137
(docs/plan/02-findings.md); research 0045 R6 (closes F5, P8-3 and P8-4);
decision 0002 "API token"; SEC-NO-PROXY (decision 0005 supervisor);
SEC-SURFACE-PIN (the route table). The run.ps1 side is SEC-HELLO-PS and the
Electron side SEC-HELLO-CLIENT; the port rules of the finding (`--port 9000`
exits non-zero, the client port rule) land with F-091. This record covers
the core route, the Python client and the supervisor.

## Decision

1. Route. `GET /api/hello` (HEAD mirrors it). The client makes a fresh
   128-bit nonce (`os.urandom(16)`, 32 lowercase hex digits) and sends it
   in `X-AL-Hello-Nonce` with `X-AL-Hello-Proof` =
   HMAC-SHA256(key = token, msg = "client" + nonce), hex. It never sends
   the token itself.
2. Gate. The core checks the nonce shape, the proof shape and the MAC in
   constant time (`hello.check_client`). No valid proof: 401
   `{"error": "token required"}`, the reply of every token route. The
   token value (X-AL-Token, Bearer or ?token=) does not open this route,
   and a valid proof opens no other route. Host, Origin and Sec-Fetch-Site
   checks run first, unchanged; CSP and every reply header are unchanged.
3. Answer. `{"port": <bound port>, "proof": HMAC-SHA256(key = token,
   msg = "server" + nonce + bound port in decimal)}`. All text is ASCII;
   the fixed-length nonce makes the concatenation unambiguous.
4. Client check (`hello.verify(port, token, opener)`, the Python client).
   No proxy (empty ProxyHandler). The answer is accepted only when its
   status is 200, its body is at most 4 KB of JSON, its `port` is the
   port dialled and its proof equals the server proof for that port, in
   constant time. Only then may the token be sent.
5. Once per token value. A verified (port, sha256 of the token) pair is
   cached in memory; the token itself is not a cache key. Any request
   error, a failed or malformed answer, clears the port's entry, so the
   next call proves the listener again.
6. Supervisor. `keepalive.health_check` calls `hello.verify` before the
   token request to `/api/health`; a failed hello means "not healthy" and
   no token is sent. A failed `/api/health` request clears the proof.
   Each poll that finds no live core (no heartbeat, a dead pid or a reused
   pid) clears the proof for its port too.
7. No process is looked at: the proof is this route's token gate (clear
   of decision 0029). Loopback only; the Game ToS floor is untouched.

## Ruling on the stack rule (adjudicator, 2026-11-18)

The plan (docs/plan/07, floor lens) sent the reading "a proof of the token
is the token gate" to a distinct adjudicator agent before merge (FLEET
item 1). Question: does a valid HMAC proof of possession of the per-start
token, never the token value, satisfy CLAUDE.md "every API / SSE call
needs the per-start token" for this one route?

- Ruling: (a) yes. For GET /api/hello only, a valid proof of possession
  of the per-start token is the token gate. Every other route still takes
  the token value.
- Alternatives: (b) also require the token itself on /api/hello after a
  prior server-proof exchange: rejected, it is circular (the first
  exchange would itself be unauthenticated or proof-gated, so the proof is
  the real gate anyway). (c) Amend the CLAUDE.md wording: rejected, it
  needs MAIN or the operator, and the rule is met as written.
- Why: the rule's purpose is that only holders of the per-start token get
  service; the proof shows possession, so the purpose is met. The token
  never reaches an unverified listener, which closes the squatter and
  port-hijack leak the rule alone leaves open. Fresh nonces and the
  "client" / "server" role tags stop replay and reflection.
- Reverses if: the proof is shown replayable or forgeable, an operator or
  MAIN ruling reads the rule as requiring the literal token value, or the
  token model changes.

## Choices the package text left open (ruled by the builder)

- Header names `X-AL-Hello-Nonce` / `X-AL-Hello-Proof`, hex encoding.
  Alternatives: one header with both values; base64. Why: two plain
  headers are easy in PowerShell and JS, and hex has one spelling.
  Reverses if: a client cannot set custom headers (then the query form,
  as for EventSource, is ruled again).
- No replay list on the core. Alternatives: remember recent nonces and
  refuse a repeat. Why: a replayed client proof only earns the server
  answer for a nonce the replayer did not choose and for the real port,
  which proves nothing to anyone but the client that made the nonce; a
  list is state with no gain. Reverses if: an answer is ever used for
  anything but this one check.
- Cache cleared on a dead core, not only on a request error. Alternatives:
  only on a request error (the finding's words). Why: with a crashed core
  and an unchanged token file, a listener that took the port would get
  the cached trust and the token on the next health check without any
  request error in between. Reverses if: the supervisor stops reading the
  heartbeat.
- The cache is per process, keyed by port and token hash. Alternatives: a
  file shared by clients. Why: nothing on disk to read or forge; one
  extra round trip per process start is cheap. Reverses if: the handshake
  pushes a start past its budget.

## Why

A client that sends the token (or item text) to whatever answers on
127.0.0.1:<port> leaks it to any program that took the port first or
after the core died. The handshake lets a client prove the listener holds
the token and bound the port it dialled, without revealing the token: a
foreign listener learns one MAC over a nonce it cannot choose, which
reveals nothing of a 192-bit key; the bound port stops a listener on a
wrong port relaying the challenge to the real core. Checked by
tests/test_hello.py, tests/test_security_surface.py and
tests/test_keepalive.py.

## Reverses if

A client that cannot compute an HMAC must be supported, the handshake
pushes a start past its budget, or the stack rule's token wording is ruled
to mean the token itself on every call.
