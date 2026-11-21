"use strict";
/* SEC-HELLO-CLIENT (F-137, decision 0054): the Electron client proves the
   core before it sends anything. No Electron here (Node crypto and http,
   injected), so node --test covers every branch.

   The handshake is server/al/hello.py's, byte for byte: the client makes a
   fresh 128-bit nonce (32 lowercase hex digits) and sends it with
   HMAC-SHA256(token, "client" + nonce) in two headers of GET /api/hello,
   never the token itself. The core answers {"port", "proof"} with
   proof = HMAC-SHA256(token, "server" + nonce + the port it bound). The
   answer counts only when the port is the one this client dialled and the
   proof matches (compared in constant time). Key and messages are ASCII; a
   token that is not ASCII never verifies.

   makeVerifier(http, crypto, port, readToken, opts) gives:
   - check(): the async handshake; true at once while the current token
     value is verified, one request in flight per token value, and any
     failure forgets the verification (the next call proves again);
   - verifiedToken(): the token only while that exact value is verified,
     else "" (synchronous, for the IPC answer and the request headers);
   - forget(): drop the verification, called after any request error;
   - opts.onVerified(changed): after a check verifies; changed is true when
     the verified token value differs from the last one verified.
   guard(verifier, fn) wraps a request so it runs only after check() and a
   failure of it forgets the verification. */

const PATH = "/api/hello";
const NONCE_HEADER = "X-AL-Hello-Nonce";
const PROOF_HEADER = "X-AL-Hello-Proof";
const NONCE_BYTES = 16; // 128 bits
const MAX_ANSWER = 4096; // bytes of an answer read, as hello.MAX_ANSWER
const TIMEOUT_MS = 3000;
const HOST = "127.0.0.1";
const NONCE_RE = /^[0-9a-f]{32}$/;
const PROOF_RE = /^[0-9a-f]{64}$/;
const ASCII_RE = /^[\x00-\x7f]+$/;

function mac(crypto, token, text) {
  return crypto.createHmac("sha256", Buffer.from(String(token), "ascii"))
    .update(Buffer.from(String(text), "ascii")).digest("hex");
}

/* HMAC-SHA256(token, "client" + nonce), hex. */
function clientProof(crypto, token, nonce) {
  return mac(crypto, token, "client" + String(nonce));
}

/* HMAC-SHA256(token, "server" + nonce + port), hex. */
function serverProof(crypto, token, nonce, port) {
  return mac(crypto, token, "server" + String(nonce) + String(Math.trunc(Number(port))));
}

function usableToken(token) {
  return typeof token === "string" && token.length > 0 && ASCII_RE.test(token);
}

function usablePort(port) {
  return Number.isInteger(port) && port > 0 && port <= 65535;
}

/* Does the parsed answer prove the token for this nonce and port? */
function answerOk(crypto, doc, token, nonce, port) {
  if (!doc || typeof doc !== "object" || Array.isArray(doc)) { return false; }
  if (typeof doc.port !== "number" || !Number.isInteger(doc.port) || doc.port !== port) {
    return false;
  }
  if (typeof doc.proof !== "string" || !PROOF_RE.test(doc.proof)) { return false; }
  const want = Buffer.from(serverProof(crypto, token, nonce, port), "ascii");
  const got = Buffer.from(doc.proof, "ascii");
  return want.length === got.length && crypto.timingSafeEqual(want, got);
}

/* One handshake against 127.0.0.1:port; resolves true / false, never
   rejects. The token itself is never sent. */
function handshake(http, crypto, port, token, timeoutMs) {
  return new Promise((resolve) => {
    let done = false;
    function finish(ok) {
      if (!done) { done = true; resolve(ok === true); }
    }
    let nonce = "";
    let proof = "";
    try {
      nonce = crypto.randomBytes(NONCE_BYTES).toString("hex");
      proof = clientProof(crypto, token, nonce);
    } catch (e) {
      finish(false);
      return;
    }
    if (!NONCE_RE.test(nonce)) { finish(false); return; }
    let req = null;
    try {
      req = http.request({
        host: HOST, port: port, path: PATH, method: "GET", timeout: timeoutMs,
        headers: { [NONCE_HEADER]: nonce, [PROOF_HEADER]: proof }
      }, (res) => {
        try {
          const chunks = [];
          let size = 0;
          res.on("data", (c) => {
            size += c.length;
            if (size > MAX_ANSWER) {
              finish(false);
              try { req.destroy(); } catch (e) { /* already gone */ }
              return;
            }
            chunks.push(c);
          });
          res.on("end", () => {
            if (res.statusCode !== 200 || size > MAX_ANSWER) { finish(false); return; }
            let doc = null;
            try { doc = JSON.parse(Buffer.concat(chunks).toString("utf8") || "null"); } catch (e) {
              finish(false);
              return;
            }
            finish(answerOk(crypto, doc, token, nonce, port));
          });
          res.on("error", () => finish(false));
        } catch (e) {
          finish(false);
        }
      });
      req.on("timeout", () => req.destroy(new Error("timeout")));
      req.on("error", () => finish(false));
      req.end();
    } catch (e) {
      finish(false);
    }
  });
}

function makeVerifier(http, crypto, port, readToken, opts) {
  const o = opts && typeof opts === "object" ? opts : {};
  const timeoutMs = Number.isFinite(o.timeoutMs) && o.timeoutMs > 0 ? o.timeoutMs : TIMEOUT_MS;
  const onVerified = typeof o.onVerified === "function" ? o.onVerified : () => {};
  let verifiedKey = ""; // sha256 of the verified token value; never the token
  let lastKey = ""; // the last value ever verified (for onVerified's changed)
  let pending = null;
  let pendingKey = "";

  function current() {
    try { return String(readToken() || ""); } catch (e) { return ""; }
  }

  function keyOf(token) {
    return crypto.createHash("sha256").update(token, "utf8").digest("hex");
  }

  function forget() {
    verifiedKey = "";
  }

  function verifiedToken() {
    const t = current();
    if (!verifiedKey || !usableToken(t)) { return ""; }
    return keyOf(t) === verifiedKey ? t : "";
  }

  function check() {
    const t = current();
    if (!usablePort(port) || !usableToken(t)) {
      forget();
      return Promise.resolve(false);
    }
    const k = keyOf(t);
    if (k === verifiedKey) { return Promise.resolve(true); }
    if (pending && pendingKey === k) { return pending; }
    const run = handshake(http, crypto, port, t, timeoutMs).then((ok) => {
      if (pending === run) { pending = null; pendingKey = ""; }
      if (!ok) {
        forget();
        return false;
      }
      verifiedKey = k;
      const changed = k !== lastKey;
      lastKey = k;
      try { onVerified(changed); } catch (e) { /* a listener never breaks the check */ }
      return true;
    });
    pending = run;
    pendingKey = k;
    return run;
  }

  const api = { check: check, verifiedToken: verifiedToken, forget: forget, port: port };
  // link.makeHealthCheck finds the verifier behind the getter it is handed.
  verifiedToken.hello = api;
  return api;
}

/* fn (a request that reads verifier.verifiedToken) runs only after the
   handshake passed; a failed handshake rejects without calling it, and a
   failure of fn forgets the verification so the next call proves again. */
function guard(verifier, fn) {
  return function guarded(...args) {
    return verifier.check().then((ok) => {
      if (!ok) { throw new Error("core not verified"); }
      return Promise.resolve().then(() => fn(...args)).catch((e) => {
        verifier.forget();
        throw e;
      });
    });
  };
}

module.exports = { makeVerifier, guard, clientProof, serverProof, answerOk, handshake,
                   PATH, NONCE_HEADER, PROOF_HEADER, NONCE_BYTES, MAX_ANSWER, TIMEOUT_MS };
