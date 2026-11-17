"""OPS-STOP / OPS-RUN-IDEMP: which AshLight processes are live, and stopping them.

    python -m server.al.procs status            JSON: core, supervisor, overlay
    python -m server.al.procs plan [--no-overlay] [--overlay-missing]
                                                JSON: components run.ps1 must start
    python -m server.al.procs record-overlay PID
                                                write <runtime>/overlay.pid
    python -m server.al.procs stop [--wait S]   stop supervisor and overlay
                                                (after stop.ps1 stopped the core)

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
import sys
import time
from pathlib import Path

from . import keepalive as ka
from . import paths

OVERLAY_PID_FILE = "overlay.pid"
ELECTRON_DIR_ENV = "AL_ELECTRON_DIR"  # tests only: a tmp electron dist dir
COMPONENTS = ("core", "supervisor", "overlay")
PYTHON_PREFIX = "python"
ELECTRON_IMAGE = "electron.exe"
_TH32CS_SNAPPROCESS = 0x2


def _read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="ascii"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def electron_dir():
    """The electron dist dir whose processes are ours, or None when the scan
    is off (a tmp runtime without an explicit AL_ELECTRON_DIR)."""
    value = (os.environ.get(ELECTRON_DIR_ENV) or "").strip().strip('"')
    if value:
        return Path(value).resolve()
    if (os.environ.get(paths.RUNTIME_ENV) or "").strip():
        return None
    return paths.repo_root() / "app" / "node_modules" / "electron" / "dist"


def _same_created(pid, created):
    created = int(created or 0)
    return created == 0 or ka.process_created(pid) == created


def is_ours(pid, image_prefix, created=0):
    """pid is alive, its image starts with image_prefix (case-insensitive)
    and, when a creation time was recorded, it is the same process."""
    pid = int(pid or 0)
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


def overlay_pids(runtime, edir=None, processes=None):
    """Sorted pids of our overlay: the recorded pid plus the dir scan."""
    found = set()
    rec = _read_json(Path(runtime) / OVERLAY_PID_FILE) or {}
    pid = int(rec.get("pid") or 0)
    if pid and is_ours(pid, ELECTRON_IMAGE, rec.get("created")):
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
    pid = int(rec.get("pid") or 0)
    return pid if is_ours(pid, PYTHON_PREFIX, rec.get("created")) else 0


def core_pid(runtime):
    rec = _read_json(Path(runtime) / ka.HEARTBEAT_FILE) or {}
    pid = int(rec.get("pid") or 0)
    return pid if is_ours(pid, PYTHON_PREFIX, rec.get("created")) else 0


def status(runtime=None, edir=None):
    runtime = Path(runtime) if runtime else paths.runtime_dir()
    cpid = core_pid(runtime)
    spid = supervisor_pid(runtime)
    olist = overlay_pids(runtime, edir)
    return {
        "core": {"live": bool(cpid), "pid": cpid},
        "supervisor": {"live": supervisor_locked(runtime) or bool(spid), "pid": spid},
        "overlay": {"live": bool(olist), "pid": olist[0] if olist else 0,
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


def record_overlay(runtime, pid):
    """Write overlay.pid for a just-started overlay; False when pid is not an
    electron process."""
    pid = int(pid)
    if not is_ours(pid, ELECTRON_IMAGE):
        return False
    data = {"pid": pid, "created": ka.process_created(pid),
            "image": ka.image_name(pid), "recorded": time.time()}
    runtime = Path(runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    tmp = runtime / (OVERLAY_PID_FILE + ".tmp")
    tmp.write_text(json.dumps(data) + "\n", encoding="ascii")
    os.replace(tmp, runtime / OVERLAY_PID_FILE)
    return True


def _terminate(pid, image_prefix):
    """Terminate pid only when its image still matches."""
    if os.name != "nt" or not ka.image_name(pid).lower().startswith(image_prefix):
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


def stop(runtime=None, wait_s=10.0, edir=None):
    """Stop the supervisor (it exits by itself on stop.request; forced after
    wait_s) and the overlay (terminated: it has no clean-exit channel and
    holds no state). Returns a report dict; "left" lists what is still up."""
    runtime = Path(runtime) if runtime else paths.runtime_dir()
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
    olist = overlay_pids(runtime, edir)
    if olist:
        for pid in olist:
            _terminate(pid, ELECTRON_IMAGE)
        _wait_gone(olist, 5.0)
        report["overlay"] = f"stopped ({len(olist)} process(es))"
    try:
        (runtime / OVERLAY_PID_FILE).unlink()
    except OSError:
        pass
    _wait_gone([spid] if spid else [], 3.0)
    left = status(runtime, edir)
    report["left"] = [c for c in COMPONENTS if left[c]["live"]]
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
    report = stop(runtime, args.wait)
    print(json.dumps(report))
    return 0 if not report["left"] else 1


if __name__ == "__main__":
    sys.exit(main())
