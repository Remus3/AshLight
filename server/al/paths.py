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
RUNTIME_ENV = "AL_RUNTIME_DIR"  # tests only: a tmp runtime dir for a test core
SIDECAR_SUBDIRS = ("Temp", "Build", "Logs", "Cache")

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
    """SIDECAR_DEFAULT from the vendored fleet kit, loaded once by file path."""
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
    """The AL sidecar root. Without a kit default (non-Windows) it falls back
    to ops/runtime/sidecar inside the repo, so nothing ever lands elsewhere."""
    env = os.environ if environ is None else environ
    value = (env.get(SIDECAR_ENV) or "").strip().strip('"')
    if value:
        return Path(value).resolve()
    default = _kit_sidecar_default()
    if default:
        return Path(default) / CODE
    return runtime_dir() / "sidecar"


def sidecar_dir(name, environ=None):
    if name not in SIDECAR_SUBDIRS:
        raise ValueError(f"unknown sidecar subdir: {name}")
    return sidecar_root(environ) / name


def token_file():
    return runtime_dir() / "token"


def consent_file():
    return runtime_dir() / "consent.json"


def weights_file():
    """TC-EVAL editable stat weights (gitignored per-host state)."""
    return runtime_dir() / "theorycraft" / "weights.json"


def local_config_file():
    """Per-host config (gitignored). Read only by the core."""
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
    out["build_stamp"] = out["build"] / "build-stamp.json"
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
