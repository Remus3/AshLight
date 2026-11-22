"""TEST-PLUGIN-PIN: the suite pins its pytest plugin set and registers its
markers in pytest.ini, so a run never depends on what the interpreter
auto-loads (anyio, pytest-asyncio, pytest-timeout) and no mark is unknown."""

import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ini():
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(ROOT / "pytest.ini", encoding="utf-8")
    return cp["pytest"]


def test_addopts_disable_the_auto_loaded_plugins():
    opts = _ini()["addopts"].split()
    pairs = {opts[i + 1] for i, o in enumerate(opts[:-1]) if o == "-p"}
    for name in ("no:cacheprovider", "no:anyio", "no:asyncio", "no:timeout"):
        assert name in pairs, name
    assert "no:xdist" not in pairs  # xdist stays loadable


def test_new_markers_are_registered_in_the_ini():
    names = {ln.split(":", 1)[0].strip()
             for ln in _ini()["markers"].splitlines() if ln.strip()}
    assert {"timing", "calc", "xdist_group"} <= names


def test_markers_reach_the_running_session(pytestconfig):
    names = {m.split(":", 1)[0].split("(", 1)[0].strip()
             for m in pytestconfig.getini("markers")}
    for name in ("timing", "calc", "xdist_group", "slow", "server", "git", "discovery"):
        assert name in names, name


def test_running_session_has_no_anyio_asyncio_or_timeout_plugin(pytestconfig):
    pm = pytestconfig.pluginmanager
    for name in ("anyio", "asyncio", "timeout", "cacheprovider"):
        assert pm.get_plugin(name) is None, name
        assert pm.is_blocked(name), name
    loaded = {pm.get_name(p) or "" for p in pm.get_plugins()}
    assert not any("anyio" in n or "asyncio" in n for n in loaded), sorted(loaded)


def test_hang_guard_is_set_in_the_ini():
    """TEST-SLOW-BUDGET: a hung test ends after 120 s with tracebacks."""
    ini = _ini()
    assert ini["faulthandler_timeout"].strip() == "120"
    assert ini["faulthandler_exit_on_timeout"].strip() == "true"


def test_hang_guard_reaches_the_running_session(pytestconfig):
    assert float(pytestconfig.getini("faulthandler_timeout")) == 120
    assert pytestconfig.getini("faulthandler_exit_on_timeout") is True
