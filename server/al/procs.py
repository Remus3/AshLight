"""OPS-STOP / OPS-RUN-IDEMP: which AshLight processes are live, and stopping them.

    python -m server.al.procs status            JSON: core, supervisor, overlay
    python -m server.al.procs plan [--no-overlay] [--overlay-missing]
                                                JSON: components run.ps1 must start
    python -m server.al.procs record-overlay PID
                                                write <runtime>/overlay.pid
    python -m server.al.procs stop [--wait S] [--asked-at FILETIME]
                                                stop supervisor and overlay
                                                (after stop.ps1 stopped the core)

RUN-STOP-RACE (F-152): stop ends only overlay processes created before stop
was asked (--asked-at, else the fresh stop.request mtime, else now); a
younger one (a racing start) is left running, reported as overlay_younger
and not counted as left. A damaged pid or creation-time record reads as 0.

RUN-SECOND-LINE-PY (decision 0005 amendment 2026-11-18): supervisor_command
builds the one supervisor start (the one command builder, windowless) and
start_supervisor starts it hidden and detached; the core uses it when no
supervisor is live (plug/secondline.py). It starts only AshLight's own
python supervisor, never Electron (decision 0041).

A process counts as AshLight's only when it is proven ours (decision 0010):

- core: the pid in <runtime>/core.alive, image python*, and its recorded
  creation time (when recorded) still matches - a reused pid is not ours;
- supervisor: the pid in <runtime>/keepalive.json, image python*, creation
  time matching; "live" is read from the supervisor's single-instance lock
  (keepalive.lock), the one authoritative signal;
- overlay: the pid in <runtime>/overlay.pid (image electron.exe, creation
  time matching) plus every electron.exe whose FULL image path lies inside
  this checkout's app/node_modules/electron/dist - that path is ours alone,
  so no unrelated Electron app and never the game client is matched. The
  directory scan runs only for the default runtime or when AL_ELECTRON_DIR
  names the directory (tests), so a tmp-runtime test can never reach a live
  overlay.

Nothing here touches the game process (ToS floor): it never opens a process
that is not one of the above, and it only ever terminates proven-ours pids.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import keepalive as ka
from . import jsonfile, paths

OVERLAY_PID_FILE = "overlay.pid"
ELECTRON_DIR_ENV = "AL_ELECTRON_DIR"  # tests only: a tmp electron dist dir
COMPONENTS = ("core", "supervisor", "overlay")
PYTHON_PREFIX = "python"
ELECTRON_IMAGE = "electron.exe"
_TH32CS_SNAPPROCESS = 0x2


def _read_json(path):
    return jsonfile.read_json(path, encoding="ascii", kind=dict)


def electron_dir():
    """The electron dist dir whose processes are ours, or None when the scan
    is off (a tmp runtime without an explicit AL_ELECTRON_DIR, or an install
    whose marker names no usable electron folder). In an install (decision
    0059): <home>/runtime/<marker "electron">, the pinned runtime folder."""
    value = (os.environ.get(ELECTRON_DIR_ENV) or "").strip().strip('"')
    if value:
        return Path(value).resolve()
    if (os.environ.get(paths.RUNTIME_ENV) or "").strip():
        return None
    # the one Electron resolver (DEP-06); the marker name check lives there
    exe = paths.electron_exe()
    return exe.parent if exe is not None else None


def _as_int(value):
    """A recorded pid or creation time as an int; a value that is not a
    whole number (a damaged record: text, a list, a float) reads as 0, so
    a bad record names no process (RUN-STOP-RACE, F-152)."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _same_created(pid, created):
    created = _as_int(created)
    return created == 0 or ka.process_created(pid) == created


def is_ours(pid, image_prefix, created=0):
    """pid is alive, its image starts with image_prefix (case-insensitive)
    and, when a creation time was recorded, it is the same process."""
    pid = _as_int(pid)
    if pid <= 0 or not ka.pid_alive(pid):
        return False
    if not ka.image_name(pid).lower().startswith(image_prefix):
        return False
    return _same_created(pid, created)


def list_processes():
    """[(pid, exe base name)] for every process (Windows; [] elsewhere)."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    k.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    k.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    snap = k.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return []
    out = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            out.append((int(entry.th32ProcessID), entry.szExeFile))
            ok = k.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k.CloseHandle(snap)
    return out


def _inside(path, folder):
    try:
        return os.path.normcase(os.path.commonpath([os.path.abspath(path),
                                                    os.path.abspath(folder)])) \
            == os.path.normcase(os.path.abspath(folder))
    except ValueError:
        return False


def overlay_main_pid(runtime):
    """The recorded overlay main process (<runtime>/overlay.pid) when it is
    provably ours, else 0. OPS-OVL-PID: Electron's children (GPU, network
    utility, renderer) also live in the dist dir and may have lower pids, so
    only this record names the main process."""
    rec = _read_json(Path(runtime) / OVERLAY_PID_FILE) or {}
    pid = _as_int(rec.get("pid"))
    return pid if pid > 0 and is_ours(pid, ELECTRON_IMAGE, rec.get("created")) else 0


def overlay_pids(runtime, edir=None, processes=None):
    """Sorted pids of our overlay: the recorded pid plus the dir scan."""
    found = set()
    pid = overlay_main_pid(runtime)
    if pid:
        found.add(pid)
    edir = electron_dir() if edir is None else edir
    if edir is not None:
        procs = list_processes() if processes is None else processes
        for p, name in procs:
            if name.lower() != ELECTRON_IMAGE:
                continue
            full = ka.image_path(p)
            if full and _inside(full, edir):
                found.add(p)
    return sorted(found)


def supervisor_locked(runtime):
    """True while a supervisor holds keepalive.lock in runtime."""
    runtime = Path(runtime)
    if not (runtime / ka.LOCK_FILE).exists():
        return False
    fh = ka.acquire_lock(runtime)
    if fh is None:
        return True
    ka.release_lock(fh)
    return False


def supervisor_pid(runtime):
    """The recorded supervisor pid when it is provably ours, else 0."""
    rec = _read_json(Path(runtime) / ka.STATE_FILE) or {}
    pid = _as_int(rec.get("pid"))
    return pid if is_ours(pid, PYTHON_PREFIX, rec.get("created")) else 0


def core_pid(runtime):
    """The core.alive pid when it is provably ours, else 0."""
    rec = _read_json(Path(runtime) / ka.HEARTBEAT_FILE) or {}
    pid = _as_int(rec.get("pid"))
    return pid if is_ours(pid, PYTHON_PREFIX, rec.get("created")) else 0


def status(runtime=None, edir=None):
    runtime = Path(runtime) if runtime else paths.runtime_dir()
    cpid = core_pid(runtime)
    spid = supervisor_pid(runtime)
    olist = overlay_pids(runtime, edir)
    main = overlay_main_pid(runtime) if olist else 0
    return {
        "core": {"live": bool(cpid), "pid": cpid},
        "supervisor": {"live": supervisor_locked(runtime) or bool(spid), "pid": spid},
        # OPS-OVL-PID: "pid" is the recorded main process; children stay in
        # "pids". Without a record (older run) the lowest scanned pid is shown.
        "overlay": {"live": bool(olist),
                    "pid": main if main in olist else (olist[0] if olist else 0),
                    "pids": olist},
    }


def plan(state, overlay_wanted=True, overlay_installed=True):
    """Components to start, in order, so the running set converges to one
    core, one supervisor and (when wanted and installed) one overlay."""
    todo = []
    if not state["core"]["live"]:
        todo.append("core")
    if not state["supervisor"]["live"]:
        todo.append("supervisor")
    if overlay_wanted and overlay_installed and not state["overlay"]["live"]:
        todo.append("overlay")
    return todo


SUPERVISOR_MODULE = "server.al.keepalive"


def supervisor_command(port, adopt_pid=0):
    """The windowless supervisor start through the one command builder
    (DEP-06): `-m server.al.keepalive` in a checkout, boot.py in an
    install; --adopt-pid only for a core that has no heartbeat yet."""
    args = ["--port", str(int(port))]
    if int(adopt_pid or 0) > 0:
        args += ["--adopt-pid", str(int(adopt_pid))]
    return paths.python_cmd(SUPERVISOR_MODULE, *args, windowless=True)


def start_supervisor(port, adopt_pid=0, popen=subprocess.Popen):
    """Start one supervisor hidden and detached from the caller (no
    window, its own process group, no inherited handles); returns the
    child (a Popen). A second supervisor exits at once on the lock, so a
    racing start is harmless. Raises OSError when it cannot start."""
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    return popen(supervisor_command(port, adopt_pid), cwd=str(paths.repo_root()),
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)


def supervisor_live(runtime):
    """A supervisor watches runtime: its recorded pid is provably ours
    (read first: no lock is touched), else it holds keepalive.lock."""
    return bool(supervisor_pid(runtime)) or supervisor_locked(runtime)


def record_overlay(runtime, pid):
    """Write overlay.pid for a just-started overlay; False when pid is not an
    electron process."""
    pid = int(pid)
    if not is_ours(pid, ELECTRON_IMAGE):
        return False
    data = {"pid": pid, "created": ka.process_created(pid),
            "image": ka.image_name(pid), "recorded": time.time()}
    jsonfile.write_text(Path(runtime) / OVERLAY_PID_FILE, json.dumps(data) + "\n")
    return True


def _terminate(pid, image_prefix, created=0):
    """Terminate pid only when its image still matches and, when a creation
    time is given, it is still the same process (no reused pid)."""
    if os.name != "nt" or not ka.image_name(pid).lower().startswith(image_prefix):
        return False
    if not _same_created(pid, created):
        return False
    ctypes, wintypes, k = ka._kernel32()
    h = k.OpenProcess(ka._TERMINATE | ka._QUERY_LIMITED, False, int(pid))
    if not h:
        return False
    try:
        return bool(k.TerminateProcess(h, 1))
    finally:
        k.CloseHandle(h)


def _wait_gone(pids, timeout, sleep=time.sleep, now=time.monotonic):
    end = now() + timeout
    left = [p for p in pids if ka.pid_alive(p)]
    while left and now() < end:
        sleep(0.2)
        left = [p for p in left if ka.pid_alive(p)]
    return left


_EPOCH_AS_FILETIME = 116444736000000000  # 1970-01-01 in 100 ns ticks since 1601


def to_filetime(ns_since_epoch):
    """A time in ns since 1970 as a FILETIME integer, the unit of
    keepalive.process_created."""
    return int(ns_since_epoch) // 100 + _EPOCH_AS_FILETIME


STOP_REQUEST_FRESH_S = 600  # an older stop.request is a leftover, not this stop


def stop_asked_at(runtime, now_ns=time.time_ns):
    """When stop was asked, as a FILETIME integer: the mtime of
    <runtime>/stop.request (stop.ps1 writes it before it calls stop; it
    also passes the time itself as --asked-at), else now (a direct
    `procs stop` with no request file, or one older than
    STOP_REQUEST_FRESH_S, a leftover of an earlier stop)."""
    now = int(now_ns())
    try:
        mtime = os.stat(Path(runtime) / ka.STOP_FILE).st_mtime_ns
    except OSError:
        return to_filetime(now)
    if mtime > now or now - mtime > STOP_REQUEST_FRESH_S * 1_000_000_000:
        return to_filetime(now)
    return to_filetime(mtime)


def _split_by_age(pids, cutoff):
    """(older, younger): RUN-STOP-RACE (F-152) - a pid created after the
    cutoff was started after stop was asked (a racing run.ps1 or client
    start) and is not this stop's to end. An unknown creation time (0)
    counts as older."""
    older, younger = [], []
    for pid in pids:
        created = ka.process_created(pid)
        (younger if created > cutoff else older).append((pid, created))
    return older, [p for p, _ in younger]


def stop(runtime=None, wait_s=10.0, edir=None, asked_at=None):
    """Stop the supervisor (it exits by itself on stop.request; forced after
    wait_s) and the overlay (terminated: it has no clean-exit channel and
    holds no state). Only overlay processes created before stop was asked
    (asked_at, a FILETIME; default stop_asked_at) are ended; younger ones
    are left alone, listed in "overlay_younger" and not counted as left
    (RUN-STOP-RACE, F-152). Returns a report dict; "left" lists what is
    still up."""
    runtime = Path(runtime) if runtime else paths.runtime_dir()
    cutoff = stop_asked_at(runtime) if asked_at is None else int(asked_at)
    report = {"supervisor": "not running", "overlay": "not running", "left": []}
    spid = supervisor_pid(runtime)
    if spid:
        if _wait_gone([spid], wait_s):
            report["supervisor"] = ("stopped (forced)" if _terminate(spid, PYTHON_PREFIX)
                                    else "could not stop")
        else:
            report["supervisor"] = "exited"
    elif supervisor_locked(runtime):
        # an unrecorded supervisor (older build) still exits on stop.request
        end = time.monotonic() + wait_s
        while supervisor_locked(runtime) and time.monotonic() < end:
            time.sleep(0.2)
        report["supervisor"] = ("still running (unrecorded pid)"
                                if supervisor_locked(runtime) else "exited")
    older, younger = _split_by_age(overlay_pids(runtime, edir), cutoff)
    if older:
        for pid, created in older:
            _terminate(pid, ELECTRON_IMAGE, created)
        # GP-09 (decision 0080): a loaded machine can take longer than 5 s
        # to tear a terminated process down; the overlay gets the same wait
        # as the supervisor (stop.ps1 -TimeoutSec), never less than 5 s.
        _wait_gone([p for p, _ in older], max(5.0, wait_s))
        report["overlay"] = f"stopped ({len(older)} process(es))"
    if not younger:
        # a younger overlay wrote its own record; keep it for its status
        try:
            (runtime / OVERLAY_PID_FILE).unlink()
        except OSError:
            pass
    _wait_gone([spid] if spid else [], 3.0)
    left = status(runtime, edir)
    # GP-09 (decision 0080): an overlay pid the process scan still lists
    # after it has exited (its exit code is set) is not left running.
    # RUN-STOP-RACE: nor is one started after stop was asked.
    _, young_now = _split_by_age(left["overlay"]["pids"], cutoff)
    young = sorted(set(younger) | set(young_now))
    alive = [p for p in left["overlay"]["pids"]
             if p not in young and ka.pid_alive(p)]
    left["overlay"]["live"] = bool(alive)
    report["left"] = [c for c in COMPONENTS if left[c]["live"]]
    if alive:
        report["overlay_left"] = alive
    if young:
        report["overlay_younger"] = young
    return report


def build_parser():
    p = argparse.ArgumentParser(prog="python -m server.al.procs",
                                description="AshLight process registry")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    pl = sub.add_parser("plan")
    pl.add_argument("--no-overlay", action="store_true")
    pl.add_argument("--overlay-missing", action="store_true",
                    help="the overlay is not installed")
    rec = sub.add_parser("record-overlay")
    rec.add_argument("pid", type=int)
    st = sub.add_parser("stop")
    st.add_argument("--wait", type=float, default=10.0)
    st.add_argument("--asked-at", type=int, default=None,
                    help="when stop was asked (FILETIME); overlay processes "
                         "created later are left alone")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    runtime = paths.runtime_dir()
    if args.cmd == "status":
        print(json.dumps(status(runtime)))
        return 0
    if args.cmd == "plan":
        state = status(runtime)
        print(json.dumps({"start": plan(state, not args.no_overlay,
                                        not args.overlay_missing),
                          "status": state}))
        return 0
    if args.cmd == "record-overlay":
        # the overlay may still be starting; give it a moment to appear
        for _ in range(20):
            if record_overlay(runtime, args.pid):
                return 0
            if not ka.pid_alive(args.pid):
                break
            time.sleep(0.1)
        return 1
    asked = args.asked_at if args.asked_at and args.asked_at > 0 else None
    report = stop(runtime, args.wait, asked_at=asked)
    print(json.dumps(report))
    return 0 if not report["left"] else 1


if __name__ == "__main__":
    sys.exit(main())
