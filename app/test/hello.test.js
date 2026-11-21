"use strict";
/* SEC-HELLO-CLIENT (F-137, decision 0054): the Electron client proves the
   core (app/hello.js) before it sends the token or any item text. Real
   loopback servers on a free port: a core that speaks the hello, a fake
   that answers 200 to everything, and wrong-port / relay answers. */
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const http = require("node:http");
const Hello = require("../hello.js");
const EvalKey = require("../eval_hotkey.js");
const Link = require("../client/link.js");

const TOKEN = "ab".repeat(24);
const NONCE = "0123456789abcdef".repeat(2);
const ITEM = "Rarity: Rare\nStorm Loop\nIron Ring";

/* Vectors from server/al/hello.py (client_proof / server_proof) for TOKEN
   and NONCE: the two sides must agree byte for byte. */
const PY = {
  client: "5aca601a63396fe27dc7899396b539bad1c7f6a4be761c1fead820b5ff9ecd89",
  server8960: "d2df22a47058127f954d99841ff4b6636d5af6032548a243a3e20154f6b8b44a",
  server8961: "b1151d0c736b5bd9bdd9fef510abc6eed4975bec6cc893c1dda42f05d3c6141d",
  clientOther: "ee2860aed9eaba06a8b0778e435e5e44bc06f1b4be804efd03efadb47bc8a8e1"
};

test("proofs match the Python vectors", () => {
  assert.equal(Hello.clientProof(crypto, TOKEN, NONCE), PY.client);
  assert.equal(Hello.serverProof(crypto, TOKEN, NONCE, 8960), PY.server8960);
  assert.equal(Hello.serverProof(crypto, TOKEN, NONCE, 8961), PY.server8961);
  assert.equal(Hello.clientProof(crypto, "cd".repeat(24), NONCE), PY.clientOther);
  assert.equal(Hello.PATH, "/api/hello");
  assert.equal(Hello.NONCE_BYTES, 16);
  // the answer check: right port and proof only
  const good = { port: 8960, proof: PY.server8960 };
  assert.equal(Hello.answerOk(crypto, good, TOKEN, NONCE, 8960), true);
  for (const bad of [null, [], "x", { port: 8961, proof: PY.server8960 },
                     { port: "8960", proof: PY.server8960 }, { port: true, proof: PY.server8960 },
                     { port: 8960, proof: PY.server8960.toUpperCase() },
                     { port: 8960, proof: PY.server8961 }, { port: 8960, proof: PY.client },
                     { port: 8960, proof: TOKEN }, { port: 8960 }]) {
    assert.equal(Hello.answerOk(crypto, bad, TOKEN, NONCE, 8960), false, JSON.stringify(bad));
  }
});

/* A loopback server; handler(req, body, port) -> {status, body}. Records
   every request (method, url, headers, body). */
async function server(handler) {
  const seen = [];
  const srv = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const body = Buffer.concat(chunks).toString("utf8");
      seen.push({ method: req.method, url: req.url, headers: req.headers, body: body });
      const out = handler(req, body, srv.address().port);
      res.statusCode = out.status;
      res.setHeader("Content-Type", "application/json");
      res.end(out.body);
    });
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  return { port: srv.address().port, seen, close: () => new Promise((r) => srv.close(r)) };
}

/* The core side of the handshake, as server/al/http.py answers it; port
   is what the answer names (the bound port unless a test says otherwise). */
function coreHandler(token, opts) {
  const o = opts || {};
  return (req, body, bound) => {
    if (req.url === "/api/hello") {
      const nonce = req.headers["x-al-hello-nonce"];
      const proof = req.headers["x-al-hello-proof"];
      if (proof !== Hello.clientProof(crypto, token, nonce)) { return { status: 401, body: "{}" }; }
      const port = o.port || bound;
      return { status: 200, body: JSON.stringify({ port: port,
        proof: Hello.serverProof(crypto, token, nonce, o.proofPort || port) }) };
    }
    if (o.failNext && o.failNext()) { return { status: 500, body: "{}" }; }
    return { status: req.headers["x-al-token"] === token ? 200 : 401, body: "{}" };
  };
}

function leaked(seen, token) {
  return seen.some((r) => JSON.stringify(r.headers).includes(token) || r.body.includes(token) ||
                          r.url.includes(token));
}

test("a fake server answering 200 gets neither the token nor the item text", async () => {
  const fake = await server(() => ({ status: 200, body: "{}" }));
  try {
    const v = Hello.makeVerifier(http, crypto, fake.port, () => TOKEN);
    assert.equal(await v.check(), false);
    assert.equal(v.verifiedToken(), "");
    // the item key's post behind the hello: rejected, nothing posted
    const post = Hello.guard(v, EvalKey.makePost(http, fake.port, v.verifiedToken));
    await assert.rejects(post("/api/eval", { item: ITEM }), /core not verified/);
    // the press handler built from it: still one read, nothing sent
    let reads = 0;
    const said = [];
    const press = EvalKey.createEvalHotkey({ readText: () => { reads += 1; return ITEM; },
      post: post, log: (m) => said.push(m) }, EvalKey.POST_EVAL);
    assert.equal(await press(), false);
    assert.equal(reads, 1);
    assert.ok(said.some((m) => m.includes("core not verified")));
    // the health check through the same verifier and through a plain reader
    assert.equal(await Link.makeHealthCheck(http, fake.port, v.verifiedToken)(), false);
    assert.equal(await Link.makeHealthCheck(http, fake.port, () => TOKEN)(), false);
    // what the fake saw: hello requests only, never the token, never the item
    assert.ok(fake.seen.length >= 1);
    assert.ok(fake.seen.every((r) => r.url === "/api/hello" && r.method === "GET"), "hello only");
    assert.equal(leaked(fake.seen, TOKEN), false, "token leaked");
    assert.ok(!fake.seen.some((r) => r.body.includes("Storm Loop")), "item text leaked");
    assert.ok(!fake.seen.some((r) => "x-al-token" in r.headers));
    for (const r of fake.seen) {
      assert.match(r.headers["x-al-hello-nonce"], /^[0-9a-f]{32}$/);
      assert.match(r.headers["x-al-hello-proof"], /^[0-9a-f]{64}$/);
    }
    // a fresh nonce each time
    const nonces = new Set(fake.seen.map((r) => r.headers["x-al-hello-nonce"]));
    assert.equal(nonces.size, fake.seen.length);
  } finally {
    await fake.close();
  }
});

test("makePost sends nothing without a verified token", async () => {
  let calls = 0;
  const fakeHttp = { request() { calls += 1; throw new Error("must not be called"); } };
  const post = EvalKey.makePost(fakeHttp, 8960, () => "");
  await assert.rejects(post("/api/eval", { item: ITEM }), /core not verified/);
  assert.equal(calls, 0);
});

test("the core proves itself once per token value; the token then goes out", async () => {
  const core = await server(coreHandler(TOKEN));
  try {
    const flips = [];
    const v = Hello.makeVerifier(http, crypto, core.port, () => TOKEN,
                                 { onVerified: (changed) => flips.push(changed) });
    assert.equal(v.verifiedToken(), "");
    // two checks at once share one request
    const both = await Promise.all([v.check(), v.check()]);
    assert.deepEqual(both, [true, true]);
    assert.equal(core.seen.length, 1);
    assert.equal(v.verifiedToken(), TOKEN);
    assert.equal(await v.check(), true);
    assert.equal(core.seen.length, 1, "cached per token value");
    assert.deepEqual(flips, [true]);
    // the post now carries the token and the item text to the proven core
    const post = Hello.guard(v, EvalKey.makePost(http, core.port, v.verifiedToken));
    assert.equal(await post("/api/eval", { item: ITEM }), 200);
    const last = core.seen[core.seen.length - 1];
    assert.equal(last.url, "/api/eval");
    assert.equal(last.headers["x-al-token"], TOKEN);
    assert.equal(JSON.parse(last.body).item, ITEM);
    // the hello request itself never carried the token
    assert.equal(leaked([core.seen[0]], TOKEN), false);
    assert.equal(await Link.makeHealthCheck(http, core.port, v.verifiedToken)(), true);
  } finally {
    await core.close();
  }
});

test("re-check after a request error", async () => {
  let fail = false;
  const core = await server(coreHandler(TOKEN, { failNext: () => fail }));
  try {
    const flips = [];
    const v = Hello.makeVerifier(http, crypto, core.port, () => TOKEN,
                                 { onVerified: (changed) => flips.push(changed) });
    const post = Hello.guard(v, EvalKey.makePost(http, core.port, v.verifiedToken));
    assert.equal(await post("/api/eval", { item: "a" }), 200);
    const hellos = () => core.seen.filter((r) => r.url === "/api/hello").length;
    assert.equal(hellos(), 1);
    fail = true;
    await assert.rejects(post("/api/eval", { item: "b" }), /HTTP 500/);
    assert.equal(v.verifiedToken(), "", "a request error forgets the verification");
    fail = false;
    assert.equal(await post("/api/eval", { item: "c" }), 200);
    assert.equal(hellos(), 2, "the next request proved the core again");
    // the same value proved again: onVerified says unchanged
    assert.deepEqual(flips, [true, false]);
  } finally {
    await core.close();
  }
});

test("a wrong port in the answer fails, and so does a proof for another port", async () => {
  const wrong = await server(coreHandler(TOKEN, { port: 8960 }));
  const relay = await server(coreHandler(TOKEN, { proofPort: 8960 }));
  try {
    const a = Hello.makeVerifier(http, crypto, wrong.port, () => TOKEN);
    assert.equal(await a.check(), false);
    assert.equal(a.verifiedToken(), "");
    const b = Hello.makeVerifier(http, crypto, relay.port, () => TOKEN);
    assert.equal(await b.check(), false);
    assert.equal(leaked(wrong.seen.concat(relay.seen), TOKEN), false);
  } finally {
    await wrong.close();
    await relay.close();
  }
});

test("a new token value is proved again; a core with another token fails", async () => {
  let token = TOKEN;
  const core = await server((req, body, bound) => coreHandler(token)(req, body, bound));
  try {
    const flips = [];
    let file = TOKEN;
    const v = Hello.makeVerifier(http, crypto, core.port, () => file,
                                 { onVerified: (changed) => flips.push(changed) });
    assert.equal(await v.check(), true);
    file = "cd".repeat(24); // the token file changed, the core did not (yet)
    assert.equal(v.verifiedToken(), "", "an unproved value is never handed out");
    assert.equal(await v.check(), false);
    token = file; // the new core is up
    assert.equal(await v.check(), true);
    assert.equal(v.verifiedToken(), file);
    assert.deepEqual(flips, [true, true]);
  } finally {
    await core.close();
  }
});

test("no request at all for an unusable token or port; a huge or broken answer fails", async () => {
  let calls = 0;
  const counting = { request() { calls += 1; throw new Error("no"); } };
  for (const t of ["", "t" + String.fromCharCode(233) + "st", null]) {
    assert.equal(await Hello.makeVerifier(counting, crypto, 8960, () => t).check(), false);
  }
  for (const p of [0, -1, 70000, "8960", NaN]) {
    assert.equal(await Hello.makeVerifier(counting, crypto, p, () => TOKEN).check(), false);
  }
  assert.equal(calls, 0);
  // a throwing reader is no token
  assert.equal(await Hello.makeVerifier(counting, crypto, 8960, () => { throw new Error("x"); })
    .check(), false);
  const big = await server(() => ({ status: 200, body: "x".repeat(Hello.MAX_ANSWER + 10) }));
  const junk = await server(() => ({ status: 200, body: "not json" }));
  try {
    assert.equal(await Hello.makeVerifier(http, crypto, big.port, () => TOKEN).check(), false);
    assert.equal(await Hello.makeVerifier(http, crypto, junk.port, () => TOKEN).check(), false);
  } finally {
    await big.close();
    await junk.close();
  }
  // a closed port and a fake http whose response has no stream methods
  assert.equal(await Hello.makeVerifier(http, crypto, big.port, () => TOKEN).check(), false);
  const odd = { request(o, cb) {
    const req = new (require("node:events"))();
    req.destroy = () => {};
    req.end = () => setImmediate(() => cb({ statusCode: 200, resume() {} }));
    return req;
  } };
  assert.equal(await Hello.makeVerifier(odd, crypto, 8960, () => TOKEN).check(), false);
});
