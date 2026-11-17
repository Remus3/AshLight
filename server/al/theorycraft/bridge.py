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
"""

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from server.al import exepin, paths

FRAME_PREFIX = "ALB1 "
SCRIPT = Path(__file__).resolve().with_name("bridge.lua")
DEFAULT_TIMEOUT = 60.0
DEFAULT_START_TIMEOUT = 120.0
# AUDIT pass 2 (P2-B1): the crash-replay list keeps the last item per slot
# (one entry per distinct text when no slot is named) and at most this many,
# so item checks over a long session cannot grow it without bound.
MAX_REPLAY_ITEMS = 32
_EOF = object()


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
                 start_timeout=DEFAULT_START_TIMEOUT, log_path=None, exe_check=None):
        self.argv = list(argv)
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
        env = dict(os.environ)
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
                self._log = open(self.log_path, "ab")
                stderr = self._log
            except OSError:
                self._log = None
        if self.env is not None and self.env.get("TEMP"):
            try:
                Path(self.env["TEMP"]).mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self._proc = subprocess.Popen(
                self.argv, cwd=self.cwd, env=self.env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=stderr, creationflags=flags)
        except OSError as exc:
            self._close_log()
            self._proc = None
            raise BridgeUnavailable(f"cannot start bridge: {exc}") from exc
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
            for raw in proc.stdout:
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
                code = self._proc.wait(5) if self._proc else None
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
        with self._lock:
            for attempt in (1, 2):
                try:
                    if not self.running():
                        self._start()
                        if cmd != "load_build":  # a new build replaces it
                            self._replay(timeout)
                    return self._send(cmd, args, timeout)
                except _Crashed as exc:
                    if attempt == 2:
                        raise BridgeError(str(exc)) from None
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


class _Crashed(BridgeError):
    """Internal: the process exited; request() restarts once."""


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
