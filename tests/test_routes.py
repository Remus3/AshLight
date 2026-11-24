"""TEST-HTTP-ROUTES (F-193): per-verb route tables in server/al/http.py.

do_GET / do_POST / do_PUT split the path, run _guard and then look the path
up in GET_ROUTES / POST_ROUTES / PUT_ROUTES. A new endpoint registers a
table entry and edits no dispatch function; an unknown path and a missing
token answer exactly as before; _guard runs before the table lookup (PUT:
an unknown path is 405 before the token check, as it always was, and a
known one runs only after _guard); the tables are the surface pinned by
tests/test_security_surface.py (read here with ast, never imported).

The server binds an ephemeral port (0) so a running AshLight is never
touched; runtime state goes to tmp_path.
"""

import ast
import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import http as al_http
from server.al import plug
from server.al.core import Core

ROOT = Path(__file__).resolve().parents[1]
HTTP_PY = ROOT / "server" / "al" / "http.py"
SURFACE_PIN = ROOT / "tests" / "test_security_surface.py"
TOKEN = "r" * 48
TEXT = "text/plain; charset=utf-8"
JSON = "application/json; charset=utf-8"
TABLES = {"GET": al_http.GET_ROUTES, "POST": al_http.POST_ROUTES,
          "PUT": al_http.PUT_ROUTES}


@pytest.fixture
def srv(tmp_path, monkeypatch):
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
    return r.status, r.getheader("Content-Type"), data


def auth():
    return {"X-AL-Token": TOKEN}


def json_body(h=None):
    return {**(h or {}), "Content-Type": "application/json"}


def test_a_registered_get_route_needs_no_dispatch_edit(srv, monkeypatch):
    calls = []

    def zzq_route(handler, path, query, extra):
        calls.append((handler.command, path))
        return handler._json(200, {"zzq": True}, extra)

    monkeypatch.setitem(al_http.GET_ROUTES, "/api/zzq-route", zzq_route)
    status, ctype, data = req(srv, "GET", "/api/zzq-route", auth())
    assert (status, ctype, json.loads(data)) == (200, JSON, {"zzq": True})
    assert req(srv, "HEAD", "/api/zzq-route", auth())[0] == 200  # HEAD runs the GET table
    assert calls == [("GET", "/api/zzq-route"), ("HEAD", "/api/zzq-route")]
    # the registered route sits behind the same guard as every other
    assert req(srv, "GET", "/api/zzq-route")[0] == 401
    assert req(srv, "GET", "/api/zzq-route", {**auth(), "Sec-Fetch-Site": "cross-site"})[0] == 403
    assert req(srv, "GET", "/api/zzq-route", auth(), host="evil.example")[0] == 400
    assert len(calls) == 2
    # a GET entry is not a POST route
    assert req(srv, "POST", "/api/zzq-route", json_body(auth()), b"{}")[0] == 404
    # POST and PUT register the same way
    monkeypatch.setitem(al_http.POST_ROUTES, "/api/zzq-route", zzq_route)
    monkeypatch.setitem(al_http.PUT_ROUTES, "/api/zzq-route", zzq_route)
    assert req(srv, "POST", "/api/zzq-route", json_body(auth()), b"{}")[0] == 200
    assert req(srv, "PUT", "/api/zzq-route", json_body(auth()), b"{}")[0] == 200
    assert req(srv, "PUT", "/api/zzq-route", json_body(), b"{}")[0] == 401
    assert calls[2:] == [("POST", "/api/zzq-route"), ("PUT", "/api/zzq-route")]
    # no dispatch function names the new route
    assert "zzq" not in HTTP_PY.read_text(encoding="ascii")


def test_a_plug_put_route_falls_through_after_the_guard(srv, monkeypatch):
    """UI-CARD-COLLAPSE (adjudicator ruling 2026-11-23): a PUT path no
    table holds reaches a plug PUT route, only after _guard; with no plug
    route it stays 405 before the token check."""
    calls = []

    def zzq_put(handler, query, extra):
        calls.append(handler.command)
        return handler._json(200, {"zzq": True}, extra)

    plug.all_routes()  # discovery first, so the planted entry stays
    monkeypatch.setitem(plug._routes, ("PUT", "/api/zzq-plug-put"), zzq_put)
    assert req(srv, "PUT", "/api/zzq-plug-put", json_body(auth()), b"{}")[0] == 200
    assert req(srv, "PUT", "/api/zzq-plug-put", json_body(), b"{}")[0] == 401
    assert req(srv, "PUT", "/api/zzq-plug-put",
               {**json_body(auth()), "Sec-Fetch-Site": "cross-site"}, b"{}")[0] == 403
    assert calls == ["PUT"]
    # a GET of the same path is not the PUT route
    assert req(srv, "GET", "/api/zzq-plug-put", auth())[0] == 404
    # no plug route and no table entry: 405, token or not
    assert req(srv, "PUT", "/api/zzq-plug-none", json_body(auth()), b"{}")[0] == 405
    assert req(srv, "PUT", "/api/zzq-plug-none", json_body(), b"{}")[0] == 405


def test_unknown_path_and_missing_token_answer_as_before(srv):
    not_found = (404, TEXT, b"not found\n")
    token_required = (401, JSON, b'{"error":"token required"}')
    refused = (405, TEXT, b"method not allowed\n")
    cases = [
        ("GET", "/zzq-nope", {}, None, not_found),
        ("GET", "/web/zzq-missing.js", {}, None, not_found),
        ("GET", "/web/*", {}, None, not_found),
        ("GET", "/api/zzq-nope", {}, None, token_required),
        ("GET", "/api/zzq-nope", auth(), None, not_found),
        ("GET", "/api/state", {}, None, token_required),
        ("GET", "/api/state", {"X-AL-Token": "wrong"}, None, token_required),
        ("GET", "/api/state?token=" + TOKEN, {}, None, token_required),
        ("HEAD", "/zzq-nope", {}, None, (404, TEXT, b"")),
        ("POST", "/zzq-nope", json_body(), b"{}", not_found),
        ("POST", "/api/zzq-nope", json_body(), b"{}", token_required),
        ("POST", "/api/zzq-nope", json_body(auth()), b"{}", not_found),
        ("POST", "/api/hints", json_body(), b"{}", token_required),
        ("PUT", "/api/state", json_body(), b"{}", refused),
        ("PUT", "/api/state", json_body(auth()), b"{}", refused),
        ("PUT", "/zzq-nope", {}, None, refused),
        ("PUT", "/api/weights", json_body(), b"{}", token_required),
        ("DELETE", "/api/state", auth(), None, refused),
        ("PATCH", "/api/zzq-nope", {}, None, refused),
    ]
    for method, path, h, body, want in cases:
        assert req(srv, method, path, h, body) == want, (method, path, h)
    assert srv.core.tailer is None and not srv.core.consented()


def test_guard_runs_before_any_table_lookup(srv, monkeypatch):
    order = []
    real_guard = al_http.Handler._guard
    real_lookup = al_http.route_for
    names = {id(t): v for v, t in TABLES.items()}

    def guard(self, path, query, needs_token):
        order.append(("guard", path))
        return real_guard(self, path, query, needs_token)

    def lookup(table, path):
        order.append(("lookup:" + names[id(table)], path))
        return real_lookup(table, path)

    monkeypatch.setattr(al_http.Handler, "_guard", guard)
    monkeypatch.setattr(al_http, "route_for", lookup)
    # a refused request never reaches a table
    refused = [
        ("GET", "/api/state", {}, None, None, 401),
        ("GET", "/", {}, None, "evil.example", 400),
        ("GET", "/api/state", {**auth(), "Sec-Fetch-Site": "cross-site"}, None, None, 403),
        ("GET", "/api/state", {**auth(), "Origin": "http://evil.example"}, None, None, 403),
        ("HEAD", "/api/state", {}, None, None, 401),
        ("POST", "/api/hints", json_body(), b"{}", None, 401),
        ("POST", "/api/hints", json_body({**auth(), "Origin": "null"}), b"{}", None, 403),
    ]
    for method, path, h, body, host, status in refused:
        order.clear()
        assert req(srv, method, path, h, body, host)[0] == status, (method, path)
        assert order == [("guard", path)], (method, path, order)
    # a request the guard lets through: the guard first, then one lookup
    for method, path, body, table in (("GET", "/api/health", None, "GET"),
                                      ("HEAD", "/", None, "GET"),
                                      ("GET", "/api/zzq-nope", None, "GET"),
                                      ("POST", "/api/hints", b'{"reset": false}', "POST")):
        order.clear()
        req(srv, method, path, json_body(auth()) if body else auth(), body)
        assert order == [("guard", path), ("lookup:" + table, path)], (method, path, order)
    # PUT: the 405 test for an unknown path comes before the guard, as it
    # always did; a known route's function runs only after the guard passed
    ran = []
    monkeypatch.setitem(al_http.PUT_ROUTES, "/api/weights",
                        lambda h, path, query, extra: ran.append(path) or h._json(200, {}))
    order.clear()
    assert req(srv, "PUT", "/api/zzq-nope", json_body(), b"{}")[0] == 405
    assert order == [("lookup:PUT", "/api/zzq-nope")]
    order.clear()
    assert req(srv, "PUT", "/api/weights", json_body(), b"{}")[0] == 401
    assert order == [("lookup:PUT", "/api/weights"), ("guard", "/api/weights")]
    assert ran == []
    assert req(srv, "PUT", "/api/weights", json_body(auth()), b"{}")[0] == 200
    assert ran == ["/api/weights"]


def test_dispatch_source_guards_then_looks_up_once():
    """The same order, read from the source: in do_GET and do_POST the
    _guard statement comes before the one route_for statement."""
    tree = ast.parse(HTTP_PY.read_text(encoding="utf-8"))
    handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Handler")
    for verb in ("GET", "POST", "PUT"):
        fn = next(n for n in handler.body
                  if isinstance(n, ast.FunctionDef) and n.name == "do_" + verb)
        src = [ast.unparse(s) for s in fn.body]
        assert src[0] == "path, query = self._url()", verb
        guard = [i for i, s in enumerate(src) if "self._guard(" in s]
        lookup = [i for i, s in enumerate(src) if f"route_for({verb}_ROUTES, path)" in s]
        assert len(guard) == 1 and len(lookup) == 1, verb
        if verb == "PUT":
            assert lookup[0] < guard[0]  # the 405 test, before the token check
        else:
            assert guard[0] < lookup[0], verb


def _pinned_surface():
    """The (method, path) keys of ROUTES in the surface pin, read with ast
    (one test file never imports another)."""
    tree = ast.parse(SURFACE_PIN.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "ROUTES" for t in n.targets))
    return {ast.literal_eval(k) for k in node.value.keys}


def test_tables_equal_the_pinned_surface():
    served = {(verb, path) for verb, table in TABLES.items() for path in table}
    served |= set(plug.all_routes())
    served |= {(verb, "*") for verb in ("DELETE", "PATCH", "OPTIONS")}
    assert served == _pinned_surface()
    # every entry is a Handler method of the route signature
    for verb, table in TABLES.items():
        for path, fn in table.items():
            assert getattr(al_http.Handler, fn.__name__) is fn, (verb, path)
            assert list(fn.__code__.co_varnames[:4]) == ["self", "path", "query", "extra"], \
                (verb, path)


def test_route_for_exact_then_prefix():
    def exact(*a):
        return "exact"

    def prefix(*a):
        return "prefix"

    table = {"/a": exact, "/w/*": prefix, "/w/x": exact}
    assert al_http.route_for(table, "/a") is exact
    assert al_http.route_for(table, "/w/x") is exact  # an exact key wins
    assert al_http.route_for(table, "/w/y.js") is prefix
    assert al_http.route_for(table, "/w/*") is prefix  # never the key itself
    for miss in ("/b", "/w", "/a/", "", "/A"):
        assert al_http.route_for(table, miss) is None, miss
    assert al_http.route_for(al_http.GET_ROUTES, "/web/app.js") is al_http.Handler._get_web
    assert al_http.route_for(al_http.PUT_ROUTES, "/api/state") is None
