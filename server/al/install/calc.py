"""`installer calc [--opt-in]` (REL-INSTALL-CALC, F-050, DEP-09): the
optional theorycraft calc component (decision 0018) in an installed copy.

- With no argument: prints `calc: on|off` and `component: built|absent`
  for this copy and exits 0. Nothing is fetched, built or written.
- With --opt-in: runs the shipped tools/tc_pin.py as a child process
  (`setup --opt-in`, the same step as setup.ps1 -TcCalc) through the one
  command builder paths.python_cmd. In an install the child gets AL_HOME =
  the home and no AL_SIDECAR_ROOT / AL_RUNTIME_DIR, so the archives land in
  <home>/cache, the LuaJIT build in <home>/build and the opt-in flag
  "tc_calc": true in <home>/data/local.json, written by tc_pin only after a
  verified install (TC-CALC-OPTIN). The child's exit code is returned:
  0 ok, 2 refused (pin, hash, unsafe archive; tc_calc left unset), 1 other
  failure. In a checkout the child runs with the caller's environment
  (the sidecar layout), the same as setup.ps1 -TcCalc.

This module imports nothing from the calc or tools/tc_pin.py and prints no
path. The decision 0027 toolchain route is unchanged.
"""

import json
import os
import subprocess
import sys

from .. import paths
from . import home as homemod

MODULE = "tools.tc_pin"
OPT_IN = "--opt-in"
OPT_IN_KEY = "tc_calc"  # tools/tc_pin.py OPT_IN_KEY (not imported: see above)
# a calc fetch and LuaJIT build; the child has its own per-request timeouts
TIMEOUT_S = 3600

RC_OK = 0
RC_FAIL = 1
RC_USAGE = 2


def usage():
    return "usage: python -m server.al.install calc [--opt-in]"


def child_env(environ=None):
    """The child's environment. In an install: AL_HOME = the home, and the
    sidecar / runtime overrides removed so the installed layout applies."""
    env = dict(os.environ if environ is None else environ)
    home = paths.install_home(env)
    if home is not None:
        env.pop(paths.SIDECAR_ENV, None)
        env.pop(paths.RUNTIME_ENV, None)
        env[paths.HOME_ENV] = str(home)
    return env


def command(environ=None):
    """The child's command line (paths.python_cmd, DEP-06)."""
    env = os.environ if environ is None else environ
    return paths.python_cmd(MODULE, "setup", OPT_IN, environ=env)


def _local_config(home):
    path = homemod.layout(home)["local_config"]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def state_lines(home):
    """`calc: on|off` and `component: built|absent` for a home (no path)."""
    lay = homemod.layout(home)
    on = _local_config(home).get(OPT_IN_KEY) is True
    built = (lay["build"] / "tc-pins-stamp.json").is_file()
    return [f"calc: {'on' if on else 'off'}",
            f"component: {'built' if built else 'absent'}"]


def main(argv=None, environ=None, runner=None, out=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out or sys.stdout
    env = dict(os.environ if environ is None else environ)
    if argv not in ([], [OPT_IN]):
        print(usage(), file=sys.stderr)
        return RC_USAGE
    opt_in = argv == [OPT_IN]
    try:
        home = paths.install_home(env)
    except paths.HomeRefused as exc:
        print(f"calc: home refused, {exc}", file=sys.stderr)
        return RC_USAGE
    if home is not None and homemod.read_marker(home) is None:
        print("calc: marker missing or invalid; nothing done", file=sys.stderr)
        return RC_FAIL
    if not opt_in:
        if home is None:
            out.write("mode: checkout\n")
            out.write("calc: " + ("on" if paths.load_local_config().get(OPT_IN_KEY) is True
                                  else "off") + "\n")
        else:
            for line in state_lines(home):
                out.write(line + "\n")
        out.write("opt in with: python -m server.al.install calc --opt-in\n")
        return RC_OK
    if home is not None:
        lay = homemod.layout(home)
        for name in ("cache", "build"):
            lay[name].mkdir(parents=True, exist_ok=True)
    cenv = child_env(env)
    run = runner or subprocess.run
    try:
        done = run(command(cenv), env=cenv, timeout=TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"calc: could not run the calc setup ({exc.__class__.__name__})",
              file=sys.stderr)
        return RC_FAIL
    code = getattr(done, "returncode", RC_FAIL)
    return code if isinstance(code, int) else RC_FAIL
