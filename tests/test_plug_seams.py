"""RUN-SEAMS (decision 0056): the plug-in folder server/al/plug/.

A plug module adds a core tick, a Checks row and a token-gated /api/ route
by being one new file; the shared files stay as they are. Plug routes run
only after the handler guard and only under /api/. Core.tick_all runs the
ticks in the old __main__ loop order and throttles a repeating tick error
(C22: first traceback, then one line a minute).

Each test points plug.__path__ at a folder under tmp_path, so the real
plug folder is never written; the server binds port 0.
"""

import ast
import http.client
import json
import logging
import sys
import threading
from pathlib import Path

import pytest

from server.al import core as core_mod
from server.al import http as al_http
from server.al import plug
from server.al.core import Core

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "p" * 48

# The calls of the core loop in server/al/__main__.py before RUN-SEAMS,
# in their order (base c8ff972, lines 289-328).
OLD_LOOP = ["ensure_tailing", "tick_build", "tick_summary", "tick_calc", "tick_sources",
            "tick_guide", "tick_history", "tick_watch", "tick_diag", "tick_reload"]

PROBE = '''
"""A test plug: one tick, one fact, one Checks row, two routes."""
ORDER = 50
calls = []
served = []


def attach(core):
    core.add_tick("zzq_probe_tick", lambda: calls.append(1))


def facts(core, now):
    return {"zzq_ticks": len(calls), "port": "not-the-port"}


def rows(f, now):
    return {"id": "zzq-probe", "label": "Probe", "status": "note",
            "detail": "Probe ran %d time(s)." % f.get("zzq_ticks", 0)}


def _get(req, query, extra):
    served.append(("GET", dict(query)))
    return req._json(200, {"probe": True}, extra)


def _post(req, query, extra):
    served.append(("POST", {}))
    return req._json(200, {"posted": True}, extra)


def _health(req, query, extra):
    served.append(("GET", "health"))
    return req._json(200, {"shadow": True}, extra)


ROUTES = {("GET", "/api/zzq-probe"): _get, ("POST", "/api/zzq-probe"): _post,
          ("GET", "/api/health"): _health}
'''

OUTSIDE = '''
served = []


def _fn(req, query, extra):
    served.append(1)
    return req._json(200, {}, extra)


ROUTES = {("GET", "/zzq-out"): _fn, ("GET", "/web/zzq.js"): _fn, ("GET", "/events"): _fn,
          ("GET", "/api/"): _fn, ("PUT", "/api/zzq-put"): _fn,
          ("DELETE", "/api/zzq-del"): _fn, ("GET", "/api/zzq-q?x=1"): _fn,
          ("GET", "/api/zzq-none"): None, "zzq": _fn,
          ("GET", "/api/zzq-ok"): _fn}
'''


@pytest.fixture
def plugs(tmp_path):
    """A plug folder under tmp_path in place of the real one."""
    folder = tmp_path / "plugs"
    folder.mkdir()
    saved = list(plug.__path__)
    plug.__path__[:] = [str(folder)]
    plug.reset()
    try:
        yield folder
    finally:
        plug.__path__[:] = saved
        plug.reset()


def _write(folder, name, text):
    (folder / f"{name}.py").write_text(text.lstrip(), encoding="ascii", newline="\n")


def _core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    return Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)


@pytest.fixture
def serve_core(tmp_path):
    made = []

    def start(core):
        server = al_http.serve(core, TOKEN, port=0, web_root=ROOT / "web",
                               tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
        t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                             daemon=True)
        t.start()
        made.append((server, core))
        return server

    yield start
    for server, core in made:
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


def auth():
    return {"X-AL-Token": TOKEN}


def _mod(name):
    return sys.modules[f"{plug.__name__}.{name}"]


# -- tests ------------------------------------------------------------------

def test_plug_module_adds_tick_row_and_route_without_shared_edits(plugs, tmp_path, serve_core):
    _write(plugs, "zzq_probe", PROBE)
    core = _core(tmp_path)
    probe = _mod("zzq_probe")
    # the tick: after the built-ins, run by tick_all
    names = [n for n, _ in core.ticks]
    assert names == OLD_LOOP + ["zzq_probe_tick"]
    core.tick_all()
    core.tick_all()
    assert probe.calls == [1, 1]
    assert set(core.tick_ms) == set(names)
    # the fact merges in; a built-in key always wins
    facts = core.diag_facts()
    assert facts["zzq_ticks"] == 2 and facts["port"] == core.port
    # the Checks row: after every built-in row, in the published view
    core.tick_diag(force=True)
    checks = core.state.snapshot()["diag"]["checks"]
    assert checks[-1] == {"id": "zzq-probe", "label": "Probe", "status": "note",
                          "detail": "Probe ran 2 time(s).", "fix": None}
    assert "[note] Probe: Probe ran 2 time(s)." in core.state.snapshot()["diag"]["report"]
    # the route: served with the token; listed for the surface pin
    srv = serve_core(core)
    r, data = req(srv, "GET", "/api/zzq-probe", auth())
    assert r.status == 200 and json.loads(data) == {"probe": True}
    assert r.getheader("Content-Security-Policy") == al_http.CSP
    r, data = req(srv, "POST", "/api/zzq-probe", {**auth(), "Content-Type": "application/json"},
                  body=b"{}")
    assert r.status == 200 and json.loads(data) == {"posted": True}
    assert ("GET", "/api/zzq-probe") in plug.all_routes()
    assert ("POST", "/api/zzq-probe") in plug.all_routes()
    # a built-in route of the same path wins over the plug one
    r, data = req(srv, "GET", "/api/health", auth())
    assert r.status == 200 and json.loads(data)["ok"] is True
    assert ("GET", "health") not in probe.served
    # no shared file names the plug: the one new file did all of it
    for rel in ("server/al/core.py", "server/al/__main__.py", "server/al/diag.py",
                "server/al/http.py", "web/checks.js"):
        assert "zzq" not in (ROOT / rel).read_text(encoding="utf-8"), rel


def test_plug_route_outside_api_is_refused(plugs, tmp_path, serve_core, caplog):
    _write(plugs, "zzq_outside", OUTSIDE)
    with caplog.at_level(logging.ERROR, logger="al.plug"):
        routes = plug.all_routes()
    assert routes == [("GET", "/api/zzq-ok")]
    assert sum("refused" in r.getMessage() for r in caplog.records) == 9
    for verb, path in (("GET", "/zzq-out"), ("GET", "/web/zzq.js"), ("GET", "/events"),
                       ("GET", "/api/"), ("PUT", "/api/zzq-put")):
        assert plug.route(verb, path) is None, (verb, path)
    # even a table entry outside /api/ (planted past discovery) is never served
    plug._routes[("GET", "/zzq-out")] = lambda *a: None
    assert plug.route("GET", "/zzq-out") is None
    del plug._routes[("GET", "/zzq-out")]
    core = _core(tmp_path)
    srv = serve_core(core)
    out = _mod("zzq_outside")
    assert req(srv, "GET", "/zzq-out", auth())[0].status == 404
    assert req(srv, "GET", "/web/zzq.js", auth())[0].status == 404
    assert req(srv, "PUT", "/api/zzq-put", auth())[0].status == 405
    assert req(srv, "DELETE", "/api/zzq-del", auth())[0].status == 405
    assert req(srv, "GET", "/api/zzq-none", auth())[0].status == 404
    assert out.served == []
    assert req(srv, "GET", "/api/zzq-ok", auth())[0].status == 200
    assert out.served == [1]
    # the http.py fall-through runs only after _guard, as the last statement
    # of do_GET and do_POST
    tree = ast.parse((ROOT / "server" / "al" / "http.py").read_text(encoding="utf-8"))
    handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Handler")
    for verb in ("GET", "POST"):
        fn = next(n for n in handler.body
                  if isinstance(n, ast.FunctionDef) and n.name == "do_" + verb)
        src = [ast.unparse(s) for s in fn.body]
        assert src[-1] == f"return self._plug({verb!r}, path, query, extra)", verb
        guard = next(i for i, s in enumerate(src) if "self._guard(" in s)
        assert guard < len(src) - 1 and all("_plug" not in s for s in src[:-1])


def test_plug_route_needs_token_and_guard(plugs, tmp_path, serve_core):
    _write(plugs, "zzq_probe", PROBE)
    core = _core(tmp_path)
    srv = serve_core(core)
    probe = _mod("zzq_probe")
    port = srv.port
    json_ct = {"Content-Type": "application/json"}
    for method in ("GET", "POST"):
        body = b"{}" if method == "POST" else None
        cases = [
            ({}, 401), ({"X-AL-Token": "wrong"}, 401), ({"Authorization": "Bearer wrong"}, 401),
            ({**auth(), "Sec-Fetch-Site": "cross-site"}, 403),
            ({**auth(), "Sec-Fetch-Site": "same-site"}, 403),
            ({**auth(), "Origin": "http://evil.example"}, 403),
            ({**auth(), "Origin": "null"}, 403),
        ]
        for h, status in cases:
            r, _ = req(srv, method, "/api/zzq-probe", {**json_ct, **h}, body=body)
            assert r.status == status, (method, h, r.status)
        # ?token= opens no /api route, plug ones included
        r, _ = req(srv, method, f"/api/zzq-probe?token={TOKEN}", json_ct, body=body)
        assert r.status == 401
        r, _ = req(srv, method, "/api/zzq-probe", {**json_ct, **auth()}, body=body,
                   host="evil.example")
        assert r.status == 400
    assert probe.served == []
    r, _ = req(srv, "GET", "/api/zzq-probe", {"Authorization": "Bearer " + TOKEN,
                                              "Origin": f"http://127.0.0.1:{port}"})
    assert r.status == 200 and len(probe.served) == 1
    # the token rule of the handler covers every plug route
    assert all(al_http.Handler._needs_token(p) for _, p in plug.all_routes())


def test_tick_order_matches_the_old_loop(plugs, tmp_path):
    assert list(core_mod.TICK_ORDER) == OLD_LOOP
    core = _core(tmp_path)
    assert [n for n, _ in core.ticks] == OLD_LOOP  # no plug module here
    ran = []
    for name in OLD_LOOP:
        # a per-instance override is honoured (looked up at each pass)
        setattr(core, name, (lambda n: lambda: ran.append(n))(name))
    core.tick_build = lambda: (ran.append("tick_build"), 1 / 0)
    core.tick_all(logging.getLogger("al.test.seams.order"))
    assert ran == OLD_LOOP  # a failing tick never stops the ticks after it
    assert set(core.tick_ms) == set(OLD_LOOP)
    assert all(v >= 0 for v in core.tick_ms.values())
    assert isinstance(core.loop_at, float)
    with pytest.raises(ValueError):
        core.add_tick("tick_diag")
    with pytest.raises(ValueError):
        core.add_tick("zzq", fn="not callable")
    # the entry point's loop is one tick_all call; no tick is called by hand
    tree = ast.parse((ROOT / "server" / "al" / "__main__.py").read_text(encoding="ascii"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n.func.attr for n in ast.walk(main)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "core"]
    assert calls.count("tick_all") == 1
    assert not set(calls) & set(OLD_LOOP)
    core.close()


def test_failing_tick_logs_once_then_once_a_minute(plugs, tmp_path):
    """C22: a tick failing on every pass of a 5-minute run (600 passes,
    0.5 s apart) writes one traceback, then one line a minute with a
    count; the log grows by under 50 KB."""
    core = _core(tmp_path)
    for name in OLD_LOOP:
        setattr(core, name, lambda: None)  # the boom tick alone writes

    def boom():
        raise RuntimeError("zzq tick exploded")

    core.add_tick("zzq_boom", boom)
    logfile = tmp_path / "core.log"
    log = logging.getLogger("al.test.seams.throttle")
    log.propagate = False
    handler = logging.FileHandler(logfile, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    try:
        for i in range(600):
            core.tick_all(log, now=1000.0 + 0.5 * i)
    finally:
        log.removeHandler(handler)
        handler.close()
    text = logfile.read_text(encoding="utf-8")
    assert logfile.stat().st_size < 50 * 1024
    assert text.count("Traceback") == 1
    assert text.count("zzq_boom failed\n") == 1
    again = [ln for ln in text.splitlines() if "zzq_boom failed again" in ln]
    # lines at 60, 120, 180 and 240 s after the first failure (299.5 s run)
    assert len(again) == 4
    assert "120 time(s) since the last line" in again[0]
    assert all("RuntimeError: zzq tick exploded" in ln for ln in again)
    assert core._tick_errors.count("zzq_boom") == 119
    core.close()
