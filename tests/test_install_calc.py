"""REL-INSTALL-CALC (F-050, DEP-09, decisions 0018 / 0059): `installer calc
--opt-in` runs the shipped tools/tc_pin.py as a child of the installer
(paths.python_cmd) with the installed-mode paths in its environment, so the
calc lands in <home>/cache and <home>/build and tc_calc is set in
<home>/data/local.json only after a verified install.

Fakes only: the child is run in-process with its environment applied, the
network step (tc_pin.run_setup) is replaced; nothing is fetched or built.
"""

import ast
import json
import os
import subprocess
from pathlib import Path

import pytest

from server.al import paths
from server.al.install import calc, cli
from server.al.install import home as homemod

ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = (paths.HOME_ENV, paths.SIDECAR_ENV, paths.RUNTIME_ENV)


@pytest.fixture
def clean_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(paths, "_MARKER_SEEN", {})
    return monkeypatch


@pytest.fixture
def home(tmp_path, clean_env):
    home = tmp_path / "Programs" / "AshLight"
    doc = homemod.new_marker("0.1.0", "python-3.14.10", "electron-45.3.3")
    homemod.write_marker(home, doc)
    (home / "data").mkdir(parents=True, exist_ok=True)
    return home


def installed_env(home, **extra):
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env[paths.HOME_ENV] = str(home)
    env.update(extra)
    return env


class FakeChild:
    """Runs tools/tc_pin.py main in-process under the child's environment,
    with run_setup replaced by `setup(layout)` (the paths it would use)."""

    def __init__(self, monkeypatch, setup):
        self.mp = monkeypatch
        self.setup = setup
        self.calls = []
        self.seen = {}

    def __call__(self, cmd, env=None, **kw):
        import tools.tc_pin as tc_pin
        self.calls.append((list(cmd), dict(env or {}), kw))
        with self.mp.context() as m:
            for key in ENV_KEYS:
                m.delenv(key, raising=False)
            for key in ENV_KEYS:
                if key in env:
                    m.setenv(key, env[key])

            def run_setup(doc, *a, **k):
                lay = tc_pin.layout(doc)
                self.seen.update(lay)
                self.seen["local_config"] = paths.local_config_file()
                return self.setup(lay)

            m.setattr(tc_pin, "run_setup", run_setup)
            argv = cmd[cmd.index("tools.tc_pin") + 1:]
            rc = tc_pin.main(argv)
        return subprocess.CompletedProcess(cmd, rc)


def read_cfg(home):
    path = home / "data" / "local.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# --- the command -------------------------------------------------------

def test_calc_is_in_the_command_table_and_loads():
    assert cli.COMMANDS["calc"] == "calc"
    assert cli.load("calc") is calc


def test_verified_run_sets_tc_calc_in_the_home_local_json(home, clean_env):
    child = FakeChild(clean_env, lambda lay: "ready")
    rc = calc.main(["--opt-in"], environ=installed_env(home), runner=child)
    assert rc == 0
    assert len(child.calls) == 1
    assert read_cfg(home) == {"tc_calc": True}
    # the checkout's config is never the one written
    assert child.seen["local_config"] == home / "data" / "local.json"


def test_other_keys_in_local_json_are_kept(home, clean_env):
    (home / "data" / "local.json").write_text('{"web_data": false}\n', encoding="ascii")
    child = FakeChild(clean_env, lambda lay: "ready")
    assert calc.main(["--opt-in"], environ=installed_env(home), runner=child) == 0
    assert read_cfg(home) == {"web_data": False, "tc_calc": True}


def test_hash_mismatch_leaves_tc_calc_unset_and_exits_2(home, clean_env):
    import tools.tc_pin as tc_pin

    def mismatch(lay):
        raise tc_pin.HashMismatch("pob2: sha256 mismatch")

    child = FakeChild(clean_env, mismatch)
    rc = calc.main(["--opt-in"], environ=installed_env(home), runner=child)
    assert rc == 2
    assert read_cfg(home) is None


def test_source_only_leaves_tc_calc_unset(home, clean_env):
    child = FakeChild(clean_env, lambda lay: "source-only")
    assert calc.main(["--opt-in"], environ=installed_env(home), runner=child) == 0
    assert read_cfg(home) is None


def test_without_opt_in_nothing_is_fetched(home, clean_env, capsys):
    def runner(*a, **k):
        raise AssertionError("no child may run without --opt-in")

    assert calc.main([], environ=installed_env(home), runner=runner) == 0
    out = capsys.readouterr().out
    assert "calc: off" in out
    assert not (home / "build").exists()
    assert not (home / "cache" / "pob2").exists()
    assert str(home) not in out  # no path is printed


def test_status_reads_tc_calc_from_the_home(home, clean_env, capsys):
    (home / "data" / "local.json").write_text('{"tc_calc": true}\n', encoding="ascii")
    assert calc.main([], environ=installed_env(home), runner=None) == 0
    assert "calc: on" in capsys.readouterr().out


def test_the_paths_used_are_home_cache_and_home_build(home, clean_env):
    child = FakeChild(clean_env, lambda lay: "ready")
    # a sidecar or runtime override in the caller's env must not leak in
    env = installed_env(home, **{paths.SIDECAR_ENV: str(home.parent / "elsewhere"),
                                 paths.RUNTIME_ENV: str(home.parent / "rt")})
    assert calc.main(["--opt-in"], environ=env, runner=child) == 0
    cmd, child_env, _ = child.calls[0]
    assert child_env[paths.HOME_ENV] == str(home)
    assert paths.SIDECAR_ENV not in child_env and paths.RUNTIME_ENV not in child_env
    cache, build = home / "cache", home / "build"
    for key in ("pob2_cache", "luajit_cache", "toolchain_cache"):
        assert child.seen[key].parent == cache, key
    for key in ("luajit_build", "stamp"):
        assert child.seen[key].parent == build, key
    assert child.seen["temp"] == home / "temp"


def test_command_goes_through_python_cmd(home, clean_env):
    env = installed_env(home)
    cmd = calc.command(env)
    assert cmd == paths.python_cmd("tools.tc_pin", "setup", "--opt-in", environ=env)
    # installed form: <python> <payload>/boot.py tools.tc_pin setup --opt-in
    assert Path(cmd[1]).name == "boot.py"
    assert cmd[2:] == ["tools.tc_pin", "setup", "--opt-in"]


def test_child_failure_code_is_passed_through(home, clean_env):
    def runner(cmd, env=None, **kw):
        return subprocess.CompletedProcess(cmd, 1)

    assert calc.main(["--opt-in"], environ=installed_env(home), runner=runner) == 1


def test_refused_home_exits_2_and_runs_nothing(tmp_path, clean_env):
    bad = tmp_path / "steamapps" / "AshLight"

    def runner(*a, **k):
        raise AssertionError("must not run")

    env = installed_env(bad)
    assert calc.main(["--opt-in"], environ=env, runner=runner) == 2


def test_missing_marker_exits_1_and_runs_nothing(tmp_path, clean_env):
    def runner(*a, **k):
        raise AssertionError("must not run")

    env = installed_env(tmp_path / "nohome")
    assert calc.main(["--opt-in"], environ=env, runner=runner) == 1


def test_unknown_argument_is_usage(home, clean_env):
    assert calc.main(["--force"], environ=installed_env(home), runner=None) == 2


def test_calc_imports_nothing_from_the_calc():
    tree = ast.parse((ROOT / "server" / "al" / "install" / "calc.py").read_text(encoding="ascii"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    assert not any("tc_pin" in n or "theorycraft" in n for n in names), names


def test_boot_shim_runs_the_tc_pin_module(clean_env):
    # the installed command form starts `boot.py tools.tc_pin ...`; `tools`
    # has no __init__.py, so it must resolve as a namespace package
    import sys
    done = subprocess.run([sys.executable, str(ROOT / "boot.py"), MODULE_NAME, "check"],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "pins ok" in done.stdout


MODULE_NAME = calc.MODULE


def test_tc_pin_ships_in_the_release_payload():
    ship = json.loads((ROOT / "config" / "ship_list.json").read_text(encoding="ascii"))
    assert "tools/tc_pin.py" in ship["include"]
    assert "boot.py" in ship["include"]
