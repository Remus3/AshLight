"""Sidecar rule (CLAUDE.md "Sidecar"): every runtime path resolves inside the
repo or inside the AL sidecar root, and no tracked app file spells a drive
path."""

import importlib.util
import re
from pathlib import Path

from server.al import paths

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("server", "web", "app", "scripts")
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
    sidecar = Path(default) / "AL" if default else ROOT / "ops" / "runtime" / "sidecar"
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
