"""The ONE runtime path resolver for AshLight.

State lives in the repo's gitignored ops/runtime/. Everything else the app
makes outside its tracked files (temp, build stamps, logs, caches) lives under
the AL sidecar root:

- env AL_SIDECAR_ROOT when set and non-empty (tests point it at tmp), else
- the fleet kit default (ops/fleet_kit/fleet_lanes.py SIDECAR_DEFAULT) + "AL".

The drive path is never spelled here; it comes from the vendored kit.
Run `python -m server.al.paths` to print every path as JSON (the scripts use it).

Installed mode (DEP-05, decision 0059, docs/plan/05 "Installed-mode layout"):
an installed copy runs from <home>/app/<version>/ with the marker
<home>/install.json two levels above the payload root, or AL_HOME names the
home. Then all player state lives in <home>/data/ (the runtime files and
local.json) and the sidecar folders become <home>/cache, logs, temp and
build; Worktree, Scratch and ClaudeHistory do not exist. A home whose path
text has a `steamapps` or `Path of Exile 2` component is refused, by path
text only: no registry read, no library file, no listing or stat of any
game folder. In a checkout nothing changes.
"""

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

CODE = "AL"
SIDECAR_ENV = "AL_SIDECAR_ROOT"
# Tests and demo mode only: a tmp runtime dir for a test core, or the scratch
# runtime of a demo instance (server/al/demo.py prepare, decision 0049).
RUNTIME_ENV = "AL_RUNTIME_DIR"
# Every sidecar folder CLAUDE.md "Sidecar" lists except Worktree (made by the
# worktree hook, see worktree_dir) - AUDIT-HYGIENE H4.
SIDECAR_SUBDIRS = ("Scratch", "Temp", "Build", "Logs", "Cache", "ClaudeHistory")

# Installed mode (decision 0059). AL_HOME names the install home (tests, and
# -InstallDir on this machine); else the marker two levels above the payload
# root (<home>/app/<version>/) makes the copy an installed one.
HOME_ENV = "AL_HOME"
HOME_NAME = "AshLight"  # %LOCALAPPDATA%/Programs/AshLight, the default home
MARKER_NAME = "install.json"
MARKER_MAX_BYTES = 64 * 1024
DATA_DIR = "data"
# the sidecar folders an install has, under their installed (lower case) name
INSTALLED_SUBDIRS = {"Cache": "cache", "Logs": "logs", "Temp": "temp", "Build": "build"}
# path components a home may never have, matched case-insensitively with
# the trailing dots and spaces Windows ignores stripped: a Steam library or
# the game's own folder. Path text only (floor audit on F-049).
REFUSED_COMPONENTS = ("steamapps", "path of exile 2")

_KIT_DEFAULT = None
_MARKER_SEEN = {}  # payload root text -> marker present (a payload never moves)


class HomeRefused(ValueError):
    """The install home lies in a Steam library or the game's folder."""


def repo_root():
    """The repository root (two levels above this package); in an install,
    the payload root <home>/app/<version>."""
    return Path(__file__).resolve().parents[2]


def _env_home(env):
    value = (env.get(HOME_ENV) or "").strip().strip('"')
    # abspath, never resolve(): no file system access before the text check
    return Path(os.path.abspath(value)) if value else None


def _marker_home(root=None):
    """<home> when the payload root is <home>/app/<version> and the marker
    <home>/install.json exists, else None. One stat of the marker inside
    the home, cached per payload root."""
    root = Path(root) if root is not None else repo_root()
    key = str(root)
    if key not in _MARKER_SEEN:
        seen = False
        if len(root.parents) >= 2 and root.parent.name.lower() == "app":
            try:
                seen = (root.parents[1] / MARKER_NAME).is_file()
            except OSError:
                seen = False
        _MARKER_SEEN[key] = seen
    return root.parents[1] if _MARKER_SEEN[key] else None


def install_mode(environ=None):
    """'installed' when AL_HOME is set or the marker lies two levels above
    the payload root, else 'checkout'."""
    env = os.environ if environ is None else environ
    if _env_home(env) is not None or _marker_home() is not None:
        return "installed"
    return "checkout"


def home_refusal(home):
    """The reason a home is refused, or None. Path text only: no registry
    read, no library file, no listing and no stat of anything."""
    for part in re.split(r"[\\/]+", str(home)):
        if part.rstrip(". ").casefold() in REFUSED_COMPONENTS:
            return (f"the install home may not lie in a '{part}' folder (a Steam "
                    "library or the game's own folder); install AshLight in its "
                    "own folder")
    return None


def install_home(environ=None):
    """The install home (AL_HOME, else two levels above the payload root),
    or None in a checkout. Raises HomeRefused for a home in a Steam library
    or the game's folder."""
    env = os.environ if environ is None else environ
    home = _env_home(env)
    if home is None:
        home = _marker_home()
    if home is None:
        return None
    reason = home_refusal(home)
    if reason:
        raise HomeRefused(reason)
    return home


def check_home(environ=None):
    """The start-up check: the refusal text for a bad home, else None."""
    try:
        install_home(environ)
    except HomeRefused as exc:
        return str(exc)
    return None


def default_home(environ=None):
    """Where a player install goes by default:
    %LOCALAPPDATA%/Programs/AshLight (the installer's -InstallDir moves it)."""
    env = os.environ if environ is None else environ
    base = (env.get("LOCALAPPDATA") or "").strip().strip('"')
    base = Path(base) if base else Path.home() / "AppData" / "Local"
    return base / "Programs" / HOME_NAME


def marker_file(environ=None):
    """<home>/install.json, or None in a checkout."""
    home = install_home(environ)
    return home / MARKER_NAME if home is not None else None


def read_marker(environ=None):
    """The marker as a dict; {} in a checkout or when it is missing or
    unreadable. The hardened reader: a torn marker is restored from its one
    .bak (RUN-DURABLE-JSONFILE)."""
    path = marker_file(environ)
    if path is None:
        return {}
    from . import jsonfile  # late: `python server/al/paths.py` still runs alone
    doc = jsonfile.read_json(path, max_bytes=MARKER_MAX_BYTES, kind=dict,
                             default={}, backup=True)
    return doc if isinstance(doc, dict) else {}


def install_info(environ=None):
    """{"mode", "previous"} for /api/health and /api/version: previous is
    the marker's previous version in an install, else None."""
    mode = install_mode(environ)
    previous = None
    if mode == "installed":
        value = read_marker(environ).get("previous")
        previous = value if isinstance(value, str) and value else None
    return {"mode": mode, "previous": previous}


def data_dir(environ=None):
    """<home>/data in an install (all player state), else None."""
    home = install_home(environ)
    return home / DATA_DIR if home is not None else None


def runtime_dir():
    """Gitignored per-host state: token, consent, pid. AL_RUNTIME_DIR moves it
    (tests run a real core and supervisor against tmp, never the live dir).
    In an install: <home>/data, shared by every version folder."""
    value = (os.environ.get(RUNTIME_ENV) or "").strip().strip('"')
    if value:
        return Path(value).resolve()
    data = data_dir()
    if data is not None:
        return data
    return repo_root() / "ops" / "runtime"


def _kit_sidecar_default():
    """SIDECAR_DEFAULT from the vendored fleet kit, loaded once by file path.
    The value is only a candidate: sidecar_root() uses it only while its
    folder exists (DEP-02, the kit's own rule), so a stranger's machine
    without that folder never gets a drive path made for it."""
    global _KIT_DEFAULT
    if _KIT_DEFAULT is None:
        kit = repo_root() / "ops" / "fleet_kit" / "fleet_lanes.py"
        value = ""
        try:
            spec = importlib.util.spec_from_file_location("_al_kit_fleet_lanes", kit)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            value = getattr(mod, "SIDECAR_DEFAULT", "") or ""
        except (OSError, ImportError, SyntaxError):
            value = ""
        _KIT_DEFAULT = value
    return _KIT_DEFAULT


def sidecar_root(environ=None):
    """The AL sidecar root: AL_SIDECAR_ROOT when set, else the install home
    in an install (decision 0059), else the kit default + AL when the kit
    default folder exists (DEP-02: the kit's own rule, so a source install
    off the operator's machine never creates a folder at a drive root),
    else ops/runtime/sidecar inside the repo (no kit default on non-Windows,
    or its folder or drive is absent), so nothing ever lands elsewhere."""
    env = os.environ if environ is None else environ
    value = (env.get(SIDECAR_ENV) or "").strip().strip('"')
    if value:
        return Path(value).resolve()
    home = install_home(env)
    if home is not None:
        return home
    default = _kit_sidecar_default()
    if default:
        try:
            present = Path(default).is_dir()
        except OSError:
            present = False
        if present:
            return Path(default) / CODE
    return runtime_dir() / "sidecar"


def _installed_layout(env):
    """True when the sidecar folders take the install layout: an install
    home and no explicit AL_SIDECAR_ROOT (tests and a demo scratch keep the
    sidecar layout)."""
    if (env.get(SIDECAR_ENV) or "").strip().strip('"'):
        return False
    return install_home(env) is not None


def sidecar_dir(name, environ=None):
    """<sidecar>/<name>; in an install <home>/cache, logs, temp or build
    (Scratch and ClaudeHistory do not exist there: ValueError)."""
    if name not in SIDECAR_SUBDIRS:
        raise ValueError(f"unknown sidecar subdir: {name}")
    env = os.environ if environ is None else environ
    if _installed_layout(env):
        if name not in INSTALLED_SUBDIRS:
            raise ValueError(f"no {name} folder in an install")
        return install_home(env) / INSTALLED_SUBDIRS[name]
    return sidecar_root(env) / name


def sidecar_names(environ=None):
    """The sidecar folder names that exist in this mode."""
    env = os.environ if environ is None else environ
    if _installed_layout(env):
        return tuple(n for n in SIDECAR_SUBDIRS if n in INSTALLED_SUBDIRS)
    return SIDECAR_SUBDIRS


def worktree_dir(environ=None):
    """<sidecar>/Worktree: git worktrees made for this tree (lanes, and the
    WT-SIDECAR WorktreeCreate hook, tools/wt_sidecar_hook.py). Not in
    SIDECAR_SUBDIRS: ensure_dirs() never creates it; the hook does. None in
    an install, which has no worktrees."""
    env = os.environ if environ is None else environ
    if _installed_layout(env):
        return None
    return sidecar_root(env) / "Worktree"


def token_file():
    return runtime_dir() / "token"


def consent_file():
    return runtime_dir() / "consent.json"


def weights_file():
    """TC-EVAL editable stat weights (gitignored per-host state)."""
    return runtime_dir() / "theorycraft" / "weights.json"


TC_PINS_ENV = "AL_TC_PINS_FILE"  # TC-DRIFT trial only: a candidate pin file


def tc_pins_file(environ=None, modules=None):
    """TC-PIN: the TRACKED hash pins of the optional calc component
    (decision 0004 item 3); read by tools/tc_pin.py, never written at runtime.
    AL_TC_PINS_FILE points the bridge tests at a candidate pin file in the
    sidecar during a TC-DRIFT trial (tools/tc_drift.py). AREA-AUDIT P3-8: it
    is honoured only inside a pytest run (the trial's child and the suite);
    the core and setup never import pytest, so the env var cannot move their
    trust root."""
    env = os.environ if environ is None else environ
    mods = sys.modules if modules is None else modules
    value = (env.get(TC_PINS_ENV) or "").strip().strip('"')
    if value and "pytest" in mods:
        return Path(value)
    return repo_root() / "config" / "tc_pins.json"


_DEMO_CONFIG = None  # set only by demo.prepare (decision 0049)


def set_demo_config(path):
    """Demo mode (decision 0049): point local_config_file at the demo's
    scratch config. Called only by server/al/demo.py prepare; a demo
    process never reads or writes config/local.json. None clears it."""
    global _DEMO_CONFIG
    _DEMO_CONFIG = Path(path) if path else None


def local_config_file():
    """Per-host config (gitignored). Read only by the core. In a demo
    process, the scratch config demo.prepare set (decision 0049). In an
    install, <home>/data/local.json (decision 0059)."""
    if _DEMO_CONFIG is not None:
        return _DEMO_CONFIG
    data = data_dir()
    if data is not None:
        return data / "local.json"
    return repo_root() / "config" / "local.json"


def all_runtime_paths(environ=None):
    """Every path the app writes at runtime, by name."""
    env = os.environ if environ is None else environ
    out = {
        "repo": repo_root(),
        "runtime": runtime_dir(),
        "token": token_file(),
        "consent": consent_file(),
        "weights": weights_file(),
        "sidecar": sidecar_root(env),
    }
    home = install_home(env)
    if home is not None:  # decision 0059
        out["home"] = home
        out["marker"] = home / MARKER_NAME
        out["local_config"] = local_config_file()
    for name in sidecar_names(env):
        out[name.lower()] = sidecar_dir(name, env)
    out["core_log"] = out["logs"] / "core.log"
    out["keepalive_log"] = out["logs"] / "keepalive.log"
    out["npm_cache"] = out["cache"] / "npm"
    out["electron_cache"] = out["cache"] / "electron"
    out["ninja_cache"] = out["cache"] / "ninja"  # DATA-NINJA rates.json
    out["build_stamp"] = out["build"] / "build-stamp.json"
    # TC-PIN (decision 0004 item 3): optional calc component, opt-in setup step.
    out["pob2_cache"] = out["cache"] / "pob2"  # PoB-PoE2 archive + source checkout
    out["luajit_cache"] = out["cache"] / "luajit"  # LuaJIT source archive
    out["luajit_build"] = out["build"] / "luajit"  # LuaJIT source tree + luajit.exe
    out["tc_stamp"] = out["build"] / "tc-pins-stamp.json"
    # decision 0027: optional pinned portable C toolchain (LuaJIT build only)
    out["toolchain_cache"] = out["cache"] / "toolchain"
    # TC-LIVE: PoB GUI reference values for the live bridge test (untracked)
    out["tc_bridge_ref"] = out["cache"] / "tc_bridge" / "gui_expected.json"
    out["tc_bridge_log"] = out["logs"] / "tc-bridge.log"  # TC-BRIDGE stderr
    worktree = worktree_dir(env)  # AUDIT-HYGIENE H4; none in an install
    if worktree is not None:
        out["worktree"] = worktree
    # the overlay's Electron profile (app/main.js, AL_SIDECAR_ROOT set by run.ps1)
    out["overlay_profile"] = out["cache"] / "overlay-profile"
    return out


def ensure_dirs(environ=None):
    """Create ops/runtime and the sidecar subdirs (idempotent). In an
    install: <home>/data, cache, logs and temp (build only with the optional
    calc component, made by its own setup step)."""
    env = os.environ if environ is None else environ
    runtime_dir().mkdir(parents=True, exist_ok=True)
    installed = _installed_layout(env)
    for name in sidecar_names(env):
        if installed and name == "Build":
            continue
        sidecar_dir(name, env).mkdir(parents=True, exist_ok=True)


def load_local_config():
    """config/local.json as a dict ({} when missing or unreadable)."""
    try:
        return json.loads(local_config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main(argv=None):
    paths = {k: str(v) for k, v in all_runtime_paths().items()}
    json.dump(paths, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
