"""Shared helpers for the live theorycraft tests (MATH-E2E-LIVE, MATH-PERF,
MATH-POB-DRIFT-GUARD) and the test port lease (TEST-PORT-LEASE). Stdlib
only.

The live tests run only where the optional calc component (setup.ps1
-TcCalc) and the PoB GUI reference (sidecar Cache\\tc_bridge, decision 0027)
exist; everywhere else they skip with the reason.
"""

import ctypes
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from server.al import paths, ports
from server.al.theorycraft import bridge


def reference():
    """(ref dict, build xml) of the recorded PoB GUI reference, or None."""
    ref_path = paths.all_runtime_paths()["tc_bridge_ref"]
    if not ref_path.is_file():
        return None
    ref = json.loads(ref_path.read_text(encoding="ascii"))
    xml_path = ref_path.parent / ref["build_xml"]
    if not xml_path.is_file():
        return None
    return ref, xml_path.read_text(encoding="utf-8")


LIVE = pytest.mark.skipif(not bridge.available(),
                          reason="optional calc component absent (setup.ps1 -TcCalc)")
LIVE_REF = pytest.mark.skipif(not bridge.available() or reference() is None,
                              reason="calc component or PoB GUI reference absent "
                              "(sidecar Cache\\tc_bridge\\gui_expected.json)")


# TEST-PORT-LEASE (finding F-022): a test that binds a real port leases it.
# A lease = an OS lock on <sidecar Temp>/port-leases/<port>.lock held for the
# test's life AND a 127.0.0.1 bind probe that succeeds, so two runs of this
# tree (two worktrees, or xdist workers) never get the same port. The OS drops
# the lock when the holder dies, so a stale lock file is harmless.
LEASE_DIRNAME = "port-leases"
LEASE_WAIT_S = 60.0  # more than 8 leases at once: poll, then skip as before
LEASE_POLL_S = 0.25
_HELD = {}  # port -> open lock file of this process
_HELD_GUARD = threading.Lock()


def lease_lock_dir(environ=None):
    """<sidecar Temp>/port-leases, from server.al.paths (the one resolver)."""
    return paths.sidecar_dir("Temp", environ) / LEASE_DIRNAME


# Resolved once at import (collection time), so a test that later points
# AL_SIDECAR_ROOT at its tmp dir still leases from the shared folder.
LEASE_DIR = lease_lock_dir()


def _never_leased():
    """Every named port of the block that is not a test lease port: the
    core's 8960, AL_DEV_PORT, the demo / self-test block and the OAuth
    redirect ports (getattr: works before or after a constant lands)."""
    out = {ports.AL_PORT}
    dev = getattr(ports, "AL_DEV_PORT", None)
    if dev is not None:
        out.add(int(dev))
    for name in ("DEMO_BLOCK", "SELFTEST_PORTS"):
        span = getattr(ports, name, None)
        if span:
            out.update(range(int(span[0]), int(span[1]) + 1))
    out.update(int(x) for x in getattr(ports, "OAUTH_REDIRECT_PORTS", ()) or ())
    return out


def lease_candidates():
    """The ports a test may lease: ports.TEST_LEASE_PORTS (8962-8969) minus
    every other named port, ascending."""
    lo, hi = ports.TEST_LEASE_PORTS
    banned = _never_leased()
    return [p for p in range(int(lo), int(hi) + 1) if p not in banned]


def _lock(path):
    """The open, locked lock file, or None when another holder has it."""
    fh = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def _unlock(fh):
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    fh.close()


def _bind_ok(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((ports.LOOPBACK, port))
    except OSError:
        return False
    finally:
        s.close()
    return True


def _try_lease(port, lock_dir):
    with _HELD_GUARD:
        if port in _HELD:
            return False
        fh = _lock(lock_dir / f"{port}.lock")
        if fh is None:
            return False
        if not _bind_ok(port):  # a bind failure always counts as taken
            _unlock(fh)
            return False
        _HELD[port] = fh
        return True


def _release(port):
    with _HELD_GUARD:
        fh = _HELD.pop(port, None)
    if fh is not None:
        _unlock(fh)


def held_leases():
    """The ports this process holds a lease on (sorted)."""
    with _HELD_GUARD:
        return sorted(_HELD)


def lease_port(candidates=None, lock_dir=None, wait_s=LEASE_WAIT_S):
    """(port, release): a port of ports.TEST_LEASE_PORTS no other lease
    holds and 127.0.0.1 can bind now. release() is idempotent; call it when
    the test is done with the port (the leased_port fixture does). All
    taken: poll until wait_s, then pytest.skip."""
    cands = lease_candidates() if candidates is None else [int(p) for p in candidates]
    banned = _never_leased()
    cands = [p for p in cands if p not in banned]
    lock_dir = Path(lock_dir) if lock_dir is not None else LEASE_DIR
    lock_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, float(wait_s))
    while True:
        for port in cands:
            if _try_lease(port, lock_dir):
                return port, (lambda p=port: _release(p))
        if time.monotonic() >= deadline:
            break
        time.sleep(LEASE_POLL_S)
    pytest.skip(f"no free test port in {ports.TEST_LEASE_PORTS[0]}-"
                f"{ports.TEST_LEASE_PORTS[1]} (all leased or bound)")


@pytest.fixture
def leased_port():
    """A function-scoped port lease (lease_port), released at teardown.
    A test module uses it by importing it from tc_live_util."""
    port, release = lease_port()
    try:
        yield port
    finally:
        release()


def free_test_port():
    """Compatibility for callers outside TEST-PORT-LEASE (tests/play_states.py,
    whose recipe audit forbids any file opened outside its tmp root): a port
    of the lease block that this process does not hold and 127.0.0.1 can bind
    now, by a bind probe only (no lock file, so no cross-run guard). New
    callers use lease_port() or the leased_port fixture."""
    mine = set(held_leases())
    for port in lease_candidates():
        if port not in mine and _bind_ok(port):
            return port
    pytest.skip(f"no free test port in {ports.TEST_LEASE_PORTS[0]}-"
                f"{ports.TEST_LEASE_PORTS[1]}")


class _PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def process_memory_mb(pid):
    """{"ws", "peak_ws", "private"} in MB for a process (Windows only)."""
    if sys.platform != "win32":
        pytest.skip("process memory read is Windows-only")
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    handle = k32.OpenProcess(0x1000 | 0x0010, False, int(pid))  # QUERY_LIMITED | VM_READ
    if not handle:
        raise OSError(f"OpenProcess failed for pid {pid}")
    try:
        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        if not psapi.GetProcessMemoryInfo(ctypes.c_void_p(handle), ctypes.byref(pmc), pmc.cb):
            raise OSError("GetProcessMemoryInfo failed")
    finally:
        k32.CloseHandle(ctypes.c_void_p(handle))
    mb = float(1 << 20)
    return {"ws": pmc.WorkingSetSize / mb, "peak_ws": pmc.PeakWorkingSetSize / mb,
            "private": pmc.PagefileUsage / mb}


# MATH-PERF budgets (decision 0028). Generous ceilings over the values
# measured on the reference build (pobb.in Nqt6FK5lIc6F, level 90) on
# 2026-11-17; a breach means the bridge or PoB got much slower or heavier.
BUDGET = {
    "cold_start_s": 30.0,       # luajit + PoB start to the ready frame (1.3 s)
    "load_build_s": 5.0,        # load_build of the real build (0.38 s)
    "reload_s": 5.0,            # load_build again (median 0.3 s)
    "set_item_s": 2.0,          # set_item + outputs, warm (0.09 s)
    "first_press_s": 60.0,      # first item check incl. bridge start (~12 s)
    "press_s": 30.0,            # an item check, bridge warm (3.4 to 5 s)
    "repeat_press_s": 10.0,     # the same item again, probes cached
    "fallback_press_s": 30.0,   # a press while the calc is being killed
    "peak_ws_mb": 768.0,        # luajit peak working set, 30 reloads (~510 MB)
}


def keep_warm(core, stops=None):
    """A test core's calc provider records its stop instead of shutting the
    session's warm bridge down (TEST-FULLSTACK-CALC-WARM)."""
    stops = [] if stops is None else stops
    core.tc_provider._stop = lambda: stops.append(True)
    return stops
