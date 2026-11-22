"""RUN-BUDGET-LOG-CORE (findings F-032, OPEN-03, row OVL-BUDGET; research
0048 R4): AshLight's own footprint, one row a minute.

The core appends one JSON line a minute (server/al/plug/budget.py runs the
tick) to budget.jsonl in the sidecar Logs dir (a test core: its tmp
runtime dir). A row holds:

- the core's own working set and CPU seconds (its own process handle,
  metrics.own_process), and its CPU percent of one core since the last row;
- luajit's working set, peak and CPU seconds while the calc child runs (the
  core's own child handle from subprocess.Popen; never opened by pid);
- the desktop client's figures from overlay-state.json in the runtime dir
  (written once a minute by app/metrics.js, schema 1), only while that
  file's "updated" is fresher than CLIENT_FRESH_S;
- tags from AshLight's own state: game_idle or game_active (Client.txt
  staleness, decision 0029), in_map (the map session), overlay_shown and
  companion_open (the client file), calc_on (the opt-in).

Floor (decisions 0006 method 3, 0029): only AshLight's own processes are
measured. The game process and window are never listed, opened or looked
at; no process scan. A row holds numbers, booleans and fixed tag words
only: no path, no name, no pid (clean_row enforces it).

The file stops at MAX_BYTES; the oldest rows are dropped first.

    python -m server.al.budgetlog check [--file PATH]

prints the row count per tag and every budget breach, and exits 1 on a
breach or when the log holds no row (0 otherwise). Budgets (research 0048,
MB unless named): B9 supervisor under 35 (only a row that carries it; the
core never measures the supervisor), B10 client with the companion closed
at most 2 processes, working set under 200, private under 120, B11 client
with the companion open at most 3 processes, working set under 384, B12
overlay CPU under 0.2 percent of a core outside a map and under 1 percent
in a map (only measurable while the companion is closed: then the one
renderer is the overlay), B17 luajit peak under 768, B18 all of AshLight
(core + client + luajit) under 460 with the calc off. B11 and B18 were
calibrated from the first live log (RUN-BUDGET-CALIBRATE-B11, decision
0002 amendment 2026-11-22): B11 was a provisional 300 and B18 350.

Standard library only.
"""

import argparse
import datetime
import json
import os
import sys
import threading
import time
from pathlib import Path

from . import metrics

VERSION = 1
FILE_NAME = "budget.jsonl"
MAX_BYTES = 1024 * 1024  # the file never grows past this
KEEP_BYTES = 896 * 1024  # a trim keeps the newest rows up to this
PERIOD_S = 60.0
CLIENT_FILE = "overlay-state.json"  # app/metrics.js, schema 1
CLIENT_SCHEMA = 1
CLIENT_MAX_BYTES = 4096
CLIENT_FRESH_S = 150.0  # 2.5 client periods; older figures are not used
CLIENT_TYPES = ("browser", "tab", "gpu", "utility", "other")

GAME_IDLE, GAME_ACTIVE = "game_idle", "game_active"
IN_MAP, OVERLAY_SHOWN, COMPANION_OPEN, CALC_ON = (
    "in_map", "overlay_shown", "companion_open", "calc_on")
TAGS = (GAME_IDLE, GAME_ACTIVE, IN_MAP, OVERLAY_SHOWN, COMPANION_OPEN, CALC_ON)

# research 0048 budgets (MB, process counts, percent of one core); B11 and
# B18 calibrated from the live log (decision 0002 amendment 2026-11-22):
# B11 384 = about 1.2 x the companion-open median (319 MB), 43 MB over its
# max (340.5); B18 460 = B11 + the core's max (68 MB), rounded up.
BUDGETS = {
    "B9": {"supervisor_mb": 35.0},
    "B10": {"processes": 2, "ws_mb": 200.0, "private_mb": 120.0},
    "B11": {"processes": 3, "ws_mb": 384.0},
    "B12": {"idle_pct": 0.2, "map_pct": 1.0},
    "B17": {"luajit_peak_mb": 768.0},
    "B18": {"total_mb": 460.0},
}

ROW_KEYS = ("v", "at", "core_mb", "core_cpu_s", "core_cpu_pct", "luajit_mb",
            "luajit_peak_mb", "luajit_cpu_s", "client", "total_mb", "tags")
CLIENT_KEYS = ("processes", "ws_mb", "private_mb", "cpu_pct", "overlay_cpu_pct",
               "age_s")


def _mb_from_kb(kb):
    return round(kb / 1024.0, 1)


def _num(v):
    """A finite non-negative number (not a bool), else None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if v != v or v < 0 or v == float("inf"):
        return None
    return v


# -- the client's figures (app/metrics.js overlay-state.json, schema 1)
def _parse_utc(text):
    if not isinstance(text, str) or len(text) > 40:
        return None
    try:
        dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()


def client_figures(doc, now):
    """The client part of a row from a parsed overlay-state.json, or None
    when the doc is not schema 1, malformed or older than CLIENT_FRESH_S.
    Returns (client dict, overlay_shown, companion_open)."""
    if not isinstance(doc, dict) or doc.get("schema") != CLIENT_SCHEMA:
        return None
    at = _parse_utc(doc.get("updated"))
    if at is None:
        return None
    age = now - at
    if age > CLIENT_FRESH_S or age < -CLIENT_FRESH_S:
        return None
    procs = _num(doc.get("processes"))
    ws = _num(doc.get("working_set_kb"))
    priv = _num(doc.get("private_kb"))
    cpu = _num(doc.get("cpu_pct"))
    if procs is None or ws is None:
        return None
    shown = doc.get("overlay_shown") is True
    companion = doc.get("companion_open") is True
    by_type = doc.get("by_type") if isinstance(doc.get("by_type"), dict) else {}
    overlay_cpu = None
    tab = by_type.get("tab")
    if not companion and isinstance(tab, dict) and _num(tab.get("count")) == 1:
        # with the companion closed the one renderer is the overlay
        overlay_cpu = _num(tab.get("cpu_pct"))
    client = {"processes": int(procs), "ws_mb": _mb_from_kb(ws),
              "private_mb": None if priv is None else _mb_from_kb(priv),
              "cpu_pct": None if cpu is None else round(cpu, 3),
              "overlay_cpu_pct": None if overlay_cpu is None else round(overlay_cpu, 3),
              "age_s": round(max(0.0, age), 1)}
    return client, shown, companion


def read_client(runtime, now):
    """client_figures of <runtime>/overlay-state.json; None when the file
    is missing, too big or unreadable. One stat-free open of one file."""
    try:
        with open(Path(runtime) / CLIENT_FILE, "rb") as fh:
            data = fh.read(CLIENT_MAX_BYTES + 1)
    except OSError:
        return None
    if len(data) > CLIENT_MAX_BYTES:
        return None
    try:
        doc = json.loads(data.decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        return None
    return client_figures(doc, now)


# -- luajit, through the core's own child handle (never by pid)
def _child_windows(handle):
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32")
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                           wintypes.DWORD]
    k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    h = wintypes.HANDLE(handle)
    if not psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
        return None
    t = [wintypes.FILETIME() for _ in range(4)]
    cpu = None
    if k32.GetProcessTimes(h, *(ctypes.byref(x) for x in t)):
        ticks = sum((x.dwHighDateTime << 32) | x.dwLowDateTime for x in t[2:])
        cpu = round(ticks / 1e7, 2)
    mb = 1024 * 1024
    return {"luajit_mb": round(pmc.WorkingSetSize / mb, 1),
            "luajit_peak_mb": round(pmc.PeakWorkingSetSize / mb, 1),
            "luajit_cpu_s": cpu}


def luajit_footprint():
    """The running calc child's figures, or None. Reads the shared calc
    bridge only when the calc wire already loaded it (the theorycraft
    package's `bridge` attribute; the core still never imports it, see
    tests/test_tc_bridge.py) and only through the Popen object's own
    handle: no import, no start, no pid."""
    pkg = sys.modules.get(__package__ + ".theorycraft")
    mod = getattr(pkg, "bridge", None) if pkg is not None else None
    b = getattr(mod, "_SHARED", None) if mod is not None else None
    proc = getattr(b, "_proc", None) if b is not None else None
    if proc is None or sys.platform != "win32":
        return None
    try:
        if proc.poll() is not None:
            return None
        handle = getattr(proc, "_handle", None)
        return _child_windows(int(handle)) if handle is not None else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


# -- rows
def tags_of(game_idle, in_map, overlay_shown, companion_open, calc_on):
    out = [GAME_IDLE if game_idle else GAME_ACTIVE]
    for flag, tag in ((in_map, IN_MAP), (overlay_shown, OVERLAY_SHOWN),
                      (companion_open, COMPANION_OPEN), (calc_on, CALC_ON)):
        if flag:
            out.append(tag)
    return out


def make_row(at, own, luajit, client, tags, cpu_pct=None):
    """One row from its parts (own = metrics.own_process(), luajit =
    luajit_footprint(), client = the client dict or None)."""
    lj = luajit or {}
    core_mb = _num((own or {}).get("working_set_mb"))
    total = None
    if core_mb is not None:
        total = core_mb + (client["ws_mb"] if client else 0.0) + (_num(lj.get("luajit_mb")) or 0.0)
        total = round(total, 1)
    row = {"v": VERSION, "at": int(at), "core_mb": core_mb,
           "core_cpu_s": _num((own or {}).get("cpu_s")),
           "core_cpu_pct": None if cpu_pct is None else round(cpu_pct, 3),
           "luajit_mb": _num(lj.get("luajit_mb")),
           "luajit_peak_mb": _num(lj.get("luajit_peak_mb")),
           "luajit_cpu_s": _num(lj.get("luajit_cpu_s")),
           "client": dict(client) if client else None,
           "total_mb": total, "tags": list(tags)}
    return clean_row(row)


def clean_row(row):
    """The row when it holds only the fixed keys, numbers, booleans, None
    and the TAGS words; ValueError otherwise (so no path, name or pid text
    can be written)."""
    if not isinstance(row, dict) or set(row) - set(ROW_KEYS):
        raise ValueError("unexpected row keys")
    for k, v in row.items():
        if k == "tags":
            if not isinstance(v, list) or any(t not in TAGS for t in v):
                raise ValueError("unexpected tag")
        elif k == "client":
            if v is None:
                continue
            if not isinstance(v, dict) or set(v) - set(CLIENT_KEYS):
                raise ValueError("unexpected client keys")
            for cv in v.values():
                if cv is not None and _num(cv) is None:
                    raise ValueError("client values are numbers")
        elif v is not None and _num(v) is None:
            raise ValueError(f"row value {k} is not a number")
    return row


class BudgetLog:
    """The capped budget.jsonl writer and the last row."""

    def __init__(self, path, max_bytes=MAX_BYTES, keep_bytes=KEEP_BYTES):
        self.path = Path(path)
        self.max_bytes = int(max_bytes)
        self.keep_bytes = min(int(keep_bytes), self.max_bytes)
        self.last = None
        self.last_breaches = []
        self.write_errors = 0
        self._lock = threading.Lock()

    def append(self, row):
        """Append one row; trim the oldest rows first when the file would
        pass max_bytes. True when written."""
        line = (json.dumps(clean_row(row), separators=(",", ":")) + "\n").encode("ascii")
        with self._lock:
            self.last = row
            self.last_breaches = sorted({b["budget"] for b in check([row])})
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    size = self.path.stat().st_size
                except FileNotFoundError:
                    size = 0
                if size + len(line) > self.max_bytes:
                    self._trim(len(line))
                with open(self.path, "ab") as fh:
                    fh.write(line)
                return True
            except OSError:
                self.write_errors += 1
                return False

    def _trim(self, room):
        """Rewrite the file with its newest whole rows, leaving `room`
        bytes under keep_bytes (tmp then replace)."""
        try:
            data = self.path.read_bytes()
        except FileNotFoundError:
            return
        budget = max(0, self.keep_bytes - room)
        lines = data.splitlines(keepends=True)
        kept = []
        size = 0
        for ln in reversed(lines):
            if not ln.endswith(b"\n"):
                continue
            if size + len(ln) > budget:
                break
            kept.append(ln)
            size += len(ln)
        kept.reverse()
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_bytes(b"".join(kept))
        os.replace(tmp, self.path)


class Sampler:
    """One row a minute from a core: call due(now) from the core loop."""

    def __init__(self, core, log, period_s=PERIOD_S, clock=time.monotonic,
                 wall=time.time):
        self.core = core
        self.log = log
        self.period_s = float(period_s)
        self.clock = clock
        self.wall = wall
        self.next_at = clock() + self.period_s
        self._prev = None  # (monotonic, cpu_s)

    def state_flags(self):
        """(game_idle, in_map, calc_on) from AshLight's own state."""
        snap = self.core.state.snapshot()
        game_idle = bool(snap.get("game_idle"))
        cur = (snap.get("maps") or {}).get("current") or {}
        in_map = bool(cur.get("inside")) and not game_idle
        try:
            calc_on = bool(self.core.tc_calc_enabled())
        except Exception:  # noqa: BLE001 - an unreadable config reads off
            calc_on = False
        return game_idle, in_map, calc_on

    def sample(self):
        """Build one row (no write)."""
        mono = self.clock()
        wall = self.wall()
        own = metrics.own_process()
        cpu_pct = None
        cpu_s = _num(own.get("cpu_s"))
        if self._prev is not None and cpu_s is not None and mono > self._prev[0]:
            cpu_pct = max(0.0, (cpu_s - self._prev[1]) / (mono - self._prev[0]) * 100.0)
        if cpu_s is not None:
            self._prev = (mono, cpu_s)
        game_idle, in_map, calc_on = self.state_flags()
        got = read_client(self.core.runtime, wall)
        client, shown, companion = got if got else (None, False, False)
        tags = tags_of(game_idle, in_map, shown, companion, calc_on)
        return make_row(wall, own, luajit_footprint(), client, tags, cpu_pct)

    def due(self, now=None):
        """Sample and append when a period has passed; the row or None."""
        now = self.clock() if now is None else now
        if now < self.next_at:
            return None
        self.next_at = now + self.period_s
        row = self.sample()
        self.log.append(row)
        return row


# -- the checker
def _breach(i, budget, field, value, limit):
    return {"row": i, "budget": budget, "field": field, "value": value, "limit": limit}


def check(rows, budgets=None):
    """Every budget breach in rows (a list of row dicts), as dicts
    {"row", "budget", "field", "value", "limit"}; [] when all are inside."""
    b = BUDGETS if budgets is None else budgets
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        tags = set(row.get("tags") or ())
        sup = _num(row.get("supervisor_mb"))
        if sup is not None and sup >= b["B9"]["supervisor_mb"]:
            out.append(_breach(i, "B9", "supervisor_mb", sup, b["B9"]["supervisor_mb"]))
        client = row.get("client") if isinstance(row.get("client"), dict) else None
        if client:
            key = "B11" if COMPANION_OPEN in tags else "B10"
            lim = b[key]
            n = _num(client.get("processes"))
            if n is not None and n > lim["processes"]:
                out.append(_breach(i, key, "processes", n, lim["processes"]))
            ws = _num(client.get("ws_mb"))
            if ws is not None and ws >= lim["ws_mb"]:
                out.append(_breach(i, key, "ws_mb", ws, lim["ws_mb"]))
            priv = _num(client.get("private_mb"))
            if "private_mb" in lim and priv is not None and priv >= lim["private_mb"]:
                out.append(_breach(i, key, "private_mb", priv, lim["private_mb"]))
            ocpu = _num(client.get("overlay_cpu_pct"))
            if ocpu is not None and COMPANION_OPEN not in tags:
                limit = b["B12"]["map_pct"] if IN_MAP in tags else b["B12"]["idle_pct"]
                if ocpu >= limit:
                    out.append(_breach(i, "B12", "overlay_cpu_pct", ocpu, limit))
        peak = _num(row.get("luajit_peak_mb"))
        if peak is None:
            peak = _num(row.get("luajit_mb"))
        if peak is not None and peak >= b["B17"]["luajit_peak_mb"]:
            out.append(_breach(i, "B17", "luajit_peak_mb", peak, b["B17"]["luajit_peak_mb"]))
        total = _num(row.get("total_mb"))
        if client and CALC_ON not in tags and total is not None \
                and total >= b["B18"]["total_mb"]:
            out.append(_breach(i, "B18", "total_mb", total, b["B18"]["total_mb"]))
    return out


def read_rows(path):
    """The parsed rows of a budget log (bad lines skipped); [] when absent."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    rows = []
    for line in data.splitlines():
        try:
            row = json.loads(line.decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def tag_counts(rows):
    counts = {t: 0 for t in TAGS}
    for row in rows:
        for t in row.get("tags") or ():
            if t in counts:
                counts[t] += 1
    return counts


def report(rows):
    """(lines, exit code) of the check command for rows."""
    lines = [f"rows: {len(rows)}"]
    for tag, n in tag_counts(rows).items():
        lines.append(f"tag {tag}: {n}")
    breaches = check(rows)
    for br in breaches:
        lines.append(f"breach {br['budget']} row {br['row']}: {br['field']} "
                     f"{br['value']} over {br['limit']}")
    if not rows:
        lines.append("FAIL: no row in the budget log yet")
        return lines, 1
    if breaches:
        lines.append(f"FAIL: {len(breaches)} breach(es)")
        return lines, 1
    lines.append("OK: every row inside its budgets")
    return lines, 0


def default_file():
    from . import paths
    return paths.sidecar_dir("Logs") / FILE_NAME


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m server.al.budgetlog",
                                 description="Check AshLight's budget log.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="row count per tag; exit 1 on a breach or no row")
    c.add_argument("--file", default=None, help="the budget log (default: sidecar Logs)")
    args = ap.parse_args(argv)
    path = Path(args.file) if args.file else default_file()
    lines, rc = report(read_rows(path))
    for line in lines:
        print(line)
    return rc


if __name__ == "__main__":
    sys.exit(main())
