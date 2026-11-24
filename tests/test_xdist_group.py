"""TEST-XDIST-GROUP-RESTORE (decision 0060 note 2026-11-24): tests marked
with one xdist_group share one pytest-xdist worker under --dist loadgroup.

Pinned pytest 9.2.0 builds Node.nodeid from Node._id, while pytest-xdist
3.8.0 still appends the "@<group>" suffix to item._nodeid, so the suffix
never reached the scheduler and loadgroup ran as plain load (the calc-a,
calc-b and supervisor groups split over workers). tests/conftest.py
carries the suffix into the node id again.

The proof runs a child pytest of this file in the repo (the real
conftest.py, the real pinned plugins) on XDIST_WORKERS workers with
--dist loadgroup, selecting only the probe tests. Each probe records the
worker it ran on; every probe of one group must name one worker. Without
xdist the test skips (xdist is an optional dev-only plugin, decision 0002).
The probes pass at once when the record directory is not set."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REL = "tests/test_xdist_group.py"
RECORD_ENV = "AL_XDIST_GROUP_PROBE_DIR"
GROUPS = ("probe-a", "probe-b")
PER_GROUP = 6
XDIST_WORKERS = 4
SCRUB = ("PYTEST_XDIST_WORKER", "PYTEST_XDIST_WORKER_COUNT",
         "PYTEST_XDIST_TESTRUNUID", "PYTEST_ADDOPTS", "PYTEST_CURRENT_TEST",
         "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "FLEET_SUITE_SLOT")


def _record(group, index):
    out = os.environ.get(RECORD_ENV)
    if not out:
        return
    worker = os.environ.get("PYTEST_XDIST_WORKER", "none")
    (Path(out) / f"{group}-{index}.txt").write_text(worker, encoding="ascii")


@pytest.mark.xdist_group(GROUPS[0])
@pytest.mark.parametrize("index", range(PER_GROUP))
def test_probe_group_a(index):
    _record(GROUPS[0], index)


@pytest.mark.xdist_group(GROUPS[1])
@pytest.mark.parametrize("index", range(PER_GROUP))
def test_probe_group_b(index):
    _record(GROUPS[1], index)


def _xdist_present():
    try:
        return all(importlib.util.find_spec(m) is not None for m in ("xdist", "execnet"))
    except (ImportError, ValueError):
        return False


@pytest.mark.slow  # a child pytest with four worker processes
def test_grouped_tests_share_one_worker(tmp_path):
    if not _xdist_present():
        pytest.skip("pytest-xdist is not installed (optional dev-only plugin)")
    env = {k: v for k, v in os.environ.items() if k not in SCRUB}
    env[RECORD_ENV] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", REL, "-k", "probe",
         "-n", str(XDIST_WORKERS), "--dist", "loadgroup"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    seen = {}
    for group in GROUPS:
        for index in range(PER_GROUP):
            path = tmp_path / f"{group}-{index}.txt"
            assert path.is_file(), f"probe {group}[{index}] did not run"
            seen.setdefault(group, set()).add(path.read_text(encoding="ascii"))
    for group, workers in seen.items():
        assert "none" not in workers, f"{group} ran outside xdist: {workers}"
        assert len(workers) == 1, (
            f"xdist_group {group!r} split over workers {sorted(workers)}; "
            "--dist loadgroup is running as plain load")
