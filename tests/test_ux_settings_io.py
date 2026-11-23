"""UX-SETTINGS-IO: settings export / import (research 0028 ruling E).
Round trip, secret exclusion, bad files, web data never switched on.
TC-WEIGHTS-DELTA-EXPORT: schema 2 carries the stat weight changes; schema 1
files still import."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import settingsio
from server.al.core import Core
from server.al.http import serve
from server.al.theorycraft import weights as weights_mod

ROOT = Path(__file__).resolve().parents[1]
FULL = {"character": "Ash", "poll_ms": 300, "overlay_toggle": "Alt+Shift+A",
        "eval_hotkey": "Alt+Shift+E", "league": "Standard", "web_data": True,
        "tc_calc": False, "underlevel_gap": 4, "run_history": False,
        "price_watch_pct": 30, "boots_speed_level": 20, "worn_gear": False,
        "wear_hotkey": "Ctrl+Shift+F7",
        "update_click_only": True,  # REL-UPDATE-TRIGGER: the click-only switch
        "theme": "light",  # PLAY-TD-04B-THEME-CHOICE: the Theme choice
        "overlay": {"display": "primary", "corner": "top-left", "scale": 1.2,
                    "opacity": 0.95, "margin": 20,
                    # OVL-OVERLAY-KEYS: the new keys round trip too
                    "parts": {"zone": True, "timer": False, "level": True,
                              "deaths": True, "status": True, "trade": False,
                              "item": True, "moment": True, "hint": False},
                    "quiet_town": True, "zone_guide": "never",
                    # OVL-TD05-PLATE: the schema marker round trips
                    "v": 2},
        # never exported
        "contact": "someone-at-example", "client_log": "somewhere/logs/Client.txt",
        "port": 8961, "loop": {"inbox_dir": ""}, "token": "t" * 48}


def test_export_holds_allowed_keys_only():
    doc = settingsio.export_doc(FULL, "1.2.3")
    assert doc["kind"] == settingsio.KIND and doc["schema"] == settingsio.SCHEMA == 2
    assert "weights" not in doc  # no block unless the core passes one
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
                      "tc_calc_offered": False, "weights_applied": False}


def test_overlay_export_import_keeps_v2():
    """OVL-TD05-PLATE: export and import keep the "v": 2 layout as is; an
    old stored layout or an old export (no "v") migrates its 0.9 to 1.0
    opacity onto the 0.86 to 1.0 plate alpha once and carries v 2 after."""
    doc = json.loads(json.dumps(settingsio.export_doc(FULL, "v")))
    assert doc["settings"]["overlay"]["v"] == 2
    assert doc["settings"]["overlay"]["opacity"] == 0.95
    update, _report = settingsio.parse_import(doc, {})
    assert update["overlay"] == FULL["overlay"]
    old = {"display": "primary", "corner": "top-left", "scale": 1.2,
           "opacity": 0.95, "margin": 20}
    doc = settingsio.export_doc({"overlay": old}, "v")
    assert doc["settings"]["overlay"]["v"] == 2
    assert doc["settings"]["overlay"]["opacity"] == 0.93
    old_file = {"kind": settingsio.KIND, "schema": 1, "settings": {"overlay": old}}
    update, _report = settingsio.parse_import(old_file, {})
    assert update["overlay"]["v"] == 2 and update["overlay"]["opacity"] == 0.93
    again, _report = settingsio.parse_import(
        {"kind": settingsio.KIND, "schema": 1, "settings": update}, {})
    assert again["overlay"] == update["overlay"]  # once, never mapped twice


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
    {"kind": settingsio.KIND, "schema": 3, "settings": {}},
    {"kind": settingsio.KIND, "schema": True, "settings": {}},
    {"kind": settingsio.KIND, "schema": 2, "settings": {}, "weights": []},
    {"kind": settingsio.KIND, "schema": 2, "settings": {}, "weights": {"weights": 5}},
    {"kind": settingsio.KIND, "schema": 2, "settings": {},
     "weights": {"weights": {"+# to maximum Life": "lots"}}},
    {"kind": settingsio.KIND, "schema": 2, "settings": {},
     "weights": {"weights": {"not a default row": None}}},
    {"kind": settingsio.KIND, "schema": 2, "settings": {},
     "weights": {"weights": {}, "sidegrade": {"abs": -1}}},
    {"kind": settingsio.KIND, "schema": 2, "settings": {},
     "weights": {"weights": {}, "sidegrade": {"evil": 1}}},
    {"kind": settingsio.KIND, "schema": 2, "settings": {},
     "weights": {"weights": {f"+# to Stat {i}": 1 for i in range(weights_mod.MAX_KEYS)}}},
    {"kind": settingsio.KIND, "schema": 1, "settings": []},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"poll_ms": 1}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"web_data": "yes"}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"overlay": {"scale": 9}}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"overlay": {"evil": 1}}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"eval_hotkey": "Alt+\n;rm"}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"league": "x" * 65}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"wear_hotkey": "Ctrl+C"}},
    {"kind": settingsio.KIND, "schema": 1, "settings": {"wear_hotkey": "W"}},
])
def test_bad_files_refused(doc):
    with pytest.raises(settingsio.SettingsError):
        settingsio.parse_import(doc, {})


CHANGES = {"weights": {"+# to maximum Life": 2.5, "+# to Spirit": None,
                       "#% increased Fire Damage": 0.7},
           "sidegrade": {"pct": 8.0}}


def _two_cores(tmp_path, src_cfg, dst_cfg):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(src_cfg), encoding="ascii")
    b.write_text(json.dumps(dst_cfg), encoding="ascii")
    src = Core(runtime=tmp_path / "ra", log_path=str(log), tail=False, config_path=a)
    dst = Core(runtime=tmp_path / "rb", log_path=str(log), tail=False, config_path=b)
    return src, dst, b


def test_schema_2_round_trips_weight_changes(tmp_path):
    """TC-WEIGHTS-DELTA-EXPORT (F-134): the export carries the weights
    store's changes (a changed row, a removed default row as null, an added
    row, a band part) and an import on another computer puts the same
    merged weights in place, with the same changes, and re-scores; a bad
    block refuses the whole file with nothing applied."""
    doc = json.loads(json.dumps(settingsio.export_doc(FULL, "v", weights=CHANGES)))
    assert doc["schema"] == 2 and doc["weights"] == CHANGES
    text = json.dumps(doc)
    for secret in ("someone-at-example", "Client.txt", "inbox_dir", "t" * 48):
        assert secret not in text
    update, report = settingsio.parse_import(doc, {"web_data": True})
    assert report["weights_applied"] is True and "weights" not in update
    full = settingsio.weights_of(doc)
    assert full == weights_mod.merge(weights_mod.validate_overrides(CHANGES))
    assert "+# to Spirit" not in full["weights"] and full["sidegrade"]["pct"] == 8.0
    # a block the store would refuse is left out of the export, never fatal
    bad = {"weights": {"+# to maximum Life": float("nan")}}
    assert "weights" not in settingsio.export_doc({}, "v", weights=bad)
    # through two cores: export from one, import into another
    src, dst, dst_cfg = _two_cores(tmp_path, {"league": "Standard"},
                                   {"league": "Other", "contact": "keep-me"})
    try:
        src.weights.put(weights_mod.merge(weights_mod.validate_overrides(CHANGES)))
        exported = json.loads(settingsio._text(src.export_settings()))
        assert exported["weights"] == src.weights.snapshot()["changed"]
        assert len(settingsio._text(exported)) <= settingsio.MAX_BYTES
        reruns = []
        dst.last_eval.rerun = lambda: reruns.append(1)
        report = dst.import_settings(exported)
        assert report["weights_applied"] is True and report["applied"] == ["league"]
        assert reruns == [1]
        assert dst.weights.snapshot()["changed"] == src.weights.snapshot()["changed"]
        assert dst.weights.get() == src.weights.get()
        saved = json.loads(dst_cfg.read_text(encoding="ascii"))
        assert saved["league"] == "Standard" and saved["contact"] == "keep-me"
        # one bad value anywhere: nothing applied, weights untouched
        before = (dst_cfg.read_text(encoding="ascii"), dst.weights.get())
        broken = dict(exported, settings={"league": "Z"},
                      weights={"weights": {"+# to maximum Life": True}})
        with pytest.raises(settingsio.SettingsError, match="stat weights"):
            dst.import_settings(broken)
        assert (dst_cfg.read_text(encoding="ascii"), dst.weights.get()) == before
        # a file from a computer with no changes puts the defaults back here
        src.weights.reset()
        plain = json.loads(json.dumps(src.export_settings()))
        assert plain["weights"] == {"weights": {}, "sidegrade": {}}
        dst.import_settings(plain)
        assert dst.weights.get() == weights_mod.defaults()
        # a weights file that did not load (defaults in use) exports no block
        src.weights.load_error = "unreadable: OSError"
        assert "weights" not in src.export_settings()
    finally:
        src.close()
        dst.close()


def test_export_leaves_out_a_block_past_the_size_cap():
    """A weights block that would push the download past MAX_BYTES is left
    out (the import would refuse such a file, 16 KB cap); a block of 100
    changed or added rows plus every default removed still fits."""
    assert settingsio.MAX_BYTES == 16 * 1024
    stem = "#% increased Damage with a long stat name of sixty char "
    rows = {f"{stem}{i:04d}": 123.25 for i in range(100)}
    rows.update({k: None for k in weights_mod.DEFAULT_WEIGHTS})
    fits = settingsio.export_doc(FULL, "v", weights={"weights": rows, "sidegrade": {}})
    assert "weights" in fits and len(settingsio._text(fits)) <= settingsio.MAX_BYTES
    _update, report = settingsio.parse_import(json.loads(settingsio._text(fits)), {})
    assert report["weights_applied"] is True
    wide = {"+# to " + "W" * 190 + f"{i:04d}": 1 for i in range(weights_mod.MAX_KEYS - 50)}
    big = settingsio.export_doc(FULL, "v", weights={"weights": wide, "sidegrade": {}})
    assert "weights" not in big and big["settings"]


def test_schema_1_file_still_imports(tmp_path):
    """A schema 1 file (no weights block) imports as before and leaves the
    weights alone; a weights block in a schema 1 file is never read."""
    doc = {"kind": settingsio.KIND, "schema": 1, "app_version": "0.1.0",
           "settings": {"league": "L", "underlevel_gap": 5}}
    update, report = settingsio.parse_import(doc, {})
    assert update == {"league": "L", "underlevel_gap": 5}
    assert report["weights_applied"] is False and settingsio.weights_of(doc) is None
    sneaky = dict(doc, weights={"weights": {"+# to maximum Life": 99}})
    assert settingsio.weights_of(sneaky) is None
    assert settingsio.parse_import(sneaky, {})[1]["weights_applied"] is False
    core, _other, _cfg = _two_cores(tmp_path, {}, {})
    _other.close()
    try:
        core.weights.put(weights_mod.merge(weights_mod.validate_overrides(CHANGES)))
        before = core.weights.get()
        report = core.import_settings(sneaky)
        assert report["applied"] == ["league", "underlevel_gap"]
        assert report["weights_applied"] is False
        assert core.weights.get() == before
        saved = json.loads((tmp_path / "a.json").read_text(encoding="ascii"))
        assert saved["underlevel_gap"] == 5
    finally:
        core.close()


def test_wear_hotkey_validated_by_the_hotkey_rule():
    """TC-WORN-KEY: the optional wear key goes through settingsio._hotkey
    (Ctrl or Alt held, never a game key), stored canonical; it has no
    default, so an export without it leaves it out."""
    assert settingsio.ALLOWED["wear_hotkey"] is settingsio._hotkey
    assert settingsio.LABELS["wear_hotkey"] == "wear item hotkey"
    doc = {"kind": settingsio.KIND, "schema": 1, "settings": {"wear_hotkey": "ctrl+shift+f7"}}
    update, _ = settingsio.parse_import(doc, {})
    assert update == {"wear_hotkey": "Ctrl+Shift+F7"}
    for bad in ("Ctrl+C", "W", "Shift+W", "", 7, None):
        with pytest.raises(settingsio.SettingsError):
            settingsio._hotkey(bad)
    bad = {"kind": settingsio.KIND, "schema": 1, "settings": {"wear_hotkey": "Ctrl+V"}}
    with pytest.raises(settingsio.SettingsError, match="wear item hotkey"):
        settingsio.parse_import(bad, {})
    assert "wear_hotkey" not in settingsio.export_doc({"league": "L"}, "v")["settings"]
    assert "wear_hotkey" not in settingsio.export_doc({"wear_hotkey": "Ctrl+C"}, "v")["settings"]


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
        assert status == 400 and "isn't an AshLight settings backup" in body
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


# -- PLAY-F-186B-PLAYER-NOTES-UI: the zone notes option (decision 0074 item 8)

def _book(n, name="Ash", text="note {i}"):
    return {name: {f"G1_{i}": {"text": text.format(i=i), "at": 100 + i} for i in range(n)}}


def test_notes_block_is_never_in_a_default_export():
    doc = settingsio.export_doc(FULL, "v")
    assert settingsio.NOTES_KEY not in doc and settingsio.NOTES_KEY not in doc["settings"]
    assert settingsio.NOTES_KEY not in settingsio.ALLOWED
    out = settingsio.with_notes(doc, _book(3))
    assert out[settingsio.NOTES_KEY][0] == {"character": "Ash", "area_id": "G1_2",
                                            "text": "note 2"}  # newest first
    assert len(out[settingsio.NOTES_KEY]) == 3 and settingsio.NOTES_LEFT_OUT not in out
    assert settingsio.NOTES_KEY not in doc  # the default document is not changed
    # what an export with notes holds imports back exactly
    rows = settingsio.notes_of(json.loads(json.dumps(out)))
    assert sorted(rows) == [("Ash", f"G1_{i}", f"note {i}") for i in range(3)]


def test_notes_past_the_size_cap_are_left_out_and_counted():
    big = _book(300, text="{i} " + "x" * 190)
    out = settingsio.with_notes(settingsio.export_doc(FULL, "v"), big)
    text = json.dumps(out, indent=2, ensure_ascii=True) + "\n"
    assert len(text.encode("ascii")) <= settingsio.MAX_BYTES
    kept = len(out[settingsio.NOTES_KEY])
    assert 0 < kept < 300 and out[settingsio.NOTES_LEFT_OUT] == 300 - kept
    assert out[settingsio.NOTES_KEY][0]["area_id"] == "G1_299"  # the newest stay
    settingsio.parse_import(json.loads(text), {})  # still a good backup
    assert settingsio.notes_of(json.loads(text)) is not None


@pytest.mark.parametrize("block", [
    "x", {}, [1], [{"character": "Ash", "area_id": "G1_1"}],
    [{"character": "Ash", "area_id": "G1_1", "text": "a", "extra": 1}],
    [{"character": "Ash", "area_id": "../x", "text": "a"}],
    [{"character": "", "area_id": "G1_1", "text": "a"}],
    [{"character": "Ash", "area_id": "G1_1", "text": ""}],
    [{"character": "Ash", "area_id": "G1_1", "text": "x" * 201}],
    [{"character": "Ash", "area_id": "G1_1", "text": "bell\x07"}],
    [{"character": "Ash", "area_id": "G1_1", "text": "a"},
     {"character": "Ash", "area_id": "G1_1", "text": "b"}],
    [{"character": "Ash", "area_id": f"G{i}", "text": "a"} for i in range(301)],
])
def test_a_bad_notes_block_refuses_the_file(block):
    with pytest.raises(settingsio.SettingsError) as e:
        settingsio.notes_of({"kind": settingsio.KIND, "schema": 2, "settings": {},
                             "notes": block})
    assert str(e.value) == "The zone notes in that file are not valid."


def test_merge_never_overwrites_and_keeps_the_bounds():
    book = {"Ash": {"G1_1": {"text": "mine", "at": 1}, "G1_2": {"text": "same", "at": 2}}}
    rows = [("Ash", "G1_1", "theirs"), ("Ash", "G1_2", "same"), ("Ash", "G1_3", "new"),
            ("Bel", "G1_1", "bel")]
    adds, report = settingsio.merge_notes(book, rows)
    assert adds == [("Ash", "G1_3", "new"), ("Bel", "G1_1", "bel")]
    assert report == {"notes_added": 2, "notes_kept": 1, "notes_full": 0}
    # full: the store's zone and character bounds are never pushed past
    full = {f"C{i}": {"A": {"text": "t", "at": 1}} for i in range(12)}
    adds, report = settingsio.merge_notes(full, [("New", "A", "x"), ("C0", "B", "y")])
    assert adds == [("C0", "B", "y")] and report["notes_full"] == 1
    many = _book(299)
    adds, report = settingsio.merge_notes(many, [("Ash", "Z1", "a"), ("Ash", "Z2", "b")])
    assert adds == [("Ash", "Z1", "a")] and report["notes_full"] == 1


def test_http_notes_leave_only_when_asked_and_import_keeps_local_notes(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps({"league": "Standard"}), encoding="ascii")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False, config_path=cfg)
    server = serve(core, "f" * 48, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        core.player_notes.save("Ash", "G1_2", "exit north")
        core.player_notes.save("Ash", "G1_3", "boss hits hard")
        for path in ("/api/settings-export", "/api/settings-export?notes=0",
                     "/api/settings-export?notes=yes"):
            status, _disp, text = _get(server.port, path)
            assert status == 200 and "exit north" not in text and '"notes"' not in text
        status, _disp, text = _get(server.port, "/api/settings-export?notes=1")
        assert status == 200
        exported = json.loads(text)
        assert {r["text"] for r in exported["notes"]} == {"exit north", "boss hits hard"}
        # another computer's notes: one zone differs, one is new
        core.player_notes.save("Ash", "G1_2", "my own words")
        core.player_notes.save("Ash", "G1_3", "")
        status, body = _post(server.port, "/api/settings-import", exported)
        assert status == 200
        report = json.loads(body)
        assert report["notes_added"] == 1 and report["notes_kept"] == 1
        assert report["notes_full"] == 0 and "notes_failed" not in report
        book = core.player_notes.book()
        assert book["Ash"]["G1_2"]["text"] == "my own words"   # never overwritten
        assert book["Ash"]["G1_3"]["text"] == "boss hits hard"
        assert core.state.player_notes == book                 # published at once
        # a bad block refuses the whole file: no setting, no note applied
        before = (cfg.read_text(encoding="ascii"), core.player_notes.book())
        bad = dict(exported, notes=[{"character": "Ash", "area_id": "G9", "text": ""}],
                   settings={"league": "Other"})
        status, body = _post(server.port, "/api/settings-import", bad)
        assert status == 400 and json.loads(body)["error"] == (
            "The zone notes in that file are not valid.")
        assert (cfg.read_text(encoding="ascii"), core.player_notes.book()) == before
        # a file without the block leaves the notes alone and says nothing of them
        plain = {k: v for k, v in exported.items() if k != "notes"}
        status, body = _post(server.port, "/api/settings-import", plain)
        assert status == 200 and "notes_added" not in json.loads(body)
        assert core.player_notes.book() == before[1]
    finally:
        server.stop()
        core.close()
