"""AUTO-18 (W14 of docs/plan/06, LEDGER-SOURCE; decisions 0069, 0071): live
log shapes and snapshot probe results become rows.

A local source: it makes no request (hosts and urls are empty, so the
frame's fetch refuses every URL) and runs on every tick. It reads, under the
tree root it is given, only the dev host's own files:

- the masked parse ledger ops/runtime/logshapes.json (server/al/logshapes.py,
  F-061; written by the core only while the ledger consent is on), re-checked
  through logshapes.Ledger.from_dict so a tampered file carries no raw text;
- the snapshot probe report ops/runtime/snapshot/probe.json
  (server/al/theorycraft/snapprobe.py, F-143: source, verdict, missing-key
  count, time), re-checked entry by entry;
- ROADMAP.md and the row files (tools/roadmap.py load_rows), to know which
  LIVE-1 rows are still open.
It never opens Client.txt and copies no raw line. An absent file is idle.

Root: ctx["root"]; else this checkout, only when ctx["live"] is true; with
neither the source reads nothing and finds nothing (hermetic loop tests).

Findings (templates in ops/loop/watch_rows/ledger.json):
- live1hit (act gate, done file for LIVE-1-<ITEM>): a pattern id of a
  logshapes.LIVE1_ITEMS item has its first live hit and the row is open.
  Key "live1:<ITEM>". LIVE-1-ACCEPTED is its own kind, live1accepted, since
  a token value may not carry the word 'accept' (tools/watch_rows.py).
- logshape (row LOG-SHAPE-<YYYYMMDD>, lane build): a masked shape passed the
  two-sighting rule (the ledger's own 'ok' flag) and was never reported
  before; at most one a local day (later new shapes wait for the next day).
  Key "log-shape:<YYYYMMDD>".
- snapprobe (row SNAP-<FILE>-<YYYYMMDD>, lane data): a probe.json entry of a
  source in the snapshot tool's own list (theorycraft/snapshot.py SOURCES)
  has verdict fail at a time not reported before; <FILE> is the source name
  in upper case with hyphens. At most one a source and local day. Key
  "snap:<FILE>:<YYYYMMDD>".
The frame queues a key once for all time; filing (and the HALT check before
any commit) is tools/watch_file.py's job.

Report: while the ledger file exists and changed since the last copy, the
masked `tools/live1_report.py --json` output (F-061's tool) is re-checked
field by field (only allow-list shapes and lines survive) and written to
ops/runtime/watch/live1_report.json; tools/al_lane.py seed_config copies that
one file into a claimed lane worktree. The runner is ctx["live1_runner"]
(root, ledger path) -> JSON text when given (tests), else a below-normal
subprocess that starts only when ctx["live"] is true.
"""

import datetime as _dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LEDGER_REL = Path("ops/runtime/logshapes.json")
PROBE_REL = Path("ops/runtime/snapshot/probe.json")
REPORT_REL = Path("ops/runtime/watch/live1_report.json")
TOOL_REL = Path("tools/live1_report.py")
PROBE_MAX_BYTES = 256 * 1024
REPORT_MAX_BYTES = 256 * 1024
RUNNER_TIMEOUT_S = 60
SEEN_MAX = 400          # reported shape digests kept (ledger holds 200)
KIND_HIT = "live1hit"
KIND_ACCEPTED = "live1accepted"
KIND_SHAPE = "logshape"
KIND_PROBE = "snapprobe"
ACCEPTED = "ACCEPTED"
ROW_PREFIX = "LIVE-1-"
FAIL = "fail"
VERDICTS = ("VERIFIED live", "NEW SHAPE", "NOT SEEN")
WAYSTONE = "WAYSTONE"

_SAFE_SOURCE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_ROW_ID = re.compile(r"^[A-Z][A-Z0-9-]{1,47}$")
_PATTERN = re.compile(r"^[a-z_]+(?:\.[A-Za-z0-9_]+)*$")
_HOUR = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}$")
_AREA_ID = re.compile(r"^[A-Za-z0-9_]{1,48}$")
_WORD = re.compile(r"^[a-z_]{1,32}$")
_STATES = ("found", "missing", "unreadable")


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


def _logshapes():
    from server.al import logshapes
    return logshapes


def load_ledger(root):
    """The re-checked ledger (logshapes.Ledger), or None when the file is
    absent or unreadable."""
    ls = _logshapes()
    doc = _read_json(Path(root) / LEDGER_REL, 2 * ls.MAX_BYTES)
    if doc is None:
        return None
    return ls.Ledger.from_dict(doc)


def snapshot_files():
    """{source name: <FILE> token} for the snapshot tool's own source list."""
    from server.al.theorycraft import snapshot
    return {name: name.upper().replace("_", "-") for name in snapshot.SOURCES}


def load_probe(root):
    """[(source, time)] of the probe.json entries with verdict fail, for a
    source of the snapshot tool's list; [] when absent or malformed."""
    doc = _read_json(Path(root) / PROBE_REL, PROBE_MAX_BYTES)
    rows = doc.get("sources") if doc else None
    if not isinstance(rows, list):
        return []
    known = snapshot_files()
    out = []
    for e in rows:
        if not isinstance(e, dict):
            continue
        src, verdict, missing, when = (e.get("source"), e.get("verdict"),
                                       e.get("missing"), e.get("time"))
        if not (isinstance(src, str) and _SAFE_SOURCE.match(src) and src in known):
            continue
        if not (isinstance(missing, int) and not isinstance(missing, bool) and missing >= 0):
            continue
        if verdict != FAIL:
            continue
        out.append((src, when if isinstance(when, str) and when.isascii() else ""))
    return out


def open_rows(root):
    """Ids of the open rows (ROADMAP.md plus row files, done files applied);
    an unreadable roadmap reads as no open row."""
    import roadmap
    try:
        return {r["id"] for r in roadmap.load_rows(Path(root)) if r["open"]}
    except (OSError, ValueError):
        return set()


def first_hits(led):
    """The LIVE1_ITEMS items with at least one live hit, in table order."""
    ls = _logshapes()
    out = []
    for item, pids in ls.LIVE1_ITEMS.items():
        if any(p in led.hits and led.hits[p][0] > 0 for p in pids):
            out.append(item)
    return out


def shape_digest(kind, shape):
    return hashlib.sha256(f"{kind}\n{shape}".encode("ascii", "replace")).hexdigest()[:16]


def confirmed_digests(led):
    """Digests of the masked shapes that passed the two-sighting rule."""
    ls = _logshapes()
    return [shape_digest(k, s) for (k, s), rec in led.shapes.items()
            if rec[3] and ls.is_safe_shape(s)]


# ---------------------------------------------------------------- report

def _count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _hour(v):
    return v if isinstance(v, str) and _HOUR.match(v) else None


def clean_report(doc):
    """The live1_report document with only checked fields: every shape an
    allow-list shape, every waystone line a safe line, every other value a
    known word, id, count or hour stamp. None when doc is not a report."""
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        return None
    ls = _logshapes()
    from server.al.plug import ledger as ledger_mod
    names = set(ls.LIVE1_ITEMS) | {WAYSTONE}
    items = []
    for it in doc.get("items") if isinstance(doc.get("items"), list) else ():
        if not isinstance(it, dict) or it.get("item") not in names:
            continue
        if it.get("verdict") not in VERDICTS:
            continue
        row = it.get("row")
        hits = it.get("hits") if isinstance(it.get("hits"), dict) else {}
        aids = it.get("area_ids") if isinstance(it.get("area_ids"), list) else []
        items.append({
            "item": it["item"],
            "row": row if isinstance(row, str) and _ROW_ID.match(row) else None,
            "verdict": it["verdict"],
            "hits": {k: v for k, v in hits.items()
                     if isinstance(k, str) and _PATTERN.match(k) and _count(v)},
            "first": _hour(it.get("first")), "last": _hour(it.get("last")),
            "shapes": it["shapes"] if _count(it.get("shapes")) else 0,
            "area_ids": [a for a in aids if isinstance(a, str) and _AREA_ID.match(a)],
        })
    rb = doc.get("readback") if isinstance(doc.get("readback"), dict) else {}
    ways = []
    for w in doc.get("waystone") if isinstance(doc.get("waystone"), list) else ():
        lines = w.get("lines") if isinstance(w, dict) else None
        if not isinstance(lines, list) or not lines:
            continue
        if not all(ledger_mod.is_safe_line(x) for x in lines):
            continue
        ways.append({"lines": list(lines), "n": w["n"] if _count(w.get("n")) else 0,
                     "first": _hour(w.get("first")), "last": _hour(w.get("last"))})
    shapes = []
    kinds = (ls.KIND_SYSTEM, ls.KIND_PLAIN, ls.KIND_NEAR)
    for s in doc.get("new_shapes") if isinstance(doc.get("new_shapes"), list) else ():
        if not isinstance(s, dict) or s.get("kind") not in kinds:
            continue
        if not ls.is_safe_shape(s.get("shape")):
            continue
        its = s.get("items") if isinstance(s.get("items"), list) else []
        shapes.append({"kind": s["kind"], "shape": s["shape"],
                       "n": s["n"] if _count(s.get("n")) else 0,
                       "first": _hour(s.get("first")), "last": _hour(s.get("last")),
                       "items": [i for i in its if i in names]})
    return {
        "schema": 1,
        "ledger": doc.get("ledger") if doc.get("ledger") in _STATES else "unreadable",
        "items": items,
        "readback": {k: v for k, v in rb.items()
                     if isinstance(k, str) and _WORD.match(k) and isinstance(v, bool)},
        "waystone": ways,
        "new_shapes": shapes,
        "pending_shapes": doc["pending_shapes"] if _count(doc.get("pending_shapes")) else 0,
    }


def default_runner(root, ledger_path):
    """stdout of tools/live1_report.py --json --file <ledger> (below normal
    priority, no window, 60 s), or None."""
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(
            [sys.executable, str(Path(root) / TOOL_REL), "--json", "--file", str(ledger_path)],
            cwd=str(root), capture_output=True, text=True, timeout=RUNNER_TIMEOUT_S,
            creationflags=flags, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _ledger_sig(path):
    try:
        st = path.stat()
    except OSError:
        return None
    return f"{st.st_mtime_ns}:{st.st_size}"


def write_report(root, ctx, data):
    """Refresh ops/runtime/watch/live1_report.json when the ledger changed
    since the last copy (or the copy is gone); returns True on a write."""
    runner = ctx.get("live1_runner")
    if runner is None:
        if not ctx.get("live"):
            return False
        runner = default_runner
    root = Path(root)
    ledger_path = root / LEDGER_REL
    sig = _ledger_sig(ledger_path)
    out = root / REPORT_REL
    if sig is None or (data.get("report_sig") == sig and out.is_file()):
        return False
    try:
        text = runner(root, ledger_path)
        doc = json.loads(text) if isinstance(text, str) and len(text) <= REPORT_MAX_BYTES \
            else None
    except Exception:  # noqa: BLE001 - a broken report never fails the source
        doc = None
    clean = clean_report(doc)
    if clean is None:
        return False
    import loop_base
    loop_base.atomic_write(out, json.dumps(clean, indent=1, ensure_ascii=True) + "\n")
    data["report_sig"] = sig
    return True


# ---------------------------------------------------------------- check

def check(state, now, fetch, ctx):
    ctx = ctx or {}
    root = _root(ctx)
    if root is None:
        return []
    data = dict(state.get("data") or {})
    today = _dt.datetime.fromtimestamp(now).date()
    stamp = today.strftime("%Y%m%d")
    found = []

    led = load_ledger(root)
    if led is not None:
        still_open = open_rows(root)
        for item in first_hits(led):
            if ROW_PREFIX + item not in still_open:
                continue
            if item == ACCEPTED:
                found.append({"kind": KIND_ACCEPTED, "key": "live1:" + item, "tokens": {}})
            else:
                found.append({"kind": KIND_HIT, "key": "live1:" + item,
                              "tokens": {"ITEM": item}})
        digests = confirmed_digests(led)
        seen = [d for d in data.get("shapes_seen") or () if isinstance(d, str)]
        new = [d for d in digests if d not in set(seen)]
        if new and data.get("shape_day") != stamp:
            found.append({"kind": KIND_SHAPE, "key": "log-shape:" + stamp, "tokens": {}})
            data["shape_day"] = stamp
            data["shapes_seen"] = (seen + new)[-SEEN_MAX:]
        write_report(root, ctx, data)

    files = snapshot_files() if (Path(root) / PROBE_REL).is_file() else {}
    reported = dict(data.get("probe_seen") or {})
    for src, when in load_probe(root):
        last = reported.get(src)
        if isinstance(last, dict) and (last.get("time") == when or last.get("day") == stamp):
            continue
        reported[src] = {"time": when, "day": stamp}
        token = files[src]
        found.append({"kind": KIND_PROBE, "key": f"snap:{token}:{stamp}",
                      "tokens": {"FILE": token}})
    if reported:
        data["probe_seen"] = reported
    state["data"] = data
    return found


SOURCE = {
    "name": "ledger",
    "home": "loop",
    "cadence_s": 0,
    "window": None,
    "needs_web_data": True,
    "hosts": [],
    "urls": [],
    "purpose": "dev: watcher ledger",
    "check": check,
}
