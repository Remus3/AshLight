"""Shared helpers for the live theorycraft tests (MATH-E2E-LIVE, MATH-PERF,
MATH-POB-DRIFT-GUARD). Stdlib only.

The live tests run only where the optional calc component (setup.ps1
-TcCalc) and the PoB GUI reference (sidecar Cache\\tc_bridge, decision 0027)
exist; everywhere else they skip with the reason.
"""

import ctypes
import json
import socket
import sys

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


def free_test_port():
    """A free port inside AshLight's block, above the core's own 8960
    (a running AshLight is never touched)."""
    for port in range(ports.AL_PORT + 1, ports.PORT_BLOCK[1] + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((ports.LOOPBACK, port))
        except OSError:
            continue
        finally:
            s.close()
        return port
    pytest.skip("no free port in 8961-8979")


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
