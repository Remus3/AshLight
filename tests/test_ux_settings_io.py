"""UX-SETTINGS-IO: settings export / import (research 0028 ruling E).
Round trip, secret exclusion, bad files, web data never switched on."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import settingsio
from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
FULL = {"character": "Ash", "poll_ms": 300, "overlay_toggle": "Alt+Shift+A",
        "eval_hotkey": "Alt+Shift+E", "league": "Standard", "web_data": True,
        "tc_calc": False, "underlevel_gap": 4, "run_history": False,
        "price_watch_pct": 30, "boots_speed_level": 20,
        "overlay": {"display": "primary", "corner": "top-left", "scale": 1.2,
                    "opacity": 0.95, "margin": 20},
        # never exported
        "contact": "someone-at-example", "client_log": "somewhere/logs/Client.txt",
        "port": 8961, "loop": {"inbox_dir": ""}, "token": "t" * 48}


def test_export_holds_allowed_keys_only():
    doc = settingsio.export_doc(FULL, "1.2.3")
    assert doc["kind"] == settingsio.KIND and doc["schema"] == 1
    assert set(doc["settings"]) == set(settingsio.ALLOWED)
    text = json.dumps(doc)
    for secret in ("someone-at-example", "Client.txt", "8961", "inbox_dir", "t" * 48):
        assert secret not in text
    for key in settingsio.NEVER:
        assert key not in settingsio.ALLOWED and key not in doc["settings"]


def test_export_skips_bad_stored_values():
    doc = settingsio.export_doc({"poll_ms": "fast", "league": "Dawn", "overlay": 5}, "v")
    assert doc["settings"] == {"league": "Dawn"}


def test_round_trip():
    doc = json.loads(json.dumps(settingsio.export_doc(FULL, "v")))
    update, report = settingsio.parse_import(doc, {"web_data": True})
    want = {k: v for k, v in FULL.items() if k in settingsio.ALLOWED}
    assert update == want
    assert report == {"applied": sorted(want), "ignored": [], "web_data_offered": False,
                      "tc_calc_offered": False}


def test_web_data_never_switched_on_by_import():
    doc = settingsio.export_doc({"web_data": True, "league": "L"}, "v")
    update, report = settingsio.parse_import(doc, {"web_data": False})
    assert "web_data" not in update and report["web_data_offered"] is True
    off = settingsio.export_doc({"web_data": False}, "v")
    update, report = settingsio.parse_import(off, {"web_data": True})
    assert update == {"web_data": False} and report["web_data_offered"] is False


def test_unknown_and_secret_keys_are_not_applied():
    doc = {"kind": settingsio.KIND, "schema": 1,
           "settings": {"league": "L", "contact": "x", "client_log": "logs/x", "port": 1,
                        "future_key": 1, "token": "abc"}}
    update, report = settingsio.parse_import(doc, {})
    assert update == {"league": "L"}
    assert report["ignored"] == ["client_log", "contact", "future_key", "port", "token"]


@pytest.mark.parametrize("doc", [
    None, [], "x", {}, {"kind": "other", "schema": 1, "settings": {}},
    {"kind": settingsio.KIND, "schema": 2, "settings": {}},
    {"kind": settingsio.KIND, "schema": 1, "settings": []},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"poll_ms": 1}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"web_data": "yes"}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"overlay": {"scale": 9}}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"overlay": {"evil": 1}}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"eval_hotkey": "Alt+\n;rm"}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"league": "x" * 65}},
])
def test_bad_files_refused(doc):
    with pytest.raises(settingsio.SettingsError):
        settingsio.parse_import(doc, {})


def _post(port, path, body, token="f" * 48, ctype="application/json"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    raw = body if isinstance(body, bytes) else json.dumps(body).encode("ascii")
    conn.request("POST", path, body=raw, headers={
        "Host": f"127.0.0.1:{port}", "X-AL-Token": token, "Content-Type": ctype,
        "Content-Length": str(len(raw))})
    r = conn.getresponse()
    out = (r.status, r.read().decode("ascii"))
    conn.close()
    return out


def _get(port, path, token="f" * 48):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": f"127.0.0.1:{port}"}
    if token:
        h["X-AL-Token"] = token
    conn.request("GET", path, headers=h)
    r = conn.getresponse()
    out = (r.status, r.getheader("Content-Disposition"), r.read().decode("ascii"))
    conn.close()
    return out


def test_http_export_download_and_import(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps(FULL), encoding="ascii")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False, config_path=cfg)
    server = serve(core, "f" * 48, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        assert _get(server.port, "/api/settings-export", token=None)[0] in (401, 403)
        status, disp, text = _get(server.port, "/api/settings-export")
        assert status == 200
        assert disp == f'attachment; filename="{settingsio.FILE_NAME}"'
        assert "someone-at-example" not in text and "Client.txt" not in text
        exported = json.loads(text)
        # import into a computer with web data off and other settings
        cfg.write_text(json.dumps({"web_data": False, "contact": "keep-me",
                                   "client_log": "other/logs"}), encoding="ascii")
        status, body = _post(server.port, "/api/settings-import", exported)
        assert status == 200
        report = json.loads(body)
        assert report["web_data_offered"] is True and "web_data" not in report["applied"]
        saved = json.loads(cfg.read_text(encoding="ascii"))
        assert saved["web_data"] is False            # never switched on
        assert saved["contact"] == "keep-me"          # local secret kept
        assert saved["client_log"] == "other/logs"          # local path kept
        assert saved["league"] == "Standard" and saved["underlevel_gap"] == 4
        assert core.state.snapshot()["overlay_layout"]["corner"] == "top-left"
        # bad file: nothing applied
        before = cfg.read_text(encoding="ascii")
        status, body = _post(server.port, "/api/settings-import",
                             {"kind": "nope", "settings": {"league": "Z"}})
        assert status == 400 and "isn't an AshLight settings file" in body
        assert cfg.read_text(encoding="ascii") == before
        # oversized body refused before reading
        big = json.dumps({"kind": settingsio.KIND, "schema": 1,
                          "settings": {"pad": "x" * (settingsio.MAX_BYTES + 10)}})
        assert _post(server.port, "/api/settings-import", big.encode("ascii"))[0] == 413
        # history and watch endpoints
        status, body = _post(server.port, "/api/run-history", {"clear": True})
        assert status == 200 and json.loads(body)["run_history"]["runs"] == 0
        assert _post(server.port, "/api/run-history", {})[0] == 400
        status, body = _post(server.port, "/api/price-watch", {"clear": True})
        assert status == 200 and json.loads(body)["price_watch"]["count"] == 0
        assert _post(server.port, "/api/price-watch", {"clear": 1})[0] == 400
    finally:
        server.stop()
        core.close()
