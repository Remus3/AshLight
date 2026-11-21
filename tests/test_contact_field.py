"""DATA-CONTACT-FIELD (F-018, decision 0015 amendment 2026-11-20): the
User-Agent contact is typed in the dashboard's "Prices and web data" card.
POST /api/web-data takes "contact"; the core stores it only in the
gitignored config/local.json and every read-back says only contact_set.

Mocked fetch only; no request reaches the network. Tmp runtime and config.
"""

import http.client
import json
import logging
import threading
import time
from pathlib import Path

import pytest

from server.al import ninja
from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "c" * 48
# A value that appears nowhere else, so any echo of it is found.
CONTACT = "zq-contact-7781"
LEAGUES = json.dumps([{"id": "Standard", "name": "Standard"}]).encode()
OVERVIEW = json.dumps({
    "core": {"items": [{"id": "divine", "name": "Divine Orb"}],
             "rates": {"exalted": 500.0}, "primary": "divine"},
    "lines": [{"id": "exalted", "primaryValue": 0.002}],
    "items": [{"id": "exalted", "name": "Exalted Orb"}]}).encode()


class FakeNet:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if url.endswith(ninja.LEAGUES_PATH):
            return 200, {}, LEAGUES
        return 200, {}, OVERVIEW


def _req(server, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}", "X-AL-Token": TOKEN}
    data = None
    if body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, raw


def _doc(raw):
    return json.loads(raw)


@pytest.fixture
def api(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    rt = tmp_path / "rt"
    rt.mkdir()
    net = FakeNet()
    core = Core(runtime=rt, log_path=str(log), poll_s=0.05, web_fetch=net)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    yield server, core, net
    server.stop()
    core.close()


def _write_cfg(core, doc):
    core.config_path.write_text(json.dumps(doc), encoding="ascii")


def _cfg(core):
    return json.loads(core.config_path.read_text(encoding="utf-8"))


@pytest.mark.server
def test_post_contact_sets_contact_set_and_first_round_writes_rates_json(api):
    srv, core, net = api
    _write_cfg(core, {"web_data": True, "league": "Standard"})
    status, raw = _req(srv, "GET", "/api/web-data")
    assert status == 200 and _doc(raw)["contact_set"] is False
    assert _doc(raw)["blocked"] == "contact not set" and net.calls == []
    status, raw = _req(srv, "POST", "/api/web-data", {"contact": "  " + CONTACT + " "})
    assert status == 200
    doc = _doc(raw)
    assert doc["contact_set"] is True and doc["web_data"] is True and doc["blocked"] is None
    assert CONTACT.encode() not in raw
    cfg = _cfg(core)
    assert cfg["contact"] == CONTACT  # cleaned (stripped); other keys kept
    assert cfg["web_data"] is True and cfg["league"] == "Standard"
    # zero-click: the contact starts the first price round by itself
    rates_file = core.rates.path
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not (rates_file.is_file() and not core.rates._busy):
        time.sleep(0.05)
    assert rates_file.is_file()
    assert json.loads(rates_file.read_text(encoding="utf-8"))["rates"]
    assert net.calls and all(CONTACT in c[2]["User-Agent"] for c in net.calls)


@pytest.mark.server
def test_contact_value_is_in_no_get_export_report_or_log(api, caplog):
    srv, core, net = api
    caplog.set_level(logging.DEBUG)
    status, raw = _req(srv, "POST", "/api/web-data", {"contact": CONTACT})
    assert status == 200 and CONTACT.encode() not in raw
    assert core.contact() == CONTACT and net.calls == []  # web data still off
    # also turned on together with the contact, in one body
    status, raw = _req(srv, "POST", "/api/web-data", {"enabled": False, "contact": CONTACT})
    assert status == 200 and CONTACT.encode() not in raw
    for path in ("/api/web-data", "/api/rates", "/api/state", "/api/settings-export",
                 "/api/health", "/api/version"):
        status, raw = _req(srv, "GET", path)
        assert status == 200, path
        assert CONTACT.encode() not in raw, path
    assert _doc(_req(srv, "GET", "/api/web-data")[1])["contact_set"] is True
    # the Checks report the player copies
    core.tick_diag(force=True)
    diag_doc = json.dumps(core.state.snapshot()["diag"])
    assert CONTACT not in diag_doc
    # the logs: no record, and no runtime file but the config and its .bak
    assert all(CONTACT not in r.getMessage() for r in caplog.records)
    keep = {core.config_path, core.config_path.with_name(core.config_path.name + ".bak")}
    for f in core.runtime.rglob("*"):
        if f.is_file() and f not in keep:
            assert CONTACT.encode() not in f.read_bytes(), f.name


@pytest.mark.server
def test_unusable_contact_is_refused_and_nothing_is_written(api):
    srv, core, net = api
    _write_cfg(core, {"league": "Standard"})
    before = core.config_path.read_bytes()
    bad = ["a(b)", "back\\slash", "x" * 121, "tab\there", "caf" + chr(233), 7, None, ["a"]]
    for value in bad:
        status, raw = _req(srv, "POST", "/api/web-data", {"contact": value})
        assert status == 400, value
        err = _doc(raw)["error"]
        assert "contact" in err and "local.json" not in err and "\\" not in err
        assert core.config_path.read_bytes() == before, value
    # a refused contact also stops the opt-in in the same body
    status, _raw = _req(srv, "POST", "/api/web-data", {"enabled": True, "contact": "a(b)"})
    assert status == 400 and core.config_path.read_bytes() == before
    # neither key, or a non-bool switch: still a 400
    assert _req(srv, "POST", "/api/web-data", {})[0] == 400
    assert _req(srv, "POST", "/api/web-data", {"enabled": "yes", "contact": CONTACT})[0] == 400
    assert core.config_path.read_bytes() == before
    # a hand-broken config with no .bak is never overwritten (500)
    core.config_path.write_text("{broken", encoding="ascii")
    assert _req(srv, "POST", "/api/web-data", {"contact": CONTACT})[0] == 500
    assert core.config_path.read_text(encoding="ascii") == "{broken"
    with pytest.raises(ValueError):
        core.set_contact("a(b)")
    assert net.calls == []


@pytest.mark.server
def test_empty_contact_clears_the_key(api):
    srv, core, _net = api
    for blank in ("", "   "):
        _write_cfg(core, {"contact": CONTACT, "league": "Standard", "web_data": True})
        assert _doc(_req(srv, "GET", "/api/web-data")[1])["contact_set"] is True
        status, raw = _req(srv, "POST", "/api/web-data", {"contact": blank})
        assert status == 200
        doc = _doc(raw)
        assert doc["contact_set"] is False and doc["blocked"] == "contact not set"
        cfg = _cfg(core)
        assert "contact" not in cfg
        assert cfg["league"] == "Standard" and cfg["web_data"] is True
    # clearing an unset contact is a no-op answer, not an error
    assert core.set_contact("") is False and "contact" not in _cfg(core)
