"""UI-CARD-COLLAPSE (decision 0082 amendment 2026-11-19): the card layout
store (server/al/uilayout.py) and its token-gated GET / PUT /api/ui/layout
plug route (server/al/plug/uilayout.py).

The server binds an ephemeral port (0) so a running AshLight is never
touched; runtime state goes to tmp_path.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import http as al_http
from server.al import jsonfile, plug, settingsio, uilayout
from server.al.core import Core
from server.al.plug import stores
from server.al.plug import uilayout as plug_uilayout

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "u" * 48
PATH = "/api/ui/layout"


def _core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    return Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setattr(al_http, "DRAIN_TIMEOUT_S", 0.05)
    core = _core(tmp_path)
    server = al_http.serve(core, TOKEN, port=0, web_root=ROOT / "web",
                           tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def req(server, method, path, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    h = {"Host": f"127.0.0.1:{server.port}"}
    h.update(headers or {})
    if body is not None and not isinstance(body, bytes):
        body = json.dumps(body).encode("ascii")
        h.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, data


def auth():
    return {"X-AL-Token": TOKEN}


# -- the store ----------------------------------------------------------------

def test_card_ids_are_build_and_run_cards_only():
    assert uilayout.CARD_IDS == uilayout.BUILD_CARDS + uilayout.RUN_CARDS
    assert len(set(uilayout.CARD_IDS)) == 12
    # Play's regions and Settings never collapse
    for cid in uilayout.CARD_IDS:
        assert not cid.startswith("play-") and "settings" not in cid
    # every id is a card section of web/index.html (the page and the store agree)
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    for cid in uilayout.CARD_IDS:
        if cid == "eventsbox":  # the Recent card, found by its class (web/collapse.js)
            assert '<section class="card grid-card events"' in html
            continue
        assert f'<section id="{cid}" class="card' in html, cid


def test_missing_file_means_all_open(tmp_path):
    store = uilayout.UiLayout(tmp_path / "ui_layout.json")
    view = store.view()
    assert view["schema"] == 1 and view["cards"] == list(uilayout.CARD_IDS)
    assert view["collapsed"] == {k: False for k in uilayout.CARD_IDS}
    assert not (tmp_path / "ui_layout.json").exists()  # a read writes nothing


def test_update_saves_with_one_bak_and_reloads(tmp_path):
    path = tmp_path / "ui_layout.json"
    store = uilayout.UiLayout(path)
    store.update({"collapsed": {"buildbox": True, "actsbox": True, "zzq": True}})
    doc = json.loads(path.read_text(encoding="ascii"))
    assert doc == {"schema": 1, "collapsed": {"buildbox": True, "actsbox": True}}
    assert jsonfile.bak_path(path).read_bytes() == path.read_bytes()
    store.update({"collapsed": {"buildbox": False}})
    again = uilayout.UiLayout(path).view()["collapsed"]
    assert [k for k, v in again.items() if v] == ["actsbox"]
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.decode("ascii")


@pytest.mark.parametrize("body", [
    None, [], "x", {}, {"collapsed": []}, {"collapsed": {"buildbox": 1}},
    {"collapsed": {"buildbox": "true"}}, {"collapsed": {}, "extra": 1},
    {"collapsed": {"buildbox": None}},
])
def test_bad_bodies_are_refused_and_change_nothing(tmp_path, body):
    path = tmp_path / "ui_layout.json"
    store = uilayout.UiLayout(path)
    with pytest.raises(uilayout.LayoutError):
        store.update(body)
    assert not path.exists()
    assert not any(store.view()["collapsed"].values())


def test_file_bounds_drop_unknown_ids_and_bad_values(tmp_path):
    path = tmp_path / "ui_layout.json"
    path.write_text(json.dumps({"schema": 1, "collapsed": {
        "buildbox": True, "play-c": True, "settings": True, "mapsbox": "yes",
        "healthbox": False}}), encoding="ascii")
    got = uilayout.UiLayout(path).view()["collapsed"]
    assert [k for k, v in got.items() if v] == ["buildbox"]
    for bad in ('{"schema": 2, "collapsed": {"buildbox": true}}', "[1]", "not json",
                '{"schema": 1, "collapsed": [1]}'):
        path.write_text(bad, encoding="ascii")
        assert not any(uilayout.UiLayout(path).view()["collapsed"].values()), bad
    path.write_bytes(b"{" + b" " * uilayout.MAX_BYTES + b"}")
    assert not any(uilayout.UiLayout(path).view()["collapsed"].values())


def test_damaged_file_is_restored_from_its_bak(tmp_path):
    path = tmp_path / "ui_layout.json"
    uilayout.UiLayout(path).update({"collapsed": {"deathsbox": True}})
    jsonfile.pop_restored()
    path.write_text("{broken", encoding="ascii")
    got = uilayout.UiLayout(path).view()["collapsed"]
    assert got["deathsbox"] is True
    assert str(path) in jsonfile.pop_restored()
    assert json.loads(path.read_text(encoding="ascii"))["collapsed"] == {"deathsbox": True}


# -- the plug: attach, Saver retry, Checks words ------------------------------

def test_attach_makes_the_store_saver_and_tick(tmp_path):
    core = _core(tmp_path)
    try:
        assert isinstance(core.ui_layout, uilayout.UiLayout)
        assert core.ui_layout.path == Path(core.runtime) / "ui_layout.json"
        assert plug_uilayout.SAVER in core.savers
        assert plug_uilayout.tick(core) is True
    finally:
        core.close()


def test_failed_write_keeps_the_change_and_retries(srv, monkeypatch):
    core = srv.core
    real = jsonfile.write_json
    fail = {"on": True}

    def flaky(path, doc, **kw):
        if fail["on"] and Path(path).name == "ui_layout.json":
            raise OSError("disk full")
        return real(path, doc, **kw)

    monkeypatch.setattr(jsonfile, "write_json", flaky)
    status, data = req(srv, "PUT", PATH, auth(), {"collapsed": {"evalbox": True}})
    body = json.loads(data)
    assert status == 200 and body["saved"] is False and body["collapsed"]["evalbox"] is True
    saver = core.savers[plug_uilayout.SAVER]
    assert saver.dirty
    # the Checks row names the card layout while it is unsaved
    rows = stores.rows(stores.facts(core, 0), 0)
    assert rows and rows[0]["id"] == "stores_unsaved" and "card layout" in rows[0]["detail"]
    fail["on"] = False
    assert saver.flush(force=True) is True
    path = Path(core.runtime) / "ui_layout.json"
    assert json.loads(path.read_text(encoding="ascii"))["collapsed"] == {"evalbox": True}
    assert stores.rows(stores.facts(core, 0), 0) == []


def test_store_words_name_the_layout():
    assert stores.unsaved_text(["uilayout"]) == (
        "AshLight couldn't save your card layout yet. It keeps trying on its own.")
    assert stores.restored_text(["ui_layout.json"]) == (
        "The card layout was damaged and restored from the last good copy.")


# -- the routes ---------------------------------------------------------------

def test_routes_are_plug_routes():
    assert ("GET", PATH) in plug.all_routes() and ("PUT", PATH) in plug.all_routes()
    assert PATH not in al_http.GET_ROUTES and PATH not in al_http.PUT_ROUTES


def test_get_and_put_round_trip(srv):
    status, data = req(srv, "GET", PATH, auth())
    assert status == 200
    assert json.loads(data)["collapsed"] == {k: False for k in uilayout.CARD_IDS}
    status, data = req(srv, "PUT", PATH, auth(), {"collapsed": {"charsbox": True}})
    assert status == 200 and json.loads(data)["saved"] is True
    status, data = req(srv, "GET", PATH, auth())
    got = json.loads(data)["collapsed"]
    assert [k for k, v in got.items() if v] == ["charsbox"]


def test_routes_need_the_token_and_refuse_bad_bodies(srv):
    assert req(srv, "GET", PATH)[0] == 401
    assert req(srv, "PUT", PATH, None, {"collapsed": {}})[0] == 401
    assert req(srv, "GET", f"{PATH}?token={TOKEN}")[0] == 401
    assert req(srv, "PUT", PATH, {**auth(), "Sec-Fetch-Site": "cross-site"},
               {"collapsed": {}})[0] == 403
    assert req(srv, "PUT", PATH, {**auth(), "Content-Type": "text/plain"}, b"{}")[0] == 415
    status, data = req(srv, "PUT", PATH, auth(), {"collapsed": {"buildbox": "yes"}})
    assert status == 400 and json.loads(data) == {"error": uilayout.BAD_BODY}
    assert req(srv, "POST", PATH, auth(), {"collapsed": {}})[0] == 404
    assert not (Path(srv.core.runtime) / "ui_layout.json").exists()


# -- not exported, not cleared --------------------------------------------------

def test_not_in_the_settings_export_and_not_cleared_with_run_history(srv):
    req(srv, "PUT", PATH, auth(), {"collapsed": {"summarybox": True}})
    status, data = req(srv, "GET", "/api/settings-export", auth())
    assert status == 200
    assert b"collapsed" not in data and b"ui_layout" not in data and b"summarybox" not in data
    assert not any("layout" in k and "overlay" not in k for k in settingsio.ALLOWED)
    status, _ = req(srv, "POST", "/api/run-history", auth(), {"clear": True})
    assert status == 200
    status, data = req(srv, "GET", PATH, auth())
    assert json.loads(data)["collapsed"]["summarybox"] is True
