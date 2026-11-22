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
import re
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from server.al import paths, ports
from server.al.theorycraft import bridge


# LOOP-DRIFT-REF (decision 0025 / 0028 amendment 2026-11-18): the PoB GUI
# reference is keyed by tag. A folder may hold gui_expected.json and any
# number of gui_expected-<tag>.json; each names its PoB tag in "pob". The
# tag under test is the pin's (AL_TC_PINS_FILE during a drift trial; a
# rehearsal candidate is "ref-<12 hex of its commit>"). The same tag
# compares the recorded numbers within 0.1 percent; another tag reports
# per-key deltas and passes only with a session's written acceptance in the
# reference: "accepted": {"<tag>": "<YYYY-MM-DD> <why>"}.
REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_REF_NAME = "gui_expected.json"
GUI_REF_GLOB = "gui_expected-*.json"
_TAG_PARTS = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_ACCEPT = re.compile(r"^\d{4}-\d{2}-\d{2} \S")


def reference_dirs():
    """The folders a GUI reference may live in, in preference order: the
    tracked fixtures (owner-allowed builds only), the gitignored runtime
    folder, the AL sidecar Cache (paths key tc_bridge_ref)."""
    return [REPO_ROOT / "tests" / "fixtures" / "tc_bridge",
            REPO_ROOT / "ops" / "runtime" / "tc_bridge",
            paths.all_runtime_paths()["tc_bridge_ref"].parent]


def tested_tag(pins_path=None):
    """The PoB tag the live tests run against: the pin file's pob2 tag, or
    ref-<12 hex> for a rehearsal candidate; None when unreadable."""
    try:
        doc = json.loads(Path(pins_path or paths.tc_pins_file()).read_text(encoding="ascii"))
        pob = doc["pob2"]
        if pob.get("rehearsal_ref"):
            return f"ref-{pob['commit'][:12]}"
        return pob["tag"] if isinstance(pob["tag"], str) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def gui_references(dirs=None):
    """[(path, ref)] of every readable GUI reference (gui_expected.json, then
    gui_expected-*.json by name, folder by folder) whose "pob" is a string,
    "outputs" an object and build_xml a file beside it."""
    out = []
    for d in reference_dirs() if dirs is None else dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for p in [d / GUI_REF_NAME, *sorted(d.glob(GUI_REF_GLOB))]:
            if not p.is_file():
                continue
            try:
                ref = json.loads(p.read_text(encoding="ascii"))
            except (OSError, ValueError):
                continue
            if (isinstance(ref, dict) and isinstance(ref.get("pob"), str)
                    and isinstance(ref.get("outputs"), dict)
                    and isinstance(ref.get("build_xml"), str)
                    and (p.parent / ref["build_xml"]).is_file()):
                out.append((p, ref))
    return out


def _tag_key(tag):
    m = _TAG_PARTS.match(tag or "")
    return tuple(int(x) for x in m.groups()) if m else (-1, -1, -1)


def pick_reference(tag, refs):
    """("same" | "other", path, ref) for the tag under test, or None. The
    first reference recorded for `tag` wins; else the newest other tag."""
    if not refs:
        return None
    for p, ref in refs:
        if tag is not None and ref["pob"] == tag:
            return "same", p, ref
    p, ref = max(refs, key=lambda pr: _tag_key(pr[1]["pob"]))
    return "other", p, ref


def reference_deltas(want, got):
    """{key: {"want", "got", "rel"}} per recorded output; rel is the
    relative delta (None when the key is missing or not a number)."""
    out = {}
    for key in sorted(want):
        w, g = want[key], got.get(key)
        rel = None
        if isinstance(w, (int, float)) and isinstance(g, (int, float)):
            rel = 0.0 if w == g else abs(g - w) / max(abs(w), 1e-12)
        out[key] = {"want": w, "got": g, "rel": rel}
    return out


def delta_lines(deltas):
    """One readable line per key, e.g. 'Life: 1234 -> 1240 (+0.486%)'."""
    lines = []
    for key, d in deltas.items():
        if d["rel"] is None:
            lines.append(f"{key}: {d['want']} -> {d['got']} (not comparable)")
        else:
            sign = "-" if (d["got"] or 0) < (d["want"] or 0) else "+"
            lines.append(f"{key}: {d['want']} -> {d['got']} ({sign}{d['rel'] * 100:.3f}%)")
    return lines


def accepted_for(ref, tag):
    """The session's written acceptance of `ref` for another `tag` (a
    "<YYYY-MM-DD> <why>" string under "accepted"), or None."""
    acc = ref.get("accepted") if isinstance(ref, dict) else None
    text = acc.get(tag) if isinstance(acc, dict) and tag else None
    return text if isinstance(text, str) and _ACCEPT.match(text) else None


def reference():
    """(ref dict, build xml) of the recorded PoB GUI reference in the sidecar
    Cache, chosen by the tag under test (another tag when none is recorded
    for it), or None."""
    pick = pick_reference(tested_tag(),
                          gui_references([paths.all_runtime_paths()["tc_bridge_ref"].parent]))
    if pick is None:
        return None
    _mode, ref_path, ref = pick
    return ref, (ref_path.parent / ref["build_xml"]).read_text(encoding="utf-8")


LIVE = pytest.mark.skipif(not bridge.available(),
                          reason="optional calc component absent (setup.ps1 -TcCalc)")
LIVE_REF = pytest.mark.skipif(not bridge.available() or reference() is None,
                              reason="calc component or PoB GUI reference absent "
                              "(sidecar Cache\\tc_bridge\\gui_expected*.json)")


# TEST-MARKS (research 0049 R4, R9): every test that starts the live calc
# carries the 'calc' mark and one xdist group of CALC_GROUPS, so a subset or
# the parallel suite can select or group it. A module lists CALC_MARKS in its
# pytestmark; a single test takes the LIVE_CALC decorator. CALC_FILES are the
# test files that hold such a test (tests/test_marks.py checks the -m calc
# selection against it).
# TEST-CALC-GROUP-SPLIT (research 0063 section 5): two groups, so two workers
# each own a session warm bridge (conftest's warm_bridge is session-scoped,
# so every worker builds its own). CALC_MARKS and a bare @LIVE_CALC use
# calc-a; @LIVE_CALC(group=CALC_GROUP_B) puts a test in calc-b. A test holds
# exactly one group (xdist joins several group marks into a third group).
CALC_GROUP_A = "calc-a"
CALC_GROUP_B = "calc-b"
CALC_GROUPS = (CALC_GROUP_A, CALC_GROUP_B)
CALC_MARKS = (pytest.mark.calc, pytest.mark.xdist_group(CALC_GROUP_A))
CALC_FILES = (
    "tests/test_audit_pass7.py",
    "tests/test_fullstack.py",
    "tests/test_math_e2e_live.py",
    "tests/test_math_perf.py",
    "tests/test_math_skill_split.py",
    "tests/test_math_weapon_type.py",
    "tests/test_tc_bridge.py",
    "tests/test_tc_pob_drift_guard.py",
)


def LIVE_CALC(obj=None, *, group=CALC_GROUP_A):  # noqa: N802 (a mark decorator, named like LIVE)
    """Apply the calc mark and one CALC_GROUPS xdist group to one test
    function: @LIVE_CALC (calc-a) or @LIVE_CALC(group=CALC_GROUP_B)."""
    if group not in CALC_GROUPS:
        raise ValueError(f"unknown calc group {group!r}")
    if obj is None:
        return lambda fn: LIVE_CALC(fn, group=group)
    for mark in (pytest.mark.calc, pytest.mark.xdist_group(group)):
        obj = mark(obj)
    return obj


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


# MATH-PERF budgets (decision 0028). Ceilings over the values measured on
# the reference build (pobb.in Nqt6FK5lIc6F, level 90) on 2026-11-17; a
# breach means the bridge or PoB got much slower or heavier.
# RUN-BUDGET-TESTS-LIVE (research 0048 B16; decision 0024 R7 amendment
# 2026-11-18): the time ceilings are about 2.5 times those values (the
# first ones were 10 to 25 times), so a twofold regression is caught.
BUDGET = {
    "cold_start_s": 5.0,        # luajit + PoB start to the ready frame (1.3 s)
    "load_build_s": 1.5,        # load_build of the real build (0.38 s)
    "reload_s": 1.0,            # load_build again (median 0.3 s)
    "set_item_s": 0.5,          # set_item + outputs, warm (0.09 s)
    "first_press_s": 30.0,      # all probes of a first item check incl. bridge start (12.4 s)
    "press_s": 12.0,            # all probes of an item check, bridge warm (3.6 to 5.5 s)
    "repeat_press_s": 4.0,      # the same item again, probes cached (1.3 s)
    "fallback_press_s": 30.0,   # a press while the calc is being killed
    "peak_ws_mb": 768.0,        # luajit peak working set, 30 reloads (~510 MB; B17)
}


def keep_warm(core, stops=None):
    """A test core's calc provider records its stop instead of shutting the
    session's warm bridge down (TEST-FULLSTACK-CALC-WARM)."""
    stops = [] if stops is None else stops
    core.tc_provider._stop = lambda: stops.append(True)
    return stops
