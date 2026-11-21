"""DATA-DIAG-SEAM (research 0047 F1): one hook for the data modules'
Checks rows, diag facts and start-up wiring (server/al/diag_data.py).

The data modules are stood in for by fake modules put in sys.modules and
named in diag_data.MODULES (monkeypatched); no real module is changed.
Test cores only (tmp runtime, no tailer, mocked fetch).
"""

import ast
import logging
import sys
import types
from pathlib import Path

import pytest

from server.al import diag, diag_data
from server.al.core import Core

ROOT = Path(__file__).resolve().parents[1]
NOW = 1_800_000_000.0


@pytest.fixture(autouse=True)
def _fresh():
    diag_data.reset()
    yield
    diag_data.reset()


def _fake(monkeypatch, name, **hooks):
    mod = types.ModuleType(name)
    for key, fn in hooks.items():
        setattr(mod, key, fn)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def _use(monkeypatch, *names):
    monkeypatch.setattr(diag_data, "MODULES", tuple(names))


def _core(tmp_path, **kw):
    return Core(runtime=tmp_path / "rt", tail=False, **kw)


def test_a_missing_module_or_function_is_skipped(monkeypatch, caplog):
    _fake(monkeypatch, "al_fake_bare")  # no hook at all
    _fake(monkeypatch, "al_fake_rows",
          diag_rows=lambda f, now: [diag._check("fake_rows", "Fake", diag.PASS, "ok")])
    _use(monkeypatch, "al_fake_missing_module", "al_fake_bare", "al_fake_rows",
         "server.al.no_such_data_module")
    with caplog.at_level(logging.ERROR, logger="al.diag_data"):
        assert [n for n, _ in diag_data.modules()] == ["al_fake_bare", "al_fake_rows"]
        assert [r["id"] for r in diag_data.rows({}, NOW)] == ["fake_rows"]
        assert diag_data.facts(object()) == {}
        diag_data.attach(object())
    assert caplog.records == []  # a module that does not exist yet is no fault
    # the shipped list names the four data modules; those not written yet skip
    diag_data.reset()
    monkeypatch.undo()
    assert diag_data.MODULES == ("server.al.pricebook", "server.al.ninjashape",
                                 "server.al.theorycraft.snapprobe", "server.al.tradestats")
    names = [n for n, _ in diag_data.modules()]
    assert "server.al.pricebook" in names and "server.al.tradestats" in names


def test_a_module_row_reaches_the_checks_view(monkeypatch, tmp_path):
    def facts(core):
        return {"fake_count": 3, "port": "not this one"}  # a built-in key always wins

    def rows(f, now):
        return [diag._check("fake_data", "Fake data", diag.FAIL,
                            f"{f.get('fake_count')} entries look wrong.", "Wait a day."),
                diag._check("port", "Port twin", diag.PASS, "an id already taken")]

    _fake(monkeypatch, "al_fake_view", diag_facts=facts, diag_rows=rows)
    _use(monkeypatch, "al_fake_view")
    core = _core(tmp_path)
    try:
        f = core.diag_facts(NOW)
        assert f["fake_count"] == 3 and f["port"] == core.port
        v = diag.view(f, "1.0.0", now=NOW)
    finally:
        core.close()
    ids = [r["id"] for r in v["checks"]]
    assert ids.count("port") == 1 and "fake_data" in ids
    # after the built-in rows up to the port, before reload / dev docs / exits
    assert ids.index("fake_data") == ids.index("port") + 1
    row = v["checks"][ids.index("fake_data")]
    assert row == {"id": "fake_data", "label": "Fake data", "status": "fail",
                   "detail": "3 entries look wrong.", "fix": "Wait a day."}
    assert "Fake data: 3 entries look wrong. Fix: Wait a day." in v["report"]
    assert v["failed"] >= 1


def test_a_raising_module_never_breaks_the_card(monkeypatch, tmp_path, caplog):
    def boom(*_a):
        raise RuntimeError("hook broke")

    pkg = tmp_path / "pkgs"
    pkg.mkdir()
    (pkg / "al_fake_import_breaks.py").write_text("raise RuntimeError('import broke')\n",
                                                  encoding="ascii")
    (pkg / "al_fake_dep_missing.py").write_text("import al_no_such_dependency\n",
                                                encoding="ascii")
    monkeypatch.syspath_prepend(str(pkg))
    _fake(monkeypatch, "al_fake_raises", attach=boom, diag_facts=boom, diag_rows=boom)
    _fake(monkeypatch, "al_fake_odd", diag_facts=lambda core: ["not", "a", "dict"],
          diag_rows=lambda f, now: [{"id": "bad"}, "text", None,
                                    diag._check("odd_ok", "Odd", diag.NOTE, "kept")])
    _use(monkeypatch, "al_fake_import_breaks", "al_fake_dep_missing", "al_fake_raises",
         "al_fake_odd")
    with caplog.at_level(logging.ERROR, logger="al.diag_data"):
        core = _core(tmp_path)  # attach raised; the core still starts
        try:
            v = diag.view(core.diag_facts(NOW), "1.0.0", now=NOW)
        finally:
            core.close()
    ids = [r["id"] for r in v["checks"]]
    for builtin in ("log", "consent", "reading", "web_data", "prices", "calc", "port"):
        assert builtin in ids
    assert "odd_ok" in ids and "bad" not in ids
    logged = " ".join(r.getMessage() for r in caplog.records)
    for part in ("al_fake_import_breaks import", "al_fake_dep_missing import",
                 "al_fake_raises attach", "al_fake_raises diag_facts",
                 "al_fake_raises diag_rows", "bad shape"):
        assert part in logged, part
    sys.modules.pop("al_fake_import_breaks", None)
    sys.modules.pop("al_fake_dep_missing", None)


def test_attach_runs_once_at_core_start(monkeypatch, tmp_path):
    calls = []

    def attach(core):
        calls.append(core)
        assert core.rates is not None and callable(core.add_tick)  # the end of __init__

    _fake(monkeypatch, "al_fake_attach", attach=attach,
          diag_rows=lambda f, now: None)
    _use(monkeypatch, "al_fake_attach")
    core = _core(tmp_path)
    try:
        assert calls == [core]
        core.diag_facts(NOW)
        core.tick_diag(force=True)
        diag.view(core.diag_facts(NOW), "1.0.0", now=NOW)
        assert calls == [core]
    finally:
        core.close()
    # the wiring is one call each in core.py and diag.py
    core_src = (ROOT / "server" / "al" / "core.py").read_text(encoding="utf-8")
    diag_src = (ROOT / "server" / "al" / "diag.py").read_text(encoding="utf-8")
    assert core_src.count("diag_data.attach(self)") == 1
    assert core_src.count("diag_data.facts(") == 1
    assert diag_src.count("diag_data.rows(") == 1


def test_the_hook_makes_no_request(tmp_path):
    src = (ROOT / "server" / "al" / "diag_data.py").read_text(encoding="utf-8")
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names |= {node.module or ""} | {a.name for a in node.names}
    for bad in ("webfetch", "urllib", "http", "socket", "ninja", "subprocess"):
        assert not any(bad in n for n in names), bad
    assert "open(" not in src
    calls = []

    def net(method, url, headers, body=None):  # mocked: never the network
        calls.append(url)
        return 200, {}, b"{}"

    cfg = tmp_path / "local.json"
    cfg.write_text('{"web_data": true, "contact": "test-contact"}', encoding="ascii")
    core = _core(tmp_path, config_path=cfg, web_fetch=net)
    try:
        diag_data.attach(core)
        f = core.diag_facts(NOW)
        diag_data.rows(f, NOW)
        diag.view(f, "1.0.0", now=NOW)
    finally:
        core.close()
    assert calls == []
