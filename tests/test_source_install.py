"""DEP-02 (F-019): the source install works for a stranger.

- The Node floor named in scripts/setup.ps1, scripts/run.ps1 and the README
  quick start equals the pinned Electron's engines.node floor in
  app/package-lock.json (one number, no stale 20).
- The README quick start is setup.ps1 then run.ps1: build.ps1 (the dev
  gate) lives in CONTRIBUTING.md instead.
- requirements-dev.txt pins pytest and every other entry with == and
  --hash lines, so `pip install --require-hashes` takes it as is.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "setup.ps1"
RUN = ROOT / "scripts" / "run.ps1"
README = ROOT / "README.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
REQS = ROOT / "requirements-dev.txt"
LOCK = ROOT / "app" / "package-lock.json"


def _electron_node_floor():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    engines = lock["packages"]["node_modules/electron"]["engines"]["node"]
    m = re.fullmatch(r">=\s*(\d+\.\d+\.\d+)", engines.strip())
    assert m, f"electron engines.node is no plain floor: {engines!r}"
    return m.group(1)


def _quick_start():
    text = README.read_text(encoding="ascii")
    start = text.index("## Quick start (Windows)")
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


def test_electron_floor_is_the_pinned_value():
    assert _electron_node_floor() == "22.12.0"


def test_setup_checks_the_electron_node_floor():
    floor = _electron_node_floor()
    text = SETUP.read_text(encoding="ascii")
    assert f"$nodeFloor = '{floor}'" in text
    assert "[version]$nodeNum -lt [version]$nodeFloor" in text
    assert f"Node >= {floor}" in text
    assert "'20.0'" not in text and "older than 20" not in text
    assert "Node >= 20," not in text


def test_run_names_the_electron_node_floor():
    floor = _electron_node_floor()
    text = RUN.read_text(encoding="ascii")
    assert f"Node {floor} or newer" in text
    assert "Node 20+" not in text


def test_readme_quick_start_names_the_floor_and_two_calls():
    floor = _electron_node_floor()
    qs = _quick_start()
    assert f"Node.js {floor} or newer" in qs
    assert "Node.js 20" not in qs
    calls = re.findall(r"^powershell .*-File scripts\\(\w+)\.ps1", qs, re.M)
    assert calls[:2] == ["setup", "run"], calls
    assert "build.ps1" not in qs


def test_build_step_moves_to_contributing():
    text = CONTRIBUTING.read_text(encoding="ascii")
    assert "scripts\\build.ps1" in text
    assert "requirements-dev.txt" in text


def _requirements():
    """(name, version, hashes) per entry, joining backslash continuations."""
    entries, cur = [], ""
    for line in REQS.read_text(encoding="ascii").splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        cur += " " + line.rstrip("\\").strip()
        if not line.endswith("\\"):
            entries.append(cur)
            cur = ""
    assert not cur, "dangling line continuation"
    out = []
    for entry in entries:
        parts = entry.split()
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", parts[0])
        assert m, f"not an exact pin: {entry.strip()!r}"
        hashes = [p for p in parts[1:] if p.startswith("--hash=")]
        assert len(hashes) == len(parts) - 1, f"unexpected option: {entry.strip()!r}"
        out.append((m.group(1).lower(), m.group(2), hashes))
    return out


def test_requirements_dev_pins_pytest_with_hashes():
    reqs = _requirements()
    names = [name for name, _, _ in reqs]
    assert "pytest" in names
    assert len(names) == len(set(names))
    for name, _, hashes in reqs:
        assert hashes, f"{name} has no --hash line"
        for h in hashes:
            assert re.fullmatch(r"--hash=sha256:[0-9a-f]{64}", h), (name, h)
    # pytest's runtime dependencies on Windows are all listed
    for dep in ("iniconfig", "packaging", "pluggy", "pygments", "colorama"):
        assert dep in names, dep
