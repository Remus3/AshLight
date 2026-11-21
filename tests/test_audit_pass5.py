"""AREA-AUDIT pass 5 regression tests (docs/audit/2026-11-17-audit.md,
"Pass 5"). Synthetic config files under tmp_path; no game, no network."""

import http.client
import json
import threading

import pytest

from server.al import settingsio
from server.al.core import Core
from server.al.http import serve

BROKEN = '{"contact": "someone-at-example", "client_log": "x/Client.txt",}\n'


def _core(tmp_path, text):
    cfg = tmp_path / "local.json"
    cfg.write_text(text, encoding="ascii", newline="\n")
    return Core(runtime=tmp_path, tail=False, config_path=cfg), cfg


def _import_doc():
    return {"kind": settingsio.KIND, "schema": settingsio.SCHEMA,
            "settings": {"underlevel_gap": 5}}


# P5-1: a hand-broken config/local.json is never overwritten (layout.save's
# rule), so a settings import, the run history switch or the web data
# switch cannot wipe the contact and the Client.txt path.
def test_p5_1_import_never_overwrites_a_broken_config(tmp_path):
    core, cfg = _core(tmp_path, BROKEN)
    with pytest.raises(OSError):
        core.import_settings(_import_doc())
    assert cfg.read_text(encoding="ascii") == BROKEN


def test_p5_1_history_switch_never_overwrites_a_broken_config(tmp_path):
    core, cfg = _core(tmp_path, BROKEN)
    with pytest.raises(OSError):
        core.set_history(enabled=False)
    assert cfg.read_text(encoding="ascii") == BROKEN


def test_p5_1_web_data_switch_never_overwrites_a_broken_config(tmp_path):
    core, cfg = _core(tmp_path, BROKEN)
    with pytest.raises(OSError):
        core.set_web_data(False)
    assert cfg.read_text(encoding="ascii") == BROKEN


def test_p5_1_non_object_config_is_not_overwritten_either(tmp_path):
    core, cfg = _core(tmp_path, "[1, 2]\n")
    with pytest.raises(OSError):
        core.set_history(enabled=True)
    assert cfg.read_text(encoding="ascii") == "[1, 2]\n"


def test_p5_1_good_and_missing_configs_still_save(tmp_path):
    core, cfg = _core(tmp_path, '{"contact": "c"}\n')
    core.set_history(enabled=False)
    assert json.loads(cfg.read_text(encoding="ascii")) == {"contact": "c",
                                                            "run_history": False}
    cfg.unlink()
    core.import_settings(_import_doc())
    assert json.loads(cfg.read_text(encoding="ascii")) == {"underlevel_gap": 5}


@pytest.fixture()
def broken_server(tmp_path):
    core, cfg = _core(tmp_path, BROKEN)
    srv = serve(core, "tok", port=0)
    t = threading.Thread(target=srv.serve_forever,
                         kwargs={"poll_interval": 0.05}, daemon=True)
    t.start()
    yield srv, cfg
    srv.stop()


def _post(srv, path, body):
    port = srv.server_address[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = json.dumps(body).encode()
    c.request("POST", path, body=data,
              headers={"Host": f"127.0.0.1:{port}", "X-AL-Token": "tok",
                       "Content-Type": "application/json"})
    r = c.getresponse()
    out = r.status, json.loads(r.read() or b"null")
    c.close()
    return out


def test_p5_1_endpoints_answer_500_and_keep_the_file(broken_server):
    srv, cfg = broken_server
    for path, body in (("/api/settings-import", _import_doc()),
                       ("/api/run-history", {"enabled": False}),
                       ("/api/web-data", {"enabled": False})):
        status, doc = _post(srv, path, body)
        assert status == 500, path
        assert "config" in doc["error"].lower() or "save" in doc["error"].lower(), path
        assert cfg.read_text(encoding="ascii") == BROKEN, path


def test_p5_1_clear_buttons_answer_500_when_the_runtime_file_cannot_be_written(
        tmp_path, monkeypatch):
    core, _cfg = _core(tmp_path, '{"contact": "c"}\n')
    srv = serve(core, "tok", port=0)
    t = threading.Thread(target=srv.serve_forever,
                         kwargs={"poll_interval": 0.05}, daemon=True)
    t.start()
    try:
        def fail():
            raise PermissionError("read-only")
        monkeypatch.setattr(core.watch, "clear", fail)
        monkeypatch.setattr(core.history, "clear", fail)
        for path in ("/api/price-watch", "/api/run-history"):
            status, doc = _post(srv, path, {"clear": True})
            assert status == 500 and doc["error"], path
    finally:
        srv.stop()
