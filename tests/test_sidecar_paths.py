"""Sidecar rule (CLAUDE.md "Sidecar"): every runtime path resolves inside the
repo or inside the AL sidecar root, and no tracked app file spells a drive
path."""

import importlib.util
import os
import re
from pathlib import Path

from server.al import paths

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("server", "web", "app", "scripts", "tools")  # tools: AUDIT-HYGIENE H5
SKIP_DIRS = {"node_modules", "__pycache__", "out", "dist"}
TEXT = {".py", ".js", ".html", ".css", ".json", ".ps1", ".md", ".txt", ".cmd", ".vbs"}


def _kit_default():
    spec = importlib.util.spec_from_file_location(
        "_t_fleet_lanes", ROOT / "ops" / "fleet_kit" / "fleet_lanes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SIDECAR_DEFAULT


def _inside(p, root):
    try:
        Path(p).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def test_default_paths_inside_repo_or_al_sidecar(monkeypatch):
    monkeypatch.delenv(paths.SIDECAR_ENV, raising=False)
    default = _kit_default()
    # DEP-02: the kit default counts only while its folder exists
    if default and Path(default).is_dir():
        sidecar = Path(default) / "AL"
    else:
        sidecar = ROOT / "ops" / "runtime" / "sidecar"
    assert paths.sidecar_root() == sidecar
    for name, p in paths.all_runtime_paths().items():
        assert _inside(p, ROOT) or _inside(p, sidecar), (name, str(p))
    for sub in paths.SIDECAR_SUBDIRS:
        assert paths.sidecar_dir(sub) == sidecar / sub


def test_env_override_points_everything_at_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "AL"))
    for name, p in paths.all_runtime_paths().items():
        assert _inside(p, ROOT) or _inside(p, tmp_path / "AL"), (name, str(p))
    paths.ensure_dirs()
    for sub in paths.SIDECAR_SUBDIRS:
        assert (tmp_path / "AL" / sub).is_dir()


def _missing_drive_dir(tmp_path):
    """A folder on a drive letter that does not exist here (Windows), or
    a missing folder under tmp (elsewhere): a stranger's machine without
    the kit's sidecar folder."""
    if os.name == "nt":
        for letter in "QRSTUVWXYZJKLMNOP":
            drive = letter + ":" + os.sep
            if not Path(drive).exists():
                return str(Path(drive) / "Sidecars")
    return str(tmp_path / "no-such-drive" / "Sidecars")


def test_kit_default_on_a_missing_drive_falls_back_inside_the_tree(tmp_path, monkeypatch):
    """DEP-02 (F-019): with the kit default pointed at a missing drive and
    AL_SIDECAR_ROOT unset, sidecar_root() lies inside the tree (the kit's own
    rule: its default counts only when the folder exists) and ensure_dirs()
    passes."""
    missing = _missing_drive_dir(tmp_path)
    assert not Path(missing).exists()
    monkeypatch.delenv(paths.SIDECAR_ENV, raising=False)
    monkeypatch.delenv(paths.RUNTIME_ENV, raising=False)
    monkeypatch.setattr(paths, "_KIT_DEFAULT", missing)
    assert paths._kit_sidecar_default() == missing
    assert paths.sidecar_root() == ROOT / "ops" / "runtime" / "sidecar"
    assert _inside(paths.sidecar_root(), ROOT)
    for name, p in paths.all_runtime_paths().items():
        assert _inside(p, ROOT), (name, str(p))
    # ensure_dirs() against a scratch runtime dir (never the tree's own
    # ops/runtime): the same fallback, created without an error.
    monkeypatch.setenv(paths.RUNTIME_ENV, str(tmp_path / "runtime"))
    assert paths.sidecar_root() == (tmp_path / "runtime" / "sidecar").resolve()
    paths.ensure_dirs()
    for sub in paths.SIDECAR_SUBDIRS:
        assert (tmp_path / "runtime" / "sidecar" / sub).is_dir()
    assert not Path(missing).exists()


def test_kit_default_counts_when_its_folder_exists(tmp_path, monkeypatch):
    monkeypatch.delenv(paths.SIDECAR_ENV, raising=False)
    monkeypatch.setattr(paths, "_KIT_DEFAULT", str(tmp_path))
    assert paths.sidecar_root() == tmp_path / "AL"


def test_runtime_state_is_gitignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="ascii").splitlines()
    assert "ops/runtime/" in ignore
    assert paths.runtime_dir() == ROOT / "ops" / "runtime"


def _files():
    for top in SCANNED:
        base = ROOT / top
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in TEXT and not (
                    SKIP_DIRS & set(p.relative_to(ROOT).parts)):
                yield p


def test_no_literal_drive_path_in_app_files():
    pat = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:(\\\\|\\|/)(?!/)")
    drive = "E" + ":"  # built from parts so this file spells no drive path
    bad = []
    for p in _files():
        text = p.read_text(encoding="utf-8", errors="replace")
        if drive + "\\" in text or drive + "/" in text:
            bad.append(f"{p.relative_to(ROOT)}: E: drive path")
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                bad.append(f"{p.relative_to(ROOT)}:{i}")
    assert not bad, bad


TC_PATHS = {"pob2_cache": ("Cache", "pob2"), "luajit_cache": ("Cache", "luajit"),
            "luajit_build": ("Build", "luajit"), "tc_stamp": ("Build", "tc-pins-stamp.json")}


def test_tc_pin_paths_live_in_the_sidecar(tmp_path, monkeypatch):
    """TC-PIN: the calc component's cache, build and stamp paths resolve under
    the AL sidecar (Cache / Build), never in the repo or elsewhere."""
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "AL"))
    got = paths.all_runtime_paths()
    for name, (sub, leaf) in TC_PATHS.items():
        assert got[name] == (tmp_path / "AL" / sub / leaf).resolve(), name
        assert _inside(got[name], tmp_path / "AL"), name
    # the pin file itself is tracked config inside the repo, not runtime state
    assert paths.tc_pins_file() == ROOT / "config" / "tc_pins.json"
    assert paths.tc_pins_file().is_file()


def test_tc_pin_layout_stays_in_the_sidecar(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import tc_pin
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "AL"))
    lay = tc_pin.layout(tc_pin.load_pins())
    for key, p in lay.items():
        assert _inside(p, tmp_path / "AL"), (key, str(p))
