"""REL-INSTALL-HOME (finding F-050, DEP-09, decision 0059): the installer
package server/al/install - its fixed command table, the home layout, the
marker <home>/install.json (schema 1) read / write / switch with read-back,
the cleanup plan and `status`.

Everything runs against tmp folders; no core, overlay or game is started
and no ACL is changed (the ACL call is injected).
"""

import ast
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from server.al import NAME, VERSION, jsonfile, paths
from server.al.install import cli, status
from server.al.install import home as homemod

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "server" / "al" / "install"
ENV_KEYS = (paths.HOME_ENV, paths.SIDECAR_ENV, paths.RUNTIME_ENV)
WHEN = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 20, 8, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def clean_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(paths, "_MARKER_SEEN", {})
    return monkeypatch


def first_marker(home, version="0.1.0"):
    doc = homemod.new_marker(version, "python-3.14.10", "electron-45.3.3", now=WHEN)
    return homemod.write_marker(home, doc)


def make_versions(home, *names):
    for name in names:
        (home / "app" / name).mkdir(parents=True, exist_ok=True)


# --- the marker ---------------------------------------------------------

def test_marker_round_trip_has_schema_1_and_every_layout_field(tmp_path):
    home = tmp_path / "home"
    doc = first_marker(home)
    # every field of plan 05 "Installed-mode layout", nothing renamed
    assert tuple(doc) == homemod.MARKER_FIELDS == (
        "schema", "name", "version", "previous", "channel", "installed_at",
        "updated_at", "python", "electron", "pending_confirm", "start_attempts")
    assert doc["schema"] == 1 and doc["name"] == NAME == "AshLight"
    assert doc["version"] == "0.1.0" and doc["previous"] is None
    assert doc["channel"] == "stable"
    assert doc["installed_at"] == doc["updated_at"] == "2026-11-19T12:00:00Z"
    assert doc["python"] == "python-3.14.10" and doc["electron"] == "electron-45.3.3"
    assert doc["pending_confirm"] is False and doc["start_attempts"] == 0
    assert homemod.read_marker(home) == doc
    raw = (home / "install.json").read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    raw.decode("ascii")
    # the core's own reader sees the same marker
    assert paths.read_marker({paths.HOME_ENV: str(home)}) == doc


def test_rc_version_gets_the_rc_channel(tmp_path):
    doc = first_marker(tmp_path / "home", "0.2.0-rc.1")
    assert doc["channel"] == "rc"


def test_write_goes_through_temp_fsync_replace_and_one_bak(tmp_path, monkeypatch):
    home = tmp_path / "home"
    calls = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync(fd):
        calls.append(("fsync",))
        return real_fsync(fd)

    def replace(src, dst):
        calls.append(("replace", Path(src).name, Path(dst).name))
        return real_replace(src, dst)

    monkeypatch.setattr(jsonfile.os, "fsync", fsync)
    monkeypatch.setattr(jsonfile.os, "replace", replace)
    doc = first_marker(home)
    replaces = [c for c in calls if c[0] == "replace"]
    assert [c[2] for c in replaces] == ["install.json", "install.json.bak"]
    for _, src, _dst in replaces:
        assert re.fullmatch(r"install\.json(\.bak)?\.\d+\.[0-9a-f]{12}\.tmp", src)
    assert calls.count(("fsync",)) == 2
    assert calls[0] == ("fsync",) and calls[2] == ("fsync",)
    names = sorted(p.name for p in home.iterdir())
    assert names == ["install.json", "install.json.bak"]  # one .bak, no temp left
    assert (home / "install.json.bak").read_bytes() == (home / "install.json").read_bytes()
    # a second write still keeps exactly one .bak
    doc2 = dict(doc, start_attempts=1)
    homemod.write_marker(home, doc2)
    assert sorted(p.name for p in home.iterdir()) == ["install.json", "install.json.bak"]
    assert json.loads((home / "install.json.bak").read_text("ascii")) == doc2


def test_torn_marker_is_restored_from_its_bak(tmp_path):
    home = tmp_path / "home"
    doc = first_marker(home)
    (home / "install.json").write_bytes(b'{"schema": 1, "na')
    assert homemod.read_marker(home) == doc
    assert json.loads((home / "install.json").read_text("ascii")) == doc


def test_read_back_mismatch_raises(tmp_path, monkeypatch):
    home = tmp_path / "home"
    real = jsonfile.write_text

    def lossy(path, text, backup=False, sync=True):
        real(path, text.replace('"start_attempts": 0', '"start_attempts": 7'),
             backup=backup, sync=sync)

    monkeypatch.setattr(jsonfile, "write_text", lossy)
    with pytest.raises(homemod.MarkerError, match="read-back"):
        first_marker(home)


@pytest.mark.parametrize("change", [
    {"schema": 2}, {"schema": True}, {"name": "Other"}, {"version": "1.2"},
    {"version": "../0.1.0"}, {"previous": "0.1.0"}, {"previous": "x"},
    {"channel": "beta"}, {"python": "..\\x"}, {"electron": ""},
    {"pending_confirm": 1}, {"start_attempts": -1}, {"start_attempts": True},
    {"installed_at": ""},
])
def test_invalid_marker_is_refused_and_writes_nothing(tmp_path, change):
    home = tmp_path / "home"
    doc = dict(homemod.new_marker("0.1.0", "python-3.14.10", "electron-45.3.3", now=WHEN))
    doc.update(change)
    with pytest.raises(homemod.MarkerError):
        homemod.write_marker(home, doc)
    assert not (home / "install.json").exists()


def test_missing_field_is_refused(tmp_path):
    doc = homemod.new_marker("0.1.0", "python-3.14.10", "electron-45.3.3", now=WHEN)
    del doc["start_attempts"]
    assert homemod.validate(doc) == ["missing start_attempts"]
    with pytest.raises(homemod.MarkerError):
        homemod.write_marker(tmp_path / "home", doc)


def test_invalid_marker_on_disk_reads_as_none(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert homemod.read_marker(home) is None
    (home / "install.json").write_text(json.dumps({"schema": 9}), encoding="ascii")
    assert homemod.read_marker(home) is None


# --- switch ---------------------------------------------------------------

def test_switch_sets_previous_pending_confirm_attempts_and_reads_back(tmp_path):
    home = tmp_path / "home"
    make_versions(home, "0.1.0", "0.1.1")
    first = first_marker(home)
    first = homemod.write_marker(home, dict(first, start_attempts=2))
    doc = homemod.switch_marker(home, "0.1.1", electron="electron-45.3.4", now=LATER)
    assert doc["version"] == "0.1.1" and doc["previous"] == "0.1.0"
    assert doc["pending_confirm"] is True and doc["start_attempts"] == 0
    assert doc["updated_at"] == "2026-11-20T08:30:00Z"
    assert doc["installed_at"] == first["installed_at"]
    assert doc["electron"] == "electron-45.3.4" and doc["python"] == "python-3.14.10"
    on_disk = json.loads((home / "install.json").read_text("ascii"))
    assert on_disk == doc == homemod.read_marker(home)
    assert json.loads((home / "install.json.bak").read_text("ascii")) == doc


def test_switch_refuses_without_folder_marker_or_change(tmp_path):
    home = tmp_path / "home"
    make_versions(home, "0.1.0")
    with pytest.raises(homemod.MarkerError, match="no valid marker"):
        homemod.switch_marker(home, "0.1.0")
    first_marker(home)
    before = (home / "install.json").read_bytes()
    with pytest.raises(homemod.MarkerError, match="no version folder"):
        homemod.switch_marker(home, "0.1.1")
    with pytest.raises(homemod.MarkerError, match="already"):
        homemod.switch_marker(home, "0.1.0")
    with pytest.raises(homemod.MarkerError, match="not a version"):
        homemod.switch_marker(home, "..")
    assert (home / "install.json").read_bytes() == before


# --- the path-shape guard -------------------------------------------------

@pytest.mark.parametrize("bad", [
    "SteamLibrary/steamapps/common/AshLight",
    "Games/Path of Exile 2/AshLight",
    "Games/path of exile 2. /AshLight",
])
def test_home_failing_the_path_shape_guard_is_refused(tmp_path, bad, monkeypatch):
    home = tmp_path / bad
    doc = homemod.new_marker("0.1.0", "python-3.14.10", "electron-45.3.3", now=WHEN)

    def no_fs(*a, **k):
        raise AssertionError("file system touched for a refused home")

    monkeypatch.setattr(jsonfile, "write_text", no_fs)
    monkeypatch.setattr(homemod.os, "listdir", no_fs)
    calls = []
    for fn in (lambda: homemod.layout(home),
               lambda: homemod.make_layout(home, private=calls.append),
               lambda: homemod.write_marker(home, doc),
               lambda: homemod.read_marker(home),
               lambda: homemod.switch_marker(home, "0.1.1"),
               lambda: homemod.version_dirs(home),
               lambda: homemod.cleanup_plan(home)):
        with pytest.raises(paths.HomeRefused):
            fn()
    assert calls == []
    assert not (tmp_path / bad.split("/")[0]).exists()


# --- layout ---------------------------------------------------------------

def test_layout_matches_the_plan_and_the_resolver(tmp_path, clean_env):
    home = tmp_path / "home"
    lay = homemod.layout(home)
    for key, value in lay.items():
        assert value == home or home in value.parents, key
    assert lay["marker"] == home / "install.json"
    assert lay["data"] == home / "data"
    assert lay["local_config"] == home / "data" / "local.json"
    assert lay["downloads"] == home / "cache" / "downloads"
    assert lay["reports"] == home / "logs" / "reports"
    assert lay["staged"] == home / "staged"
    assert lay["uninstall"] == home / "uninstall.ps1"
    # the same folders the core's resolver uses in installed mode
    clean_env.setenv(paths.HOME_ENV, str(home))
    for name, sub in paths.INSTALLED_SUBDIRS.items():
        assert paths.sidecar_dir(name) == lay[sub]
    assert paths.data_dir() == lay["data"]
    assert paths.local_config_file() == lay["local_config"]
    assert not home.exists()  # layout touches nothing


def test_make_layout_makes_the_folders_and_makes_data_private(tmp_path):
    home = tmp_path / "home"
    calls = []

    def private(path):
        calls.append(Path(path))
        return True

    assert homemod.make_layout(home, private=private) is True
    assert sorted(p.name for p in home.iterdir()) == sorted(homemod.LAYOUT_DIRS)
    assert calls == [home / "data"]
    assert homemod.make_layout(home, private=private) is True  # idempotent
    assert calls == [home / "data", home / "data"]


# --- version folders and cleanup -----------------------------------------

def test_cleanup_lists_old_version_folders_never_the_two_kept(tmp_path):
    home = tmp_path / "home"
    make_versions(home, "0.1.0", "0.1.1", "0.1.2", "0.2.0-rc.1", "0.2.0",
                  "0.1.10", "0.3.0.partial", "notes")
    (home / "app" / "0.4.0").write_text("not a folder", encoding="ascii")
    first_marker(home, "0.1.0")
    homemod.switch_marker(home, "0.1.2", now=LATER)
    homemod.switch_marker(home, "0.2.0", now=LATER)
    assert homemod.version_dirs(home) == [
        "0.1.0", "0.1.1", "0.1.2", "0.1.10", "0.2.0-rc.1", "0.2.0"]
    plan = homemod.cleanup_plan(home)
    assert plan == [home / "app" / n for n in ("0.1.0", "0.1.1", "0.1.10", "0.2.0-rc.1")]
    assert home / "app" / "0.2.0" not in plan and home / "app" / "0.1.2" not in plan
    # listed only: nothing was deleted
    assert all(p.is_dir() for p in plan)


def test_cleanup_with_no_marker_lists_nothing(tmp_path):
    home = tmp_path / "home"
    make_versions(home, "0.1.0", "0.1.1")
    assert homemod.cleanup_plan(home) == []
    first_marker(home, "0.1.1")
    assert homemod.cleanup_plan(home) == [home / "app" / "0.1.0"]


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows feature")
def test_cleanup_skips_a_junction(tmp_path):
    home = tmp_path / "home"
    make_versions(home, "0.1.0")
    target = tmp_path / "elsewhere"
    target.mkdir()
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(home / "app" / "0.0.9"),
                        str(target)], capture_output=True)
    if r.returncode != 0:
        pytest.skip("mklink /J not available")
    first_marker(home, "0.1.0")
    assert homemod.version_dirs(home) == ["0.1.0"]
    assert homemod.cleanup_plan(home) == []


def test_version_order_puts_a_pre_release_below_its_release():
    names = ["0.2.0", "0.2.0-rc.10", "0.2.0-rc.2", "0.1.9", "0.10.0"]
    assert sorted(names, key=homemod.version_key) == [
        "0.1.9", "0.2.0-rc.2", "0.2.0-rc.10", "0.2.0", "0.10.0"]


# --- the command table -----------------------------------------------------

def test_command_table_is_the_fixed_set():
    assert set(cli.COMMANDS) == {"install", "repair", "status", "calc", "update",
                                 "apply-staged", "rollback", "confirm", "migrate"}
    for mod in cli.COMMANDS.values():
        assert re.fullmatch(r"[a-z_]+", mod)


@pytest.mark.parametrize("argv", [["no-such-command"], [], ["--help"]])
def test_unknown_command_exits_2(argv, capsys):
    assert cli.main(argv) == 2
    assert "usage:" in capsys.readouterr().err


def test_not_yet_built_command_exits_2(capsys, monkeypatch):
    missing = [c for c, m in cli.COMMANDS.items() if not (PKG / f"{m}.py").exists()]
    assert missing, "every command is built; pick a fake one"
    for command in missing:
        assert cli.main([command]) == 2
        assert "not available in this build" in capsys.readouterr().err
    # also when the table names a module that does not exist
    monkeypatch.setitem(cli.COMMANDS, "status", "no_such_module")
    assert cli.main(["status"]) == 2
    assert "not available in this build" in capsys.readouterr().err


def test_cli_status_runs_the_status_module(capsys, clean_env):
    assert cli.main(["status"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "mode: checkout"
    assert cli.main(["status", "extra"]) == 2


# --- status ---------------------------------------------------------------

def _status(environ):
    out = io.StringIO()
    code = status.main([], environ=environ, out=out)
    return code, out.getvalue()


def _no_foreign_path(text, home):
    """No path outside the home, and in fact no path at all."""
    assert "\\" not in text and "/" not in text, text
    assert str(home) not in text
    assert str(ROOT) not in text


def test_status_in_a_checkout(clean_env):
    code, text = _status({})
    assert code == 0
    assert text.splitlines() == ["mode: checkout", f"version: {VERSION}", "previous: none"]
    _no_foreign_path(text, ROOT)


def test_status_in_an_install_prints_mode_version_previous(tmp_path, clean_env):
    home = tmp_path / "home"
    make_versions(home, "0.1.0", "0.1.1", "0.0.9")
    first_marker(home)
    homemod.switch_marker(home, "0.1.1", now=LATER)
    code, text = _status({paths.HOME_ENV: str(home)})
    assert code == 0
    assert text.splitlines() == [
        "mode: installed", "version: 0.1.1", "previous: 0.1.0", "channel: stable",
        "pending_confirm: true", "start_attempts: 0", "old_versions: 1"]
    _no_foreign_path(text, home)


def test_status_with_no_marker_or_a_refused_home_exits_1(tmp_path, clean_env):
    home = tmp_path / "home"
    home.mkdir()
    code, text = _status({paths.HOME_ENV: str(home)})
    assert (code, text.splitlines()) == (1, ["mode: installed", "marker: missing or invalid"])
    bad = tmp_path / "steamapps" / "AshLight"
    code, text = _status({paths.HOME_ENV: str(bad)})
    assert code == 1 and "refused" in text
    _no_foreign_path(text, bad)


def test_module_entry_point_status_in_a_checkout():
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    r = subprocess.run([sys.executable, "-m", "server.al.install", "status"],
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[0] == "mode: checkout"
    r = subprocess.run([sys.executable, "-m", "server.al.install", "migrate"],
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       timeout=60)
    if not (PKG / "migrate.py").exists():
        assert r.returncode == 2
        assert "not available in this build" in r.stderr


# --- static checks --------------------------------------------------------

ELEVATION = re.compile(r"runas|ShellExecute|IsUserAnAdmin|"
                       r"Start-Process|-Verb\b|elevat|UAC\b", re.I)


def test_no_elevation_call_in_the_package():
    files = sorted(PKG.glob("*.py"))
    assert {p.name for p in files} >= {"__init__.py", "__main__.py", "cli.py",
                                       "home.py", "status.py"}
    for path in files:
        text = path.read_text(encoding="ascii")
        assert not ELEVATION.search(text), path.name
        assert "winreg" not in text and "_winreg" not in text, path.name


def _imports_install(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name.startswith("server.al.install") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "server.al.install" or mod.startswith("server.al.install."):
                return True
            if node.level == 1 and (mod == "install" or mod.startswith("install.")):
                return True
            if node.level == 1 and not mod and any(a.name == "install" for a in node.names):
                return True
            if mod == "server.al" and any(a.name == "install" for a in node.names):
                return True
    text = path.read_text(encoding="utf-8")
    return re.search(r"""["']server\.al\.install|["']\.install\b""", text) is not None


def test_core_http_and_state_never_import_the_installer(tmp_path):
    for name in ("core.py", "http.py", "state.py"):
        assert not _imports_install(ROOT / "server" / "al" / name), name
    # the checker itself catches each import form
    for src in ("from .install import home\n", "from . import install\n",
                "import server.al.install.cli\n", "from server.al import install\n",
                "importlib.import_module('server.al.install')\n"):
        probe = tmp_path / "probe.py"
        probe.write_text(src, encoding="ascii")
        assert _imports_install(probe), src
