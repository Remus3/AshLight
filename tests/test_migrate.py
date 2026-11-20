"""DEP-13 (findings F-049, F-050): `installer migrate` copies a checkout's
allow-listed player data into an install home.

Everything runs against tmp folders: a fake checkout runtime dir and
local.json, and a laid-out home (the ACL call is injected, so no ACL is
changed). No core, client or game is started; no live file is read.
"""

import hashlib
import io
import json
import os
from pathlib import Path

import pytest

from server.al import jsonfile, paths
from server.al.install import cli, firstrun
from server.al.install import home as homemod
from server.al.install import migrate

CONTACT = "migrate-contact-value-7f3a"
TOKEN = "secret-token-value-91c2"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("ascii"))


def checkout(tmp_path):
    """A fake checkout: ops/runtime with player data and the files that
    must never move, and a config/local.json with player and dev keys."""
    root = tmp_path / "checkout"
    rt = root / "ops" / "runtime"
    _write(rt / "consent.json", json.dumps({"consented": True, "at": "2026-11-19T10:00:00Z",
                                            "file": "Client.txt"}) + "\n")
    _write(rt / "run_history.json", json.dumps({"schema": 2, "runs": [{"char": "Ash"}]}) + "\n")
    _write(rt / "price_watch.json", json.dumps({"items": [{"name": "Chaos Orb"}]}) + "\n")
    _write(rt / "zone_visits.json", json.dumps({"Ash": ["G1_1"]}) + "\n")
    _write(rt / "gen_builds.json", json.dumps({"tabs": []}) + "\n")
    _write(rt / "theorycraft" / "weights.json", json.dumps({"life": 1.0}) + "\n")
    _write(rt / "build" / "last-code.txt", "eNoLcode\n")
    _write(rt / "build" / "chars" / "c-Ash-12345678.txt", "eNoAshcode\n")
    _write(rt / "build" / "active-character.txt", "Ash\n")
    # never moved
    _write(rt / "token", TOKEN + "\n")
    _write(rt / "token.reuse", TOKEN + "\n")
    _write(rt / "core.alive", "123\n")
    _write(rt / "stop.request", "stop\n")
    _write(rt / "core.pid", "4242\n")
    _write(rt / "overlay.pid", "4243\n")
    _write(rt / "keepalive.json", "{}\n")
    _write(rt / "hotreload.json", "{}\n")
    _write(rt / "consent.json.bak", "{}\n")
    _write(rt / "build" / "core.pid", "1\n")
    _write(rt / "gamedata" / "skilltree.json", "{}\n")
    cfg = root / "config" / "local.json"
    _write(cfg, json.dumps({
        "character": "Ash", "league": "Standard", "web_data": True, "tc_calc": False,
        "poll_ms": 300, "eval_hotkey": "Alt+Shift+E", "contact": CONTACT,
        "client_log": "fixture-logs/Client.txt",
        "loop": {"inbox_dir": ""}, "loop_push": True, "hot_reload": True,
        "tc_drift_live_unattended": True, "port": 8961, "token": TOKEN,
        "unknown_key": 1,
    }) + "\n")
    return rt, cfg


def laid_out_home(tmp_path):
    home = tmp_path / "home"
    homemod.make_layout(home, private=lambda p: None)
    return home


def snapshot(folder):
    out = {}
    for p in sorted(Path(folder).rglob("*")):
        if p.is_file():
            out[p.relative_to(folder).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def files_under(folder):
    return sorted(p for p in Path(folder).rglob("*") if p.is_file())


def test_migrate_is_a_copy_the_checkout_stays_byte_for_byte(tmp_path):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    before = snapshot(tmp_path / "checkout")
    results = migrate.run(migrate.plan(rt, cfg, home), home=home)
    assert results and all(s == "copied" for _n, s in results), results
    assert snapshot(tmp_path / "checkout") == before


def test_player_data_reads_the_same_in_the_home(tmp_path):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    migrate.run(migrate.plan(rt, cfg, home), home=home)
    data = home / "data"
    for rel in ("consent.json", "run_history.json", "price_watch.json", "zone_visits.json",
                "gen_builds.json", "theorycraft/weights.json", "build/last-code.txt",
                "build/chars/c-Ash-12345678.txt", "build/active-character.txt"):
        assert (data / rel).read_bytes() == (rt / rel).read_bytes(), rel
    # consent reads the same through the reader the core uses
    a = jsonfile.read_json(rt / "consent.json", kind=dict, default={}, backup=True)
    b = jsonfile.read_json(data / "consent.json", kind=dict, default={}, backup=True)
    assert a == b and b["consented"] is True
    # settings read the same: every allow-listed key and value
    src = json.loads(cfg.read_text(encoding="ascii"))
    got = json.loads((data / "local.json").read_text(encoding="ascii"))
    for key in ("character", "league", "web_data", "tc_calc", "poll_ms", "eval_hotkey",
                "contact", "client_log"):
        assert got[key] == src[key], key


def test_token_pids_heartbeat_stop_and_dev_keys_never_move(tmp_path):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    pairs = migrate.plan(rt, cfg, home)
    names = {Path(s).name for s, _t in pairs}
    for never in ("token", "token.reuse", "core.alive", "stop.request", "core.pid",
                  "overlay.pid", "keepalive.json", "hotreload.json", "consent.json.bak",
                  "skilltree.json"):
        assert never not in names, never
    migrate.run(pairs, home=home)
    data = home / "data"
    written = {p.relative_to(data).as_posix() for p in files_under(data)}
    for never in ("token", "token.reuse", "core.alive", "stop.request", "core.pid",
                  "overlay.pid", "build/core.pid", "keepalive.json", "hotreload.json",
                  "gamedata/skilltree.json"):
        assert never not in written, never
    cfg_doc = json.loads((data / "local.json").read_text(encoding="ascii"))
    for key in ("loop", "loop_push", "hot_reload", "tc_drift_live_unattended", "port",
                "token", "unknown_key"):
        assert key not in cfg_doc, key
    for p in files_under(home):
        assert TOKEN.encode() not in p.read_bytes(), p.name


def test_never_table_overrides_a_table_edit(tmp_path, monkeypatch):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    monkeypatch.setattr(migrate, "RUNTIME_FILES", migrate.RUNTIME_FILES + ("token", "core.alive"))
    names = {Path(s).name for s, _t in migrate.plan(rt, cfg, home)}
    assert "token" not in names and "core.alive" not in names
    # and a hand-made pair to a never name is refused by run
    res = migrate.run([(rt / "token", home / "data" / "token")], home=home)
    assert res == [("token", "refused")]
    assert not (home / "data" / "token").exists()


def test_contact_lands_only_in_the_homes_local_json(tmp_path):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    migrate.run(migrate.plan(rt, cfg, home), home=home)
    holders = [p for p in files_under(home) if CONTACT.encode() in p.read_bytes()]
    names = sorted(p.name for p in holders)
    assert names == ["local.json", "local.json.bak"]
    assert all(p.parent == home / "data" for p in holders)


def test_existing_file_is_kept_unless_force(tmp_path):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    data = home / "data"
    _write(data / "run_history.json", "{\"mine\": true}\n")
    _write(data / "local.json", json.dumps({"character": "Other", "web_data": False}) + "\n")
    res = dict(migrate.run(migrate.plan(rt, cfg, home), home=home))
    assert res["run_history.json"] == "kept" and res["local.json"] == "kept"
    assert (data / "run_history.json").read_text() == "{\"mine\": true}\n"
    assert json.loads((data / "local.json").read_text())["character"] == "Other"
    res = dict(migrate.run(migrate.plan(rt, cfg, home), force=True, home=home))
    assert res["run_history.json"] == "copied" and res["local.json"] == "copied"
    assert (data / "run_history.json").read_bytes() == (rt / "run_history.json").read_bytes()
    doc = json.loads((data / "local.json").read_text())
    assert doc["character"] == "Ash" and doc["contact"] == CONTACT
    assert "port" not in doc and "loop" not in doc


def test_first_run_local_json_counts_as_fresh(tmp_path):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    assert firstrun.write_first_run(home) == "written"
    res = dict(migrate.run(migrate.plan(rt, cfg, home), home=home))
    assert res["local.json"] == "copied"
    doc = json.loads((home / "data" / "local.json").read_text())
    assert doc["character"] == "Ash" and doc["web_data"] is True


def test_invalid_setting_value_is_left_out(tmp_path):
    rt, cfg = checkout(tmp_path)
    _write(cfg, json.dumps({"poll_ms": 99999, "character": "Ash", "eval_hotkey": "F1"}) + "\n")
    home = laid_out_home(tmp_path)
    migrate.run(migrate.plan(rt, cfg, home), home=home)
    doc = json.loads((home / "data" / "local.json").read_text())
    assert doc["character"] == "Ash"
    assert "eval_hotkey" not in doc
    assert doc.get("poll_ms") != 99999


def test_every_written_path_is_inside_the_home(tmp_path):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    outside_before = snapshot(tmp_path)
    outside_before = {k: v for k, v in outside_before.items() if not k.startswith("home/")}
    pairs = migrate.plan(rt, cfg, home)
    for _s, t in pairs:
        assert os.path.commonpath([str(t), str(home / "data")]) == str(home / "data")
    # a hand-made pair aiming outside the data folder is refused
    evil = tmp_path / "elsewhere" / "data" / ".." / "x.json"
    res = migrate.run(pairs + [(rt / "run_history.json", home / "data" / ".." / "x.json"),
                               (rt / "run_history.json", evil)], home=home)
    assert res[-2][1] == "refused" and res[-1][1] == "refused"
    after = {k: v for k, v in snapshot(tmp_path).items() if not k.startswith("home/")}
    assert after == outside_before
    assert not (home / "x.json").exists()


def test_home_not_laid_out_or_refused_or_source_inside_home(tmp_path):
    rt, cfg = checkout(tmp_path)
    with pytest.raises(migrate.MigrateError):
        migrate.plan(rt, cfg, tmp_path / "bare")
    assert not (tmp_path / "bare").exists()
    with pytest.raises(paths.HomeRefused):
        migrate.plan(rt, cfg, tmp_path / "steamapps" / "AshLight")
    home = laid_out_home(tmp_path)
    with pytest.raises(migrate.MigrateError):
        migrate.plan(home / "data", None, home)


def test_links_in_the_source_are_not_followed(tmp_path):
    rt, cfg = checkout(tmp_path)
    secret = tmp_path / "outside.txt"
    _write(secret, "outside\n")
    link = rt / "build" / "link.txt"
    try:
        os.symlink(secret, link)
    except (OSError, NotImplementedError):
        pytest.skip("no symlink right here")
    home = laid_out_home(tmp_path)
    names = {Path(s).name for s, _t in migrate.plan(rt, cfg, home)}
    assert "link.txt" not in names


def test_cli_migrate_runs_with_force_and_dry_run(tmp_path, capsys):
    rt, cfg = checkout(tmp_path)
    home = laid_out_home(tmp_path)
    base = ["migrate", "--home", str(home), "--from-runtime", str(rt), "--from-config", str(cfg)]
    assert cli.main(base + ["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would copy consent.json" in out and str(tmp_path) not in out
    assert not (home / "data" / "consent.json").exists()
    assert cli.main(base) == 0
    out = capsys.readouterr().out
    assert "copied consent.json" in out and str(tmp_path) not in out
    assert cli.main(base) == 0
    assert "kept consent.json" in capsys.readouterr().out
    assert cli.main(base + ["--force"]) == 0
    assert "copied consent.json" in capsys.readouterr().out


def test_cli_usage_errors_exit_2(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(paths.HOME_ENV, raising=False)
    assert migrate.main([], environ={}) == 2
    assert migrate.main(["--bogus"], environ={}) == 2
    rt, _cfg = checkout(tmp_path)
    assert migrate.main(["--home", str(tmp_path / "nohome"), "--from-runtime", str(rt)],
                        environ={}) == 2
    capsys.readouterr()


def test_allow_list_is_one_table_with_no_never_names():
    for rel in migrate.RUNTIME_FILES + migrate.RUNTIME_TREES:
        assert not migrate._never(rel), rel
        assert ".." not in rel.split("/") and not rel.startswith("/")
    for key in ("loop", "loop_push", "hot_reload", "tc_drift_live_unattended", "port"):
        assert key not in migrate.CONFIG_KEYS and key in migrate.NEVER_KEYS
    assert "contact" in migrate.CONFIG_KEYS


def test_migrate_module_is_stdlib_and_ascii():
    raw = Path(migrate.__file__).read_bytes()
    assert b"\r" not in raw
    text = raw.decode("ascii")
    assert "winreg" not in text and "subprocess" not in text
    assert "urllib" not in text and "socket" not in text
