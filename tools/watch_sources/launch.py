"""AUTO-07 (W11 of docs/plan/06, F-052; decision 0069): the launch gate.

A local source: it makes no request of its own (hosts and urls are empty,
so the frame's fetch refuses every URL) and runs on every tick. It reads,
under the tree root it is given:

- the clock (the tick's `now`, local date);
- the 'data' records of the repoe-fork and ggg-tree sources in
  ops/runtime/watch/state.json (LOOP-WATCH-META: version, preview,
  live_version);
- AshLight's own run-history file, ops/runtime/run_history.json
  (server/al/runhistory.py FILE_NAME, ruling Q-28), read only, never
  restored or rewritten;
- the masked parse ledger ops/runtime/logshapes.json (server/al/logshapes.py,
  F-061): only its 'hits' counts, never a shape;
- ROADMAP.md and the row files (tools/roadmap.py load_rows), to know which
  gate rows are still open.
It never opens Client.txt and never starts a subprocess.

Root: ctx["root"]; else this checkout, only when ctx["live"] is true; with
neither the source reads nothing and finds nothing (hermetic loop tests).

Findings (templates in ops/loop/watch_rows/launch.json):
- gatepoe210 (act gate, row GATE-POE2-10): the local date is 2026-12-11 or
  later and the repoe-fork or ggg-tree record shows a version of 1.0 or
  higher that is not a preview (live_version, or version while preview is
  false). Key "poe2-10:<source>:<version>".
- gateact5seen (act gate, row GATE-ACT5-SEEN): the first Act 5 split (act
  key G5) in the run-history file; else, when that file shows none (run
  history off or empty), the ledger's first 'area.act.G5' hit. Key
  "act5-seen:run-history" or "act5-seen:ledger".
- launchcheck (act row, LAUNCH-CHECK-<YYYYMMDD>, BLOCKED: session): the
  local date is three days or more past 2026-12-11, no upstream record
  shows 1.0 and GATE-POE2-10 is still open. Key "no-signal".
Each finding is made at most once for all time: state["data"]["made"]
records it (the frame keeps 'data' after a good run), and a gate whose row
is no longer open (flipped by hand) makes none. Filing (and the HALT
check before any commit) is tools/watch_file.py's job.
"""

import datetime as _dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LAUNCH_DATE = _dt.date(2026, 12, 11)
CHECK_AFTER_DAYS = 3
UPSTREAMS = ("repoe-fork", "ggg-tree")
MIN_VERSION = (1, 0)
RUN_HISTORY_REL = Path("ops/runtime/run_history.json")
LEDGER_REL = Path("ops/runtime/logshapes.json")
ACT5_KEY = "G5"
LEDGER_ACT5 = "area.act." + ACT5_KEY
LEDGER_SCHEMA = 1
LEDGER_MAX_BYTES = 256 * 1024
RUN_HISTORY_MAX_BYTES = 1024 * 1024
GATE_POE2 = "GATE-POE2-10"
GATE_ACT5 = "GATE-ACT5-SEEN"
KIND_POE2 = "gatepoe210"
KIND_ACT5 = "gateact5seen"
KIND_CHECK = "launchcheck"

VERSION_RX = re.compile(r"^(\d{1,3})\.(\d{1,3})(?:\.\d{1,4}){0,2}$")


def version_key(text):
    """(major, minor) of a plain version string such as '1.0.0.2', or None."""
    m = VERSION_RX.match(str(text or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _root(ctx):
    root = ctx.get("root")
    if root:
        return Path(root)
    return ROOT if ctx.get("live") else None


def _read_json(path, max_bytes):
    """The parsed JSON object of path, or None (absent, too big, bad)."""
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            return None
        doc = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def upstream_signal(root):
    """(source name, version) of the first upstream record showing a 1.0 or
    higher version that is not a preview, else None."""
    import upstream_watch
    recs = upstream_watch.load_state(root)["sources"]
    for name in UPSTREAMS:
        data = (recs.get(name) or {}).get("data") or {}
        found = [data.get("live_version")]
        if data.get("preview") is False:
            found.append(data.get("version"))
        for version in found:
            key = version_key(version)
            if key is not None and key >= MIN_VERSION:
                return name, str(version)
    return None


def run_history_act5(root):
    """True when AshLight's own run-history file holds an Act 5 split."""
    from server.al import runhistory
    doc = _read_json(Path(root) / RUN_HISTORY_REL,
                     min(RUN_HISTORY_MAX_BYTES, getattr(runhistory, "MAX_BYTES",
                                                        RUN_HISTORY_MAX_BYTES)))
    if doc is None:
        return False
    if isinstance(doc.get("characters"), dict):
        raw = []
        for entry in doc["characters"].values():
            if isinstance(entry, dict) and isinstance(entry.get("runs"), list):
                raw.extend(entry["runs"])
    else:
        raw = doc.get("runs") if isinstance(doc.get("runs"), list) else []
    for run in raw:
        clean = runhistory.clean_run(run)
        if clean and any(s.get("key") == ACT5_KEY for s in clean["splits"]):
            return True
    return False


def ledger_act5(root):
    """True when the parse ledger counts at least one Act 5 area hit."""
    doc = _read_json(Path(root) / LEDGER_REL, LEDGER_MAX_BYTES)
    if doc is None or doc.get("schema") != LEDGER_SCHEMA:
        return False
    hits = doc.get("hits")
    row = hits.get(LEDGER_ACT5) if isinstance(hits, dict) else None
    if not isinstance(row, list) or not row:
        return False
    n = row[0]
    return isinstance(n, int) and not isinstance(n, bool) and n > 0


def open_rows(root):
    """The ids of the open rows (ROADMAP.md plus row files, done files
    applied); an unreadable roadmap reads as no open row."""
    import roadmap
    try:
        return {r["id"] for r in roadmap.load_rows(Path(root)) if r["open"]}
    except (OSError, ValueError):
        return set()


def check(state, now, fetch, ctx):
    root = _root(ctx or {})
    if root is None:
        return []
    data = dict(state.get("data") or {})
    made = dict(data.get("made") or {})
    today = _dt.datetime.fromtimestamp(now).date()
    still_open = open_rows(root)
    found = []

    def make(kind, key):
        found.append({"kind": kind, "key": key, "tokens": {}})
        made[kind] = key

    signal = upstream_signal(root)
    if KIND_POE2 not in made and GATE_POE2 in still_open and today >= LAUNCH_DATE and signal:
        make(KIND_POE2, f"poe2-10:{signal[0]}:{signal[1]}")
    if (KIND_CHECK not in made and KIND_POE2 not in made and GATE_POE2 in still_open
            and signal is None
            and today >= LAUNCH_DATE + _dt.timedelta(days=CHECK_AFTER_DAYS)):
        make(KIND_CHECK, "no-signal")
    if KIND_ACT5 not in made and GATE_ACT5 in still_open:
        if run_history_act5(root):
            make(KIND_ACT5, "act5-seen:run-history")
        elif ledger_act5(root):
            make(KIND_ACT5, "act5-seen:ledger")
    if made:
        data["made"] = made
    state["data"] = data
    return found


SOURCE = {
    "name": "launch",
    "home": "loop",
    "cadence_s": 0,
    "window": None,
    "needs_web_data": True,
    "hosts": [],
    "urls": [],
    "purpose": "dev: watcher launch gate",
    "check": check,
}
