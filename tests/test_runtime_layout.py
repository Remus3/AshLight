"""DEP-06 (F-047): the private runtimes and the one command builder.

paths.python_cmd() is today's `-m` form in a checkout and
`<python> <payload>/boot.py <module>` in an install; keepalive's
core_command() and run_preflight() go through it; python_exe() and
electron_exe() lie under <home>/runtime in an install and are read from the
marker; boot.py puts its own folder first on sys.path. With the pinned
embeddable CPython zip in the sidecar cache (skipped when absent),
`<python> boot.py server.al --check` returns 0 with no Python on PATH.
Everything runs against tmp folders; no core, overlay or game is started.
"""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from server.al import keepalive as ka
from server.al import paths, procs

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / "boot.py"
ENV_KEYS = (paths.HOME_ENV, paths.SIDECAR_ENV, paths.RUNTIME_ENV,
            procs.ELECTRON_DIR_ENV)
PY_FOLDER = "python-3.14.10"
EL_FOLDER = "electron-45.3.3"
# plan 05 Design point 4 and the DEP-01 spike record (read back there)
EMBED_ZIP = "python-3.14.10-embed-amd64.zip"
EMBED_SHA256 = "90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159"
EMBED_ENV = "AL_EMBED_ZIP"  # tests only: another copy of the pinned zip
BAD_NAMES = ("..", "", "a/b", "..\\x", "C:x", 7, None)


@pytest.fixture
def clean_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(paths, "_MARKER_SEEN", {})
    return monkeypatch


def install(tmp_path, env, **fields):
    """A scratch install home with a marker; AL_HOME names it."""
    home = tmp_path / "home"
    doc = {"schema": 1, "name": "AshLight", "version": "0.1.1", "previous": None,
           "channel": "stable", "python": PY_FOLDER, "electron": EL_FOLDER,
           "pending_confirm": False, "start_attempts": 0}
    doc.update(fields)
    home.mkdir(parents=True, exist_ok=True)
    (home / paths.MARKER_NAME).write_text(json.dumps(doc), encoding="ascii")
    env.setenv(paths.HOME_ENV, str(home))
    return home


def running(windowless):
    exe = Path(sys.executable)
    if os.name != "nt":
        return exe
    want, other = ("pythonw.exe", "python.exe") if windowless else ("python.exe", "pythonw.exe")
    if exe.name.lower() != other:  # already the wanted kind (any case), or neither
        return exe
    twin = exe.with_name(want)
    return twin if twin.exists() else exe


# ------------------------------------------------------------ the builder

def test_python_cmd_in_a_checkout_is_the_m_form(clean_env):
    assert paths.install_mode() == "checkout"
    cmd = paths.python_cmd("server.al.paths")
    assert cmd == [str(running(False)), "-m", "server.al.paths"]
    cmd = paths.python_cmd("server.al", "--port", 8961, windowless=True)
    assert cmd == [str(running(True)), "-m", "server.al", "--port", "8961"]
    # root only names another payload in an install; a checkout ignores it
    assert paths.python_cmd("server.al", root="elsewhere")[1:] == ["-m", "server.al"]


def test_python_cmd_in_an_install_starts_through_boot_py(tmp_path, clean_env):
    home = install(tmp_path, clean_env)
    rt = home / "runtime" / PY_FOLDER
    assert paths.python_cmd("server.al", "--check") == [
        str(rt / "python.exe"), str(ROOT / "boot.py"), "server.al", "--check"]
    assert paths.python_cmd("server.al.keepalive", windowless=True) == [
        str(rt / "pythonw.exe"), str(ROOT / "boot.py"), "server.al.keepalive"]
    other = tmp_path / "home" / "app" / "0.1.2"  # N+1 self-tests while N runs
    assert paths.python_cmd("server.al", "--check", root=other)[1] == str(other / "boot.py")


def test_python_cmd_without_a_usable_marker_name_uses_the_running_python(tmp_path, clean_env):
    for bad in BAD_NAMES:
        install(tmp_path, clean_env, python=bad)
        assert paths.python_exe() is None, bad
        cmd = paths.python_cmd("server.al", "--check")
        assert cmd == [str(running(False)), str(ROOT / "boot.py"), "server.al", "--check"], bad


# ------------------------------------------------------------ the resolvers

def test_runtimes_lie_under_home_runtime_from_the_marker(tmp_path, clean_env):
    home = install(tmp_path, clean_env)
    assert paths.python_exe() == home / "runtime" / PY_FOLDER / "python.exe"
    assert paths.python_exe(windowless=True) == home / "runtime" / PY_FOLDER / "pythonw.exe"
    assert paths.electron_exe() == home / "runtime" / EL_FOLDER / "electron.exe"
    assert procs.electron_dir() == home / "runtime" / EL_FOLDER  # one resolver
    install(tmp_path, clean_env, python="python-3.14.11", electron="electron-46.0.0")
    assert paths.python_exe().parent.name == "python-3.14.11"
    assert paths.electron_exe().parent.name == "electron-46.0.0"
    for bad in BAD_NAMES:
        install(tmp_path, clean_env, electron=bad)
        assert paths.electron_exe() is None, bad
        assert procs.electron_dir() is None, bad


def test_runtimes_in_a_checkout(clean_env):
    assert paths.python_exe() == running(False)
    assert paths.python_exe(windowless=True) == running(True)
    dist = ROOT / "app" / "node_modules" / "electron" / "dist"
    assert paths.electron_exe() == dist / "electron.exe"
    assert procs.electron_dir() == dist


def test_runtime_pins_file_is_tracked_config():
    assert paths.runtime_pins_file() == ROOT / "config" / "runtime_pins.json"


def test_a_refused_home_refuses_the_runtimes(tmp_path, clean_env):
    clean_env.setenv(paths.HOME_ENV, str(tmp_path / "steamapps" / "AshLight"))
    for call in (paths.python_exe, paths.electron_exe,
                 lambda: paths.python_cmd("server.al")):
        with pytest.raises(paths.HomeRefused):
            call()


# ------------------------------------------------------------ the spawn sites

def test_core_command_uses_the_builder(tmp_path, clean_env):
    cmd = ka.core_command(8961, ["--no-tail"])
    assert cmd == paths.python_cmd("server.al", "--quiet", "--port", "8961",
                                   "--no-tail", windowless=True)
    assert cmd[1:3] == ["-m", "server.al"]
    home = install(tmp_path, clean_env)
    cmd = ka.core_command(8961, ["--no-tail"])
    assert cmd == [str(home / "runtime" / PY_FOLDER / "pythonw.exe"), str(BOOT),
                   "server.al", "--quiet", "--port", "8961", "--no-tail"]


def test_run_preflight_uses_the_builder(tmp_path, clean_env):
    seen = []

    class R:
        returncode = 0
        stdout = b""
        stderr = b""

    def run(cmd, **kw):
        seen.append((cmd, kw.get("cwd")))
        return R()

    assert ka.run_preflight(tmp_path, run=run) == (True, None)
    assert seen[-1] == ([str(running(False)), "-m", "server.al", "--check"], str(tmp_path))
    home = install(tmp_path, clean_env)
    payload = tmp_path / "payload"
    assert ka.run_preflight(payload, run=run) == (True, None)
    assert seen[-1] == ([str(home / "runtime" / PY_FOLDER / "python.exe"),
                         str(payload / "boot.py"), "server.al", "--check"], str(payload))


# ------------------------------------------------------------ boot.py

def _boot_module():
    spec = importlib.util.spec_from_file_location("_al_boot_under_test", BOOT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_boot_put_first_moves_its_folder_to_the_front(tmp_path):
    boot = _boot_module()
    here = str(tmp_path)
    assert boot.put_first(["a", here, "", "b"], here) == [here, "a", "", "b"]
    assert boot.put_first([], here) == [here]
    assert boot.payload_root() == str(ROOT)


def test_boot_py_runs_a_module_with_its_folder_first(tmp_path):
    payload = tmp_path / "payload"
    pkg = payload / "alprobe"
    pkg.mkdir(parents=True)
    shutil.copy2(BOOT, payload / "boot.py")
    (pkg / "__init__.py").write_text("", encoding="ascii")
    (pkg / "__main__.py").write_text(
        "import json, sys\n"
        "print(json.dumps({'first': sys.path[0], 'argv': sys.argv[1:],"
        " 'name': __name__, 'file': sys.argv[0]}))\n"
        "sys.exit(7)\n", encoding="ascii")
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    # -I: isolated like the embeddable runtime (no script folder, no cwd)
    r = subprocess.run([sys.executable, "-I", str(payload / "boot.py"), "alprobe", "x", "--y"],
                       cwd=str(cwd), capture_output=True, text=True, timeout=60)
    assert r.returncode == 7, r.stderr
    out = json.loads(r.stdout)
    assert os.path.normcase(out["first"]) == os.path.normcase(str(payload))
    assert out["argv"] == ["x", "--y"]
    assert out["name"] == "__main__"
    assert Path(out["file"]).name == "__main__.py"
    # the same module without the shim is not found under -I
    r = subprocess.run([sys.executable, "-I", "-m", "alprobe"], cwd=str(cwd),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0


def test_boot_py_refuses_a_bad_module_name(tmp_path):
    for argv in ([], ["../x"], ["a b"], ["server.al;x"]):
        r = subprocess.run([sys.executable, "-I", str(BOOT)] + argv, cwd=str(tmp_path),
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 2, argv
        assert "usage: boot.py" in r.stderr


# ------------------------------------------------------------ the real runtime

def _embed_zip():
    value = (os.environ.get(EMBED_ENV) or "").strip().strip('"')
    if value:
        return Path(value)
    return paths.sidecar_dir("Cache") / "downloads" / EMBED_ZIP


@pytest.mark.skipif(os.name != "nt", reason="the embeddable runtime is Windows only")
def test_boot_check_under_the_embeddable_runtime_without_path_python(tmp_path, clean_env):
    src = _embed_zip()
    if not src.is_file():
        pytest.skip(f"pinned {EMBED_ZIP} not in the sidecar cache")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    if digest != EMBED_SHA256:
        pytest.skip(f"{src.name} is not the pinned zip")
    home = install(tmp_path, clean_env)
    rt = home / "runtime" / PY_FOLDER
    with zipfile.ZipFile(src) as zf:
        zf.extractall(rt)
    cmd = paths.python_cmd("server.al", "--check")
    assert cmd[:3] == [str(rt / "python.exe"), str(BOOT), "server.al"]
    sysroot = os.environ.get("SystemRoot") or os.environ.get("windir")
    if not sysroot:
        pytest.skip("no SystemRoot in the environment")
    bare = os.pathsep.join([os.path.join(sysroot, "System32"), sysroot])
    for name in ("python", "py", "node"):
        assert shutil.which(name, path=bare) is None, name
    env = {"SystemRoot": sysroot, "PATH": bare, "TEMP": str(tmp_path), "TMP": str(tmp_path),
           paths.SIDECAR_ENV: str(tmp_path / "sidecar"),
           paths.RUNTIME_ENV: str(tmp_path / "rt")}
    r = subprocess.run(cmd, cwd=str(tmp_path), env=env, capture_output=True, text=True,
                       timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
    assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
