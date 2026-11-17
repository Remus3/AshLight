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
reads as empty. UTIL-MULTICHAR (decision 0038): runs are kept per
character name as the player's own Client.txt reports it (at most
MAX_CHARACTERS names, MAX_RUNS runs each; the name never leaves the
machine), bests and deaths by zone are per character, and a schema 1 file
(one flat list) is migrated in place on load. The player can turn it off ("run_history": false in the
local config, or the dashboard switch) and clear it (dashboard button).
"""

from pathlib import Path

from . import jsonfile, num

FILE_NAME = "run_history.json"
CONFIG_KEY = "run_history"
SCHEMA = 2
MAX_RUNS = 20  # per character
MAX_CHARACTERS = 12
MAX_SPLITS = 16
MAX_ZONES = 40
MAX_TEXT = 64
MAX_BYTES = 2 * 1024 * 1024
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
    # AREA-TEST batch 6: num.finite also drops a huge int, whose float()
    # raised OverflowError out of load()
    f = num.finite(value)
    return None if f is None or f < 0 else f


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


def char_key(run):
    """The history key of a run: its character name, "" when unknown."""
    return run.get("character") or ""


def group(runs):
    """{key: [runs oldest first]} with the MAX_RUNS / MAX_CHARACTERS caps;
    the characters whose newest run is oldest are dropped first."""
    by = {}
    for r in sorted(runs, key=lambda r: r["started_at"]):
        by.setdefault(char_key(r), []).append(r)
    for k in by:
        by[k] = by[k][-MAX_RUNS:]
    keep = sorted(by, key=lambda k: by[k][-1]["started_at"])[-MAX_CHARACTERS:]
    return {k: by[k] for k in keep}


def flat(by):
    return sorted((r for runs in by.values() for r in runs),
                  key=lambda r: r["started_at"])


def _read(path):
    """(doc, schema) of the file, or (None, None)."""
    doc = jsonfile.read_json(path, max_bytes=MAX_BYTES, kind=dict)
    if doc is None:
        return None, None
    return doc, doc.get("schema")


def _raw_runs(doc):
    if doc is None:
        return []
    if isinstance(doc.get("characters"), dict):
        raw = []
        for entry in doc["characters"].values():
            if isinstance(entry, dict) and isinstance(entry.get("runs"), list):
                raw.extend(entry["runs"])
        return raw
    # schema 1: one flat list (UTIL-RUN-HISTORY before UTIL-MULTICHAR)
    return doc.get("runs") if isinstance(doc.get("runs"), list) else []


def load(path):
    """The saved runs of every character, oldest first ([] when missing,
    oversized or bad); schema 1 and 2 files both read."""
    doc, _ = _read(path)
    out = [r for r in (clean_run(x) for x in _raw_runs(doc)) if r is not None]
    return flat(group(out))


def save(path, runs):
    """Write the runs (a flat list, any characters) as schema 2."""
    by = group(runs)
    doc = {"schema": SCHEMA,
           "characters": {k: {"runs": v} for k, v in by.items()}}
    jsonfile.write_json(path, doc)


def migrate(path):
    """UTIL-MULTICHAR: rewrite a schema 1 file as schema 2 (runs grouped by
    their character). True when the file was rewritten."""
    doc, schema = _read(path)
    if doc is None or schema == SCHEMA or not isinstance(doc.get("runs"), list):
        return False
    save(path, load(path))
    return True


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
        try:
            migrate(self.path)
        except OSError:
            pass  # read as is; the next save writes schema 2
        self.runs = load(self.path)

    def characters(self):
        """The character keys with saved runs, newest run last."""
        return list(group(self.runs))

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
        self.runs = flat(group(self.runs))
        save(self.path, self.runs)
        return True

    def clear(self):
        self.runs = []
        save(self.path, self.runs)

    def view(self, current=None, enabled=True, character=None):
        """The snapshot `run_history` part. current: the live run record
        (state.run_record()), excluded from the bests so the act card can
        show the delta to the best of the OTHER runs. UTIL-MULTICHAR: only
        one character's runs count: `character`, else the current run's
        character (None and "" are the unknown character)."""
        if not enabled:
            return {"on": False, "runs": 0, "best": [], "deaths_by_zone": [],
                    "text": OFF_TEXT, "empty_text": "", "deaths_empty_text": ""}
        cur = clean_run(current) if current else None
        if character is None and cur is not None:
            key = char_key(cur)
        else:
            key = character or ""
        if cur is not None and char_key(cur) != key:
            cur = None
        others = [r for r in self.runs if char_key(r) == key
                  and (cur is None or not same_run(r, cur))]
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
            if own:  # UX-REGRESSION-SWEEP: "best so far", not "not yet"
                row["this_run"] = True
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
