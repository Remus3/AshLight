"""DEP-05 (decision 0059, finding F-049): one path resolver serves a source
checkout and an install home.

An installed copy runs from <home>/app/<version>/ with the marker
<home>/install.json (or AL_HOME names the home): player state in
<home>/data/, the sidecar folders as <home>/cache, logs, temp and build. A
home in a Steam library or the game's folder is refused by path text only.
Everything runs against tmp folders; no core, overlay or game is started.
"""

import http.client
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from server.al import __main__ as entry
from server.al import jsonfile, paths, ports, procs

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "i" * 48
ENV_KEYS = (paths.HOME_ENV, paths.SIDECAR_ENV, paths.RUNTIME_ENV,
            procs.ELECTRON_DIR_ENV)
# the payload files `python -m server.al.paths` needs (stdlib only)
PAYLOAD = ("server/__init__.py", "server/al/__init__.py", "server/al/paths.py",
           "server/al/jsonfile.py")


def _inside(p, root):
    try:
        Path(os.path.abspath(p)).relative_to(Path(os.path.abspath(root)))
        return True
    except ValueError:
        return False


@pytest.fixture
def clean_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(paths, "_MARKER_SEEN", {})
    monkeypatch.setattr(paths, "_DEMO_CONFIG", None)
    return monkeypatch


def write_marker(home, **fields):
    doc = {"schema": 1, "name": "AshLight", "version": "0.1.1", "previous": "0.1.0",
           "channel": "stable", "electron": "electron-45.3.3",
           "python": "python-3.14.10", "pending_confirm": False, "start_attempts": 0}
    doc.update(fields)
    home.mkdir(parents=True, exist_ok=True)
    (home / paths.MARKER_NAME).write_text(json.dumps(doc), encoding="ascii")
    return doc


def make_payload(home, version):
    """<home>/app/<version>/ with the stdlib modules the resolver needs and
    no fleet kit folder (an installed payload ships none)."""
    root = home / "app" / version
    for rel in PAYLOAD:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    assert not (root / "ops" / "fleet_kit").exists()
    return root


def run_payload(root, code, extra_env=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ENV_KEYS and k != "PYTHONPATH"}
    env.update(extra_env or {})
    out = subprocess.run([sys.executable, "-c", code], cwd=str(root), env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


PRINT_PATHS = ("import json; from server.al import paths; "
               "print(json.dumps({'mode': paths.install_mode(), "
               "'paths': {k: str(v) for k, v in paths.all_runtime_paths().items()}}))")


# --- AL_HOME --------------------------------------------------------------


def test_al_home_puts_every_runtime_path_inside_home(tmp_path, clean_env):
    home = tmp_path / "home"
    clean_env.setenv(paths.HOME_ENV, str(home))
    assert paths.install_mode() == "installed"
    assert paths.install_home() == home
    got = paths.all_runtime_paths()
    for name, p in got.items():
        if name == "repo":  # the code this test runs from, not a runtime path
            continue
        assert _inside(p, home), (name, str(p))
    assert got["runtime"] == home / "data"
    assert paths.consent_file() == home / "data" / "consent.json"
    assert paths.token_file() == home / "data" / "token"
    assert paths.local_config_file() == home / "data" / "local.json"
    assert got["local_config"] == home / "data" / "local.json"
    assert got["marker"] == home / "install.json"
    assert got["sidecar"] == home
    for name, leaf in paths.INSTALLED_SUBDIRS.items():
        assert paths.sidecar_dir(name) == home / leaf
    assert got["core_log"] == home / "logs" / "core.log"
    assert got["electron_cache"] == home / "cache" / "electron"
    for gone in ("scratch", "claudehistory", "worktree"):
        assert gone not in got
    for name in ("Scratch", "ClaudeHistory"):
        with pytest.raises(ValueError):
            paths.sidecar_dir(name)
    assert paths.worktree_dir() is None


def test_ensure_dirs_in_an_install_makes_data_cache_logs_temp(tmp_path, clean_env):
    home = tmp_path / "home"
    clean_env.setenv(paths.HOME_ENV, str(home))
    paths.ensure_dirs()
    assert sorted(p.name for p in home.iterdir()) == ["cache", "data", "logs", "temp"]


def test_explicit_sidecar_root_keeps_the_sidecar_layout(tmp_path, clean_env):
    """A demo scratch (decision 0049) or a test sets AL_SIDECAR_ROOT: it wins
    in an install too, with the sidecar folder names."""
    clean_env.setenv(paths.HOME_ENV, str(tmp_path / "home"))
    clean_env.setenv(paths.SIDECAR_ENV, str(tmp_path / "sc"))
    assert paths.sidecar_dir("Cache") == (tmp_path / "sc" / "Cache").resolve()
    assert paths.sidecar_dir("Scratch") == (tmp_path / "sc" / "Scratch").resolve()
    assert paths.runtime_dir() == tmp_path / "home" / "data"


def test_checkout_is_unchanged(clean_env):
    assert paths.install_mode() == "checkout"
    assert paths.install_home() is None
    assert paths.install_info() == {"mode": "checkout", "previous": None}
    assert paths.read_marker() == {}
    assert paths.runtime_dir() == ROOT / "ops" / "runtime"
    assert paths.local_config_file() == ROOT / "config" / "local.json"
    assert "home" not in paths.all_runtime_paths()


def test_marker_needs_the_app_folder_shape(tmp_path, clean_env):
    write_marker(tmp_path / "h")
    assert paths._marker_home(tmp_path / "h" / "app" / "0.1.0") == tmp_path / "h"
    assert paths._marker_home(tmp_path / "h" / "other" / "0.1.0") is None
    assert paths._marker_home(Path(tmp_path.anchor) / "x") is None  # no two parents


# --- the marker route, in a real separate process --------------------------


def test_default_install_stays_in_local_app_data(tmp_path, clean_env):
    """No AL_HOME, no AL_SIDECAR_ROOT and no kit folder: an install at the
    default home keeps every path inside the per-user local app data."""
    lad = tmp_path / "LocalAppData"
    home = paths.default_home({"LOCALAPPDATA": str(lad)})
    assert home == lad / "Programs" / "AshLight"
    write_marker(home)
    root = make_payload(home, "0.1.1")
    doc = run_payload(root, PRINT_PATHS, {"LOCALAPPDATA": str(lad)})
    assert doc["mode"] == "installed"
    assert Path(doc["paths"]["home"]) == home
    for name, p in doc["paths"].items():
        assert _inside(p, lad), (name, p)
    assert Path(doc["paths"]["runtime"]) == home / "data"


def test_two_version_folders_read_the_same_consent_file(tmp_path, clean_env):
    home = tmp_path / "inst"
    write_marker(home)
    (home / "data").mkdir(parents=True)
    (home / "data" / "consent.json").write_text('{"log": "x"}', encoding="ascii")
    code = ("import json; from server.al import paths; "
            "print(json.dumps({'consent': str(paths.consent_file()), "
            "'body': paths.consent_file().read_text(encoding='ascii'), "
            "'config': str(paths.local_config_file())}))")
    old = run_payload(make_payload(home, "0.1.0"), code)
    new = run_payload(make_payload(home, "0.1.1"), code)
    assert old == new
    assert Path(old["consent"]) == home / "data" / "consent.json"
    assert old["body"] == '{"log": "x"}'
    assert Path(old["config"]) == home / "data" / "local.json"


# --- the path-shape refusal -------------------------------------------------


class _NoRegistry:
    def __getattr__(self, name):
        raise AssertionError(f"winreg.{name} used by the home check")


def _no_fs(*args, **kwargs):
    raise AssertionError(f"file system touched by the home check: {args!r}")


def _hostile(monkeypatch):
    monkeypatch.setitem(sys.modules, "winreg", _NoRegistry())
    for name in ("stat", "lstat", "listdir", "scandir"):
        monkeypatch.setattr(os, name, _no_fs)


@pytest.mark.parametrize("parts", [
    ("Steam", "steamapps", "common", "AshLight"),
    ("SteamApps.", "AshLight"),
    ("Games", "Path of Exile 2", "AshLight"),
    ("PATH OF EXILE 2 ", "tools"),
])
def test_home_in_a_steam_library_or_game_folder_is_refused(tmp_path, clean_env, parts):
    home = tmp_path.joinpath(*parts)
    clean_env.setenv(paths.HOME_ENV, str(home))
    _hostile(clean_env)
    assert paths.install_mode() == "installed"
    with pytest.raises(paths.HomeRefused):
        paths.install_home()
    with pytest.raises(paths.HomeRefused):
        paths.runtime_dir()
    reason = paths.check_home()
    assert reason and "own folder" in reason


@pytest.mark.parametrize("parts", [
    ("steamapps2", "AshLight"), ("My Path of Exile 2 notes", "AshLight"),
    ("Programs", "AshLight"),
])
def test_near_misses_are_not_refused(tmp_path, clean_env, parts):
    clean_env.setenv(paths.HOME_ENV, str(tmp_path.joinpath(*parts)))
    _hostile(clean_env)
    assert paths.check_home() is None


def test_marker_home_in_a_steam_library_is_refused(tmp_path, clean_env):
    home = tmp_path / "steamapps" / "common" / "AL"
    write_marker(home)
    root = home / "app" / "0.1.0"
    root.mkdir(parents=True)
    clean_env.setattr(paths, "repo_root", lambda: root)
    real_stat = os.stat

    def stat_inside_home(path, *args, **kwargs):  # only the marker may be read
        if not _inside(os.fspath(path), home):
            raise AssertionError(f"stat outside the home: {path!r}")
        return real_stat(path, *args, **kwargs)

    clean_env.setitem(sys.modules, "winreg", _NoRegistry())
    clean_env.setattr(os, "stat", stat_inside_home)
    for name in ("listdir", "scandir"):
        clean_env.setattr(os, name, _no_fs)
    assert paths.install_mode() == "installed"
    with pytest.raises(paths.HomeRefused):
        paths.install_home()
    assert "steamapps" in paths.check_home()


def test_core_start_refuses_a_bad_home_before_anything(tmp_path, clean_env, capsys):
    clean_env.setenv(paths.HOME_ENV, str(tmp_path / "steamapps" / "AshLight"))

    def never(*args, **kwargs):
        raise AssertionError("the core went past the home check")

    clean_env.setattr(entry, "setup_logging", never)
    clean_env.setattr(entry.demo, "prepare", never)
    assert entry.main(["--quiet", "--no-tail"]) == 2
    assert "steamapps" in capsys.readouterr().err
    assert not (tmp_path / "steamapps").exists()


# --- marker reading, electron folder, ports ----------------------------------


def test_read_marker_restores_a_torn_marker_from_its_backup(tmp_path, clean_env):
    home = tmp_path / "home"
    clean_env.setenv(paths.HOME_ENV, str(home))
    doc = write_marker(home, previous="0.0.9")
    jsonfile.write_json(home / "install.json", doc, backup=True)
    (home / "install.json").write_text('{"schema": 1, "na', encoding="ascii")
    assert paths.read_marker()["previous"] == "0.0.9"
    assert paths.install_info() == {"mode": "installed", "previous": "0.0.9"}


def test_electron_dir_in_an_install_is_the_marker_runtime(tmp_path, clean_env):
    home = tmp_path / "home"
    clean_env.setenv(paths.HOME_ENV, str(home))
    write_marker(home, electron="electron-45.3.3")
    assert procs.electron_dir() == home / "runtime" / "electron-45.3.3"
    for bad in ("..", "", "a/b", "..\\x", "C:x", 7, None):
        write_marker(home, electron=bad)
        assert procs.electron_dir() is None, bad
    clean_env.setenv(paths.RUNTIME_ENV, str(tmp_path / "rt"))
    assert procs.electron_dir() is None  # a tmp runtime keeps the scan off


def test_dev_and_selftest_ports_lie_in_the_block():
    assert ports.in_block(ports.AL_DEV_PORT)
    assert ports.AL_DEV_PORT != ports.AL_PORT
    for port in ports.block_range(ports.SELFTEST_PORTS):
        assert ports.in_block(port)


# --- /api/health and /api/version -------------------------------------------


@pytest.fixture
def srv(tmp_path, clean_env):
    from server.al.core import Core
    from server.al.http import serve
    clean_env.setenv(paths.SIDECAR_ENV, str(tmp_path / "sidecar"))
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def _get(server, path):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    conn.request("GET", path, headers={"Host": f"127.0.0.1:{server.port}",
                                       "X-AL-Token": TOKEN})
    r = conn.getresponse()
    data = json.loads(r.read())
    conn.close()
    assert r.status == 200, data
    return data


def test_health_and_version_carry_mode_and_previous(srv, tmp_path, clean_env):
    for route in ("/api/health", "/api/version"):
        doc = _get(srv, route)
        assert doc["mode"] == "checkout" and doc["previous"] is None, route
    home = tmp_path / "home"
    write_marker(home, previous="0.1.0")
    clean_env.setenv(paths.HOME_ENV, str(home))
    for route in ("/api/health", "/api/version"):
        doc = _get(srv, route)
        assert doc["mode"] == "installed" and doc["previous"] == "0.1.0", route


# --- REL-CLIENT-HOME: the client's JS resolver mirrors this one ------------


def _js_const(src, name):
    import re
    m = re.search(r'^const %s = "([^"]*)";$' % name, src, re.M)
    assert m, name
    return m.group(1)


def test_js_and_python_resolvers_agree():
    """Static: app/client/home.js uses the same marker name, folder names,
    environment names and refusal words as server/al/paths.py."""
    import re
    src = (ROOT / "app" / "client" / "home.js").read_text(encoding="ascii")
    assert _js_const(src, "HOME_ENV") == paths.HOME_ENV
    assert _js_const(src, "SIDECAR_ENV") == paths.SIDECAR_ENV
    assert _js_const(src, "MARKER_NAME") == paths.MARKER_NAME
    assert _js_const(src, "DATA_DIR") == paths.DATA_DIR
    assert _js_const(src, "CACHE_DIR") == paths.INSTALLED_SUBDIRS["Cache"]
    assert _js_const(src, "RUNTIME_FOLDER") == paths.RUNTIME_FOLDER
    assert _js_const(src, "BOOT_NAME") == paths.BOOT_NAME
    assert _js_const(src, "APP_FOLDER") == "app"  # paths._marker_home: parent.name == "app"
    assert 'root.parent.name.lower() == "app"' in (ROOT / "server" / "al" / "paths.py").read_text(
        encoding="ascii")
    m = re.search(r"^const MARKER_MAX_BYTES = (\d+) \* (\d+);$", src, re.M)
    assert m and int(m.group(1)) * int(m.group(2)) == paths.MARKER_MAX_BYTES
    m = re.search(r"^const REFUSED_COMPONENTS = \[([^\]]*)\];$", src, re.M)
    assert m
    assert tuple(re.findall(r'"([^"]*)"', m.group(1))) == paths.REFUSED_COMPONENTS
    # the refusal sentence is the same words
    probe = paths.home_refusal(Path("x") / "steamapps")
    assert probe
    for piece in ("the install home may not lie in a '", "' folder (a Steam ",
                  "library or the game's own folder); install AshLight in its own folder"):
        assert piece in src, piece
        assert piece in probe, piece
