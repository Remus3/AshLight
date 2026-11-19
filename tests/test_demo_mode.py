"""SEC-DEMO-CORE (decision 0049): a demo core is an isolated instance on a
fixture folder. It reads and writes only under its fixture and scratch dirs
(plus AshLight's own tracked package data), never config/local.json or the
live runtime dir, never the network, and ends with exit 97 before a log
outside the fixture folder is opened."""

import builtins
import io
import json
import os
from pathlib import Path

import pytest

from server.al import core as core_mod
from server.al import demo, logfile, paths, ports, webfetch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DATA = ROOT / "server" / "al" / "data"
LINE = "2026/11/18 10:00:00 123 abc [INFO Client 1] : You have entered Clearfell.\n"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """os.environ and the paths override restored after the test; the
    sidecar root points at tmp, so the scratch dir lands there."""
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "sidecar"))
    # set, then deleted: monkeypatch restores the real state either way
    # (a bare delenv of an absent key records nothing to restore)
    monkeypatch.setenv(paths.RUNTIME_ENV, "unset")
    monkeypatch.delenv(paths.RUNTIME_ENV)
    monkeypatch.setenv(demo.HOT_RELOAD_ENV, "0")
    monkeypatch.setattr(paths, "_DEMO_CONFIG", None)
    return tmp_path


def make_fixture(base, name="fixture", marker=True, log=True):
    d = base / name
    d.mkdir(parents=True)
    if marker:
        (d / demo.MARKER).write_text(json.dumps({"ashlight_demo": 1}), encoding="ascii")
    if log:
        (d / "Client.txt").write_text(LINE, encoding="ascii")
    return d


class Exited(Exception):
    pass


def exit_spy(calls):
    def fake_exit(code):
        calls.append(code)
        raise Exited(code)
    return fake_exit


def _inside(p, root):
    try:
        Path(os.path.abspath(p)).relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def test_prepare_points_runtime_config_and_sidecar_at_scratch(env):
    fixture = make_fixture(env)
    temp = (env / "sidecar" / "Temp").resolve()
    d = demo.prepare(fixture)
    assert d.fixture == fixture.resolve()
    assert d.log == fixture.resolve() / "Client.txt"
    assert d.scratch.parent == temp and d.scratch.name.startswith(demo.SCRATCH_PREFIX)
    assert os.environ[paths.RUNTIME_ENV] == str(d.runtime)
    assert os.environ[paths.SIDECAR_ENV] == str(d.sidecar)
    assert os.environ[demo.HOT_RELOAD_ENV] == "0"
    assert paths.runtime_dir() == d.runtime
    assert paths.sidecar_root() == d.sidecar
    assert paths.local_config_file() == d.config
    assert paths.consent_file() == d.consent
    for name, p in paths.all_runtime_paths().items():
        if name == "repo":
            continue
        assert _inside(p, d.scratch), (name, str(p))
    for sub in paths.SIDECAR_SUBDIRS:
        assert (d.sidecar / sub).is_dir()
    rec = json.loads(d.consent.read_text(encoding="ascii"))
    assert rec["consented"] is True and rec["demo"] is True
    assert rec["file"] == "Client.txt" and rec["path"] == str(d.log)
    # a second instance gets its own scratch dir
    os.environ[paths.SIDECAR_ENV] = str(env / "sidecar")
    d2 = demo.prepare(fixture)
    assert d2.scratch != d.scratch and d2.scratch.parent == temp
    # an explicit environ dict is the one written
    os.environ[paths.SIDECAR_ENV] = str(env / "sidecar")
    mine = {paths.SIDECAR_ENV: str(env / "other")}
    d3 = demo.prepare(fixture, environ=mine)
    assert d3.scratch.parent == (env / "other" / "Temp").resolve()
    assert mine[paths.RUNTIME_ENV] == str(d3.runtime)
    assert mine[paths.SIDECAR_ENV] == str(d3.sidecar)
    assert mine[demo.HOT_RELOAD_ENV] == "0"


def test_missing_fixture_or_marker_is_an_error(env):
    cases = [env / "nothing-here",
             make_fixture(env, "no-marker", marker=False),
             make_fixture(env, "no-log", log=False)]
    bad = make_fixture(env, "bad-marker")
    (bad / demo.MARKER).write_text("[1, 2]", encoding="ascii")
    cases.append(bad)
    broken = make_fixture(env, "broken-marker")
    (broken / demo.MARKER).write_text("{nope", encoding="ascii")
    cases.append(broken)
    folder_log = make_fixture(env, "dir-log", log=False)
    (folder_log / "Client.txt").mkdir()
    cases.append(folder_log)
    for case in cases:
        with pytest.raises(demo.DemoError):
            demo.prepare(case)
    for junk in ("", None, 5):
        with pytest.raises(demo.DemoError):
            demo.prepare(junk)
    # nothing was made and nothing was pointed anywhere
    assert not (env / "sidecar" / "Temp").exists()
    assert paths.RUNTIME_ENV not in os.environ
    assert paths._DEMO_CONFIG is None


def test_game_folder_shaped_path_is_refused(env, monkeypatch):
    real = make_fixture(env / "steamapps" / "common", "Path of Exile 2")
    shapes = [real, str(real).upper(),
              env / "steamapps" / "fixture",
              env / "Games" / "path of exile 2" / "logs",
              str(env / "STEAMAPPS" / "x").replace("\\", "/")]
    stats = []
    real_stat = os.stat

    def stat_spy(p, *a, **k):
        stats.append(str(p))
        return real_stat(p, *a, **k)

    monkeypatch.setattr(os, "stat", stat_spy)
    monkeypatch.setattr(os, "lstat", stat_spy)
    for shape in shapes:
        with pytest.raises(demo.DemoError, match="game folder"):
            demo.check_fixture(shape)
    assert not [s for s in stats if demo.game_path_part(s)], stats
    assert demo.game_path_part("a/b/c") is None
    assert demo.game_path_part("x\\SteamApps\\y") == "SteamApps"


def test_log_outside_the_fixture_exits_97(env, monkeypatch):
    fixture = make_fixture(env)
    outside = make_fixture(env, "elsewhere") / "Client.txt"
    d = demo.prepare(fixture)
    calls = []
    opened = []
    real_tailer = logfile.Tailer

    def tailer_spy(path, *a, **k):
        opened.append(Path(path))
        return real_tailer(path, *a, **k)

    monkeypatch.setattr(logfile, "Tailer", tailer_spy)
    core = demo.DemoCore(d, exit_fn=exit_spy(calls))
    try:
        assert core.log_path == d.log and calls == []
        # a configured log that leaves the fixture: exit 97, nothing opened
        core._configured_log = str(outside)
        with pytest.raises(Exited):
            core.locate_log()
        assert calls == [demo.EXIT_LOG_OUTSIDE] == [97]
        core.log_path = outside
        with pytest.raises(Exited):
            core.start_tailing()
        assert calls == [97, 97]
        assert core.tailer is None and opened == []
        # a relative path climbing out of the fixture is caught as well
        assert not core.log_allowed(str(d.fixture / ".." / "elsewhere" / "Client.txt"))
        # an exit function that returns still never lets the open happen
        core._exit = lambda code: calls.append(code)
        with pytest.raises(SystemExit) as info:
            core.start_tailing()
        assert info.value.code == 97 and opened == []
        # the fixture's own log is the one that is tailed
        core.log_path = d.log
        assert core.start_tailing() is True
        assert opened == [d.log]
    finally:
        core.stop_tailing()
        core.close()


def test_consent_api_cannot_move_the_demo_log(env):
    fixture = make_fixture(env)
    other = make_fixture(env, "other")
    d = demo.prepare(fixture)
    core = demo.DemoCore(d, exit_fn=exit_spy([]), tail=False)
    try:
        before = d.consent.read_bytes()
        for path in (str(other / "Client.txt"), str(other), str(d.log)):
            with pytest.raises(ValueError, match="demo mode"):
                core.record_consent(True, path)
        assert core.log_path == d.log
        assert core._configured_log == str(d.log)
        assert d.consent.read_bytes() == before
        rec = core.record_consent(False)
        assert rec["consented"] is False and rec["demo"] is True
        assert rec["path"] == str(d.log)
        assert core.consented() is False
        rec = core.record_consent(True)
        assert rec["consented"] is True and core.consented() is True
        assert json.loads(d.consent.read_text(encoding="ascii"))["scope"] == \
            "demo fixture file only"
    finally:
        core.close()
    with pytest.raises(TypeError):
        demo.DemoCore(d, log_path=str(other / "Client.txt"))
    with pytest.raises(TypeError):
        demo.DemoCore(d, discover=True)


def test_fetcher_refuses_every_request(env):
    d = demo.prepare(make_fixture(env))
    for method, url in (("GET", "https://poe.ninja/api/data/x"),
                        ("POST", "https://example.invalid/"),
                        ("GET", "http://127.0.0.1:8960/")):
        with pytest.raises(webfetch.WebDataOff):
            demo.refuse_fetch(method, url, {"User-Agent": "x"}, None)
    core = demo.DemoCore(d, exit_fn=exit_spy([]), tail=False)
    try:
        assert core.web_fetch is demo.refuse_fetch
        assert core.rates.fetch is demo.refuse_fetch
        assert core.discover is False
        # even a turned-on setting in the scratch config stays off
        d.config.write_text(json.dumps({"web_data": True, "contact": "demo contact"}),
                            encoding="ascii")
        assert core.web_data_enabled() is False
        with pytest.raises(webfetch.FetchError):
            core.load_share_url("https://pobb.in/abc")
        with pytest.raises(webfetch.WebDataOff):
            webfetch.request("GET", "https://poe.ninja/x", {"User-Agent": "x"},
                             ["poe.ninja"], fetch=core.web_fetch)
    finally:
        core.close()


def test_first_free_port_of_the_demo_block():
    lo, hi = ports.DEMO_BLOCK
    asked = []

    def probe(port):
        asked.append(port)
        return port >= lo + 2

    assert demo.pick_port(probe) == lo + 2
    assert asked == [lo, lo + 1, lo + 2]
    assert demo.pick_port(lambda p: True) == lo
    asked.clear()
    with pytest.raises(demo.DemoError):
        demo.pick_port(lambda p: asked.append(p) or False)
    assert asked == list(range(lo, hi + 1))
    assert ports.AL_PORT not in asked and ports.AL_PORT not in range(lo, hi + 1)


def test_real_config_is_never_opened(env, monkeypatch):
    fixture = make_fixture(env)
    real_config = paths.repo_root() / "config" / "local.json"
    live_runtime = paths.repo_root() / "ops" / "runtime"
    live_before = live_runtime.stat().st_mtime_ns if live_runtime.exists() else None
    d = demo.prepare(fixture)
    assert paths.local_config_file() == d.config != real_config
    seen = []
    real_open = io.open
    real_os_open = os.open

    def open_spy(f, mode="r", *a, **k):
        if isinstance(f, (str, os.PathLike)):
            seen.append((os.fspath(f), mode))
        return real_open(f, mode, *a, **k)

    def os_open_spy(p, flags, *a, **k):
        writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
        seen.append((os.fspath(p), "w" if writing else "r"))
        return real_os_open(p, flags, *a, **k)

    loads = []
    monkeypatch.setattr(builtins, "open", open_spy)
    monkeypatch.setattr(io, "open", open_spy)
    monkeypatch.setattr(os, "open", os_open_spy)
    monkeypatch.setattr(paths, "load_local_config",
                        lambda: loads.append(1) or pytest.fail("real config read"))
    core = demo.DemoCore(d, exit_fn=exit_spy([]))
    try:
        assert core.config_path == d.config
        assert core.consent_path == d.consent
        assert core.start_tailing() is True
        assert core.tailer.path == d.log
        core.set_overlay_layout({})
        core.record_consent(True)
    finally:
        core.stop_tailing()
        core.close()
    assert loads == []
    files = [(Path(os.path.abspath(p)), m) for p, m in seen if not p.endswith((".py", ".pyc"))]
    assert files, "the spy saw no file at all"
    for p, mode in files:
        assert p != real_config, "config/local.json was opened"
        assert not _inside(p, live_runtime), f"live runtime touched: {p}"
        if any(c in mode for c in "wax+"):
            assert _inside(p, d.scratch), f"write outside scratch: {p}"
        else:
            assert (_inside(p, d.scratch) or _inside(p, d.fixture)
                    or _inside(p, PACKAGE_DATA)), f"read outside: {p}"
    after = live_runtime.stat().st_mtime_ns if live_runtime.exists() else None
    assert after == live_before
    assert core_mod.Core.web_data_enabled is not demo.DemoCore.web_data_enabled
