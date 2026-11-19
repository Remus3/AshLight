"""The ONE runtime path resolver for AshLight.

State lives in the repo's gitignored ops/runtime/. Everything else the app
makes outside its tracked files (temp, build stamps, logs, caches) lives under
the AL sidecar root:

- env AL_SIDECAR_ROOT when set and non-empty (tests point it at tmp), else
- the fleet kit default (ops/fleet_kit/fleet_lanes.py SIDECAR_DEFAULT) + "AL".

The drive path is never spelled here; it comes from the vendored kit.
Run `python -m server.al.paths` to print every path as JSON (the scripts use it).
"""

import importlib.util
import json
import os
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

_KIT_DEFAULT = None


def repo_root():
    """The repository root (two levels above this package)."""
    return Path(__file__).resolve().parents[2]


def runtime_dir():
    """Gitignored per-host state: token, consent, pid. AL_RUNTIME_DIR moves it
    (tests run a real core and supervisor against tmp, never the live dir)."""
    value = (os.environ.get(RUNTIME_ENV) or "").strip().strip('"')
    if value:
        return Path(value).resolve()
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
    """The AL sidecar root: AL_SIDECAR_ROOT when set, else the kit default +
    AL when the kit default folder exists (DEP-02: the kit's own rule, so a
    source install off the operator's machine never creates a folder at a
    drive root), else ops/runtime/sidecar inside the repo (no kit default on
    non-Windows, or its folder or drive is absent), so nothing ever lands
    elsewhere."""
    env = os.environ if environ is None else environ
    value = (env.get(SIDECAR_ENV) or "").strip().strip('"')
    if value:
        return Path(value).resolve()
    default = _kit_sidecar_default()
    if default:
        try:
            present = Path(default).is_dir()
        except OSError:
            present = False
        if present:
            return Path(default) / CODE
    return runtime_dir() / "sidecar"


def sidecar_dir(name, environ=None):
    if name not in SIDECAR_SUBDIRS:
        raise ValueError(f"unknown sidecar subdir: {name}")
    return sidecar_root(environ) / name


def worktree_dir(environ=None):
    """<sidecar>/Worktree: git worktrees made for this tree (lanes, and the
    WT-SIDECAR WorktreeCreate hook, tools/wt_sidecar_hook.py). Not in
    SIDECAR_SUBDIRS: ensure_dirs() never creates it; the hook does."""
    return sidecar_root(environ) / "Worktree"


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
    process, the scratch config demo.prepare set (decision 0049)."""
    if _DEMO_CONFIG is not None:
        return _DEMO_CONFIG
    return repo_root() / "config" / "local.json"


def all_runtime_paths(environ=None):
    """Every path the app writes at runtime, by name."""
    out = {
        "repo": repo_root(),
        "runtime": runtime_dir(),
        "token": token_file(),
        "consent": consent_file(),
        "weights": weights_file(),
        "sidecar": sidecar_root(environ),
    }
    for name in SIDECAR_SUBDIRS:
        out[name.lower()] = sidecar_dir(name, environ)
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
    out["worktree"] = worktree_dir(environ)  # AUDIT-HYGIENE H4
    # the overlay's Electron profile (app/main.js, AL_SIDECAR_ROOT set by run.ps1)
    out["overlay_profile"] = out["cache"] / "overlay-profile"
    return out


def ensure_dirs(environ=None):
    """Create ops/runtime and the sidecar subdirs (idempotent)."""
    runtime_dir().mkdir(parents=True, exist_ok=True)
    for name in SIDECAR_SUBDIRS:
        sidecar_dir(name, environ).mkdir(parents=True, exist_ok=True)


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
