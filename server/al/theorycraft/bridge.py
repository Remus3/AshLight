"""TC-BRIDGE client: drive the unmodified, pinned Path of Building PoE2
checkout through our own Lua script (bridge.lua) under luajit.exe, over a
line-based JSON protocol on stdin / stdout (decision 0004 item 3, decision
0018, decision 0022).

Protocol: one JSON object per line. Request `{"id": n, "cmd": ..., ...}`;
reply line `ALB1 {"id": n, "ok": true, "result": {...}}` or
`ALB1 {"id": n, "ok": false, "error": "..."}`. Lines without the `ALB1 `
prefix are PoB's own prints and are ignored. On start the script sends one
ready frame with id 0.

Commands: ping, load_build {xml}, set_item {text, slot?},
outputs {keys?}, quit.

ZERO-CLICK: nothing starts until the first call; a crash (process exit)
restarts the bridge once, replays the last build and its items, and retries
the call; a call past its timeout kills the process (the next call starts a
fresh one). The optional component is absent unless the user opted in at
setup (setup.ps1 -TcCalc): then every call raises BridgeUnavailable and the
core, which never imports this module, runs unchanged.

Inputs are only user-pasted build XML and hotkey-read item text; nothing
here touches the game (CLAUDE.md ToS floor).

TC-CALC-CONFINE-PROC (decision 0022 amendment 2026-11-19): every start
hands the child only the allow-listed environment names (ENV_ALLOW) and,
on Windows, starts it suspended inside its own job object (kill on job
close, one active process, a per-process memory limit of JOB_MEMORY_LIMIT)
before it runs a single instruction; a start that cannot be confined is
killed and refused.

RUN-METRICS-SITES (decision 0067): every start is counted in AshLight's own
metrics as `calc.start` (a restart after a crash as `calc.restart`), every
time-out as `calc.timeout`, and every request as `calc|<outcome>` (ok,
error, timeout, crash, unavailable) with its milliseconds in the `calc_ms`
ring and one typed `calc` emit naming the command; no build or item text is
ever recorded.

RUN-OBS-LOGS-PY (F-090): tc-bridge.log (the child's stderr) rotates when it
is over 1 MB at a calc start (one old file kept; a held file keeps
appending), and every calc start writes one banner line first (build id,
pid of the core) in the one log format of server/al/logs.py.
RUN-CALC-PRIORITY (F-107): luajit starts with the below-normal priority
class (server/al/prio.py), so a calc never competes with the game.
"""

import ctypes
import functools
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from server.al import exepin, logs, metrics, paths, prio

FRAME_PREFIX = "ALB1 "
SCRIPT = Path(__file__).resolve().with_name("bridge.lua")
DEFAULT_TIMEOUT = 60.0
DEFAULT_START_TIMEOUT = 120.0
# AUDIT pass 2 (P2-B1): the crash-replay list keeps the last item per slot
# (one entry per distinct text when no slot is named) and at most this many,
# so item checks over a long session cannot grow it without bound.
MAX_REPLAY_ITEMS = 32
# AUDIT-BRIDGE-LOW (P2-B5): the reader takes at most this many bytes per
# stdout line from PoB; a longer line is dropped whole (never buffered), so
# a runaway print cannot grow the client's memory without bound.
MAX_LINE_BYTES = 1 << 20
_EOF = object()
# TC-CALC-CONFINE-PROC: the only environment names the child gets (matched
# case-insensitively, as Windows does). LUA_INIT, the user's PATH and every
# other inherited name are dropped. Windows needs SYSTEMROOT / WINDIR for its
# own DLLs; TEMP / TMP point at the sidecar Temp; LUA_PATH / LUA_CPATH find
# PoB's runtime.
ENV_ALLOW = ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LUA_PATH", "LUA_CPATH")
# Per-process committed memory cap of the job: well above the 384 MB Lua heap
# ceiling (decision 0028: peak working set 511 MB with it, ~900 MB without).
JOB_MEMORY_LIMIT = 1536 << 20


def child_env(env=None, extra=()):
    """The child's environment: only ENV_ALLOW (plus `extra`) names of `env`
    (default os.environ)."""
    allow = {n.upper() for n in ENV_ALLOW} | {n.upper() for n in extra}
    src = os.environ if env is None else env
    return {k: v for k, v in src.items() if k.upper() in allow}


# --- job object (Windows; stdlib ctypes) --------------------------------------

_JOB_LIMIT_ACTIVE_PROCESS = 0x0008
_JOB_LIMIT_PROCESS_MEMORY = 0x0100
_JOB_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001
_THREAD_SUSPEND_RESUME = 0x0002
_TH32CS_SNAPTHREAD = 0x0004
_CREATE_SUSPENDED = 0x0004
_K32 = None


def _kernel32():
    """A private kernel32 handle with typed prototypes (never the shared
    ctypes.windll one, whose prototypes other code may set)."""
    global _K32
    if _K32 is None:
        from ctypes import wintypes as w
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        protos = {
            "CreateJobObjectW": (w.HANDLE, [w.LPVOID, w.LPCWSTR]),
            "SetInformationJobObject": (w.BOOL, [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD]),
            "QueryInformationJobObject": (w.BOOL, [w.HANDLE, ctypes.c_int, w.LPVOID,
                                                   w.DWORD, w.LPVOID]),
            "OpenProcess": (w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
            "AssignProcessToJobObject": (w.BOOL, [w.HANDLE, w.HANDLE]),
            "CreateToolhelp32Snapshot": (w.HANDLE, [w.DWORD, w.DWORD]),
            "Thread32First": (w.BOOL, [w.HANDLE, w.LPVOID]),
            "Thread32Next": (w.BOOL, [w.HANDLE, w.LPVOID]),
            "OpenThread": (w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
            "ResumeThread": (w.DWORD, [w.HANDLE]),
            "CloseHandle": (w.BOOL, [w.HANDLE]),
        }
        for name, (res, args) in protos.items():
            fn = getattr(k, name)
            fn.restype, fn.argtypes = res, args
        _K32 = k
    return _K32


def _winerror():
    return ctypes.WinError(ctypes.get_last_error())


@functools.lru_cache(maxsize=None)
def _structs():
    from ctypes import wintypes as w

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", w.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", w.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", w.DWORD),
                    ("SchedulingClass", w.DWORD)]

    class Io(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Io),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class ThreadEntry(ctypes.Structure):
        _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD),
                    ("th32ThreadID", w.DWORD), ("th32OwnerProcessID", w.DWORD),
                    ("tpBasePri", w.LONG), ("tpDeltaPri", w.LONG),
                    ("dwFlags", w.DWORD)]

    return Extended, ThreadEntry


class Job:
    """One Windows job object for one bridge process: kill on job close,
    one active process, a per-process memory limit. The handle is not
    inheritable; closing it (close(), or the core exiting) kills the child."""

    def __init__(self, memory_limit=JOB_MEMORY_LIMIT):
        k = _kernel32()
        self._handle = k.CreateJobObjectW(None, None)
        if not self._handle:
            self._handle = None
            raise _winerror()
        extended, _ = _structs()
        info = extended()
        info.BasicLimitInformation.LimitFlags = (
            _JOB_LIMIT_KILL_ON_JOB_CLOSE | _JOB_LIMIT_ACTIVE_PROCESS
            | _JOB_LIMIT_PROCESS_MEMORY)
        info.BasicLimitInformation.ActiveProcessLimit = 1
        info.ProcessMemoryLimit = int(memory_limit)
        if not k.SetInformationJobObject(self._handle, _JOB_EXTENDED_LIMIT_INFORMATION,
                                         ctypes.byref(info), ctypes.sizeof(info)):
            err = _winerror()
            self.close()
            raise err

    @property
    def closed(self):
        return self._handle is None

    def adopt(self, pid):
        """Put the suspended process `pid` in the job, then resume it."""
        k = _kernel32()
        proc = k.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
        if not proc:
            raise _winerror()
        try:
            if not k.AssignProcessToJobObject(self._handle, proc):
                raise _winerror()
        finally:
            k.CloseHandle(proc)
        self._resume(pid)

    @staticmethod
    def _resume(pid):
        k = _kernel32()
        _, thread_entry = _structs()
        snap = k.CreateToolhelp32Snapshot(_TH32CS_SNAPTHREAD, 0)
        if not snap or snap == ctypes.c_void_p(-1).value:
            raise _winerror()
        resumed = 0
        try:
            entry = thread_entry()
            entry.dwSize = ctypes.sizeof(entry)
            ok = k.Thread32First(snap, ctypes.byref(entry))
            while ok:
                if entry.th32OwnerProcessID == pid:
                    th = k.OpenThread(_THREAD_SUSPEND_RESUME, False, entry.th32ThreadID)
                    if not th:
                        raise _winerror()
                    try:
                        if k.ResumeThread(th) == 0xFFFFFFFF:
                            raise _winerror()
                        resumed += 1
                    finally:
                        k.CloseHandle(th)
                ok = k.Thread32Next(snap, ctypes.byref(entry))
        finally:
            k.CloseHandle(snap)
        if not resumed:
            raise OSError(f"no thread of process {pid} to resume")

    def limits(self):
        """{"flags", "active_processes", "process_memory"} as set on the job."""
        k = _kernel32()
        extended, _ = _structs()
        info = extended()
        if not k.QueryInformationJobObject(self._handle, _JOB_EXTENDED_LIMIT_INFORMATION,
                                           ctypes.byref(info), ctypes.sizeof(info), None):
            raise _winerror()
        basic = info.BasicLimitInformation
        return {"flags": basic.LimitFlags,
                "active_processes": basic.ActiveProcessLimit,
                "process_memory": info.ProcessMemoryLimit}

    def close(self):
        """Close the handle (once); the kernel kills what is still inside."""
        handle, self._handle = self._handle, None
        if handle:
            _kernel32().CloseHandle(handle)


def open_job():
    """A fresh Job on Windows, None elsewhere (no job objects there)."""
    return Job() if os.name == "nt" else None


class BridgeError(RuntimeError):
    """The bridge answered with an error or died mid-call."""


class BridgeTimeout(BridgeError):
    """A call ran past its timeout; the process was killed."""


class BridgeUnavailable(BridgeError):
    """The optional calc component (luajit.exe + PoB checkout) is absent."""


# --- component discovery ----------------------------------------------------

def _load_pins():
    return json.loads(paths.tc_pins_file().read_text(encoding="ascii"))


def component_paths(environ=None):
    """Where setup put the component (same layout as tools/tc_pin.py)."""
    pins = _load_pins()
    p = paths.all_runtime_paths(environ)
    lj_src = p["luajit_build"] / pins["luajit"]["top_dir"]
    return {
        "luajit": lj_src / "src" / "luajit.exe",
        "pob_src": p["pob2_cache"] / pins["pob2"]["top_dir"] / "src",
        "script": SCRIPT,
        "temp": p["temp"],
        "log": p["tc_bridge_log"],
    }


def status(environ=None):
    """{"available": bool, "missing": [names]} - never raises."""
    try:
        comp = component_paths(environ)
    except (OSError, ValueError, KeyError) as exc:
        return {"available": False, "missing": ["pins"], "error": str(exc)}
    missing = []
    if not exepin.verified(comp["luajit"]):
        # AUDIT-EXE-PATH: only the luajit.exe setup built and recorded
        missing.append("luajit")
    if not (comp["pob_src"] / "HeadlessWrapper.lua").is_file():
        missing.append("pob")
    if not comp["script"].is_file():
        missing.append("script")
    return {"available": not missing, "missing": missing}


def available(environ=None):
    return status(environ)["available"]


# --- the client ---------------------------------------------------------------

class Bridge:
    """One bridge process, started on first need. Not thread-safe by itself;
    a lock serialises calls so the core may share one instance."""

    def __init__(self, argv, cwd=None, env=None, timeout=DEFAULT_TIMEOUT,
                 start_timeout=DEFAULT_START_TIMEOUT, log_path=None, exe_check=None,
                 env_allow=()):
        self.argv = list(argv)
        # TC-CALC-CONFINE-PROC: names kept in the child's environment beyond
        # ENV_ALLOW (tests only; the component passes none)
        self.env_allow = tuple(env_allow)
        self._job = None
        # AUDIT-EXE-PATH: when set, argv[0] must match its recorded SHA-256
        # before every exec (first start and every restart).
        self.exe_check = Path(exe_check) if exe_check else None
        self.cwd = cwd
        self.env = env
        self.timeout = float(timeout)
        self.start_timeout = float(start_timeout)
        self.log_path = log_path
        self._proc = None
        self._lines = None
        self._log = None
        self._next_id = 1
        self._lock = threading.RLock()
        self._build = None  # last load_build xml, replayed after a crash
        self._items = []  # set_item args since that build

    @classmethod
    def from_component(cls, environ=None, **kw):
        st = status(environ)
        if not st["available"]:
            raise BridgeUnavailable("calc component absent: "
                                    + ", ".join(st["missing"]))
        comp = component_paths(environ)
        env = child_env()  # TC-CALC-CONFINE-PROC: allow-listed names only
        for name in ("TEMP", "TMP"):
            env[name] = str(comp["temp"])
        runtime = comp["pob_src"].parent / "runtime"
        env["LUA_PATH"] = ";".join([
            "?.lua", str(runtime / "lua" / "?.lua"),
            str(runtime / "lua" / "?" / "init.lua")])
        env["LUA_CPATH"] = ";".join(["?.dll", str(runtime / "?.dll")])
        return cls([str(comp["luajit"]), str(comp["script"])],
                   cwd=str(comp["pob_src"]), env=env, log_path=comp["log"],
                   exe_check=comp["luajit"], **kw)

    # -- lifecycle --

    def running(self):
        return self._proc is not None and self._proc.poll() is None

    def _start(self):
        self._stop(kill=True)
        if self.exe_check is not None and not exepin.verified(self.exe_check):
            raise BridgeUnavailable("luajit.exe does not match its recorded hash; "
                                    "re-run setup.ps1 -TcCalc")
        stderr = subprocess.DEVNULL
        if self.log_path is not None:
            try:
                Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
                logs.rotate_at_start(self.log_path)
                self._log = open(self.log_path, "ab")
                line = logs.format_line("tc-bridge", "INFO", logs.banner("calc bridge"))
                self._log.write((line + "\n").encode("ascii", "replace"))
                self._log.flush()
                stderr = self._log
            except OSError:
                self._close_log()
        if self.env is not None and self.env.get("TEMP"):
            try:
                Path(self.env["TEMP"]).mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        flags = prio.below_normal(flags)  # RUN-CALC-PRIORITY (F-107)
        # TC-CALC-CONFINE-PROC: the job exists before the child, which starts
        # suspended and runs only once it is inside the job.
        try:
            job = open_job()
        except OSError as exc:
            self._close_log()
            raise BridgeUnavailable(f"cannot confine bridge: {exc}") from exc
        if job is not None:
            flags |= _CREATE_SUSPENDED
        try:
            self._proc = subprocess.Popen(
                self.argv, cwd=self.cwd, env=child_env(self.env, self.env_allow),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                creationflags=flags)
        except OSError as exc:
            if job is not None:
                job.close()
            self._close_log()
            self._proc = None
            raise BridgeUnavailable(f"cannot start bridge: {exc}") from exc
        self._job = job
        if job is not None:
            try:
                job.adopt(self._proc.pid)
            except OSError as exc:
                self._stop(kill=True)
                raise BridgeUnavailable(f"cannot confine bridge: {exc}") from exc
        self._lines = queue.Queue()
        threading.Thread(target=self._reader, args=(self._proc, self._lines),
                         daemon=True, name="al-tc-bridge-reader").start()
        ready = self._read(0, self.start_timeout)
        if not ready.get("ok"):
            self._stop(kill=True)
            raise BridgeError("bridge failed to start: "
                              + str(ready.get("error", "no ready frame")))

    @staticmethod
    def _reader(proc, lines):
        try:
            skipping = False
            while True:
                raw = proc.stdout.readline(MAX_LINE_BYTES + 1)
                if not raw:
                    break
                if skipping:  # the tail of an overlong line
                    skipping = not raw.endswith(b"\n")
                    continue
                if len(raw) > MAX_LINE_BYTES and not raw.endswith(b"\n"):
                    skipping = True
                    continue
                text = raw.decode("utf-8", "replace").rstrip("\r\n")
                if not text.startswith(FRAME_PREFIX):
                    continue  # PoB's own prints
                try:
                    lines.put(json.loads(text[len(FRAME_PREFIX):]))
                except ValueError:
                    continue
        except (OSError, ValueError):
            pass
        lines.put(_EOF)

    def _read(self, rid, timeout):
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                self._stop(kill=True)
                raise BridgeTimeout(f"bridge call timed out after {timeout:g} s")
            try:
                msg = self._lines.get(timeout=left)
            except queue.Empty:
                continue
            if msg is _EOF:
                # AUDIT-BRIDGE-LOW (P2-B4): a process that closed stdout but
                # does not exit must still surface as a BridgeError.
                try:
                    code = self._proc.wait(5) if self._proc else None
                except subprocess.TimeoutExpired:
                    code = "still running after EOF"
                self._stop(kill=True)
                raise _Crashed(f"bridge exited (code {code})")
            if isinstance(msg, dict) and msg.get("id") == rid:
                return msg

    def _stop(self, kill=False):
        proc, self._proc = self._proc, None
        if proc is not None:
            if kill or proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                pass
            for stream in (proc.stdin, proc.stdout):
                try:
                    if stream:
                        stream.close()
                except OSError:
                    pass
        job, self._job = self._job, None
        if job is not None:
            job.close()  # TC-CALC-CONFINE-PROC: kills anything left inside
        self._close_log()

    def _close_log(self):
        if self._log is not None:
            try:
                self._log.close()
            except OSError:
                pass
            self._log = None

    def close(self):
        """Ask the bridge to quit, then make sure it is gone."""
        with self._lock:
            if self.running():
                try:
                    self._send("quit", {}, 5.0)
                except BridgeError:
                    pass
            self._stop(kill=True)

    # -- calls --

    def _send(self, cmd, args, timeout):
        rid = self._next_id
        self._next_id += 1
        req = dict(args)
        req["id"] = rid
        req["cmd"] = cmd
        line = json.dumps(req, ensure_ascii=True, separators=(",", ":")) + "\n"
        try:
            self._proc.stdin.write(line.encode("ascii"))
            self._proc.stdin.flush()
        except (OSError, ValueError, AttributeError) as exc:
            self._stop(kill=True)
            raise _Crashed(f"bridge exited (write failed: {exc})") from exc
        msg = self._read(rid, timeout)
        if not msg.get("ok"):
            raise BridgeError(str(msg.get("error", "bridge error")))
        result = msg.get("result")
        return result if isinstance(result, dict) else {}

    def _replay(self, timeout):
        if self._build is not None:
            self._send("load_build", {"xml": self._build}, timeout)
        for args in self._items:
            self._send("set_item", args, timeout)

    def request(self, cmd, timeout=None, **args):
        """Send one command; start (or restart after a crash) on demand."""
        timeout = self.timeout if timeout is None else float(timeout)
        t0 = time.monotonic()
        with self._lock:
            for attempt in (1, 2):
                try:
                    if not self.running():
                        metrics.inc("calc.restart" if attempt == 2 else "calc.start")
                        self._start()
                        if cmd != "load_build":  # a new build replaces it
                            self._replay(timeout)
                    result = self._send(cmd, args, timeout)
                    _count_call(cmd, "ok", t0)
                    return result
                except _Crashed as exc:
                    if attempt == 2:
                        _count_call(cmd, "crash", t0)
                        raise BridgeError(str(exc)) from None
                except BridgeTimeout:
                    metrics.inc("calc.timeout")
                    _count_call(cmd, "timeout", t0)
                    raise
                except BridgeUnavailable:
                    _count_call(cmd, "unavailable", t0)
                    raise
                except BridgeError:
                    _count_call(cmd, "error", t0)
                    raise
            raise BridgeError("unreachable")  # pragma: no cover

    def ping(self):
        return self.request("ping")

    def load_build(self, xml):
        """Load a PoB build from its XML; resets the replayed item list."""
        if not isinstance(xml, str) or not xml.strip():
            raise ValueError("build xml must be non-empty text")
        with self._lock:
            result = self.request("load_build", xml=xml)
            self._build = xml
            self._items = []
            return result

    def set_item(self, text, slot=None):
        """Equip an item from its in-game copy text (slot: PoB slot name,
        else the item's primary slot). Returns {"slot": name}."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("item text must be non-empty text")
        args = {"text": text}
        if slot:
            args["slot"] = str(slot)
        with self._lock:
            result = self.request("set_item", **args)
            self._remember(args)
            return result

    def _remember(self, args):
        key = ("slot", args["slot"]) if "slot" in args else ("text", args["text"])

        def same(a):
            return (("slot", a["slot"]) if "slot" in a else ("text", a["text"])) == key

        self._items = [a for a in self._items if not same(a)]
        self._items.append(args)
        del self._items[:-MAX_REPLAY_ITEMS]

    def outputs(self, keys=None):
        """PoB's main output table: {stat name: number or bool}."""
        args = {}
        if keys is not None:
            if isinstance(keys, (str, bytes)) or not all(isinstance(k, str) for k in keys):
                raise ValueError("keys must be a list of output names")
            args["keys"] = list(keys)
        result = self.request("outputs", **args)
        out = result.get("outputs")
        return out if isinstance(out, dict) else {}

    def main_skill(self):
        """MATH-WEAPON-TYPE: PoB's state of the build's main skill after the
        last calc: {"found", "disabled", "reason", "name"} (reason and name
        only when PoB has them, e.g. "Main Hand weapon is not usable with
        this skill")."""
        result = self.request("main_skill")
        return result if isinstance(result, dict) else {}


class _Crashed(BridgeError):
    """Internal: the process exited; request() restarts once."""


def _count_call(cmd, outcome, t0):
    """One bridge request in AshLight's own counters (decision 0067): the
    command name (a protocol constant, else "other"), the outcome word and
    the milliseconds; never an argument."""
    word = cmd if isinstance(cmd, str) and metrics.WORD_RE.match(cmd) else "other"
    ms = round((time.monotonic() - t0) * 1000.0, 1)
    metrics.inc(f"calc|{outcome}")
    metrics.timing("calc_ms", ms)
    metrics.emit("calc", cmd=word, outcome=outcome, ms=ms)


# --- one shared instance for the core (started on first need) ----------------

_SHARED = None
_SHARED_LOCK = threading.Lock()


def shared(environ=None):
    """The process-wide bridge, created on first need. Raises
    BridgeUnavailable when the component is absent (callers fall back)."""
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None:
            _SHARED = Bridge.from_component(environ=environ)
        return _SHARED


def shutdown_shared():
    global _SHARED
    with _SHARED_LOCK:
        b, _SHARED = _SHARED, None
    if b is not None:
        b.close()
