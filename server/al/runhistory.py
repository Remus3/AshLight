"""UTIL-RUN-HISTORY: personal-best act splits and deaths by zone across
campaign runs (research 0028 section 3, ruling C; decision 0036).

A run is the act splits of one campaign (acts.ActSplits) plus the
player's deaths per zone in it, all from the opted-in Client.txt tail.
Each time an act split closes (and when the run finishes) the core saves a
small summary of the run to one local JSON file under the runtime dir
(ops/runtime, gitignored; paths.runtime_dir()). Nothing else is stored:
no log lines, no whispers, no other player's names.

LIVE-RESUME (decision 0008) is untouched: it still rebuilds the current
run from Client.txt and persists nothing; this file is a separate record
of FINISHED parts of runs, so a deleted or trimmed Client.txt keeps the
player's bests. A resumed run matches its saved record by character and
start time (MATCH_S), so a core restart never duplicates a run.

Bounded: at most MAX_RUNS runs (oldest dropped), MAX_SPLITS splits and
MAX_ZONES zones per run, strings cut to MAX_TEXT, a file over MAX_BYTES
reads as empty. The player can turn it off ("run_history": false in the
local config, or the dashboard switch) and clear it (dashboard button).
"""

import json
import os
from pathlib import Path

FILE_NAME = "run_history.json"
CONFIG_KEY = "run_history"
SCHEMA = 1
MAX_RUNS = 20
MAX_SPLITS = 16
MAX_ZONES = 40
MAX_TEXT = 64
MAX_BYTES = 256 * 1024
MATCH_S = 300.0
TOP_ZONES = 5

# Dashboard copy (design 0001 section 9); the page prints these as given.
ON_TEXT = "Run history is on: AshLight keeps your act times and deaths on this computer."
OFF_TEXT = "Run history is off. Nothing is saved."
EMPTY_TEXT = ("No finished acts saved yet. Your best act times show here by "
              "themselves after you finish an act.")
DEATHS_EMPTY_TEXT = "No deaths in your saved runs."


def enabled_setting(value):
    """On unless the local config says false."""
    return value is not False


def _text(value):
    return value[:MAX_TEXT] if isinstance(value, str) and value else None


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")) or value < 0:
        return None
    return float(value)


def clean_run(run):
    """A bounded, valid run record, or None."""
    if not isinstance(run, dict):
        return None
    started = _num(run.get("started_at"))
    if started is None:
        return None
    splits = []
    for s in run.get("splits") or ():
        if not isinstance(s, dict):
            continue
        key, label, t = _text(s.get("key")), _text(s.get("label")), _num(s.get("time_s"))
        if key and label and t is not None:
            splits.append({"key": key, "label": label, "time_s": round(t, 1)})
        if len(splits) >= MAX_SPLITS:
            break
    deaths = {}
    raw = run.get("deaths") if isinstance(run.get("deaths"), dict) else {}
    for zone, n in raw.items():
        zone = _text(zone)
        if zone and isinstance(n, int) and not isinstance(n, bool) and n > 0:
            deaths[zone] = min(n, 9999)
        if len(deaths) >= MAX_ZONES:
            break
    return {"started_at": started, "character": _text(run.get("character")),
            "class": _text(run.get("class")), "splits": splits, "deaths": deaths,
            "finished": run.get("finished") is True}


def load(path):
    """The saved runs, oldest first ([] when missing, oversized or bad)."""
    try:
        p = Path(path)
        if p.stat().st_size > MAX_BYTES:
            return []
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    runs = doc.get("runs") if isinstance(doc, dict) else None
    out = [r for r in (clean_run(x) for x in runs or ()) if r is not None]
    return out[-MAX_RUNS:]


def save(path, runs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps({"schema": SCHEMA, "runs": runs[-MAX_RUNS:]}, indent=1,
                      ensure_ascii=True) + "\n"
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def same_run(a, b):
    return (a.get("character") == b.get("character")
            and abs(a["started_at"] - b["started_at"]) <= MATCH_S)


def _fmt(s):
    s = int(max(0, s))
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


class RunHistory:
    """The history file and its in-memory copy. Not thread-safe: the core
    calls it from its loop tick and the clear request under its lock."""

    def __init__(self, path):
        self.path = Path(path)
        self.runs = load(self.path)

    def record(self, run):
        """Save one run (a new one, or the update of a saved one). True
        when the file was written."""
        run = clean_run(run)
        if run is None or not (run["splits"] or run["deaths"]):
            return False
        for i, old in enumerate(self.runs):
            if same_run(old, run):
                if old == run:
                    return False
                self.runs[i] = run
                break
        else:
            self.runs.append(run)
            self.runs = self.runs[-MAX_RUNS:]
        save(self.path, self.runs)
        return True

    def clear(self):
        self.runs = []
        save(self.path, self.runs)

    def view(self, current=None, enabled=True):
        """The snapshot `run_history` part. current: the live run record
        (state.run_record()), excluded from the bests so the act card can
        show the delta to the best of the OTHER runs."""
        if not enabled:
            return {"on": False, "runs": 0, "best": [], "deaths_by_zone": [],
                    "text": OFF_TEXT, "empty_text": "", "deaths_empty_text": ""}
        cur = clean_run(current) if current else None
        others = [r for r in self.runs if cur is None or not same_run(r, cur)]
        best = {}
        for r in others:
            for s in r["splits"]:
                b = best.get(s["key"])
                if b is None or s["time_s"] < b["best_s"]:
                    best[s["key"]] = {"key": s["key"], "label": s["label"],
                                      "best_s": s["time_s"]}
        # AREA-AUDIT P5-6: a split only the current run has closed is the
        # best so far (no other run to compare: delta stays None), so the
        # empty text keys on "no saved split at all", not "no other run".
        for s in (cur["splits"] if cur else ()):
            if s["key"] not in best:
                best[s["key"]] = {"key": s["key"], "label": s["label"],
                                  "best_s": s["time_s"], "own": True}
        rows = []
        cur_times = {s["key"]: s["time_s"] for s in cur["splits"]} if cur else {}
        for key, b in best.items():
            own = b.pop("own", False)
            row = dict(b, best_text=_fmt(b["best_s"]), delta_s=None)
            if key in cur_times and not own:
                row["delta_s"] = round(cur_times[key] - b["best_s"], 1)
            rows.append(row)
        deaths = {}
        for r in others + ([cur] if cur else []):
            for zone, n in r["deaths"].items():
                deaths[zone] = deaths.get(zone, 0) + n
        top = sorted(deaths.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_ZONES]
        n_runs = len(others) + (1 if cur else 0)
        return {"on": True, "runs": n_runs, "best": rows,
                "deaths_by_zone": [{"zone": z, "deaths": n} for z, n in top],
                "text": ON_TEXT, "empty_text": EMPTY_TEXT if not rows else "",
                "deaths_empty_text": DEATHS_EMPTY_TEXT if not top else ""}
