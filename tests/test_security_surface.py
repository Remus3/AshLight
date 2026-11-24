"""SEC-SURFACE-PIN: the local HTTP surface, pinned in one file.

ROUTES below is the reviewed table of every route (method, path, token
rule, body cap). routes_from_source() reads the per-verb route tables of
server/al/http.py (GET_ROUTES, POST_ROUTES, PUT_ROUTES; F-193) with ast (no
import side effect) and the two must match, so a new route or a dropped one
cannot land without a table row. The reply header set is
pinned by name and value, and one short case per P0 fix (SEC-STATIC-MAP,
SEC-XML-NUL, SEC-CROSS-SITE, SEC-NO-DISCOVERY) sits here too.

A package that adds a route adds its row to ROUTES and its entry to the
verb's table in http.py (TEST-HTTP-ROUTES); do_GET / do_POST / do_PUT only
look the path up there. RUN-SEAMS (decision 0056): a route a plug
module adds (server/al/plug/, served by the handler's fall-through) is read
by served_routes() from plug.all_routes(), so it needs its row here too.

The server binds an ephemeral port (0) so a running AshLight is never
touched; runtime state goes to tmp_path. Source: research 0045 route
inventory.
"""

import ast
import http.client
import json
import socket
import threading
from pathlib import Path

import pytest

from server.al import NAME, hello, plug
from server.al import http as al_http
from server.al.core import Core
from server.al.theorycraft import codec

ROOT = Path(__file__).resolve().parents[1]
HTTP_PY = ROOT / "server" / "al" / "http.py"
TOKEN = "s" * 48

# Token rules. NONE: Host / Origin / Sec-Fetch-Site checks only.
# HEADER: X-AL-Token or Authorization: Bearer; ?token= is refused.
# QUERY: the header, or ?token= (EventSource cannot set headers).
# REFUSED: 405 on every path, no token read.
# PROOF: a nonce + HMAC of the token in two headers, never the token itself
# (SEC-HELLO-CORE, decision 0054); the token value alone is refused.
NONE, HEADER, QUERY, REFUSED = "none", "header", "header or ?token=", "405"
PROOF = "token proof"

# (method, path): (token rule, body cap in bytes or None = no body read).
# A path ending in "*" is a prefix route. HEAD mirrors every GET row.
ROUTES = {
    # token-free GET (5)
    ("GET", "/"): (NONE, None),
    ("GET", "/index.html"): (NONE, None),
    ("GET", "/web/*"): (NONE, None),
    ("GET", "/tokens.css"): (NONE, None),
    ("GET", "/favicon.ico"): (NONE, None),
    # token-proof GET (1): the client proves the core before it sends the token
    ("GET", "/api/hello"): (PROOF, None),
    # token GET (17)
    ("GET", "/api/health"): (HEADER, None),
    ("GET", "/api/version"): (HEADER, None),
    ("GET", "/api/state"): (HEADER, None),
    ("GET", "/api/overlay-layout"): (HEADER, None),
    ("GET", "/api/build"): (HEADER, None),
    ("GET", "/api/filter"): (HEADER, None),
    ("GET", "/api/buildfile"): (HEADER, None),
    ("GET", "/api/settings-export"): (HEADER, None),
    ("GET", "/api/weights"): (HEADER, None),
    ("GET", "/api/gfx"): (HEADER, None),
    ("GET", "/api/rates"): (HEADER, None),
    ("GET", "/api/web-data"): (HEADER, None),
    ("GET", "/api/theme"): (HEADER, None),  # PLAY-TD-04B-THEME-CHOICE
    # RUN-VERDICTS-CORE: the plug route (server/al/plug/verdicts.py)
    ("GET", "/api/verdicts"): (HEADER, None),
    # KINDLER-STORE: the plug route (server/al/plug/genbuilds.py)
    ("GET", "/api/gen-builds"): (HEADER, None),
    # RUN-METRICS-CORE: the plug route (server/al/plug/debug.py, decision 0067)
    ("GET", "/api/debug"): (HEADER, None),
    # RUN-VERDICTS-UI (folded RUN-REPORT-ROUTE): the plug route
    # (server/al/plug/report.py); the report built on the click
    ("GET", "/api/report"): (HEADER, None),
    ("GET", "/events"): (QUERY, None),
    # token POST (19)
    ("POST", "/api/clipboard-read"): (HEADER, None),  # a 501 stub (decision 0003)
    ("POST", "/api/consent"): (HEADER, 4096),
    ("POST", "/api/overlay-layout"): (HEADER, 4096),
    ("POST", "/api/trade-dismiss"): (HEADER, 4096),
    ("POST", "/api/build-code"): (HEADER, 256 * 1024),
    ("POST", "/api/eval"): (HEADER, 256 * 1024),  # TC-PRESS-BUILD: the build size
    ("POST", "/api/web-data"): (HEADER, 4096),
    ("POST", "/api/filter-merge"): (HEADER, 2 * 1024 * 1024),  # octet-stream
    ("POST", "/api/settings-import"): (HEADER, 16 * 1024),
    ("POST", "/api/run-history"): (HEADER, 4096),
    ("POST", "/api/price-watch"): (HEADER, 4096),
    ("POST", "/api/hints"): (HEADER, 4096),
    ("POST", "/api/verdicts"): (HEADER, 4096),  # RUN-VERDICTS-CORE plug route
    ("POST", "/api/character"): (HEADER, 4096),  # RUN-CHARACTER-PIN plug route
    ("POST", "/api/gen-builds"): (HEADER, 4096),  # KINDLER-STORE plug route
    ("POST", "/api/wear"): (HEADER, 256 * 1024),  # TC-WORN-WIRE: the eval body cap
    ("POST", "/api/hotkeys"): (HEADER, 4096),  # HOTKEYS-LIVE (OVL-KEYS-CORE)
    ("POST", "/api/overlay-sample"): (HEADER, 4096),  # OVL-CARD-SLOT
    ("POST", "/api/update-now"): (HEADER, 4096),  # REL-UPDATE-TRIGGER: an empty body
    ("POST", "/api/theme"): (HEADER, 4096),  # PLAY-TD-04B-THEME-CHOICE
    ("POST", "/api/player-note"): (HEADER, 4096),  # PLAY-F-186A: text/plain
    # token PUT (1)
    ("PUT", "/api/weights"): (HEADER, 64 * 1024),
    # refused verbs
    ("DELETE", "*"): (REFUSED, None),
    ("PATCH", "*"): (REFUSED, None),
    ("OPTIONS", "*"): (REFUSED, None),
}

# The one request path a prefix row is probed with.
SAMPLE = {"/web/*": "/web/app.js"}

# Headers on every reply, with their pinned values (None: value varies).
BASE_HEADERS = {
    "server": NAME,
    "date": None,
    "content-type": None,
    "content-length": None,
    "content-security-policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"),
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cache-control": "no-store",
    "cross-origin-resource-policy": "same-origin",
    "vary": "Sec-Fetch-Site",
}


# -- the route reader -------------------------------------------------------

ROUTE_VERBS = ("GET", "POST", "PUT")
# TEST-HTTP-ROUTES (F-193): the module-level table of each routed verb
TABLES = {verb: verb + "_ROUTES" for verb in ROUTE_VERBS}
LOOKUP = "route_for"


def _is_path(node):
    return isinstance(node, ast.Name) and node.id == "path"


def _str(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _table_routes(tree):
    """{verb: set of paths} from the module-level GET_ROUTES / POST_ROUTES /
    PUT_ROUTES dict literals. Every key must be a string literal; a table
    written any other way, assigned twice, or changed by a later statement
    (item assignment, update(), setdefault(), ...) raises ValueError."""
    names = {name: verb for verb, name in TABLES.items()}
    out = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for tgt in targets:
            if not (isinstance(tgt, ast.Name) and tgt.id in names):
                continue
            verb = names[tgt.id]
            if verb in out:
                raise ValueError(f"{tgt.id} assigned twice")
            if not isinstance(node.value, ast.Dict) or not all(
                    k is not None and _str(k) for k in node.value.keys):
                raise ValueError(f"{tgt.id} is not a dict of literal paths")
            keys = [k.value for k in node.value.keys]
            if len(keys) != len(set(keys)):
                raise ValueError(f"{tgt.id} repeats a path")
            out[verb] = set(keys)
    for node in ast.walk(tree):
        # a table changed after its literal: a route the reader cannot see
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)) \
                and isinstance(node.value, ast.Name) and node.value.id in names:
            raise ValueError(f"{node.value.id} changed at line {node.lineno}")
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in names:
            raise ValueError(f"{node.value.id}.{node.attr} at line {node.lineno}")
    gone = set(TABLES) - set(out)
    if gone:
        raise ValueError(f"route tables gone: {sorted(TABLES[v] for v in gone)}")
    return out


def routes_from_source(source):
    """The set of (method, path) routes of the given http.py source text,
    read with ast (nothing is imported or run).

    - GET_ROUTES / POST_ROUTES / PUT_ROUTES: every key of the module-level
      dict literal is a (verb, key) route; a key ending in "*" is a prefix
      route ("/web/*").
    - do_GET / do_POST / do_PUT: the one test on `path` is the lookup
      route_for(<VERB>_ROUTES, path) in the verb's own table. Any
      comparison or method call on `path` there raises ValueError, so a
      route written outside the table cannot slip by.
    - do_HEAD must be exactly `self.do_GET()` (HEAD mirrors GET).
    - Any other do_<VERB> must be the refusal (_not_allowed) and reads as
      (VERB, "*").
    """
    tree = ast.parse(source)
    tables = _table_routes(tree)
    handler = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == "Handler")
    found = set()
    seen = set()
    for item in handler.body:
        if isinstance(item, ast.FunctionDef) and item.name.startswith("do_"):
            verb = item.name[3:]
            seen.add(verb)
            if verb in ROUTE_VERBS:
                _check_dispatch(verb, item)
                found |= {(verb, p) for p in tables[verb]}
            elif verb == "HEAD":
                calls = [s for s in item.body if not (
                    isinstance(s, ast.Expr) and _str(s.value))]
                if len(calls) != 1 or ast.dump(calls[0]) != ast.dump(
                        ast.parse("self.do_GET()").body[0]):
                    raise ValueError("do_HEAD is no longer exactly self.do_GET()")
            else:
                raise ValueError(f"do_{verb} has its own body: route it in the table")
        elif isinstance(item, ast.Assign):
            for tgt in item.targets:
                if isinstance(tgt, ast.Name) and tgt.id.startswith("do_"):
                    verb = tgt.id[3:]
                    seen.add(verb)
                    if not (isinstance(item.value, ast.Name)
                            and item.value.id == "_not_allowed"):
                        raise ValueError(f"do_{verb} is not the 405 refusal")
                    found.add((verb, "*"))
    missing = {"GET", "HEAD", "POST", "PUT"} - seen
    if missing:
        raise ValueError(f"verbs gone: {sorted(missing)}")
    return found


def _check_dispatch(verb, fn):
    """do_<verb> looks the path up once, in its own table, and tests the
    path no other way."""
    lookups = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare) and (
                _is_path(node.left) or any(_is_path(c) for c in node.comparators)):
            raise ValueError(f"do_{verb}: path test outside the table at line {node.lineno}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and _is_path(node.func.value):
            raise ValueError(f"do_{verb}: path call outside the table at line {node.lineno}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == LOOKUP:
            args = node.args
            if not (len(args) == 2 and not node.keywords and isinstance(args[0], ast.Name)
                    and args[0].id == TABLES[verb] and _is_path(args[1])):
                raise ValueError(f"do_{verb}: lookup not in {TABLES[verb]} "
                                 f"at line {node.lineno}")
            lookups += 1
    if lookups != 1:
        raise ValueError(f"do_{verb}: {lookups} table lookups, want 1")


def served_routes():
    """Every route the server answers: the route tables of http.py plus
    every plug module's route (plug.all_routes, RUN-SEAMS)."""
    return routes_from_source(HTTP_PY.read_text(encoding="utf-8")) | set(plug.all_routes())


def compare(table, found):
    """(rows the source lacks, routes the table lacks)."""
    return set(table) - found, found - set(table)


# -- the live server --------------------------------------------------------

@pytest.fixture
def srv(tmp_path, monkeypatch):
    # a refused body is drained for at most this long (the cap probes send
    # a Content-Length with no body behind it)
    monkeypatch.setattr(al_http, "DRAIN_TIMEOUT_S", 0.05)
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


def req(server, method, path, headers=None, body=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    h = {"Host": host or f"127.0.0.1:{server.port}"}
    h.update(headers or {})
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r, data


def raw(server, text):
    """Send a raw request; return the reply head lines (status first) once
    the head (and, for an SSE stream, its first state event) arrived."""
    s = socket.create_connection(("127.0.0.1", server.port), timeout=10)
    s.sendall(text.encode("ascii"))
    buf = b""
    try:
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        if b"text/event-stream" in buf.split(b"\r\n\r\n")[0]:
            while b"event: state" not in buf:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
    finally:
        s.close()
    return buf.split(b"\r\n\r\n")[0].decode("ascii").split("\r\n")


def auth():
    return {"X-AL-Token": TOKEN}


def hello_proof(nonce="0" * 32):
    return {hello.NONCE_HEADER: nonce, hello.PROOF_HEADER: hello.client_proof(TOKEN, nonce)}


def probe_path(path):
    return SAMPLE.get(path, path)


# -- tests ------------------------------------------------------------------

def test_route_table_matches_http_py():
    found = served_routes()
    missing, extra = compare(ROUTES, found)
    assert not extra, f"route(s) in http.py without a table row: {sorted(extra)}"
    assert not missing, f"table row(s) http.py no longer serves: {sorted(missing)}"
    counts = {}
    for (method, _), (rule, _) in ROUTES.items():
        counts[(method, rule)] = counts.get((method, rule), 0) + 1
    assert counts == {("GET", NONE): 5, ("GET", PROOF): 1, ("GET", HEADER): 17,
                      ("GET", QUERY): 1,
                      ("POST", HEADER): 21, ("PUT", HEADER): 1,
                      ("DELETE", REFUSED): 1, ("PATCH", REFUSED): 1,
                      ("OPTIONS", REFUSED): 1}
    # the token rule in the source is the one the table assumes
    assert [al_http.Handler._needs_token(probe_path(p)) for (m, p), (rule, _)
            in ROUTES.items() if rule in (NONE, PROOF, HEADER, QUERY)] == \
        [rule != NONE for (m, p), (rule, _) in ROUTES.items()
         if rule in (NONE, PROOF, HEADER, QUERY)]
    # the one proof route is the hello route
    assert [p for (_, p), (rule, _) in ROUTES.items() if rule == PROOF] == [hello.PATH]
    # the named caps in http.py are the pinned numbers
    assert al_http.MAX_BODY == 4096
    assert al_http.MAX_BUILD_BODY == 256 * 1024
    # TC-PRESS-BUILD: the item key may carry a copied build (the build size)
    assert al_http.MAX_EVAL_BODY == 256 * 1024
    assert al_http.MAX_WEIGHTS_BODY == 64 * 1024


def _with_branch(source, verb, path_lit):
    """A copy of source with an `if path == <lit>:` branch at the top of
    do_<verb>: a route outside the table."""
    tree = ast.parse(source)
    handler = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == "Handler")
    fn = next(n for n in handler.body
              if isinstance(n, ast.FunctionDef) and n.name == "do_" + verb)
    fn.body.insert(0, ast.parse(
        f"if path == {path_lit!r}:\n    return self._json(200, {{}})").body[0])
    return ast.unparse(ast.fix_missing_locations(tree))


def _with_entry(source, verb, path_lit):
    """A copy of source with one more entry in the verb's route table."""
    tree = ast.parse(source)
    table = next(n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == TABLES[verb]
                         for t in n.targets))
    table.value.keys.append(ast.Constant(path_lit))
    table.value.values.append(ast.parse("Handler._get_state", mode="eval").body)
    return ast.unparse(ast.fix_missing_locations(tree))


def test_unlisted_route_fails_the_comparison():
    source = HTTP_PY.read_text(encoding="utf-8")
    plugged = set(plug.all_routes())  # RUN-SEAMS: plug routes have rows too
    # the unchanged copy round-trips clean
    assert compare(ROUTES, routes_from_source(ast.unparse(ast.parse(source))) | plugged) \
        == (set(), set())
    for verb in ROUTE_VERBS:
        # a new table entry is a new route
        copy = _with_entry(source, verb, "/api/zzq-new")
        missing, extra = compare(ROUTES, routes_from_source(copy) | plugged)
        assert extra == {(verb, "/api/zzq-new")} and not missing, verb
        # a route written in the dispatch function, past the table, is refused
        with pytest.raises(ValueError):
            routes_from_source(_with_branch(source, verb, "/api/zzq-new"))
    # a dropped route shows as a missing row
    gone = source.replace('"/api/hints": Handler._hints,', '"/api/zzq-gone": Handler._hints,', 1)
    assert gone != source
    missing, extra = compare(ROUTES, routes_from_source(gone) | plugged)
    assert missing == {("POST", "/api/hints")} and extra == {("POST", "/api/zzq-gone")}
    # a new verb, a lookup in the wrong table, a key the reader cannot read,
    # a table changed after its literal or a route in an unknown shape is
    # refused
    for bad in (source.replace("do_PATCH = _not_allowed", "do_PATCH = do_POST", 1),
                source.replace("route_for(POST_ROUTES, path)", "route_for(GET_ROUTES, path)", 1),
                source.replace('"/api/hints": Handler._hints,', 'HINTS: Handler._hints,', 1),
                source + '\nPOST_ROUTES["/api/zzq"] = Handler._hints\n',
                source + "\nPOST_ROUTES.update(GET_ROUTES)\n",
                source.replace("        fn = route_for(POST_ROUTES, path)\n",
                               "        fn = route_for(POST_ROUTES, path)\n"
                               "        if path.endswith('/hints'):\n"
                               "            return None\n", 1),
                source.replace("    def do_HEAD(self):\n        self.do_GET()",
                               "    def do_HEAD(self):\n        self.do_POST()", 1),
                source.replace("    do_OPTIONS = _not_allowed\n",
                               "    def do_TRACE(self):\n        return None\n", 1)):
        assert bad != source
        with pytest.raises(ValueError):
            routes_from_source(bad)


# REL-UPDATE-TRIGGER: about 7 real requests per route row (31 rows) put it
# at the 1.5 s unmarked ceiling
@pytest.mark.slow
def test_every_token_route_answers_401_without_the_token(srv):
    port = srv.port
    for (method, path), (rule, _) in ROUTES.items():
        target = probe_path(path) if path != "*" else "/api/state"
        methods = (method, "HEAD") if method == "GET" else (method,)
        for m in methods:
            if rule == NONE:
                r, _ = req(srv, m, target)
                assert r.status == 200, (m, target)
                continue
            if rule == REFUSED:
                r, _ = req(srv, m, target)
                assert r.status == 405, (m, target)
                continue
            probes = [{}, {"X-AL-Token": "wrong"}, {"Authorization": "Bearer wrong"},
                      {"Authorization": "Basic " + TOKEN}]
            if rule == PROOF:
                # the token value is not the proof route's credential
                probes += [auth(), {"Authorization": "Bearer " + TOKEN}]
            else:
                # a hello proof opens no other route
                probes.append(hello_proof())
            for h in probes:
                r, data = req(srv, m, target, h)
                assert r.status == 401, (m, target, h)
                if m != "HEAD":
                    assert json.loads(data) == {"error": "token required"}
            # ?token= opens only /events (EventSource); never an /api route
            if rule == QUERY and m == "GET":
                head = raw(srv, f"GET {target}?token={TOKEN} HTTP/1.1\r\n"
                                f"Host: 127.0.0.1:{port}\r\n\r\n")
                assert head[0].endswith("200 OK"), head[0]
                continue
            r, _ = req(srv, m, f"{target}?token={TOKEN}")
            if rule == QUERY:
                assert r.status == 405, (m, target)  # HEAD never opens the stream
            else:
                assert r.status == 401, (m, target)
    # a path under /api/ that no row names still needs the token
    for m in ("GET", "POST"):
        assert req(srv, m, "/api/zzq-unlisted")[0].status == 401
        assert req(srv, m, "/api/zzq-unlisted", auth())[0].status == 404
    assert req(srv, "PUT", "/api/state", auth())[0].status == 405
    assert req(srv, "GET", "/zzq-unlisted")[0].status == 404
    assert srv.core.tailer is None and not srv.core.consented()


def _cap_probe(server, path, length, ctype):
    """A POST / PUT head declaring `length` bytes, none sent; the status."""
    method = "PUT" if path == "/api/weights" else "POST"
    head = raw(server, f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
                       f"X-AL-Token: {TOKEN}\r\nContent-Type: {ctype}\r\n"
                       f"Content-Length: {length}\r\n\r\n")
    return int(head[0].split()[1])


def test_body_caps_are_pinned(srv):
    for (method, path), (rule, cap) in ROUTES.items():
        if method not in ("POST", "PUT"):
            continue
        if cap is None:  # the 501 stub reads no body
            r, _ = req(srv, method, path, {**auth(), "Content-Type": "application/json"},
                       body=b"{}")
            assert r.status == 501, path
            continue
        ctype = {"/api/filter-merge": "application/octet-stream",
                 "/api/player-note": "text/plain"}.get(path, "application/json")
        assert _cap_probe(srv, path, cap + 1, ctype) == 413, path
        # exactly the cap is read (a refused body, never a 413); bad JSON, a
        # non-filter or a note that is not UTF-8 keeps every handler from
        # changing anything
        body = b"[" + b" " * (cap - 1) if ctype == "application/json" else b"\xff" * cap
        r, _ = req(srv, method, path, {**auth(), "Content-Type": ctype}, body=body)
        assert r.status == 400, (path, r.status)
    assert srv.core.tailer is None and not srv.core.consented()


def _names(headers):
    names = [k.lower() for k, _ in headers]
    assert len(names) == len(set(names)), f"repeated header: {names}"
    return dict((k.lower(), v) for k, v in headers)


def _check(got, extra=None, without=()):
    want = {**{k: v for k, v in BASE_HEADERS.items() if k not in without}, **(extra or {})}
    assert set(got) == set(want), (sorted(set(got) ^ set(want)))
    for k, v in want.items():
        if v is not None:
            assert got[k] == v, (k, got[k])


def test_reply_header_set_is_pinned(srv):
    port = srv.port
    cases = [
        ("GET", "/", {}, None, 200, {}),
        ("GET", "/web/app.js", {}, None, 200, {}),
        ("HEAD", "/", {}, None, 200, {}),
        ("GET", "/api/health", auth(), None, 200, {}),
        ("GET", "/api/hello", hello_proof(), None, 200, {}),
        ("GET", "/api/hello", auth(), None, 401, {}),
        ("GET", "/api/state", {}, None, 401, {}),
        ("GET", "/zzq-nope", {}, None, 404, {}),
        ("DELETE", "/api/state", {}, None, 405, {}),
        ("GET", "/api/state", {**auth(), "Sec-Fetch-Site": "cross-site"}, None, 403, {}),
        ("GET", "/api/state", {**auth(), "Origin": "http://evil.example"}, None, 403, {}),
        ("POST", "/api/hints", {**auth(), "Content-Type": "text/plain"}, b"x", 415, {}),
        ("POST", "/api/hints", {**auth(), "Content-Type": "application/json"},
         b"[" + b" " * 4096, 413, {}),
        ("GET", "/api/filter", auth(), None, 200, {"content-disposition": None}),
        ("GET", "/api/settings-export", auth(), None, 200, {"content-disposition": None}),
        ("HEAD", "/events", auth(), None, 405, {"allow": "GET"}),
    ]
    for method, path, h, body, status, extra in cases:
        r, _ = req(srv, method, path, h, body=body)
        assert r.status == status, (method, path, r.status)
        _check(_names(r.getheaders()), extra)
    r, _ = req(srv, "GET", "/", host="evil.example")
    assert r.status == 400
    _check(_names(r.getheaders()))
    # the SSE stream: no length, Connection: close; the app origin adds
    # the one CORS header and its Vary entry; Origin null is refused
    for origin, extra in ((None, {}), (al_http.APP_ORIGIN, {
            "access-control-allow-origin": "al-app://app",
            "vary": "Origin, Sec-Fetch-Site"})):
        lines = raw(srv, f"GET /events?token={TOKEN} HTTP/1.1\r\n"
                         f"Host: 127.0.0.1:{port}\r\n"
                         + (f"Origin: {origin}\r\n" if origin else "") + "\r\n")
        assert lines[0].endswith("200 OK"), lines[0]
        got = _names([tuple(x.split(": ", 1)) for x in lines[1:]])
        _check(got, {"connection": "close", "content-type": "text/event-stream; charset=utf-8",
                     **extra}, without=("content-length",))
    lines = raw(srv, f"GET /events?token={TOKEN} HTTP/1.1\r\n"
                     f"Host: 127.0.0.1:{port}\r\nOrigin: null\r\n\r\n")
    assert " 403 " in lines[0], lines[0]


def test_fix_cases_static_xml_cross_site_discovery(srv, tmp_path):
    h = {**auth(), "Content-Type": "application/json"}
    # SEC-STATIC-MAP: traversal and UNC shapes miss the name map
    for path in ("/web/../server/al/http.py", "/web/%2e%2e/README.md",
                 "/web//zzqhost/share/x.js", "/web/index.html::$DATA"):
        assert req(srv, "GET", path)[0].status == 404, path
    assert srv.static.lookup("../README.md") is None
    # SEC-XML-NUL: a UTF-16 entity code and a NUL in the payload are 400
    dtd = '<!DOCTYPE x [<!ENTITY a "aaaa">]><PathOfBuilding2/>'
    for payload in (dtd.encode("utf-16-le"), b"<PathOfBuilding2>\x00</PathOfBuilding2>"):
        body = json.dumps({"code": codec.encode_bytes(payload)})
        assert req(srv, "POST", "/api/build-code", h, body=body)[0].status == 400
    r, data = req(srv, "GET", "/api/build", auth())
    assert r.status == 200 and json.loads(data)["loaded"] is False
    # SEC-CROSS-SITE: same-site is refused before the token check; the null
    # origin no longer reads /api/state
    assert req(srv, "GET", "/api/state", {"Sec-Fetch-Site": "same-site"})[0].status == 403
    assert req(srv, "GET", "/api/state", {**auth(), "Origin": "null"})[0].status == 403
    # SEC-NO-DISCOVERY: a pointed core never scans, and consent to a file
    # not named Client.txt is refused with nothing changed
    assert srv.core.discover is False
    other = tmp_path / "notes" / "secrets"
    other.parent.mkdir()
    other.write_bytes(b"not a log\n")
    before = srv.core.log_path
    body = json.dumps({"consent": True, "path": str(other)})
    assert req(srv, "POST", "/api/consent", h, body=body)[0].status == 400
    assert srv.core.log_path == before and not srv.core.consented()
