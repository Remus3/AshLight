"""HOTKEYS-LIVE (decision 0058, OVL-KEYS-CORE, F-026): the core side of the
two global keys. read_runtime validates and bounds the client's
ops/runtime/hotkeys.json; the snapshot carries the effective keys; POST
/api/hotkeys needs the token, keeps the Host / Origin checks, refuses a
game key and the other shortcut's key, and writes config/local.json; the
fallback lists equal the shared case table.

The server binds an ephemeral port (0); runtime state goes to tmp_path. No
key is registered here and nothing is sent anywhere but the loopback test
server."""

import http.client
import json
import os
import threading
from pathlib import Path

import pytest

from server.al import hotkeys
from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "app" / "test" / "hotkey_cases.json").read_text(encoding="utf-8"))
TOKEN = "k" * 48


def _doc(eval_=None, toggle=None, user_on=True):
    """A hotkeys.json document as app/parts/20-hotkeys.js writes it."""
    def entry(want, bound, registered=True, fallback=False):
        return {"want": want, "bound": bound, "registered": registered, "fallback": fallback}
    return {"updated": "2026-11-20T00:00:00.000Z",
            "keys": {"eval": eval_ or entry("Alt+Shift+E", "Alt+Shift+E"),
                     "toggle": toggle or entry("Alt+Shift+A", "Alt+Shift+A")},
            "overlay": {"user_on": user_on}}


def _write(dirpath, doc):
    path = Path(dirpath) / hotkeys.FILE_NAME
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="ascii")
    return path


# -- read_runtime

def test_read_runtime_reads_the_client_file(tmp_path):
    assert hotkeys.read_runtime(tmp_path) is None  # no file
    _write(tmp_path, _doc(eval_={"want": "Alt+Shift+E", "bound": "Ctrl+Shift+F9",
                                 "registered": True, "fallback": True}, user_on=False))
    rt = hotkeys.read_runtime(tmp_path)
    assert rt == {"eval": {"key": "Ctrl+Shift+F9", "want": "Alt+Shift+E",
                           "registered": True, "fallback": True},
                  "toggle": {"key": "Alt+Shift+A", "want": "Alt+Shift+A",
                             "registered": True, "fallback": False},
                  "overlay_on": False}


def test_read_runtime_drops_bad_parts(tmp_path):
    doc = _doc(eval_={"want": "Ctrl+C", "bound": "Ctrl+C", "registered": True,
                      "fallback": "yes"},
               toggle={"want": "C", "bound": None, "registered": False, "fallback": False})
    doc["overlay"] = {"user_on": "off"}
    _write(tmp_path, doc)
    rt = hotkeys.read_runtime(tmp_path)
    # a game key is never shown as bound: the claimed binding reads unknown
    assert rt["eval"] == {"key": None, "want": None, "registered": None, "fallback": None}
    assert rt["toggle"] == {"key": None, "want": None, "registered": False, "fallback": False}
    assert rt["overlay_on"] is None
    for bad in ({"keys": [], "overlay": 5}, {"keys": {"eval": "x"}}):
        _write(tmp_path, bad)
        rt = hotkeys.read_runtime(tmp_path)
        assert rt["eval"]["registered"] is None and rt["overlay_on"] is None
    for doc in ([1, 2], "text", None):
        _write(tmp_path, doc)
        assert hotkeys.read_runtime(tmp_path) is None
    (tmp_path / hotkeys.FILE_NAME).write_bytes(b"{not json")
    assert hotkeys.read_runtime(tmp_path) is None
    (tmp_path / hotkeys.FILE_NAME).write_bytes(b'{"keys": "\xe9"}')
    assert hotkeys.read_runtime(tmp_path) is None  # the client writes ASCII only
    (tmp_path / hotkeys.FILE_NAME).write_bytes(b"[" * 100000 + b"]" * 100000)
    assert hotkeys.read_runtime(tmp_path) is None


def test_read_runtime_is_bounded(tmp_path):
    doc = _doc()
    doc["pad"] = "x" * hotkeys.MAX_FILE_BYTES
    _write(tmp_path, doc)
    assert hotkeys.read_runtime(tmp_path) is None
    os.remove(tmp_path / hotkeys.FILE_NAME)
    (tmp_path / hotkeys.FILE_NAME).mkdir()  # not a file
    assert hotkeys.read_runtime(tmp_path) is None


def test_view_without_a_runtime_file():
    v = hotkeys.view({"eval_hotkey": "ctrl+alt+k", "overlay_toggle": "Ctrl+C"}, None)
    assert v == {"eval": {"key": None, "want": "Ctrl+Alt+K", "registered": None,
                          "fallback": None},
                 "toggle": {"key": None, "want": "Alt+Shift+A", "registered": None,
                            "fallback": None},
                 "overlay_on": None}
    assert hotkeys.view(None, "junk")["eval"]["want"] == "Alt+Shift+E"


def test_fallbacks_equal_the_case_table():
    assert {k: list(v) for k, v in hotkeys.FALLBACKS.items()} == CASES["fallbacks"]
    assert set(hotkeys.FALLBACKS) == set(hotkeys.NAMES) == set(hotkeys.CONFIG_KEYS)
    assert hotkeys.CONFIG_KEYS == {"eval": "eval_hotkey", "toggle": "overlay_toggle"}
    for keys in hotkeys.FALLBACKS.values():
        assert len(keys) <= 4
        for k in keys:
            assert hotkeys.safe_accelerator(k) == k and k not in hotkeys.GAME_KEYS


# -- the core: snapshot and set_hotkey

def test_snapshot_carries_hotkeys(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    try:
        core.tick_diag(force=True)
        hk = core.state.snapshot()["hotkeys"]
        assert hk["eval"]["key"] is None and hk["eval"]["want"] == "Alt+Shift+E"
        v0 = core.state.version
        core.tick_diag(force=True)
        assert core.state.version == v0  # no change, no bump
        _write(tmp_path, _doc(toggle={"want": "Alt+Shift+A", "bound": "Ctrl+Shift+F10",
                                      "registered": True, "fallback": True},
                              user_on=False))
        core.tick_diag()  # throttled checks, but the keys are re-read
        hk = core.state.snapshot()["hotkeys"]
        assert hk["toggle"]["key"] == "Ctrl+Shift+F10" and hk["overlay_on"] is False
        assert hk["eval"]["key"] == "Alt+Shift+E"
        # the Checks card shows the fallback and the overlay-off note
        core.tick_diag(force=True)
        rows = {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}
        assert rows["hotkey_toggle"]["status"] == "note"
        assert rows["overlay_off"]["detail"].endswith("Press Ctrl+Shift+F10 to show it.")
    finally:
        core.close()


def test_runtime_file_is_read_only_when_its_stat_changes(tmp_path, monkeypatch):
    core = Core(runtime=tmp_path, tail=False)
    try:
        _write(tmp_path, _doc())
        calls = []
        real = hotkeys.read_runtime
        monkeypatch.setattr(hotkeys, "read_runtime",
                            lambda d: calls.append(1) or real(d))
        for _ in range(5):
            core.tick_diag()
        assert calls == [1]
        path = tmp_path / hotkeys.FILE_NAME
        _write(tmp_path, _doc(user_on=False))
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
        core.tick_diag()
        assert calls == [1, 1]
        assert core.state.snapshot()["hotkeys"]["overlay_on"] is False
    finally:
        core.close()


def test_set_hotkey_writes_the_config(tmp_path):
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps({"contact": "someone", "web_data": False}), encoding="ascii")
    core = Core(runtime=tmp_path, tail=False, config_path=cfg)
    try:
        view = core.set_hotkey("eval", "ctrl+shift+f8")
        assert view["eval"]["want"] == "Ctrl+Shift+F8"
        stored = json.loads(cfg.read_text(encoding="ascii"))
        assert stored == {"contact": "someone", "web_data": False,
                          "eval_hotkey": "Ctrl+Shift+F8"}
        assert core.state.snapshot()["hotkeys"]["eval"]["want"] == "Ctrl+Shift+F8"
        core.set_hotkey("toggle", "Alt+Shift+F11")
        assert json.loads(cfg.read_text(encoding="ascii"))["overlay_toggle"] == "Alt+Shift+F11"
        for name, key in (("eval", "Ctrl+C"), ("eval", "C"), ("toggle", "Alt+F4"),
                          ("eval", "Alt+Shift+F11"), ("toggle", "Ctrl+Shift+F8"),
                          ("both", "Alt+Shift+K")):
            with pytest.raises(ValueError):
                core.set_hotkey(name, key)
        stored = json.loads(cfg.read_text(encoding="ascii"))
        assert stored["eval_hotkey"] == "Ctrl+Shift+F8"
        assert stored["overlay_toggle"] == "Alt+Shift+F11"
    finally:
        core.close()


def test_set_hotkey_refuses_the_other_keys_bound_fallback(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    try:
        _write(tmp_path, _doc(toggle={"want": "Alt+Shift+A", "bound": "Ctrl+Shift+F10",
                                      "registered": True, "fallback": True}))
        with pytest.raises(ValueError, match="same key as the overlay hotkey"):
            core.set_hotkey("eval", "Ctrl+Shift+F10")
        with pytest.raises(ValueError, match="same key as the overlay hotkey"):
            core.set_hotkey("eval", "Alt+Shift+A")
        assert core.set_hotkey("eval", "Ctrl+Shift+F9")["eval"]["want"] == "Alt+Shift+E"
        # the runtime file still names the old want until the client
        # re-registers; the config holds the new one
        assert json.loads((tmp_path / "local.json").read_text(encoding="ascii")) == \
            {"eval_hotkey": "Ctrl+Shift+F9"}
    finally:
        core.close()


# -- POST /api/hotkeys

@pytest.fixture
def srv(tmp_path):
    core = Core(runtime=tmp_path / "rt", tail=False)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def post(server, body, headers=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{server.port}", "Content-Type": "application/json"}
    h.update(headers or {})
    conn.request("POST", "/api/hotkeys", body=json.dumps(body).encode("ascii"), headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, (json.loads(data) if data.startswith(b"{") else data)


def auth():
    return {"X-AL-Token": TOKEN}


def _config(server):
    path = server.core.config_path
    return json.loads(path.read_text(encoding="ascii")) if path.is_file() else {}


def test_post_needs_the_token(srv):
    body = {"name": "eval", "key": "Ctrl+Shift+F8"}
    assert post(srv, body)[0] == 401
    assert post(srv, body, {"X-AL-Token": "wrong"})[0] == 401
    assert _config(srv) == {}


def test_post_keeps_host_and_origin_checks(srv):
    body = {"name": "eval", "key": "Ctrl+Shift+F8"}
    assert post(srv, body, auth(), host=f"evil.example:{srv.port}")[0] == 400
    assert post(srv, body, {**auth(), "Origin": "http://evil.example"})[0] == 403
    assert post(srv, body, {**auth(), "Sec-Fetch-Site": "cross-site"})[0] == 403
    assert _config(srv) == {}


def test_post_writes_the_config(srv):
    status, doc = post(srv, {"name": "toggle", "key": "alt+shift+f11"}, auth())
    assert status == 200 and doc["hotkeys"]["toggle"]["want"] == "Alt+Shift+F11"
    assert set(doc["hotkeys"]) == {"eval", "toggle", "overlay_on"}
    assert _config(srv) == {"overlay_toggle": "Alt+Shift+F11"}


def test_post_refuses_a_game_key_and_the_other_key(srv):
    for key in ("Ctrl+C", "Alt+F4", "Ctrl+Alt+C", "C", "Shift+C", "Win+D"):
        status, doc = post(srv, {"name": "eval", "key": key}, auth())
        assert status == 400, key
        assert doc["error"] == ("The item check hotkey needs Ctrl or Alt held with a "
                                "key, and can't be a key the game uses.")
    status, doc = post(srv, {"name": "eval", "key": "Alt+Shift+A"}, auth())
    assert status == 400
    assert doc["error"] == "The item check hotkey can't be the same key as the overlay hotkey."
    status, doc = post(srv, {"name": "toggle", "key": "Alt+Shift+E"}, auth())
    assert status == 400 and "item check hotkey" in doc["error"]
    for body in ({"name": "zap", "key": "Alt+Shift+K"}, {"name": "eval"},
                 {"name": "eval", "key": 5}, {}):
        assert post(srv, body, auth())[0] == 400, body
    assert _config(srv) == {}


def test_post_on_a_broken_config_writes_nothing(srv):
    path = srv.core.config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="ascii")
    status, doc = post(srv, {"name": "eval", "key": "Ctrl+Shift+F8"}, auth())
    assert status == 500
    assert path.read_text(encoding="ascii") == "{broken"
